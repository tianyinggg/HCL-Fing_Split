#include <cuda_runtime.h>

#include <algorithm>
#include <chrono>
#include <cstdlib>
#include <iostream>
#include <map>
#include <stdexcept>
#include <string>
#include <vector>

#include "SILU.h"
#include "benchmark_config.h"
#include "csrbin_utils.h"
#include "matrix.h"
#include "result_csv.h"

#ifndef DEFAULT_REPO_ROOT
#define DEFAULT_REPO_ROOT "/home/HCL-Fing_Split"
#endif

namespace {

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

struct RunResult {
  double analysis_ms = 0.0;
  double solve_ms = 0.0;
  double split_internal_sum_ms = 0.0;
  double split_sptrsv1_ms = 0.0;
  double split_spmv_ms = 0.0;
  double split_sptrsv2_ms = 0.0;
  double split_transfer_ms = 0.0;
  std::vector<double> x;
};

void CudaCheck(cudaError_t status, const char* expr) {
  if (status != cudaSuccess) {
    throw std::runtime_error(std::string(expr) + ": " + cudaGetErrorString(status));
  }
}

#define CUDA_CHECK(expr) CudaCheck((expr), #expr)

Options ParseArgs(int argc, char** argv) {
  Options opt;
  for (int i = 1; i < argc; ++i) {
    std::string arg = argv[i];
    auto need = [&](const std::string& name) -> std::string {
      if (i + 1 >= argc) throw std::runtime_error("missing value for " + name);
      return argv[++i];
    };
    if (arg == "--mode") opt.mode = need(arg);
    else if (arg == "--matrix") opt.matrix = need(arg);
    else if (arg == "--csrbin") opt.csrbin_path = need(arg);
    else if (arg == "--rhs") opt.rhs_path = need(arg);
    else if (arg == "--output") opt.output_path = need(arg);
    else if (arg == "--x-output") opt.x_output_path = need(arg);
    else if (arg == "--config") opt.config_path = need(arg);
    else if (arg == "--warmup") opt.warmup = std::stoi(need(arg));
    else if (arg == "--repeat") opt.repeat = std::stoi(need(arg));
    else if (arg == "--repeat-analysis") opt.repeat_analysis = std::stoi(need(arg));
    else if (arg == "--help" || arg == "-h") {
      std::cout
          << "用法: split_sptrsv_baseline --mode quick|benchmark --matrix NAME [选项]\n"
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
    }
    else throw std::runtime_error("unknown argument: " + arg);
  }
  bench_common::ApplyTimingConfig(opt.config_path, &opt.mode, &opt.warmup, &opt.repeat,
                                  &opt.repeat_analysis, &opt.statistic);
  if (opt.csrbin_path.empty()) {
    if (opt.matrix.empty()) throw std::runtime_error("provide --matrix or --csrbin");
    opt.csrbin_path = std::string(DEFAULT_REPO_ROOT) + "/data/csrbin/" + opt.matrix + ".csrbin";
  }
  if (opt.matrix.empty()) opt.matrix = bench_common::BaseNameNoExt(opt.csrbin_path);
  if (opt.rhs_path.empty()) {
    opt.rhs_path = std::string(DEFAULT_REPO_ROOT) + "/data/rhs/" + opt.matrix + ".rhs.txt";
  }
  if (opt.x_output_path.empty()) {
    opt.x_output_path = std::string(DEFAULT_REPO_ROOT) + "/results/sanity/x/split_sptrsv_" + opt.matrix + ".x.txt";
  }
  return opt;
}

bool FileExists(const std::string& path) {
  std::ifstream in(path);
  return static_cast<bool>(in);
}

csr_matrix MakeSplitMatrix(const bench_common::CsrMatrix& src) {
  auto* row_ptr = static_cast<ind_type*>(malloc(sizeof(ind_type) * src.row_ptr.size()));
  auto* col_idx = static_cast<ind_type*>(malloc(sizeof(ind_type) * src.col_idx.size()));
  auto* values = static_cast<val_type*>(malloc(sizeof(val_type) * src.values.size()));
  if (!row_ptr || !col_idx || !values) {
    throw std::runtime_error("failed to allocate Split csr_matrix arrays");
  }
  for (size_t i = 0; i < src.row_ptr.size(); ++i) row_ptr[i] = src.row_ptr[i];
  for (size_t i = 0; i < src.col_idx.size(); ++i) col_idx[i] = src.col_idx[i];
  for (size_t i = 0; i < src.values.size(); ++i) values[i] = src.values[i];
  return csr_matrix(row_ptr, col_idx, values, src.n, src.n, src.nnz, src.name);
}

void FreeSplitMatrix(csr_matrix* matrix) {
  free(matrix->csrRowPtr);
  free(matrix->csrColIdx);
  free(matrix->csrVal);
  matrix->csrRowPtr = nullptr;
  matrix->csrColIdx = nullptr;
  matrix->csrVal = nullptr;
}

double SplitAnalysisMs(SILU& silu) {
  return static_cast<double>(silu.getlevelAna_Time()) +
         static_cast<double>(silu.getDagAna_Time()) +
         static_cast<double>(silu.getSplit_Time()) +
         static_cast<double>(silu.getDataStruct_Time()) +
         static_cast<double>(silu.getAlgoAna_Time());
}

double NowMs() {
  using clock = std::chrono::steady_clock;
  static const auto start = clock::now();
  auto now = clock::now();
  return std::chrono::duration<double, std::milli>(now - start).count();
}

double SplitInternalSumMs(SILU& silu) {
  int description = silu.policy.description;
  switch (description) {
    case 0:
    case 1:
    case 5:
    case 6:
      return silu.getSpTRSV1_Time();
    case 2:
      return static_cast<double>(silu.getSpTRSV1_Time()) +
             static_cast<double>(silu.getSpMV_Time()) +
             static_cast<double>(silu.getSpTRSV2_Time()) +
             static_cast<double>(silu.geth2d_sptrsv1_Time());
    case 3:
      return static_cast<double>(silu.getSpTRSV1_Time()) +
             static_cast<double>(silu.getSpMV_Time()) +
             static_cast<double>(silu.getSpTRSV2_Time()) +
             static_cast<double>(silu.getd2h_spmv_Time());
    case 4:
      return static_cast<double>(silu.getSpTRSV1_Time()) +
             static_cast<double>(silu.getSpMV_Time()) +
             static_cast<double>(silu.getSpTRSV2_Time());
    default:
      return static_cast<double>(silu.getSpTRSV1_Time()) +
             static_cast<double>(silu.getSpMV_Time()) +
             static_cast<double>(silu.getSpTRSV2_Time());
  }
}

double SplitTransferMs(SILU& silu) {
  return static_cast<double>(silu.getd2h_Time()) +
         static_cast<double>(silu.getd2h_sptrsv1_Time()) +
         static_cast<double>(silu.getd2h_spmv_Time()) +
         static_cast<double>(silu.getd2h_final_Time()) +
         static_cast<double>(silu.geth2d_Time()) +
         static_cast<double>(silu.geth2d_sptrsv1_Time()) +
         static_cast<double>(silu.geth2d_spmv_Time());
}

RunResult RunSplitOnce(const bench_common::CsrMatrix& input, const std::vector<double>& rhs,
                       bool solve) {
  csr_matrix matrix = MakeSplitMatrix(input);
  std::vector<double> b = rhs;
  std::vector<double> x(input.n, 0.0);
  RunResult result;
  result.x.assign(input.n, 0.0);

  {
    SILU silu;
    if (silu.Analyze(&matrix, &matrix, b.data()) != EXIT_SUCCESS) {
      throw std::runtime_error("Split_SpTRSV Analyze failed");
    }
    CUDA_CHECK(cudaDeviceSynchronize());
    result.analysis_ms = SplitAnalysisMs(silu);
    if (solve) {
      std::fill(x.begin(), x.end(), 0.0);
      CUDA_CHECK(cudaDeviceSynchronize());
      double solve_start_ms = NowMs();
      if (silu.trsv(b.data(), x.data(), SUBSTITUTION_FORWARD) != EXIT_SUCCESS) {
        throw std::runtime_error("Split_SpTRSV trsv failed");
      }
      CUDA_CHECK(cudaDeviceSynchronize());
      double solve_end_ms = NowMs();
      result.solve_ms = solve_end_ms - solve_start_ms;
      result.split_internal_sum_ms = SplitInternalSumMs(silu);
      result.split_sptrsv1_ms = static_cast<double>(silu.getSpTRSV1_Time());
      result.split_spmv_ms = static_cast<double>(silu.getSpMV_Time());
      result.split_sptrsv2_ms = static_cast<double>(silu.getSpTRSV2_Time());
      result.split_transfer_ms = SplitTransferMs(silu);
      result.x = x;
    }
  }

  FreeSplitMatrix(&matrix);
  return result;
}

std::map<std::string, std::string> EmptyRow(const Options& opt) {
  std::map<std::string, std::string> row;
  for (const auto& field : bench_common::ResultCsvFields()) row[field] = "";
  bench_common::FillTimingRow(&row, opt.mode, opt.warmup, opt.repeat,
                              opt.repeat_analysis, opt.statistic);
  row["method"] = "split_sptrsv";
  row["matrix"] = opt.matrix;
  row["timeout"] = "false";
  row["status"] = "unknown";
  return row;
}

void FillTotals(std::map<std::string, std::string>* row, double analysis_ms, double solve_ms) {
  (*row)["analysis_ms"] = bench_common::FormatDouble(analysis_ms);
  (*row)["solve_ms"] = bench_common::FormatDouble(solve_ms);
  (*row)["total_1_ms"] = bench_common::FormatDouble(analysis_ms + solve_ms);
  (*row)["total_10_ms"] = bench_common::FormatDouble(analysis_ms + 10.0 * solve_ms);
  (*row)["total_100_ms"] = bench_common::FormatDouble(analysis_ms + 100.0 * solve_ms);
}

void FillSplitInternalTiming(std::map<std::string, std::string>* row,
                             double split_internal_sum_ms,
                             double split_sptrsv1_ms,
                             double split_spmv_ms,
                             double split_sptrsv2_ms,
                             double split_transfer_ms) {
  (*row)["split_internal_sum_ms"] = bench_common::FormatDouble(split_internal_sum_ms);
  (*row)["split_sptrsv1_ms"] = bench_common::FormatDouble(split_sptrsv1_ms);
  (*row)["split_spmv_ms"] = bench_common::FormatDouble(split_spmv_ms);
  (*row)["split_sptrsv2_ms"] = bench_common::FormatDouble(split_sptrsv2_ms);
  (*row)["split_transfer_ms"] = bench_common::FormatDouble(split_transfer_ms);
}

}  // namespace

int main(int argc, char** argv) {
  Options opt;
  try {
    opt = ParseArgs(argc, argv);
    auto matrix = bench_common::ReadCsrbin(opt.csrbin_path);
    auto rhs = bench_common::ReadRhs(opt.rhs_path, matrix.n);

    for (int i = 0; i < opt.warmup; ++i) {
      (void)RunSplitOnce(matrix, rhs, true);
    }

    std::vector<double> analysis_times;
    analysis_times.reserve(opt.repeat_analysis);
    for (int i = 0; i < opt.repeat_analysis; ++i) {
      analysis_times.push_back(RunSplitOnce(matrix, rhs, false).analysis_ms);
    }
    double analysis_ms = bench_common::Median(analysis_times);

    std::vector<double> solve_times;
    std::vector<double> split_internal_sum_times;
    std::vector<double> split_sptrsv1_times;
    std::vector<double> split_spmv_times;
    std::vector<double> split_sptrsv2_times;
    std::vector<double> split_transfer_times;
    std::vector<double> x;
    solve_times.reserve(opt.repeat);
    split_internal_sum_times.reserve(opt.repeat);
    split_sptrsv1_times.reserve(opt.repeat);
    split_spmv_times.reserve(opt.repeat);
    split_sptrsv2_times.reserve(opt.repeat);
    split_transfer_times.reserve(opt.repeat);
    for (int i = 0; i < opt.repeat; ++i) {
      RunResult result = RunSplitOnce(matrix, rhs, true);
      solve_times.push_back(result.solve_ms);
      split_internal_sum_times.push_back(result.split_internal_sum_ms);
      split_sptrsv1_times.push_back(result.split_sptrsv1_ms);
      split_spmv_times.push_back(result.split_spmv_ms);
      split_sptrsv2_times.push_back(result.split_sptrsv2_ms);
      split_transfer_times.push_back(result.split_transfer_ms);
      x = std::move(result.x);
    }
    double solve_ms = bench_common::Median(solve_times);
    double split_internal_sum_ms = bench_common::Median(split_internal_sum_times);
    double split_sptrsv1_ms = bench_common::Median(split_sptrsv1_times);
    double split_spmv_ms = bench_common::Median(split_spmv_times);
    double split_sptrsv2_ms = bench_common::Median(split_sptrsv2_times);
    double split_transfer_ms = bench_common::Median(split_transfer_times);

    double residual = bench_common::Residual(matrix, x, rhs);
    bool pass = residual < 1e-10;
    bench_common::WriteVectorText(opt.x_output_path, x);

    auto row = EmptyRow(opt);
    row["n"] = std::to_string(matrix.n);
    row["nnz"] = std::to_string(matrix.nnz);
    row["diag_filled"] = std::to_string(matrix.diag_filled);
    FillTotals(&row, analysis_ms, solve_ms);
    FillSplitInternalTiming(&row, split_internal_sum_ms, split_sptrsv1_ms,
                            split_spmv_ms, split_sptrsv2_ms, split_transfer_ms);
    row["residual"] = bench_common::FormatDouble(residual);
    row["residual_pass"] = pass ? "true" : "false";
    row["status"] = pass ? "ok" : "residual_error";
    row["error"] = pass ? "" : "residual >= 1e-10";
    bench_common::AppendResultCsv(opt.output_path, row, !FileExists(opt.output_path));

    std::cout << "x=";
    for (size_t i = 0; i < x.size(); ++i) std::cout << (i ? "," : "") << x[i];
    std::cout << "\nresidual=" << residual << "\nanalysis_ms=" << analysis_ms
              << "\nsolve_ms=" << solve_ms << "\nmode=" << opt.mode
              << "\nsplit_internal_sum_ms=" << split_internal_sum_ms
              << "\nsplit_sptrsv1_ms=" << split_sptrsv1_ms
              << "\nsplit_spmv_ms=" << split_spmv_ms
              << "\nsplit_sptrsv2_ms=" << split_sptrsv2_ms
              << "\nsplit_transfer_ms=" << split_transfer_ms
              << "\nwarmup=" << opt.warmup << "\nrepeat_solve=" << opt.repeat
              << "\nrepeat_analysis=" << opt.repeat_analysis
              << "\nstatistic=" << opt.statistic << "\n";
    return pass ? 0 : 2;
  } catch (const std::exception& ex) {
    try {
      auto row = EmptyRow(opt);
      row["status"] = "error";
      row["error"] = ex.what();
      row["residual_pass"] = "false";
      bench_common::AppendResultCsv(opt.output_path, row, !FileExists(opt.output_path));
    } catch (...) {
    }
    std::cerr << "split_sptrsv_baseline error: " << ex.what() << "\n";
    return 1;
  }
}
