#!/usr/bin/env python3
"""Run the tiny preprocessing sanity check for the shared CSR format."""

from __future__ import annotations

import math
from pathlib import Path

from csrbin_format import read_csrbin, rhs_from_ones
from prepare_matrix import REPO_ROOT, prepare_matrix
from result_schema import append_result, empty_result_row


SANITY_NAME = "tiny_lower_missing_diag"
SANITY_MTX = REPO_ROOT / "data" / "sanity" / f"{SANITY_NAME}.mtx"
EXPECTED_ROW_PTR = [0, 1, 3, 5, 8]
EXPECTED_COL_IDX = [0, 0, 1, 1, 2, 0, 2, 3]
EXPECTED_VALUES = [2.0, 3.0, 4.0, 5.0, 1.0, 7.0, 8.0, 9.0]
EXPECTED_RHS = [2.0, 7.0, 6.0, 24.0]


def _assert_close_list(actual: list[float], expected: list[float], name: str) -> None:
    if len(actual) != len(expected):
        raise AssertionError(f"{name} length mismatch: {len(actual)} != {len(expected)}")
    for idx, (lhs, rhs) in enumerate(zip(actual, expected)):
        if not math.isclose(lhs, rhs, rel_tol=0.0, abs_tol=1e-12):
            raise AssertionError(f"{name}[{idx}] mismatch: {lhs} != {rhs}")


def main() -> int:
    matrix, csrbin_path, _, _ = prepare_matrix(SANITY_MTX, name=SANITY_NAME)
    loaded = read_csrbin(csrbin_path)
    rhs = rhs_from_ones(loaded)

    if matrix.diag_filled != 1 or loaded.diag_filled != 1:
        raise AssertionError("expected exactly one filled diagonal")
    if loaded.row_ptr != EXPECTED_ROW_PTR:
        raise AssertionError(f"row_ptr mismatch: {loaded.row_ptr}")
    if loaded.col_idx != EXPECTED_COL_IDX:
        raise AssertionError(f"col_idx mismatch: {loaded.col_idx}")
    _assert_close_list(loaded.values, EXPECTED_VALUES, "values")
    _assert_close_list(rhs, EXPECTED_RHS, "rhs")

    residual = math.sqrt(sum((lhs - rhs_value) ** 2 for lhs, rhs_value in zip(rhs, EXPECTED_RHS)))
    row = empty_result_row("sanity_preprocess", SANITY_NAME)
    row.update(
        {
            "n": loaded.n,
            "nnz": loaded.nnz,
            "diag_filled": loaded.diag_filled,
            "residual": f"{residual:.17g}",
            "residual_pass": str(residual <= 1e-12).lower(),
            "status": "ok",
            "timeout": "false",
        }
    )
    append_result(REPO_ROOT / "results" / "csv" / "main_results.csv", row)

    print(f"sanity ok: {csrbin_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
