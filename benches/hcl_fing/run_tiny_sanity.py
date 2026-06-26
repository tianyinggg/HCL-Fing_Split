#!/usr/bin/env python3
"""Run HCL-Fing baseline only on shared tiny CSR sanity matrices."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BENCH_DIR = REPO_ROOT / "benches" / "hcl_fing"
BIN = BENCH_DIR / "hcl_fing_baseline"
DEFAULT_OUTPUT = REPO_ROOT / "results" / "csv" / "main_results.csv"
THRESHOLD = 1e-10


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def tiny_csrbins() -> list[Path]:
    return sorted((REPO_ROOT / "data" / "csrbin").glob("tiny*.csrbin"))


def validate_companion_files(matrix_name: str) -> tuple[Path, Path]:
    rhs = REPO_ROOT / "data" / "rhs" / f"{matrix_name}.rhs.txt"
    meta = REPO_ROOT / "data" / "meta" / f"{matrix_name}.json"
    if not rhs.exists():
        raise FileNotFoundError(f"missing rhs for {matrix_name}: {rhs}")
    if not meta.exists():
        raise FileNotFoundError(f"missing meta for {matrix_name}: {meta}")
    payload = json.loads(meta.read_text(encoding="utf-8"))
    if payload.get("value_type") != "double":
        raise ValueError(f"{meta} is not double")
    if payload.get("triangular") != "lower":
        raise ValueError(f"{meta} is not lower triangular")
    if payload.get("index_base") != 0:
        raise ValueError(f"{meta} is not 0-based")
    return rhs, meta


def read_latest_row(output: Path, matrix_name: str, mode: str) -> dict[str, str]:
    rows: list[dict[str, str]] = []
    with output.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(line for line in handle if not line.startswith("#"))
        for row in reader:
            if (
                row.get("mode") == mode
                and row.get("method") == "hcl_fing"
                and row.get("matrix") == matrix_name
            ):
                rows.append(row)
    if not rows:
        raise RuntimeError(f"no hcl_fing CSV row found for {matrix_name}")
    return rows[-1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--mode", choices=["quick", "benchmark"], default="quick")
    parser.add_argument("--config", type=Path, default=REPO_ROOT / "config" / "experiment.yaml")
    parser.add_argument("--warmup", type=int)
    parser.add_argument("--repeat", type=int)
    parser.add_argument("--repeat-analysis", type=int)
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="运行前删除输出 CSV",
    )
    args = parser.parse_args()

    matrices = tiny_csrbins()
    if not matrices:
        print("no tiny*.csrbin matrices found under data/csrbin", file=sys.stderr)
        return 1

    build = run(["make", "-C", str(BENCH_DIR)])
    print(build.stdout, end="")
    if build.returncode != 0:
        return build.returncode

    if args.fresh and args.output.exists():
        args.output.unlink()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    for csrbin in matrices:
        matrix_name = csrbin.stem
        try:
            rhs, _ = validate_companion_files(matrix_name)
        except Exception as exc:
            failures.append(f"{matrix_name}: {exc}")
            continue

        cmd = [
            str(BIN),
            "--mode",
            args.mode,
            "--matrix",
            matrix_name,
            "--csrbin",
            str(csrbin),
            "--rhs",
            str(rhs),
            "--output",
            str(args.output),
            "--config",
            str(args.config),
        ]
        if args.warmup is not None:
            cmd.extend(["--warmup", str(args.warmup)])
        if args.repeat is not None:
            cmd.extend(["--repeat", str(args.repeat)])
        if args.repeat_analysis is not None:
            cmd.extend(["--repeat-analysis", str(args.repeat_analysis)])
        proc = run(cmd)
        print(proc.stdout, end="")
        if proc.returncode != 0:
            failures.append(f"{matrix_name}: baseline exited {proc.returncode}")
            continue

        try:
            row = read_latest_row(args.output, matrix_name, args.mode)
            residual = float(row.get("residual") or "inf")
            status = row.get("status")
            residual_pass = row.get("residual_pass")
            if status != "ok" or residual_pass != "true" or not residual < THRESHOLD:
                failures.append(
                    f"{matrix_name}: status={status} residual_pass={residual_pass} "
                    f"residual={residual}"
                )
        except Exception as exc:
            failures.append(f"{matrix_name}: {exc}")

    if failures:
        print("HCL-Fing tiny sanity failed:", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        return 1

    print(f"HCL-Fing {args.mode} tiny sanity passed for {len(matrices)} matrix/matrices")
    print(f"results: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
