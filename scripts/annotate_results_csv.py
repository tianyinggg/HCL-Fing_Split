#!/usr/bin/env python3
"""Annotate result CSV files with Chinese descriptions and refresh the CSV index."""

from __future__ import annotations

import csv
from pathlib import Path

from result_schema import CSV_FIELD_DESCRIPTIONS


REPO_ROOT = Path(__file__).resolve().parents[1]
CSV_DIR = REPO_ROOT / "results" / "csv"
CSV_INDEX = CSV_DIR / "README.md"
COMMENT_PREFIX = "#"


FILE_DESCRIPTIONS = {
    "main_results.csv": "默认 quick sanity 结果文件；历史追加记录较多，只用于快速检查和回溯。",
    "main_results_clean.csv": "四个小矩阵 quick sanity 的干净结果文件，不作为正式性能结论。",
    "benchmark_results_clean.csv": "四个小矩阵 benchmark sanity 的干净结果文件，用于验证统一计时协议。",
    "hcl_fix_check.csv": "HCL-Fing wrapper 修正后的专项检查结果，主要用于确认边界和调度保护逻辑。",
    "hcl_smoke_lower4_quick.csv": "HCL smoke lower4 小矩阵 quick 检查结果。",
    "hcl_smoke_lower4_benchmark.csv": "HCL smoke lower4 小矩阵 benchmark 检查结果。",
    "suitesparse_selected_quick.csv": "早期 SuiteSparse 小批量矩阵 quick 筛选结果。",
    "suitesparse_batch1_quick.csv": "SuiteSparse batch1 十二个候选矩阵 quick 筛选结果。",
    "suitesparse_batch1_benchmark.csv": "SuiteSparse batch1 十二个候选矩阵 benchmark 结果，允许 HCL 缺失结果。",
    "hcl_schedule_diagnostics_suitesparse_batch1.csv": "SuiteSparse batch1 的 HCL-Fing 调度诊断统计，用于分析 analysis_order_error。",
    "suitesparse_final_large_quick.csv": "最终大矩阵候选集合 quick 筛选结果，包含可运行性和残差状态。",
    "suitesparse_final_large_benchmark.csv": "最终大矩阵筛选过程 benchmark 原始结果，保留中间被剔除矩阵。",
    "suitesparse_final_large_benchmark_clean.csv": "最终大矩阵 8 个矩阵的干净 benchmark 主结果，用于正式比较结论。",
    "hcl_schedule_diagnostics_suitesparse_final_large.csv": "最终大矩阵候选集合的 HCL-Fing 调度诊断统计。",
    "suitesparse_final_large_robustness_status.csv": "最终大矩阵候选 quick 阶段的四方法鲁棒性状态统计。",
    "suitesparse_final_large_robust_stats.csv": "最终大矩阵干净 benchmark 的稳健统计结果，含均值、中位数和截尾均值。",
    "suitesparse_final_large_diag_filled_subset.csv": "最终大矩阵 benchmark 按补对角比例分组后的子集统计。",
    "suitesparse_final_large_structure_performance.csv": "最终大矩阵结构特征与性能指标合并表，用于解释性能差异。",
    "suitesparse_split_flip_test_quick.csv": "Split 翻盘三矩阵专项 quick 检查结果。",
    "suitesparse_split_flip_test_benchmark.csv": "Split 翻盘三矩阵专项 benchmark 结果。",
    "suitesparse_split_flip_test_structure.csv": "Split 翻盘三矩阵专项结构特征统计。",
    "suitesparse_split_flip_extended_quick.csv": "Split 翻盘五矩阵扩展 quick 检查结果。",
    "suitesparse_split_flip_extended_benchmark.csv": "Split 翻盘五矩阵扩展 benchmark 结果。",
    "suitesparse_split_flip_extended_structure.csv": "Split 翻盘五矩阵扩展结构特征统计。",
    "representative_repeat300_benchmark.csv": "六个代表矩阵 repeat_solve=300 的 benchmark 稳定性测试结果。",
    "hcl_modified_representative_quick.csv": "用户修改 HCL-Fing 后，六个代表矩阵四方法 quick 检查结果。",
    "hcl_modified_representative_benchmark.csv": "用户修改 HCL-Fing 后，六个代表矩阵四方法 benchmark 结果。",
}


FILE_ORDER = {
    "main_results.csv": 10,
    "hcl_fix_check.csv": 20,
    "main_results_clean.csv": 30,
    "benchmark_results_clean.csv": 40,
    "hcl_smoke_lower4_quick.csv": 50,
    "hcl_smoke_lower4_benchmark.csv": 60,
    "suitesparse_selected_quick.csv": 70,
    "suitesparse_batch1_quick.csv": 80,
    "hcl_schedule_diagnostics_suitesparse_batch1.csv": 90,
    "suitesparse_batch1_benchmark.csv": 100,
    "suitesparse_final_large_quick.csv": 110,
    "hcl_schedule_diagnostics_suitesparse_final_large.csv": 120,
    "suitesparse_final_large_benchmark.csv": 130,
    "suitesparse_final_large_benchmark_clean.csv": 140,
    "suitesparse_final_large_robustness_status.csv": 150,
    "suitesparse_final_large_robust_stats.csv": 160,
    "suitesparse_final_large_diag_filled_subset.csv": 170,
    "suitesparse_final_large_structure_performance.csv": 180,
    "suitesparse_split_flip_test_quick.csv": 190,
    "suitesparse_split_flip_test_benchmark.csv": 200,
    "suitesparse_split_flip_test_structure.csv": 210,
    "suitesparse_split_flip_extended_quick.csv": 220,
    "suitesparse_split_flip_extended_benchmark.csv": 230,
    "suitesparse_split_flip_extended_structure.csv": 240,
    "representative_repeat300_benchmark.csv": 250,
    "hcl_modified_representative_quick.csv": 260,
    "hcl_modified_representative_benchmark.csv": 270,
}


FILE_STAGES = {
    "main_results.csv": "最早 tiny quick 试跑",
    "hcl_fix_check.csv": "HCL 修正检查",
    "main_results_clean.csv": "小矩阵 quick 干净重跑",
    "benchmark_results_clean.csv": "小矩阵 benchmark 干净重跑",
    "hcl_smoke_lower4_quick.csv": "HCL smoke quick",
    "hcl_smoke_lower4_benchmark.csv": "HCL smoke benchmark",
    "suitesparse_selected_quick.csv": "SuiteSparse 早期 quick",
    "suitesparse_batch1_quick.csv": "SuiteSparse batch1 quick",
    "hcl_schedule_diagnostics_suitesparse_batch1.csv": "SuiteSparse batch1 HCL 诊断",
    "suitesparse_batch1_benchmark.csv": "SuiteSparse batch1 benchmark",
    "suitesparse_final_large_quick.csv": "最终大矩阵 quick 筛选",
    "hcl_schedule_diagnostics_suitesparse_final_large.csv": "最终大矩阵 HCL 诊断",
    "suitesparse_final_large_benchmark.csv": "最终大矩阵 benchmark 原始",
    "suitesparse_final_large_benchmark_clean.csv": "最终大矩阵 benchmark 干净主结果",
    "suitesparse_final_large_robustness_status.csv": "最终大矩阵鲁棒性状态统计",
    "suitesparse_final_large_robust_stats.csv": "最终大矩阵稳健统计",
    "suitesparse_final_large_diag_filled_subset.csv": "最终大矩阵补对角子集分析",
    "suitesparse_final_large_structure_performance.csv": "最终大矩阵结构性能分析",
    "suitesparse_split_flip_test_quick.csv": "Split 三矩阵 quick",
    "suitesparse_split_flip_test_benchmark.csv": "Split 三矩阵 benchmark",
    "suitesparse_split_flip_test_structure.csv": "Split 三矩阵结构分析",
    "suitesparse_split_flip_extended_quick.csv": "Split 五矩阵 quick",
    "suitesparse_split_flip_extended_benchmark.csv": "Split 五矩阵 benchmark",
    "suitesparse_split_flip_extended_structure.csv": "Split 五矩阵结构分析",
    "representative_repeat300_benchmark.csv": "代表矩阵 repeat300 benchmark",
    "hcl_modified_representative_quick.csv": "HCL 修改后代表矩阵 quick",
    "hcl_modified_representative_benchmark.csv": "HCL 修改后代表矩阵 benchmark",
}


EXTRA_FIELD_DESCRIPTIONS = {
    "scope": "统计范围",
    "matrix_count": "矩阵数量",
    "ok_count": "成功数量",
    "ok_rate": "成功比例",
    "analysis_order_error_count": "HCL调度顺序错误数量",
    "residual_error_count": "残差错误数量",
    "timeout_count": "超时数量",
    "other_error_count": "其他错误数量",
    "metric": "统计指标",
    "count": "样本数量",
    "mean": "算术平均值",
    "median": "中位数",
    "trimmed_mean": "截尾平均值",
    "geomean": "几何平均值",
    "min": "最小值",
    "max": "最大值",
    "std": "标准差",
    "stdev": "标准差",
    "diag_class": "补对角比例分组",
    "matrices": "矩阵列表",
    "analysis_ms_mean": "分析时间平均值ms",
    "analysis_ms_median": "分析时间中位数ms",
    "solve_ms_mean": "求解时间平均值ms",
    "solve_ms_median": "求解时间中位数ms",
    "total_100_ms_mean": "百次求解总时间平均值ms",
    "total_100_ms_median": "百次求解总时间中位数ms",
    "diag_ratio": "补对角数量占矩阵维度比例",
    "zero_diag": "显式零对角数量",
    "tiny_diag_lt_1e-12": "绝对值小于1e-12的对角数量",
    "tiny_diag_lt_1e-8": "绝对值小于1e-8的对角数量",
    "min_abs_diag": "最小对角绝对值",
    "max_abs_diag": "最大对角绝对值",
    "max_abs_value": "矩阵元素最大绝对值",
    "max_abs_row_sum": "最大行绝对值和",
    "avg_row_nnz": "平均每行非零元数量",
    "max_row_nnz": "最大行非零元数量",
    "num_levels": "层级数量",
    "avg_parallelism": "平均层级并行度",
    "max_level_width": "最大层宽",
    "min_level_width": "最小层宽",
    "same_warp_dependencies": "同一warp内依赖数量",
    "non_prior_warp_dependencies": "非前序warp依赖数量",
    "residual_pass_count": "残差通过数量",
    "status_counts": "状态计数字典",
    "q1": "第一四分位数",
    "q3": "第三四分位数",
    "iqr": "四分位距",
    "cv": "变异系数",
    "analysis_ms_geomean": "分析时间几何平均值ms",
    "solve_ms_geomean": "求解时间几何平均值ms",
    "total_1_ms_mean": "一次求解总时间平均值ms",
    "total_1_ms_median": "一次求解总时间中位数ms",
    "total_1_ms_geomean": "一次求解总时间几何平均值ms",
    "total_10_ms_mean": "十次求解总时间平均值ms",
    "total_10_ms_median": "十次求解总时间中位数ms",
    "total_10_ms_geomean": "十次求解总时间几何平均值ms",
    "total_100_ms_geomean": "百次求解总时间几何平均值ms",
    "fastest_solve_method": "求解时间最快方法",
    "fastest_total100_method": "百次总时间最快方法",
    "hcl_vs_cusparse_solve_speedup": "HCL相对cuSPARSE求解加速比",
    "hcl_vs_split_solve_speedup": "HCL相对Split求解加速比",
    "hcl_vs_cusparse_total100_speedup": "HCL相对cuSPARSE百次总时间加速比",
    "hcl_vs_split_total100_speedup": "HCL相对Split百次总时间加速比",
    "cusparse_spsv_analysis_ms": "cuSPARSE分析时间ms",
    "cusparse_spsv_solve_ms": "cuSPARSE求解时间ms",
    "cusparse_spsv_total_1_ms": "cuSPARSE一次求解总时间ms",
    "cusparse_spsv_total_10_ms": "cuSPARSE十次求解总时间ms",
    "cusparse_spsv_total_100_ms": "cuSPARSE百次求解总时间ms",
    "mkl_analysis_ms": "MKL分析时间ms",
    "mkl_total_1_ms": "MKL一次求解总时间ms",
    "mkl_total_10_ms": "MKL十次求解总时间ms",
    "hcl_fing_analysis_ms": "HCL-Fing分析时间ms",
    "hcl_fing_solve_ms": "HCL-Fing求解时间ms",
    "hcl_fing_total_1_ms": "HCL-Fing一次求解总时间ms",
    "hcl_fing_total_10_ms": "HCL-Fing十次求解总时间ms",
    "hcl_fing_total_100_ms": "HCL-Fing百次求解总时间ms",
    "split_sptrsv_analysis_ms": "Split_SpTRSV分析时间ms",
    "split_sptrsv_solve_ms": "Split_SpTRSV求解时间ms",
    "split_sptrsv_total_1_ms": "Split_SpTRSV一次求解总时间ms",
    "split_sptrsv_total_10_ms": "Split_SpTRSV十次求解总时间ms",
    "split_sptrsv_total_100_ms": "Split_SpTRSV百次求解总时间ms",
    "section": "分析部分",
    "topic": "分析主题",
    "item": "条目",
    "metric": "指标名",
    "value": "指标值",
    "unit": "单位",
    "note": "中文说明",
    "conclusion": "分析结论",
    "evidence": "数据依据",
    "interpretation": "原因解释",
    "next_step": "后续建议",
    "hcl_solve_ms": "HCL-Fing求解时间ms",
    "split_solve_ms": "Split求解时间ms",
    "cusparse_solve_ms": "cuSPARSE求解时间ms",
    "mkl_solve_ms": "MKL求解时间ms",
    "hcl_total_100_ms": "HCL-Fing百次总时间ms",
    "split_total_100_ms": "Split百次总时间ms",
    "cusparse_total_100_ms": "cuSPARSE百次总时间ms",
    "mkl_total_100_ms": "MKL百次总时间ms",
    "winner_solve": "求解时间最快方法",
    "winner_total_100": "百次总时间最快方法",
}


FIELD_DESCRIPTIONS = {**CSV_FIELD_DESCRIPTIONS, **EXTRA_FIELD_DESCRIPTIONS}


def has_chinese(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)


def description_row_for(header: list[str]) -> list[str]:
    return [FIELD_DESCRIPTIONS.get(field, f"{field}字段说明待补充") for field in header]


def default_file_description(filename: str) -> str:
    return FILE_DESCRIPTIONS.get(filename, "结果文件说明待补充")


def comment_rows_for(path: Path) -> list[list[str]]:
    description = default_file_description(path.name)
    return [
        [f"# 文件说明: {description}"],
        ["# CSV格式: 注释行以#开头；随后第一行是字段名；第二行是中文字段说明；第三行开始是数据"],
        ["# 维护命令: python3 scripts/annotate_results_csv.py"],
    ]


def read_rows(path: Path) -> list[list[str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.reader(handle))


def write_rows(path: Path, rows: list[list[str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerows(rows)


def split_leading_comments(rows: list[list[str]]) -> tuple[list[list[str]], list[list[str]]]:
    index = 0
    while index < len(rows) and rows[index] and rows[index][0].startswith(COMMENT_PREFIX):
        index += 1
    return rows[:index], rows[index:]


def ensure_description_row(path: Path) -> tuple[int, int, bool]:
    rows = read_rows(path)
    if not rows:
        return 0, 0, False
    _, body = split_leading_comments(rows)
    if not body:
        return 0, 0, False
    header = body[0]
    expected = description_row_for(header)
    has_description = len(body) >= 2 and has_chinese(",".join(body[1]))
    if not has_description:
        body.insert(1, expected)
        has_description = True
    elif body[1] != expected:
        body[1] = expected
    comments = comment_rows_for(path)
    write_rows(path, comments + body)
    data_rows = max(0, len(body) - (2 if has_description else 1))
    return len(header), data_rows, has_description


def schema_name(header: list[str]) -> str:
    if header[: len(CSV_FIELD_DESCRIPTIONS)] == list(CSV_FIELD_DESCRIPTIONS):
        return "四方法统一结果 schema"
    if "num_levels" in header and "avg_parallelism" in header:
        return "矩阵结构/调度诊断 schema"
    if "ok_rate" in header:
        return "鲁棒性状态统计 schema"
    if "trimmed_mean" in header:
        return "稳健统计 schema"
    if "diag_class" in header and "matrix_count" in header:
        return "补对角子集统计 schema"
    if "winner_solve" in header or "hcl_solve_ms" in header:
        return "结构与性能合并 schema"
    return "专项统计 schema"


def file_sort_key(filename: str) -> tuple[int, str]:
    return (FILE_ORDER.get(filename, 10_000), filename)


def generate_index(rows_by_file: dict[str, tuple[list[str], int, int, bool]]) -> None:
    lines = [
        "# results/csv 文件说明",
        "",
        "本目录保存结构化 CSV 结果。约定如下：",
        "",
        "- 每个 CSV 顶部可以有若干 `#` 开头的中文注释行。",
        "- 注释行之后第一行是字段名。",
        "- 字段名之后第二行是中文字段说明。",
        "- 再往后是数据行。",
        "- 新生成或手工整理 CSV 后，运行 `python3 scripts/annotate_results_csv.py` 刷新本索引并补齐文件注释和中文字段说明。",
        "- 文件索引按实验推进时间顺序排列；未知新文件会排在已知文件之后。",
        "",
        "## 文件索引",
        "",
        "| 顺序 | 阶段 | 文件 | 中文描述 | schema | 数据行数 |",
        "| ---: | --- | --- | --- | --- | ---: |",
    ]
    for sequence, name in enumerate(sorted(rows_by_file, key=file_sort_key), start=1):
        header, field_count, data_rows, _ = rows_by_file[name]
        description = FILE_DESCRIPTIONS.get(name, "结果文件说明待补充")
        stage = FILE_STAGES.get(name, "未登记新文件")
        lines.append(
            f"| {sequence} | {stage} | `{name}` | {description} | {schema_name(header)}，{field_count} 个字段 | {data_rows} |"
        )
    lines.extend(
        [
            "",
            "## 维护规则",
            "",
            "- 正式结论优先看带 `clean` 或明确实验批次名的 benchmark 文件。",
            "- `quick` 文件只用于可运行性、残差和 CSV 格式检查，不作为正式性能结论。",
            "- `hcl_schedule_diagnostics_*` 文件只用于 HCL-Fing 调度错误诊断，不是四方法性能结果。",
            "- `structure`、`robust`、`diag_filled` 文件是从原始结果派生的统计表。",
            "- 新文件名应包含实验范围和模式，例如 `suitesparse_xxx_quick.csv` 或 `suitesparse_xxx_benchmark.csv`。",
        ]
    )
    CSV_INDEX.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    rows_by_file: dict[str, tuple[list[str], int, int, bool]] = {}
    for path in sorted(CSV_DIR.glob("*.csv")):
        field_count, data_rows, has_description = ensure_description_row(path)
        _, body = split_leading_comments(read_rows(path))
        header = body[0] if field_count and body else []
        rows_by_file[path.name] = (header, field_count, data_rows, has_description)
    generate_index(rows_by_file)
    print(f"annotated {len(rows_by_file)} CSV files")
    print(f"wrote {CSV_INDEX.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
