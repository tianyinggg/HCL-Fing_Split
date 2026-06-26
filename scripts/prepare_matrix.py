#!/usr/bin/env python3
"""Convert Matrix Market input to the shared lower-CSR experiment format."""

from __future__ import annotations

import argparse
from pathlib import Path

from csrbin_format import (
    read_matrix_market_lower,
    rhs_from_ones,
    write_csrbin,
    write_metadata,
    write_rhs_text,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def prepare_matrix(
    input_mtx: Path,
    name: str | None = None,
    csrbin_dir: Path = REPO_ROOT / "data" / "csrbin",
    rhs_dir: Path = REPO_ROOT / "data" / "rhs",
    meta_dir: Path = REPO_ROOT / "data" / "meta",
):
    matrix = read_matrix_market_lower(input_mtx, name=name)
    rhs = rhs_from_ones(matrix)

    csrbin_path = csrbin_dir / f"{matrix.name}.csrbin"
    rhs_path = rhs_dir / f"{matrix.name}.rhs.txt"
    meta_path = meta_dir / f"{matrix.name}.json"

    write_csrbin(csrbin_path, matrix)
    write_rhs_text(rhs_path, rhs)
    write_metadata(meta_path, matrix, input_mtx, rhs_path)

    return matrix, csrbin_path, rhs_path, meta_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_mtx", type=Path, help="Matrix Market input file")
    parser.add_argument("--name", help="output matrix name; defaults to input stem")
    parser.add_argument("--csrbin-dir", type=Path, default=REPO_ROOT / "data" / "csrbin")
    parser.add_argument("--rhs-dir", type=Path, default=REPO_ROOT / "data" / "rhs")
    parser.add_argument("--meta-dir", type=Path, default=REPO_ROOT / "data" / "meta")
    args = parser.parse_args()

    matrix, csrbin_path, rhs_path, meta_path = prepare_matrix(
        args.input_mtx,
        name=args.name,
        csrbin_dir=args.csrbin_dir,
        rhs_dir=args.rhs_dir,
        meta_dir=args.meta_dir,
    )
    print(
        f"prepared {matrix.name}: n={matrix.n} nnz={matrix.nnz} "
        f"diag_filled={matrix.diag_filled}"
    )
    print(f"csrbin={csrbin_path}")
    print(f"rhs={rhs_path}")
    print(f"meta={meta_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
