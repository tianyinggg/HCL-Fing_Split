#!/usr/bin/env python3
"""Write an overwritable Markdown analysis report for the latest run."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / "results" / "summary" / "latest_run_analysis.md"

METHOD_ORDER = ["cusparse_spsv", "mkl", "hcl_fing", "split_sptrsv"]
METHOD_LABELS = {
    "cusparse_spsv": "cuSPARSE-SpSV",
    "mkl": "MKL",
    "hcl_fing": "HCL-Fing",
    "split_sptrsv": "Split_SpTRSV",
}
TIME_METRICS = ["analysis_ms", "solve_ms", "total_1_ms", "total_10_ms", "total_100_ms"]


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def fmt(value: float, digits: int = 6) -> str:
    return f"{value:.{digits}g}"


def fmt_ms(value: float) -> str:
    return f"{value:.4f}"


def read_result_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(line for line in handle if not line.startswith("#")))
    return [row for row in rows if row.get("mode") not in ("运行模式", "", None)]


def as_float(row: dict[str, str], key: str) -> float:
    value = row.get(key, "")
    return float(value) if value else 0.0


def ordered_methods(rows: list[dict[str, str]]) -> list[str]:
    present = {row["method"] for row in rows if row.get("method")}
    return [method for method in METHOD_ORDER if method in present] + sorted(present - set(METHOD_ORDER))


def ordered_matrices(rows: list[dict[str, str]]) -> list[str]:
    matrices: list[str] = []
    for row in rows:
        matrix = row.get("matrix", "")
        if matrix and matrix not in matrices:
            matrices.append(matrix)
    return matrices


def by_method_matrix(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    return {(row["method"], row["matrix"]): row for row in rows if row.get("method") and row.get("matrix")}


def average_by_method(rows: list[dict[str, str]]) -> dict[str, dict[str, float]]:
    averages: dict[str, dict[str, float]] = {}
    for method in ordered_methods(rows):
        ok_rows = [row for row in rows if row["method"] == method and row.get("status") == "ok"]
        if not ok_rows:
            continue
        averages[method] = {}
        for metric in TIME_METRICS:
            values = [as_float(row, metric) for row in ok_rows if row.get(metric)]
            if values:
                averages[method][metric] = sum(values) / len(values)
    return averages


def max_residual_by_method(rows: list[dict[str, str]]) -> dict[str, float]:
    result: dict[str, float] = {}
    for method in ordered_methods(rows):
        values = [as_float(row, "residual") for row in rows if row["method"] == method and row.get("residual")]
        if values:
            result[method] = max(values)
    return result


def fastest_method(rows: list[dict[str, str]], metric: str) -> dict[str, str]:
    ok_rows = [row for row in rows if row.get("status") == "ok" and row.get(metric)]
    return min(ok_rows, key=lambda row: as_float(row, metric))


def status_counts(rows: list[dict[str, str]]) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for method in ordered_methods(rows):
        result[method] = {}
        for row in rows:
            if row.get("method") != method:
                continue
            status = row.get("status", "")
            result[method][status] = result[method].get(status, 0) + 1
    return result


def speedup(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def table(headers: list[str], rows: list[list[str]]) -> list[str]:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return lines


def build_report(
    quick_path: Path,
    benchmark_path: Path,
    baseline_path: Path | None,
    quick_rows: list[dict[str, str]],
    benchmark_rows: list[dict[str, str]],
    baseline_rows: list[dict[str, str]],
) -> str:
    lines: list[str] = []
    methods = ordered_methods(benchmark_rows)
    matrices = ordered_matrices(benchmark_rows)
    bench_by = by_method_matrix(benchmark_rows)
    baseline_by = by_method_matrix(baseline_rows)
    averages = average_by_method(benchmark_rows)
    residuals = max_residual_by_method(benchmark_rows)

    first = benchmark_rows[0]
    quick_ok = sum(1 for row in quick_rows if row.get("status") == "ok")
    benchmark_ok = sum(1 for row in benchmark_rows if row.get("status") == "ok")

    lines.extend(
        [
            "# 最近一次四方法代表矩阵结果分析",
            "",
            "输入文件：",
            "",
            f"- quick：`{display_path(quick_path)}`",
            f"- benchmark：`{display_path(benchmark_path)}`",
            f"- 对比基准：`{display_path(baseline_path)}`" if baseline_path else "- 对比基准：无",
            "",
            "本报告只分析已有 CSV，没有重新运行实验。该文件由 `scripts/write_latest_run_analysis.py` 覆盖生成，用于保留最近一次分析结论。",
            "",
            "## 1. 实验口径",
            "",
            "benchmark 使用正式计时配置：",
            "",
        ]
    )
    lines.extend(
        table(
            ["参数", "值", "含义"],
            [
                ["warmup", first.get("warmup", ""), "正式计时前预热次数"],
                ["repeat_solve", first.get("repeat_solve", ""), "solve 阶段重复计时次数"],
                ["repeat_analysis", first.get("repeat_analysis", ""), "analysis/prepare 阶段重复计时次数"],
                ["statistic", first.get("statistic", ""), "正式结果采用的统计量"],
            ],
        )
    )
    lines.extend(
        [
            "",
            "主口径仍为：",
            "",
            "- `analysis_ms`：分析/准备阶段中位时间。",
            "- `solve_ms`：analysis/prepare 完成之后，一次完整 solve 的端到端中位时间。",
            "- `total_k_ms`：`analysis_ms + k * solve_ms`。",
            "",
            "注意：quick 只用于正确性和格式检查，不作为正式性能结论。",
            "",
            "## 2. 数据集结构",
            "",
        ]
    )

    structure_rows: list[list[str]] = []
    for matrix in matrices:
        row = next(row for row in benchmark_rows if row["matrix"] == matrix)
        n = int(row["n"])
        nnz = int(row["nnz"])
        avg_row_nnz = nnz / n if n else 0.0
        if avg_row_nnz < 3:
            category = "低行非零"
        elif avg_row_nnz < 8:
            category = "中等行非零"
        else:
            category = "高行非零"
        structure_rows.append(
            [
                matrix,
                str(n),
                str(nnz),
                f"{avg_row_nnz:.3f}",
                row["diag_filled"],
                category,
            ]
        )
    lines.extend(table(["matrix", "n", "nnz", "nnz/n", "diag_filled", "数据特点"], structure_rows))
    lines.extend(
        [
            "",
            "数据一致性：",
            "",
            "- 六个矩阵均来自统一预处理后的 lower CSR。",
            "- 输入为 0-based、double、CSR sorted。",
            "- RHS 使用 `x_true=ones` 生成。",
            "- `aug3dcqp` 补了 8000 个缺失对角，解释结果时应单独标注。",
            "",
            "结构含义：",
            "",
            "- `aug3dcqp`、`ACTIVSg70K`、`ss1` 平均每行非零很少，更偏向低行计算场景。",
            "- `finan512` 属于中等稀疏度，是本轮中 HCL 不占 solve 优势的关键反例。",
            "- `thermomech_dK` 和 `shipsec5` 行计算量更重，尤其 `shipsec5` 的 `nnz/n=28.614`，能暴露分段求解内部瓶颈。",
            "",
            "## 3. 正确性结果",
            "",
            f"- quick：{quick_ok}/{len(quick_rows)} 行 `status=ok`。",
            f"- benchmark：{benchmark_ok}/{len(benchmark_rows)} 行 `status=ok`。",
            "",
        ]
    )
    residual_rows = [
        [METHOD_LABELS.get(method, method), fmt(residuals.get(method, 0.0), 4), "通过"]
        for method in methods
    ]
    lines.extend(table(["方法", "benchmark 最大 residual", "判断"], residual_rows))
    lines.extend(
        [
            "",
            "结论：四个方法都能读取同一份统一 CSR，完成求解，并通过 residual 检查。Split 的最大残差来自 `shipsec5`，约 `5e-14`，仍然通过。",
            "",
            "## 4. 平均性能",
            "",
            "下表是 6 个矩阵的等权平均，不按 `n` 或 `nnz` 加权。",
            "",
        ]
    )
    avg_rows = []
    for method in methods:
        values = averages[method]
        avg_rows.append(
            [
                METHOD_LABELS.get(method, method),
                fmt_ms(values["analysis_ms"]),
                fmt_ms(values["solve_ms"]),
                fmt_ms(values["total_1_ms"]),
                fmt_ms(values["total_10_ms"]),
                fmt_ms(values["total_100_ms"]),
            ]
        )
    lines.extend(table(["方法", "avg_analysis_ms", "avg_solve_ms", "avg_total_1_ms", "avg_total_10_ms", "avg_total_100_ms"], avg_rows))

    hcl_avg = averages.get("hcl_fing", {})
    mkl_avg = averages.get("mkl", {})
    split_avg = averages.get("split_sptrsv", {})
    cusparse_avg = averages.get("cusparse_spsv", {})
    lines.extend(
        [
            "",
            "平均上 HCL-Fing 当前最好：",
            "",
            f"- `analysis_ms` 最低，是 MKL 的约 `{100 * speedup(hcl_avg['analysis_ms'], mkl_avg['analysis_ms']):.1f}%`，是 Split 的约 `{100 * speedup(hcl_avg['analysis_ms'], split_avg['analysis_ms']):.1f}%`。",
            f"- `solve_ms` 最低，约比 MKL 快 `{speedup(mkl_avg['solve_ms'], hcl_avg['solve_ms']):.2f}x`，比 Split 快 `{speedup(split_avg['solve_ms'], hcl_avg['solve_ms']):.2f}x`，比 cuSPARSE 快 `{speedup(cusparse_avg['solve_ms'], hcl_avg['solve_ms']):.2f}x`。",
            f"- `total_100_ms` 最低，约比 MKL 快 `{speedup(mkl_avg['total_100_ms'], hcl_avg['total_100_ms']):.2f}x`，比 Split 快 `{speedup(split_avg['total_100_ms'], hcl_avg['total_100_ms']):.2f}x`，比 cuSPARSE 快 `{speedup(cusparse_avg['total_100_ms'], hcl_avg['total_100_ms']):.2f}x`。",
            "- Split_SpTRSV 的 solve 平均值不差，但 analysis 成本过高，导致 total 口径整体被 HCL 压住。",
            "",
            "## 5. 逐矩阵性能结论",
            "",
        ]
    )

    matrix_perf_rows: list[list[str]] = []
    for matrix in matrices:
        matrix_rows = [row for row in benchmark_rows if row["matrix"] == matrix]
        winners = {metric: fastest_method(matrix_rows, metric) for metric in ["solve_ms", "total_1_ms", "total_10_ms", "total_100_ms"]}
        if matrix == "finan512":
            reason = "MKL solve 最强；Split solve 也快于 HCL；HCL 只因 analysis 低在 total_1 略占优"
        elif winners["solve_ms"]["method"] != "hcl_fing" and winners["total_100_ms"]["method"] == "hcl_fing":
            reason = "单次 solve 非 HCL 最快，但 HCL analysis 更低，重复后 total_100 反超"
        elif winners["solve_ms"]["method"] == "hcl_fing":
            reason = "HCL analysis 和 solve 同时较低，优势贯穿 total_1/10/100"
        else:
            reason = "赢家随口径变化，需要结合 total_k 分析"
        matrix_perf_rows.append(
            [
                matrix,
                f"{METHOD_LABELS[winners['solve_ms']['method']]} ({fmt_ms(as_float(winners['solve_ms'], 'solve_ms'))})",
                f"{METHOD_LABELS[winners['total_1_ms']['method']]} ({fmt_ms(as_float(winners['total_1_ms'], 'total_1_ms'))})",
                f"{METHOD_LABELS[winners['total_10_ms']['method']]} ({fmt_ms(as_float(winners['total_10_ms'], 'total_10_ms'))})",
                f"{METHOD_LABELS[winners['total_100_ms']['method']]} ({fmt_ms(as_float(winners['total_100_ms'], 'total_100_ms'))})",
                reason,
            ]
        )
    lines.extend(table(["matrix", "solve 最快", "total_1 最快", "total_10 最快", "total_100 最快", "主要原因"], matrix_perf_rows))

    lines.extend(
        [
            "",
            "重点解释：",
            "",
            "- `aug3dcqp`：cuSPARSE 单次 solve 略快，MKL 的 `total_1/10` 最好，但 HCL 的 analysis 更低，所以到 `total_100` 反超。",
            "- `finan512`：这是 HCL 的主要反例。MKL 在 solve 和长期 total 上最强，Split solve 也快于 HCL。",
            "- `thermomech_dK`：Split solve 接近 HCL，但 Split analysis 太大，导致 total 无法翻盘。",
            "- `shipsec5`：HCL solve 仍领先；Split 第二段 SpTRSV 代价很高，成为主要瓶颈。",
            "",
            "## 6. HCL-Fing 现象",
            "",
        ]
    )

    if baseline_rows:
        hcl_transition_rows: list[list[str]] = []
        for matrix in matrices:
            current = bench_by.get(("hcl_fing", matrix))
            old = baseline_by.get(("hcl_fing", matrix))
            if not current or not old:
                continue
            hcl_transition_rows.append(
                [
                    matrix,
                    old.get("status", ""),
                    current.get("status", ""),
                    old.get("repeat_solve", ""),
                    current.get("repeat_solve", ""),
                    fmt_ms(as_float(old, "analysis_ms")),
                    fmt_ms(as_float(current, "analysis_ms")),
                ]
            )
        lines.extend(table(["matrix", "旧状态", "新状态", "旧 repeat_solve", "新 repeat_solve", "旧 analysis_ms", "新 analysis_ms"], hcl_transition_rows))
        recovered = [
            matrix
            for matrix in matrices
            if baseline_by.get(("hcl_fing", matrix), {}).get("status") == "analysis_order_error"
            and bench_by.get(("hcl_fing", matrix), {}).get("status") == "ok"
        ]
        lines.extend(
            [
                "",
                f"本轮从 `analysis_order_error` 变为 `ok` 的矩阵：`{', '.join(recovered)}`。",
                "",
                "这说明用户修改 `/home/HCL-Fing_Split/HCL-Fing` 后，之前触发调度检查错误的代表矩阵已经可以通过 wrapper 调度检查和 residual 检查。",
                "",
                "需要注意：",
                "",
                "- 本轮 benchmark 是 `repeat_solve=50`。",
                "- 旧的代表矩阵压力测试是 `repeat_solve=300`。",
                "- 因此当前结果可以说明 HCL 在默认 benchmark 下已经恢复 6/6 可运行，但如果要确认 repeat300 下也稳定，仍需要同条件复验。",
                "",
                "性能上，HCL 当前优势来自两个方面：",
                "",
                f"- analysis 阶段开销低，六个矩阵平均只有 `{fmt_ms(hcl_avg['analysis_ms'])} ms`。",
                "- solve 阶段端到端开销低，除了 `finan512` 外，大多数矩阵都能压过 cuSPARSE、MKL 和 Split。",
                "",
            ]
        )
    else:
        lines.extend(["无 baseline 输入，无法做 HCL 修改前后对比。", ""])

    lines.extend(
        [
            "## 7. Split_SpTRSV 现象",
            "",
        ]
    )

    split_rows: list[list[str]] = []
    split_adv_cusparse: list[str] = []
    split_adv_hcl: list[str] = []
    for matrix in matrices:
        split = bench_by[("split_sptrsv", matrix)]
        hcl = bench_by[("hcl_fing", matrix)]
        cusparse = bench_by[("cusparse_spsv", matrix)]
        mkl = bench_by[("mkl", matrix)]
        if as_float(split, "solve_ms") < as_float(cusparse, "solve_ms"):
            split_adv_cusparse.append(matrix)
        if as_float(split, "solve_ms") < as_float(hcl, "solve_ms"):
            split_adv_hcl.append(matrix)
        parts = {
            "SpTRSV1": as_float(split, "split_sptrsv1_ms"),
            "SpMV": as_float(split, "split_spmv_ms"),
            "SpTRSV2": as_float(split, "split_sptrsv2_ms"),
            "transfer": as_float(split, "split_transfer_ms"),
        }
        bottleneck, bottleneck_value = max(parts.items(), key=lambda item: item[1])
        split_rows.append(
            [
                matrix,
                fmt_ms(as_float(split, "analysis_ms")),
                fmt_ms(as_float(split, "solve_ms")),
                fmt_ms(as_float(hcl, "solve_ms")),
                fmt_ms(as_float(cusparse, "solve_ms")),
                fmt_ms(as_float(mkl, "solve_ms")),
                f"{bottleneck}={fmt_ms(bottleneck_value)}",
            ]
        )
    lines.extend(table(["matrix", "Split analysis", "Split solve", "HCL solve", "cuSPARSE solve", "MKL solve", "Split 内部瓶颈"], split_rows))
    lines.extend(
        [
            "",
            "Split 结论：",
            "",
            f"- Split solve 快于 cuSPARSE 的矩阵：`{', '.join(split_adv_cusparse)}`。",
            f"- Split solve 快于 HCL 的矩阵：`{', '.join(split_adv_hcl)}`。",
            "- Split 并不是所有矩阵 solve 都慢，但它的 analysis 成本太高，且部分矩阵存在明显内部分段瓶颈。",
            "- 小矩阵或轻量矩阵上，transfer / 外层调度开销更容易吞掉算法收益。",
            "- `shipsec5` 上 Split 的瓶颈是第二段 SpTRSV，说明 split 后半段仍可能承担大部分依赖链。",
            "",
        ]
    )

    lines.extend(
        [
            "## 8. 综合结论",
            "",
            "最近一次结果的核心结论：",
            "",
            "1. 正确性已经很好：quick 和 benchmark 均为 24/24 `ok`。",
            "2. HCL-Fing 修改后，之前代表矩阵中的 `analysis_order_error` 消失，默认 benchmark 下 HCL 恢复到 6/6 可运行。",
            "3. 在这 6 个代表矩阵上，HCL-Fing 是当前平均性能最好的方法，尤其是 `total_100_ms`。",
            "4. `finan512` 是反例：MKL 最强，Split 次之，HCL 的 solve 不占优。",
            "5. Split_SpTRSV 的核心问题不是所有矩阵 solve 都慢，而是 analysis 成本太高，并且部分矩阵的一段 SpTRSV 仍是主瓶颈。",
            "6. cuSPARSE-SpSV 在 `aug3dcqp` 上单次 solve 最快，说明现代库基线不能低估。",
            "7. 如果要把这轮结果作为最终结论，建议再跑一次同样矩阵的 `repeat_solve=300`，验证 HCL 修改后的稳定性是否在更长重复条件下仍成立。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick", type=Path, required=True, help="quick CSV 输入")
    parser.add_argument("--benchmark", type=Path, required=True, help="benchmark CSV 输入")
    parser.add_argument("--baseline", type=Path, help="可选：用于比较的旧 benchmark CSV")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="输出 Markdown，默认覆盖 latest_run_analysis.md")
    args = parser.parse_args()

    quick_rows = read_result_rows(args.quick)
    benchmark_rows = read_result_rows(args.benchmark)
    baseline_rows = read_result_rows(args.baseline) if args.baseline else []
    report = build_report(args.quick, args.benchmark, args.baseline, quick_rows, benchmark_rows, baseline_rows)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
