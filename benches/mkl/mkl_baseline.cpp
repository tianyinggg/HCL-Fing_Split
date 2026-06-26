#include <mkl.h>
#include <mkl_spblas.h>

#include <chrono>
#include <cstdlib>
#include <iostream>
#include <map>
#include <stdexcept>
#include <string>
#include <vector>

#include "benchmark_config.h"
#include "csrbin_utils.h"
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

double NowMs() {
  using clock = std::chrono::steady_clock;
  static const auto start = clock::now();
  auto now = clock::now();
  return std::chrono::duration<double, std::milli>(now - start).count();
}

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
          << "用法: mkl_baseline --mode quick|benchmark --matrix NAME [选项]\n"
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
    opt.x_output_path = std::string(DEFAULT_REPO_ROOT) + "/results/sanity/x/mkl_" + opt.matrix + ".x.txt";
  }
  return opt;
}

bool FileExists(const std::string& path) {
  std::ifstream in(path);
  return static_cast<bool>(in);
}

void CheckMkl(sparse_status_t status, const std::string& what) {
  if (status != SPARSE_STATUS_SUCCESS) {
    throw std::runtime_error(what + " failed with MKL status " + std::to_string(status));
  }
}

std::map<std::string, std::string> EmptyRow(const Options& opt) {
  std::map<std::string, std::string> row;
  for (const auto& field : bench_common::ResultCsvFields()) row[field] = "";
  bench_common::FillTimingRow(&row, opt.mode, opt.warmup, opt.repeat,
                              opt.repeat_analysis, opt.statistic);
  row["method"] = "mkl";
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
    setenv("OMP_NUM_THREADS", "1", 0);
    setenv("MKL_NUM_THREADS", "1", 0);
    setenv("MKL_DYNAMIC", "FALSE", 0);
    mkl_set_num_threads(1);
    mkl_set_dynamic(0);

    auto matrix = bench_common::ReadCsrbin(opt.csrbin_path);
    auto rhs = bench_common::ReadRhs(opt.rhs_path, matrix.n);

    std::vector<double> analysis_times;
    analysis_times.reserve(opt.repeat_analysis);
    for (int i = 0; i < opt.repeat_analysis; ++i) {
      sparse_matrix_t A = nullptr;
      matrix_descr descr;
      descr.type = SPARSE_MATRIX_TYPE_TRIANGULAR;
      descr.mode = SPARSE_FILL_MODE_LOWER;
      descr.diag = SPARSE_DIAG_NON_UNIT;

      double t0 = NowMs();
      CheckMkl(mkl_sparse_d_create_csr(&A, SPARSE_INDEX_BASE_ZERO, matrix.n, matrix.n,
                                       matrix.row_ptr.data(), matrix.row_ptr.data() + 1,
                                       matrix.col_idx.data(), matrix.values.data()),
               "mkl_sparse_d_create_csr");
      CheckMkl(mkl_sparse_set_sv_hint(A, SPARSE_OPERATION_NON_TRANSPOSE, descr, 1),
               "mkl_sparse_set_sv_hint");
      CheckMkl(mkl_sparse_optimize(A), "mkl_sparse_optimize");
      double t1 = NowMs();
      analysis_times.push_back(t1 - t0);
      mkl_sparse_destroy(A);
    }
    double analysis_ms = bench_common::Median(analysis_times);

    sparse_matrix_t A = nullptr;
    matrix_descr descr;
    descr.type = SPARSE_MATRIX_TYPE_TRIANGULAR;
    descr.mode = SPARSE_FILL_MODE_LOWER;
    descr.diag = SPARSE_DIAG_NON_UNIT;
    CheckMkl(mkl_sparse_d_create_csr(&A, SPARSE_INDEX_BASE_ZERO, matrix.n, matrix.n,
                                     matrix.row_ptr.data(), matrix.row_ptr.data() + 1,
                                     matrix.col_idx.data(), matrix.values.data()),
             "mkl_sparse_d_create_csr");
    CheckMkl(mkl_sparse_set_sv_hint(A, SPARSE_OPERATION_NON_TRANSPOSE, descr, 1),
             "mkl_sparse_set_sv_hint");
    CheckMkl(mkl_sparse_optimize(A), "mkl_sparse_optimize");

    std::vector<double> x(matrix.n, 0.0);
    for (int i = 0; i < opt.warmup; ++i) {
      std::fill(x.begin(), x.end(), 0.0);
      CheckMkl(mkl_sparse_d_trsv(SPARSE_OPERATION_NON_TRANSPOSE, 1.0, A, descr,
                                 rhs.data(), x.data()),
               "mkl_sparse_d_trsv");
    }
    std::vector<double> solve_times;
    solve_times.reserve(opt.repeat);
    for (int i = 0; i < opt.repeat; ++i) {
      std::fill(x.begin(), x.end(), 0.0);
      double t0 = NowMs();
      CheckMkl(mkl_sparse_d_trsv(SPARSE_OPERATION_NON_TRANSPOSE, 1.0, A, descr,
                                 rhs.data(), x.data()),
               "mkl_sparse_d_trsv");
      double t1 = NowMs();
      solve_times.push_back(t1 - t0);
    }
    double solve_ms = bench_common::Median(solve_times);
    mkl_sparse_destroy(A);

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
    std::cerr << "mkl_baseline error: " << ex.what() << "\n";
    return 1;
  }
}
