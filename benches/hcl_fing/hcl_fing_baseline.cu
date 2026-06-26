#include <cuda_runtime.h>

#include <algorithm>
#include <cstdlib>
#include <iostream>
#include <map>
#include <stdexcept>
#include <string>
#include <vector>

#include "benchmark_config.h"
#include "common.h"
#include "analysis.h"
#include "csrbin_utils.h"
#include "dfr_syncfree.h"
#include "result_csv.h"
#include "solver.h"

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
          << "用法: hcl_fing_baseline --mode quick|benchmark --matrix NAME [选项]\n"
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
    opt.x_output_path = std::string(DEFAULT_REPO_ROOT) + "/results/sanity/x/hcl_fing_" + opt.matrix + ".x.txt";
  }
  return opt;
}

bool FileExists(const std::string& path) {
  std::ifstream in(path);
  return static_cast<bool>(in);
}

float EventElapsed(cudaEvent_t start, cudaEvent_t stop) {
  float ms = 0.0f;
  CUDA_CHECK(cudaEventElapsedTime(&ms, start, stop));
  return ms;
}

bool TraceEnabled() {
  static const bool enabled = std::getenv("HCL_FING_TRACE") != nullptr;
  return enabled;
}

void Trace(const std::string& message) {
  if (!TraceEnabled()) return;
  std::cerr << "[hcl_fing_trace] " << message << '\n';
  std::cerr.flush();
}

struct ScheduleCheckResult {
  int missing_rows = 0;
  int duplicate_rows = 0;
  int invalid_ranges = 0;
  int invalid_rows = 0;
  int over_capacity_warps = 0;
  int same_warp_dependencies = 0;
  int non_prior_warp_dependencies = 0;
  std::string first_missing;
  std::string first_same_warp;
  std::string first_non_prior_warp;

  bool ok() const {
    return missing_rows == 0 && duplicate_rows == 0 && invalid_ranges == 0 &&
           invalid_rows == 0 && over_capacity_warps == 0 &&
           non_prior_warp_dependencies == 0;
  }

  std::string Summary() const {
    return "missing_rows=" + std::to_string(missing_rows) +
           " duplicate_rows=" + std::to_string(duplicate_rows) +
           " invalid_ranges=" + std::to_string(invalid_ranges) +
           " invalid_rows=" + std::to_string(invalid_rows) +
           " over_capacity_warps=" + std::to_string(over_capacity_warps) +
           " same_warp_dependencies=" + std::to_string(same_warp_dependencies) +
           " non_prior_warp_dependencies=" +
           std::to_string(non_prior_warp_dependencies) +
           " first_missing=" + first_missing +
           " first_same_warp=" + first_same_warp +
           " first_non_prior_warp=" + first_non_prior_warp;
  }
};

ScheduleCheckResult CheckScheduleCoverage(const bench_common::CsrMatrix& matrix,
                                          const dfr_analysis_info_t* info) {
  ScheduleCheckResult result;
  std::vector<int> iorder(matrix.n);
  std::vector<int> ibase_row(info->n_warps + 1);
  std::vector<int> ivect_size(info->n_warps);
  CUDA_CHECK(cudaMemcpy(iorder.data(), info->iorder, sizeof(int) * iorder.size(),
                        cudaMemcpyDeviceToHost));
  CUDA_CHECK(cudaMemcpy(ibase_row.data(), info->ibase_row, sizeof(int) * ibase_row.size(),
                        cudaMemcpyDeviceToHost));
  CUDA_CHECK(cudaMemcpy(ivect_size.data(), info->ivect_size_warp,
                        sizeof(int) * ivect_size.size(), cudaMemcpyDeviceToHost));

  std::vector<int> covered(matrix.n, 0);
  std::vector<int> row_to_warp(matrix.n, -1);
  for (int warp = 0; warp < info->n_warps; ++warp) {
    int base = ibase_row[warp];
    int next = ibase_row[warp + 1];
    int n_vects = next - base;
    int vect_size = ivect_size[warp];
    int capacity = vect_size == 0 ? 32 : 32 / vect_size;
    if (base < 0 || next < base || next > matrix.n || capacity <= 0) {
      ++result.invalid_ranges;
      continue;
    }
    if (n_vects > capacity) {
      ++result.over_capacity_warps;
    }
    int active = std::min(n_vects, capacity);
    for (int j = 0; j < active; ++j) {
      int row = iorder[base + j];
      if (row < 0 || row >= matrix.n) {
        ++result.invalid_rows;
      } else {
        covered[row] += 1;
        row_to_warp[row] = warp;
      }
    }
  }

  for (int row = 0; row < matrix.n; ++row) {
    if (covered[row] == 0) {
      if (result.missing_rows < 12) {
        if (!result.first_missing.empty()) result.first_missing += ",";
        result.first_missing += std::to_string(row);
      }
      ++result.missing_rows;
    } else if (covered[row] > 1) {
      ++result.duplicate_rows;
    }
  }
  for (int row = 0; row < matrix.n; ++row) {
    int row_warp = row_to_warp[row];
    if (row_warp < 0) continue;
    for (int idx = matrix.row_ptr[row]; idx < matrix.row_ptr[row + 1]; ++idx) {
      int dep = matrix.col_idx[idx];
      if (dep >= row) continue;
      if (row_to_warp[dep] == row_warp) {
        if (result.same_warp_dependencies < 12) {
          if (!result.first_same_warp.empty()) result.first_same_warp += ";";
          result.first_same_warp += std::to_string(row) + "<-" + std::to_string(dep) +
                                    "@w" + std::to_string(row_warp);
        }
        ++result.same_warp_dependencies;
      }
      if (row_to_warp[dep] >= row_warp) {
        if (result.non_prior_warp_dependencies < 12) {
          if (!result.first_non_prior_warp.empty()) result.first_non_prior_warp += ";";
          result.first_non_prior_warp += std::to_string(row) + "<-" +
                                         std::to_string(dep) + "@w" +
                                         std::to_string(row_warp) + "<=w" +
                                         std::to_string(row_to_warp[dep]);
        }
        ++result.non_prior_warp_dependencies;
      }
    }
  }
  Trace("schedule coverage " + result.Summary());
  return result;
}

void FreeAnalysis(dfr_analysis_info_t* info) {
  if (!info) return;
  cudaFree(info->iorder);
  cudaFree(info->row_ctr);
  cudaFree(info->ibase_row);
  cudaFree(info->ivect_size_warp);
  free(info);
}

void FreeMatrix(sp_mat_t* mat) {
  if (!mat) return;
  cudaFree(mat->ia);
  cudaFree(mat->ja);
  cudaFree(mat->a);
  free(mat);
}

void BuildAnalyzedMatrix(const bench_common::CsrMatrix& matrix, sp_mat_t** gpu_L,
                         dfr_analysis_info_t** info) {
  *gpu_L = static_cast<sp_mat_t*>(malloc(sizeof(sp_mat_t)));
  if (!*gpu_L) throw std::runtime_error("malloc sp_mat_t failed");
  (*gpu_L)->nr = matrix.n;
  (*gpu_L)->nc = matrix.n;
  (*gpu_L)->nnz = matrix.nnz;
  CUDA_CHECK(cudaMalloc(&(*gpu_L)->ia, sizeof(int) * matrix.row_ptr.size()));
  CUDA_CHECK(cudaMalloc(&(*gpu_L)->ja, sizeof(int) * matrix.col_idx.size()));
  CUDA_CHECK(cudaMalloc(&(*gpu_L)->a, sizeof(double) * matrix.values.size()));
  CUDA_CHECK(cudaMemcpy((*gpu_L)->ia, matrix.row_ptr.data(), sizeof(int) * matrix.row_ptr.size(),
                        cudaMemcpyHostToDevice));
  CUDA_CHECK(cudaMemcpy((*gpu_L)->ja, matrix.col_idx.data(), sizeof(int) * matrix.col_idx.size(),
                        cudaMemcpyHostToDevice));
  CUDA_CHECK(cudaMemcpy((*gpu_L)->a, matrix.values.data(), sizeof(double) * matrix.values.size(),
                        cudaMemcpyHostToDevice));
  *info = static_cast<dfr_analysis_info_t*>(malloc(sizeof(dfr_analysis_info_t)));
  if (!*info) throw std::runtime_error("malloc dfr_analysis_info_t failed");
  (*info)->mode = MULTIROW;
  multirow_analysis_base_GPU(info, *gpu_L, MULTIROW);
  CUDA_CHECK(cudaDeviceSynchronize());
}

std::map<std::string, std::string> EmptyRow(const Options& opt) {
  std::map<std::string, std::string> row;
  for (const auto& field : bench_common::ResultCsvFields()) row[field] = "";
  bench_common::FillTimingRow(&row, opt.mode, opt.warmup, opt.repeat,
                              opt.repeat_analysis, opt.statistic);
  row["method"] = "hcl_fing";
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

}  // namespace

int main(int argc, char** argv) {
  Options opt;
  try {
    opt = ParseArgs(argc, argv);
    Trace("parsed arguments");
    auto matrix = bench_common::ReadCsrbin(opt.csrbin_path);
    auto rhs = bench_common::ReadRhs(opt.rhs_path, matrix.n);
    Trace("read input matrix=" + opt.matrix + " n=" + std::to_string(matrix.n) +
          " nnz=" + std::to_string(matrix.nnz));

    cudaEvent_t start = nullptr, stop = nullptr;
    CUDA_CHECK(cudaEventCreate(&start));
    CUDA_CHECK(cudaEventCreate(&stop));

    std::vector<double> analysis_times;
    for (int i = 0; i < opt.repeat_analysis; ++i) {
      Trace("analysis iteration begin " + std::to_string(i));
      sp_mat_t* tmp_mat = nullptr;
      dfr_analysis_info_t* tmp_info = nullptr;
      CUDA_CHECK(cudaDeviceSynchronize());
      CUDA_CHECK(cudaEventRecord(start));
      BuildAnalyzedMatrix(matrix, &tmp_mat, &tmp_info);
      CUDA_CHECK(cudaEventRecord(stop));
      CUDA_CHECK(cudaEventSynchronize(stop));
      analysis_times.push_back(EventElapsed(start, stop));
      Trace("analysis iteration end " + std::to_string(i));
      FreeAnalysis(tmp_info);
      FreeMatrix(tmp_mat);
    }
    double analysis_ms = bench_common::Median(analysis_times);

    sp_mat_t* gpu_L = nullptr;
    dfr_analysis_info_t* info = nullptr;
    Trace("final analysis begin");
    BuildAnalyzedMatrix(matrix, &gpu_L, &info);
    Trace("final analysis end n_warps=" + std::to_string(info->n_warps) +
          " nlevs=" + std::to_string(info->nlevs));
    ScheduleCheckResult schedule_check = CheckScheduleCoverage(matrix, info);
    if (!schedule_check.ok()) {
      auto row = EmptyRow(opt);
      row["n"] = std::to_string(matrix.n);
      row["nnz"] = std::to_string(matrix.nnz);
      row["diag_filled"] = std::to_string(matrix.diag_filled);
      row["analysis_ms"] = bench_common::FormatDouble(analysis_ms);
      row["residual_pass"] = "false";
      row["status"] = "analysis_order_error";
      row["error"] = "HCL analysis schedule may deadlock: " + schedule_check.Summary();
      bench_common::AppendResultCsv(opt.output_path, row, !FileExists(opt.output_path));
      std::cerr << "hcl_fing_baseline analysis_order_error: "
                << schedule_check.Summary() << "\n";
      FreeAnalysis(info);
      FreeMatrix(gpu_L);
      cudaEventDestroy(start);
      cudaEventDestroy(stop);
      return 3;
    }
    double *d_b = nullptr, *d_x = nullptr, *pinned_rhs = nullptr;
    CUDA_CHECK(cudaMalloc(&d_b, sizeof(double) * rhs.size()));
    CUDA_CHECK(cudaMalloc(&d_x, sizeof(double) * rhs.size()));
    CUDA_CHECK(cudaHostAlloc(&pinned_rhs, sizeof(double) * rhs.size(), cudaHostAllocDefault));
    std::copy(rhs.begin(), rhs.end(), pinned_rhs);

    for (int i = 0; i < opt.warmup; ++i) {
      Trace("warmup solve begin " + std::to_string(i));
      CUDA_CHECK(cudaMemcpy(d_b, pinned_rhs, sizeof(double) * rhs.size(), cudaMemcpyHostToDevice));
      csr_L_solve_multirow(gpu_L, info, d_b, d_x, matrix.n, 0);
      CUDA_CHECK(cudaDeviceSynchronize());
      Trace("warmup solve end " + std::to_string(i));
    }

    std::vector<double> solve_times;
    for (int i = 0; i < opt.repeat; ++i) {
      Trace("timed solve begin " + std::to_string(i));
      CUDA_CHECK(cudaDeviceSynchronize());
      CUDA_CHECK(cudaEventRecord(start));
      CUDA_CHECK(cudaMemcpyAsync(d_b, pinned_rhs, sizeof(double) * rhs.size(), cudaMemcpyHostToDevice));
      csr_L_solve_multirow(gpu_L, info, d_b, d_x, matrix.n, 0);
      CUDA_CHECK(cudaEventRecord(stop));
      CUDA_CHECK(cudaEventSynchronize(stop));
      CUDA_CHECK(cudaDeviceSynchronize());
      solve_times.push_back(EventElapsed(start, stop));
      Trace("timed solve end " + std::to_string(i));
    }
    double solve_ms = bench_common::Median(solve_times);

    std::vector<double> x(matrix.n, 0.0);
    Trace("copy result begin");
    CUDA_CHECK(cudaMemcpy(x.data(), d_x, sizeof(double) * x.size(), cudaMemcpyDeviceToHost));
    Trace("copy result end");
    double residual = bench_common::Residual(matrix, x, rhs);
    bool pass = residual < 1e-10;
    bench_common::WriteVectorText(opt.x_output_path, x);

    auto row = EmptyRow(opt);
    row["n"] = std::to_string(matrix.n);
    row["nnz"] = std::to_string(matrix.nnz);
    row["diag_filled"] = std::to_string(matrix.diag_filled);
    FillTotals(&row, analysis_ms, solve_ms);
    row["residual"] = bench_common::FormatDouble(residual);
    row["residual_pass"] = pass ? "true" : "false";
    row["status"] = pass ? "ok" : "residual_error";
    row["error"] = pass ? "" : "residual >= 1e-10";
    bench_common::AppendResultCsv(opt.output_path, row, !FileExists(opt.output_path));

    std::cout << "x=";
    for (size_t i = 0; i < x.size(); ++i) std::cout << (i ? "," : "") << x[i];
    std::cout << "\nresidual=" << residual << "\nanalysis_ms=" << analysis_ms
              << "\nsolve_ms=" << solve_ms << "\nmode=" << opt.mode
              << "\nwarmup=" << opt.warmup << "\nrepeat_solve=" << opt.repeat
              << "\nrepeat_analysis=" << opt.repeat_analysis
              << "\nstatistic=" << opt.statistic << "\n";

    cudaFreeHost(pinned_rhs);
    cudaFree(d_x);
    cudaFree(d_b);
    FreeAnalysis(info);
    FreeMatrix(gpu_L);
    cudaEventDestroy(start);
    cudaEventDestroy(stop);
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
    std::cerr << "hcl_fing_baseline error: " << ex.what() << "\n";
    return 1;
  }
}
