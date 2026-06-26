#!/usr/bin/env python3
"""Canonical CSV schema helpers for benchmark results."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Mapping


CSV_FIELDS = [
    "mode",
    "method",
    "matrix",
    "n",
    "nnz",
    "diag_filled",
    "warmup",
    "repeat_solve",
    "repeat_analysis",
    "statistic",
    "analysis_ms",
    "solve_ms",
    "total_1_ms",
    "total_10_ms",
    "total_100_ms",
    "split_internal_sum_ms",
    "split_sptrsv1_ms",
    "split_spmv_ms",
    "split_sptrsv2_ms",
    "split_transfer_ms",
    "residual",
    "residual_pass",
    "status",
    "error",
    "timeout",
]


CSV_FIELD_DESCRIPTIONS = {
    "mode": "运行模式",
    "method": "方法名",
    "matrix": "矩阵名",
    "n": "矩阵维度",
    "nnz": "lower CSR非零元数",
    "diag_filled": "补对角数量",
    "warmup": "预热次数",
    "repeat_solve": "求解计时重复次数",
    "repeat_analysis": "分析/准备计时重复次数",
    "statistic": "统计方式",
    "analysis_ms": "分析准备中位时间ms",
    "solve_ms": "单次完整求解端到端中位时间ms",
    "total_1_ms": "一次求解总时间ms",
    "total_10_ms": "十次求解总时间ms",
    "total_100_ms": "百次求解总时间ms",
    "split_internal_sum_ms": "Split内部计时求和ms",
    "split_sptrsv1_ms": "Split第一段三角求解ms",
    "split_spmv_ms": "Split中间SpMV时间ms",
    "split_sptrsv2_ms": "Split第二段三角求解ms",
    "split_transfer_ms": "Split内部传输求和ms",
    "residual": "相对残差 ||Ax-b||/||b||",
    "residual_pass": "残差是否通过阈值检查",
    "status": "运行状态或错误类型",
    "error": "失败原因或诊断信息",
    "timeout": "是否超时",
}


CSV_FILE_COMMENTS = [
    "# 文件说明: 四方法统一实验结果；包含运行模式、方法名、矩阵名、计时、残差和状态",
    "# CSV格式: 注释行以#开头；随后第一行是字段名；第二行是中文字段说明；第三行开始是数据",
    "# 主口径: analysis_ms为分析/准备时间；solve_ms为单次完整solve端到端时间；total_k_ms=analysis_ms+k*solve_ms",
]


def empty_result_row(method: str, matrix: str) -> dict[str, str]:
    row = {field: "" for field in CSV_FIELDS}
    row["mode"] = "unknown"
    row["method"] = method
    row["matrix"] = matrix
    row["status"] = "unknown"
    row["timeout"] = "false"
    return row


def append_result(path: Path, row: Mapping[str, object]) -> None:
    unknown = sorted(set(row) - set(CSV_FIELDS))
    if unknown:
        raise ValueError(f"unknown CSV fields: {unknown}")
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists() and path.stat().st_size > 0
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="raise")
        if not exists:
            for comment in CSV_FILE_COMMENTS:
                handle.write(comment + "\n")
            writer.writeheader()
            writer.writerow({field: CSV_FIELD_DESCRIPTIONS[field] for field in CSV_FIELDS})
        writer.writerow({field: row.get(field, "") for field in CSV_FIELDS})
