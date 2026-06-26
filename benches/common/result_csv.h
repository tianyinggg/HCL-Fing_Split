#ifndef HCL_FING_SPLIT_BENCHES_COMMON_RESULT_CSV_H_
#define HCL_FING_SPLIT_BENCHES_COMMON_RESULT_CSV_H_

#include <fstream>
#include <map>
#include <stdexcept>
#include <string>
#include <vector>

namespace bench_common {

inline const std::vector<std::string>& ResultCsvFields() {
  static const std::vector<std::string> fields = {
      "mode",         "method",      "matrix",      "n",
      "nnz",          "diag_filled", "warmup",      "repeat_solve",
      "repeat_analysis", "statistic", "analysis_ms", "solve_ms",
      "total_1_ms",   "total_10_ms", "total_100_ms", "split_internal_sum_ms",
      "split_sptrsv1_ms", "split_spmv_ms", "split_sptrsv2_ms",
      "split_transfer_ms", "residual", "residual_pass", "status",
      "error",       "timeout"};
  return fields;
}

inline const std::vector<std::string>& ResultCsvDescriptions() {
  static const std::vector<std::string> descriptions = {
      "运行模式",
      "方法名",
      "矩阵名",
      "矩阵维度",
      "lower CSR非零元数",
      "补对角数量",
      "预热次数",
      "求解重复次数",
      "分析重复次数",
      "统计方式",
      "分析准备中位时间ms",
      "单次完整求解端到端中位时间ms",
      "一次求解总时间ms",
      "十次求解总时间ms",
      "百次求解总时间ms",
      "Split内部计时求和ms",
      "Split第一段三角求解ms",
      "Split中间SpMV时间ms",
      "Split第二段三角求解ms",
      "Split内部传输求和ms",
      "相对残差",
      "残差是否通过",
      "运行状态或错误类型",
      "错误原因或诊断信息",
      "是否超时"};
  return descriptions;
}

inline std::string CsvEscape(const std::string& value) {
  bool needs_quotes = false;
  for (char ch : value) {
    if (ch == ',' || ch == '"' || ch == '\n' || ch == '\r') {
      needs_quotes = true;
      break;
    }
  }
  if (!needs_quotes) {
    return value;
  }
  std::string out = "\"";
  for (char ch : value) {
    if (ch == '"') {
      out += "\"\"";
    } else {
      out += ch;
    }
  }
  out += "\"";
  return out;
}

inline void WriteCsvRow(std::ofstream& out,
                        const std::vector<std::string>& values) {
  for (std::size_t i = 0; i < values.size(); ++i) {
    if (i != 0) {
      out << ',';
    }
    out << CsvEscape(values[i]);
  }
  out << '\n';
}

inline void WriteCsvCommentPreamble(std::ofstream& out) {
  out << "# 文件说明: 四方法统一实验结果；包含运行模式、方法名、矩阵名、计时、残差和状态\n";
  out << "# CSV格式: 注释行以#开头；随后第一行是字段名；第二行是中文字段说明；第三行开始是数据\n";
  out << "# 主口径: analysis_ms为分析/准备时间；solve_ms为单次完整solve端到端时间；total_k_ms=analysis_ms+k*solve_ms\n";
}

inline void AppendResultCsv(const std::string& path,
                            const std::map<std::string, std::string>& row,
                            bool write_header) {
  std::ofstream out(path, std::ios::app);
  if (!out) {
    throw std::runtime_error("failed to open CSV output: " + path);
  }
  const auto& fields = ResultCsvFields();
  if (write_header) {
    WriteCsvCommentPreamble(out);
    WriteCsvRow(out, fields);
    WriteCsvRow(out, ResultCsvDescriptions());
  }
  for (std::size_t i = 0; i < fields.size(); ++i) {
    if (i != 0) {
      out << ',';
    }
    auto iter = row.find(fields[i]);
    if (iter != row.end()) {
      out << CsvEscape(iter->second);
    }
  }
  out << '\n';
}

}  // namespace bench_common

#endif  // HCL_FING_SPLIT_BENCHES_COMMON_RESULT_CSV_H_
