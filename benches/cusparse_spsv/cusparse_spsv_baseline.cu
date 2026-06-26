#include <cuda_runtime.h>
#include <cusparse.h>

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <map>
#include <numeric>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

#include "benchmark_config.h"
#include "result_csv.h"

#ifndef DEFAULT_REPO_ROOT
#define DEFAULT_REPO_ROOT "/home/HCL-Fing_Split"
#endif

namespace {

constexpr char kMagic[8] = {'C', 'S', 'R', 'L', 'O', 'W', '1', '\0'};
constexpr uint32_t kVersion = 1;
constexpr uint32_t kRequiredFlags = 0x01 | 0x02 | 0x04 | 0x08;

struct Options {
  std::string mode = "benchmark";
  std::string matrix;
  std::string csrbin_path;
  std::string rhs_path;
  std::string output_path = std::string(DEFAULT_REPO_ROOT) + "/results/csv/main_results.csv";
  std::string x_output_path;
  std::string config_path = std::string(DEFAULT_REPO_ROOT) + "/config/experiment.yaml";
  std::string statistic = "median";
  int warmup = -1;
  int repeat = -1;
  int repeat_analysis = -1;
};

struct CsrMatrix {
  std::string name;
  int64_t n = 0;
  int64_t nnz = 0;
  uint64_t diag_filled = 0;
  std::vector<int32_t> row_ptr;
  std::vector<int32_t> col_idx;
  std::vector<double> values;
};

struct DeviceCsr {
  int32_t* row_ptr = nullptr;
  int32_t* col_idx = nullptr;
  double* values = nullptr;
};

struct DeviceVectors {
  double* b = nullptr;
  double* x = nullptr;
};

std::string BaseNameNoExt(const std::string& path) {
  size_t slash = path.find_last_of("/\\");
  std::string name = slash == std::string::npos ? path : path.substr(slash + 1);
  size_t dot = name.find_last_of('.');
  if (dot != std::string::npos) {
    name = name.substr(0, dot);
  }
  return name;
}

bool FileExists(const std::string& path) {
  std::ifstream in(path, std::ios::binary);
  return static_cast<bool>(in);
}

void CudaCheck(cudaError_t status, const char* expr) {
  if (status != cudaSuccess) {
    throw std::runtime_error(std::string(expr) + ": " + cudaGetErrorString(status));
  }
}

void CusparseCheck(cusparseStatus_t status, const char* expr) {
  if (status != CUSPARSE_STATUS_SUCCESS) {
    throw std::runtime_error(std::string(expr) + ": cusparse status " +
                             std::to_string(static_cast<int>(status)));
  }
}

#define CUDA_CHECK(expr) CudaCheck((expr), #expr)
#define CUSPARSE_CHECK(expr) CusparseCheck((expr), #expr)

template <typename T>
void ReadExact(std::ifstream& in, T* data, size_t count, const std::string& what) {
  in.read(reinterpret_cast<char*>(data), static_cast<std::streamsize>(sizeof(T) * count));
  if (!in) {
    throw std::runtime_error("failed to read " + what);
  }
}

CsrMatrix ReadCsrbin(const std::string& path) {
  std::ifstream in(path, std::ios::binary);
  if (!in) {
    throw std::runtime_error("failed to open csrbin: " + path);
  }

  char magic[8];
  uint32_t version = 0;
  uint32_t flags = 0;
  uint64_t n = 0;
  uint64_t nnz = 0;
  uint64_t diag_filled = 0;
  ReadExact(in, magic, 8, "magic");
  ReadExact(in, &version, 1, "version");
  ReadExact(in, &flags, 1, "flags");
  ReadExact(in, &n, 1, "n");
  ReadExact(in, &nnz, 1, "nnz");
  ReadExact(in, &diag_filled, 1, "diag_filled");

  if (std::memcmp(magic, kMagic, 8) != 0) {
    throw std::runtime_error("invalid csrbin magic");
  }
  if (version != kVersion) {
    throw std::runtime_error("unsupported csrbin version: " + std::to_string(version));
  }
  if ((flags & kRequiredFlags) != kRequiredFlags) {
    throw std::runtime_error("csrbin is not lower/sorted/double/0-based");
  }
  if (n > static_cast<uint64_t>(std::numeric_limits<int32_t>::max()) ||
      nnz > static_cast<uint64_t>(std::numeric_limits<int32_t>::max())) {
    throw std::runtime_error("cuSPARSE-SpSV baseline currently requires n and nnz <= INT32_MAX");
  }

  std::vector<uint64_t> raw_row_ptr(n + 1);
  std::vector<uint32_t> raw_col_idx(nnz);
  std::vector<double> values(nnz);
  ReadExact(in, raw_row_ptr.data(), raw_row_ptr.size(), "row_ptr");
  ReadExact(in, raw_col_idx.data(), raw_col_idx.size(), "col_idx");
  ReadExact(in, values.data(), values.size(), "values");

  CsrMatrix matrix;
  matrix.name = BaseNameNoExt(path);
  matrix.n = static_cast<int64_t>(n);
  matrix.nnz = static_cast<int64_t>(nnz);
  matrix.diag_filled = diag_filled;
  matrix.row_ptr.resize(raw_row_ptr.size());
  matrix.col_idx.resize(raw_col_idx.size());
  for (size_t i = 0; i < raw_row_ptr.size(); ++i) {
    if (raw_row_ptr[i] > static_cast<uint64_t>(std::numeric_limits<int32_t>::max())) {
      throw std::runtime_error("row_ptr entry exceeds INT32_MAX");
    }
    matrix.row_ptr[i] = static_cast<int32_t>(raw_row_ptr[i]);
  }
  for (size_t i = 0; i < raw_col_idx.size(); ++i) {
    matrix.col_idx[i] = static_cast<int32_t>(raw_col_idx[i]);
  }
  matrix.values = std::move(values);

  if (matrix.row_ptr.empty() || matrix.row_ptr.front() != 0 ||
      matrix.row_ptr.back() != matrix.nnz) {
    throw std::runtime_error("invalid csr row_ptr");
  }
  return matrix;
}

std::vector<double> ReadRhs(const std::string& path, int64_t n) {
  std::ifstream in(path);
  if (!in) {
    throw std::runtime_error("failed to open rhs: " + path);
  }
  std::vector<double> rhs;
  rhs.reserve(static_cast<size_t>(n));
  double value = 0.0;
  while (in >> value) {
    rhs.push_back(value);
  }
  if (rhs.size() != static_cast<size_t>(n)) {
    throw std::runtime_error("rhs length mismatch: " + std::to_string(rhs.size()) +
                             " != " + std::to_string(n));
  }
  return rhs;
}

Options ParseArgs(int argc, char** argv) {
  Options options;
  for (int i = 1; i < argc; ++i) {
    std::string arg = argv[i];
    auto need_value = [&](const std::string& name) -> std::string {
      if (i + 1 >= argc) {
        throw std::runtime_error("missing value for " + name);
      }
      return argv[++i];
    };
    if (arg == "--mode") {
      options.mode = need_value(arg);
    } else if (arg == "--matrix") {
      options.matrix = need_value(arg);
    } else if (arg == "--csrbin") {
      options.csrbin_path = need_value(arg);
    } else if (arg == "--rhs") {
      options.rhs_path = need_value(arg);
    } else if (arg == "--output") {
      options.output_path = need_value(arg);
    } else if (arg == "--x-output") {
      options.x_output_path = need_value(arg);
    } else if (arg == "--config") {
      options.config_path = need_value(arg);
    } else if (arg == "--warmup") {
      options.warmup = std::stoi(need_value(arg));
    } else if (arg == "--repeat") {
      options.repeat = std::stoi(need_value(arg));
    } else if (arg == "--repeat-analysis") {
      options.repeat_analysis = std::stoi(need_value(arg));
    } else if (arg == "--help" || arg == "-h") {
      std::cout
          << "用法: cusparse_spsv_baseline --mode quick|benchmark --matrix NAME [选项]\n"
          << "  --mode              运行模式。quick 用于 tiny 正确性检查；benchmark 用于正式计时。\n"
          << "  --config            实验配置文件，默认 config/experiment.yaml。\n"
          << "  --matrix            矩阵名，会读取 data/csrbin/NAME.csrbin 和 data/rhs/NAME.rhs.txt。\n"
          << "  --csrbin            显式指定统一 lower CSR 二进制输入。\n"
          << "  --rhs               显式指定 RHS 文本输入。\n"
          << "  --output            CSV 输出路径，默认 results/csv/main_results.csv。\n"
          << "  --warmup            覆盖预热次数。\n"
          << "  --repeat            覆盖求解计时重复次数。\n"
          << "  --repeat-analysis   覆盖分析/准备计时重复次数。\n";
      std::exit(0);
    } else {
      throw std::runtime_error("unknown argument: " + arg);
    }
  }

  bench_common::ApplyTimingConfig(options.config_path, &options.mode, &options.warmup,
                                  &options.repeat, &options.repeat_analysis,
                                  &options.statistic);

  if (options.csrbin_path.empty()) {
    if (options.matrix.empty()) {
      throw std::runtime_error("provide --matrix or --csrbin");
    }
    options.csrbin_path = std::string(DEFAULT_REPO_ROOT) + "/data/csrbin/" +
                          options.matrix + ".csrbin";
  }
  if (options.rhs_path.empty()) {
    std::string name = options.matrix.empty() ? BaseNameNoExt(options.csrbin_path) : options.matrix;
    options.rhs_path = std::string(DEFAULT_REPO_ROOT) + "/data/rhs/" + name + ".rhs.txt";
  }
  if (options.matrix.empty()) {
    options.matrix = BaseNameNoExt(options.csrbin_path);
  }
  if (options.x_output_path.empty()) {
    options.x_output_path = std::string(DEFAULT_REPO_ROOT) + "/results/sanity/x/cusparse_spsv_" +
                            options.matrix + ".x.txt";
  }
  return options;
}

float ElapsedMs(cudaEvent_t start, cudaEvent_t stop) {
  float ms = 0.0f;
  CUDA_CHECK(cudaEventElapsedTime(&ms, start, stop));
  return ms;
}

double Median(std::vector<double> values) {
  if (values.empty()) {
    throw std::runtime_error("median of empty vector");
  }
  std::sort(values.begin(), values.end());
  size_t mid = values.size() / 2;
  if (values.size() % 2 == 1) {
    return values[mid];
  }
  return 0.5 * (values[mid - 1] + values[mid]);
}

double Residual(const CsrMatrix& matrix, const std::vector<double>& x,
                const std::vector<double>& b) {
  long double diff2 = 0.0;
  long double b2 = 0.0;
  for (int64_t row = 0; row < matrix.n; ++row) {
    long double ax = 0.0;
    for (int64_t idx = matrix.row_ptr[row]; idx < matrix.row_ptr[row + 1]; ++idx) {
      ax += static_cast<long double>(matrix.values[idx]) *
            static_cast<long double>(x[matrix.col_idx[idx]]);
    }
    long double diff = ax - static_cast<long double>(b[row]);
    diff2 += diff * diff;
    b2 += static_cast<long double>(b[row]) * static_cast<long double>(b[row]);
  }
  if (b2 == 0.0) {
    return diff2 == 0.0 ? 0.0 : std::numeric_limits<double>::infinity();
  }
  return std::sqrt(static_cast<double>(diff2 / b2));
}

std::string FormatDouble(double value) {
  std::ostringstream out;
  out << std::setprecision(17) << value;
  return out.str();
}

void FillTotals(std::map<std::string, std::string>* row, double analysis_ms,
                double solve_ms) {
  (*row)["analysis_ms"] = FormatDouble(analysis_ms);
  (*row)["solve_ms"] = FormatDouble(solve_ms);
  (*row)["total_1_ms"] = FormatDouble(analysis_ms + solve_ms);
  (*row)["total_10_ms"] = FormatDouble(analysis_ms + 10.0 * solve_ms);
  (*row)["total_100_ms"] = FormatDouble(analysis_ms + 100.0 * solve_ms);
}

void WriteVectorText(const std::string& path, const std::vector<double>& values) {
  std::filesystem::path out_path(path);
  if (out_path.has_parent_path()) {
    std::filesystem::create_directories(out_path.parent_path());
  }
  std::ofstream out(path);
  if (!out) {
    throw std::runtime_error("failed to open vector output: " + path);
  }
  out << std::setprecision(17);
  for (double value : values) {
    out << value << '\n';
  }
}

std::map<std::string, std::string> EmptyRow(const Options& options) {
  std::map<std::string, std::string> row;
  for (const auto& field : bench_common::ResultCsvFields()) {
    row[field] = "";
  }
  bench_common::FillTimingRow(&row, options.mode, options.warmup, options.repeat,
                              options.repeat_analysis, options.statistic);
  row["method"] = "cusparse_spsv";
  row["matrix"] = options.matrix;
  row["timeout"] = "false";
  row["status"] = "unknown";
  return row;
}

bool OutputNeedsHeader(const std::string& path) {
  return !FileExists(path);
}

void RunBenchmark(const Options& options) {
  CsrMatrix matrix = ReadCsrbin(options.csrbin_path);
  std::vector<double> rhs = ReadRhs(options.rhs_path, matrix.n);

  DeviceCsr d_csr;
  DeviceVectors d_vec;
  double* pinned_rhs = nullptr;
  void* external_buffer = nullptr;
  size_t buffer_size = 0;
  cudaEvent_t start = nullptr;
  cudaEvent_t stop = nullptr;
  cusparseHandle_t handle = nullptr;
  cusparseSpMatDescr_t mat_descr = nullptr;
  cusparseDnVecDescr_t b_descr = nullptr;
  cusparseDnVecDescr_t x_descr = nullptr;
  cusparseSpSVDescr_t spsv_descr = nullptr;
  cudaStream_t stream = nullptr;

  try {
    CUDA_CHECK(cudaStreamCreate(&stream));
    CUSPARSE_CHECK(cusparseCreate(&handle));
    CUSPARSE_CHECK(cusparseSetStream(handle, stream));

    CUDA_CHECK(cudaMalloc(&d_csr.row_ptr, sizeof(int32_t) * matrix.row_ptr.size()));
    CUDA_CHECK(cudaMalloc(&d_csr.col_idx, sizeof(int32_t) * matrix.col_idx.size()));
    CUDA_CHECK(cudaMalloc(&d_csr.values, sizeof(double) * matrix.values.size()));
    CUDA_CHECK(cudaMalloc(&d_vec.b, sizeof(double) * rhs.size()));
    CUDA_CHECK(cudaMalloc(&d_vec.x, sizeof(double) * rhs.size()));
    CUDA_CHECK(cudaHostAlloc(&pinned_rhs, sizeof(double) * rhs.size(), cudaHostAllocDefault));
    std::copy(rhs.begin(), rhs.end(), pinned_rhs);

    CUDA_CHECK(cudaMemcpyAsync(d_csr.row_ptr, matrix.row_ptr.data(),
                               sizeof(int32_t) * matrix.row_ptr.size(),
                               cudaMemcpyHostToDevice, stream));
    CUDA_CHECK(cudaMemcpyAsync(d_csr.col_idx, matrix.col_idx.data(),
                               sizeof(int32_t) * matrix.col_idx.size(),
                               cudaMemcpyHostToDevice, stream));
    CUDA_CHECK(cudaMemcpyAsync(d_csr.values, matrix.values.data(),
                               sizeof(double) * matrix.values.size(),
                               cudaMemcpyHostToDevice, stream));
    CUDA_CHECK(cudaStreamSynchronize(stream));

    CUSPARSE_CHECK(cusparseCreateCsr(
        &mat_descr, matrix.n, matrix.n, matrix.nnz, d_csr.row_ptr, d_csr.col_idx,
        d_csr.values, CUSPARSE_INDEX_32I, CUSPARSE_INDEX_32I,
        CUSPARSE_INDEX_BASE_ZERO, CUDA_R_64F));
    cusparseFillMode_t fill_mode = CUSPARSE_FILL_MODE_LOWER;
    cusparseDiagType_t diag_type = CUSPARSE_DIAG_TYPE_NON_UNIT;
    CUSPARSE_CHECK(cusparseSpMatSetAttribute(mat_descr, CUSPARSE_SPMAT_FILL_MODE,
                                             &fill_mode, sizeof(fill_mode)));
    CUSPARSE_CHECK(cusparseSpMatSetAttribute(mat_descr, CUSPARSE_SPMAT_DIAG_TYPE,
                                             &diag_type, sizeof(diag_type)));
    CUSPARSE_CHECK(cusparseCreateDnVec(&b_descr, matrix.n, d_vec.b, CUDA_R_64F));
    CUSPARSE_CHECK(cusparseCreateDnVec(&x_descr, matrix.n, d_vec.x, CUDA_R_64F));
    CUSPARSE_CHECK(cusparseSpSV_createDescr(&spsv_descr));

    const double alpha = 1.0;
    CUSPARSE_CHECK(cusparseSpSV_bufferSize(
        handle, CUSPARSE_OPERATION_NON_TRANSPOSE, &alpha, mat_descr, b_descr,
        x_descr, CUDA_R_64F, CUSPARSE_SPSV_ALG_DEFAULT, spsv_descr, &buffer_size));
    CUDA_CHECK(cudaMalloc(&external_buffer, buffer_size));
    CUDA_CHECK(cudaEventCreate(&start));
    CUDA_CHECK(cudaEventCreate(&stop));

    std::vector<double> analysis_times;
    analysis_times.reserve(static_cast<size_t>(options.repeat_analysis));
    CUDA_CHECK(cudaMemcpyAsync(d_vec.b, pinned_rhs, sizeof(double) * rhs.size(),
                               cudaMemcpyHostToDevice, stream));
    CUDA_CHECK(cudaStreamSynchronize(stream));
    for (int i = 0; i < options.repeat_analysis; ++i) {
      CUDA_CHECK(cudaDeviceSynchronize());
      CUDA_CHECK(cudaEventRecord(start, stream));
      CUSPARSE_CHECK(cusparseSpSV_analysis(
          handle, CUSPARSE_OPERATION_NON_TRANSPOSE, &alpha, mat_descr, b_descr,
          x_descr, CUDA_R_64F, CUSPARSE_SPSV_ALG_DEFAULT, spsv_descr,
          external_buffer));
      CUDA_CHECK(cudaEventRecord(stop, stream));
      CUDA_CHECK(cudaEventSynchronize(stop));
      CUDA_CHECK(cudaDeviceSynchronize());
      analysis_times.push_back(ElapsedMs(start, stop));
    }
    double analysis_ms = Median(analysis_times);

    for (int i = 0; i < options.warmup; ++i) {
      CUDA_CHECK(cudaDeviceSynchronize());
      CUDA_CHECK(cudaMemcpyAsync(d_vec.b, pinned_rhs, sizeof(double) * rhs.size(),
                                 cudaMemcpyHostToDevice, stream));
      CUSPARSE_CHECK(cusparseSpSV_solve(
          handle, CUSPARSE_OPERATION_NON_TRANSPOSE, &alpha, mat_descr, b_descr,
          x_descr, CUDA_R_64F, CUSPARSE_SPSV_ALG_DEFAULT, spsv_descr));
      CUDA_CHECK(cudaStreamSynchronize(stream));
      CUDA_CHECK(cudaDeviceSynchronize());
    }

    std::vector<double> solve_times;
    solve_times.reserve(static_cast<size_t>(options.repeat));
    for (int i = 0; i < options.repeat; ++i) {
      CUDA_CHECK(cudaDeviceSynchronize());
      CUDA_CHECK(cudaEventRecord(start, stream));
      CUDA_CHECK(cudaMemcpyAsync(d_vec.b, pinned_rhs, sizeof(double) * rhs.size(),
                                 cudaMemcpyHostToDevice, stream));
      CUSPARSE_CHECK(cusparseSpSV_solve(
          handle, CUSPARSE_OPERATION_NON_TRANSPOSE, &alpha, mat_descr, b_descr,
          x_descr, CUDA_R_64F, CUSPARSE_SPSV_ALG_DEFAULT, spsv_descr));
      CUDA_CHECK(cudaEventRecord(stop, stream));
      CUDA_CHECK(cudaEventSynchronize(stop));
      CUDA_CHECK(cudaDeviceSynchronize());
      solve_times.push_back(ElapsedMs(start, stop));
    }
    double solve_ms = Median(solve_times);

    std::vector<double> x(static_cast<size_t>(matrix.n));
    CUDA_CHECK(cudaMemcpy(x.data(), d_vec.x, sizeof(double) * x.size(),
                          cudaMemcpyDeviceToHost));
    double residual = Residual(matrix, x, rhs);
    bool residual_pass = residual < 1e-10;
    WriteVectorText(options.x_output_path, x);

    auto row = EmptyRow(options);
    row["n"] = std::to_string(matrix.n);
    row["nnz"] = std::to_string(matrix.nnz);
    row["diag_filled"] = std::to_string(matrix.diag_filled);
    FillTotals(&row, analysis_ms, solve_ms);
    row["residual"] = FormatDouble(residual);
    row["residual_pass"] = residual_pass ? "true" : "false";
    row["status"] = residual_pass ? "ok" : "residual_error";
    row["error"] = residual_pass ? "" : "residual >= 1e-10";
    bench_common::AppendResultCsv(options.output_path, row,
                                  OutputNeedsHeader(options.output_path));
    std::cout << "x=";
    for (size_t i = 0; i < x.size(); ++i) {
      std::cout << (i ? "," : "") << x[i];
    }
    std::cout << "\nresidual=" << residual << "\nanalysis_ms=" << analysis_ms
              << "\nsolve_ms=" << solve_ms << "\nmode=" << options.mode
              << "\nwarmup=" << options.warmup
              << "\nrepeat_solve=" << options.repeat
              << "\nrepeat_analysis=" << options.repeat_analysis
              << "\nstatistic=" << options.statistic << "\n";

    CUSPARSE_CHECK(cusparseSpSV_destroyDescr(spsv_descr));
    CUSPARSE_CHECK(cusparseDestroyDnVec(x_descr));
    CUSPARSE_CHECK(cusparseDestroyDnVec(b_descr));
    CUSPARSE_CHECK(cusparseDestroySpMat(mat_descr));
    CUSPARSE_CHECK(cusparseDestroy(handle));
    CUDA_CHECK(cudaEventDestroy(start));
    CUDA_CHECK(cudaEventDestroy(stop));
    CUDA_CHECK(cudaFree(external_buffer));
    CUDA_CHECK(cudaFreeHost(pinned_rhs));
    CUDA_CHECK(cudaFree(d_vec.x));
    CUDA_CHECK(cudaFree(d_vec.b));
    CUDA_CHECK(cudaFree(d_csr.values));
    CUDA_CHECK(cudaFree(d_csr.col_idx));
    CUDA_CHECK(cudaFree(d_csr.row_ptr));
    CUDA_CHECK(cudaStreamDestroy(stream));
  } catch (...) {
    if (spsv_descr) cusparseSpSV_destroyDescr(spsv_descr);
    if (x_descr) cusparseDestroyDnVec(x_descr);
    if (b_descr) cusparseDestroyDnVec(b_descr);
    if (mat_descr) cusparseDestroySpMat(mat_descr);
    if (handle) cusparseDestroy(handle);
    if (start) cudaEventDestroy(start);
    if (stop) cudaEventDestroy(stop);
    if (external_buffer) cudaFree(external_buffer);
    if (pinned_rhs) cudaFreeHost(pinned_rhs);
    if (d_vec.x) cudaFree(d_vec.x);
    if (d_vec.b) cudaFree(d_vec.b);
    if (d_csr.values) cudaFree(d_csr.values);
    if (d_csr.col_idx) cudaFree(d_csr.col_idx);
    if (d_csr.row_ptr) cudaFree(d_csr.row_ptr);
    if (stream) cudaStreamDestroy(stream);
    throw;
  }
}

}  // namespace

int main(int argc, char** argv) {
  Options options;
  try {
    options = ParseArgs(argc, argv);
    RunBenchmark(options);
    return 0;
  } catch (const std::exception& ex) {
    try {
      auto row = EmptyRow(options);
      row["status"] = "error";
      row["error"] = ex.what();
      row["residual_pass"] = "false";
      bench_common::AppendResultCsv(options.output_path, row,
                                    OutputNeedsHeader(options.output_path));
    } catch (...) {
    }
    std::cerr << "cusparse_spsv_baseline error: " << ex.what() << "\n";
    return 1;
  }
}
