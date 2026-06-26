#!/usr/bin/env python3
"""Shared lower-CSR binary format utilities for SpTRSV experiments."""

from __future__ import annotations

from array import array
from dataclasses import dataclass
import json
from pathlib import Path
import struct
import sys
from typing import Dict, Iterable, List, Tuple


MAGIC = b"CSRLOW1\0"
VERSION = 1
FLAG_LOWER = 0x01
FLAG_SORTED = 0x02
FLAG_DOUBLE = 0x04
FLAG_ZERO_BASED = 0x08
DEFAULT_FLAGS = FLAG_LOWER | FLAG_SORTED | FLAG_DOUBLE | FLAG_ZERO_BASED
HEADER = struct.Struct("<8sIIQQQ")


@dataclass(frozen=True)
class CsrMatrix:
    name: str
    n: int
    row_ptr: List[int]
    col_idx: List[int]
    values: List[float]
    diag_filled: int

    @property
    def nnz(self) -> int:
        return len(self.col_idx)


def _to_little_endian_array(typecode: str, values: Iterable[int | float]) -> array:
    out = array(typecode, values)
    if sys.byteorder != "little":
        out.byteswap()
    return out


def write_csrbin(path: Path, matrix: CsrMatrix) -> None:
    validate_csr(matrix)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        handle.write(
            HEADER.pack(
                MAGIC,
                VERSION,
                DEFAULT_FLAGS,
                matrix.n,
                matrix.nnz,
                matrix.diag_filled,
            )
        )
        _to_little_endian_array("Q", matrix.row_ptr).tofile(handle)
        _to_little_endian_array("I", matrix.col_idx).tofile(handle)
        _to_little_endian_array("d", matrix.values).tofile(handle)


def _read_array(handle, typecode: str, count: int) -> List[int | float]:
    out = array(typecode)
    out.fromfile(handle, count)
    if sys.byteorder != "little":
        out.byteswap()
    return out.tolist()


def read_csrbin(path: Path) -> CsrMatrix:
    with path.open("rb") as handle:
        header = handle.read(HEADER.size)
        if len(header) != HEADER.size:
            raise ValueError(f"{path} is too small to contain a csrbin header")
        magic, version, flags, n, nnz, diag_filled = HEADER.unpack(header)
        if magic != MAGIC:
            raise ValueError(f"{path} has invalid magic {magic!r}")
        if version != VERSION:
            raise ValueError(f"{path} has unsupported version {version}")
        if flags & DEFAULT_FLAGS != DEFAULT_FLAGS:
            raise ValueError(f"{path} is missing required csrbin flags: {flags:#x}")
        row_ptr = _read_array(handle, "Q", n + 1)
        col_idx = _read_array(handle, "I", nnz)
        values = _read_array(handle, "d", nnz)

    matrix = CsrMatrix(
        name=path.stem,
        n=int(n),
        row_ptr=[int(x) for x in row_ptr],
        col_idx=[int(x) for x in col_idx],
        values=[float(x) for x in values],
        diag_filled=int(diag_filled),
    )
    validate_csr(matrix)
    return matrix


def validate_csr(matrix: CsrMatrix) -> None:
    if matrix.n < 0:
        raise ValueError("matrix dimension must be non-negative")
    if len(matrix.row_ptr) != matrix.n + 1:
        raise ValueError("row_ptr length must be n + 1")
    if matrix.row_ptr[0] != 0:
        raise ValueError("row_ptr[0] must be 0")
    if matrix.row_ptr[-1] != matrix.nnz:
        raise ValueError("row_ptr[-1] must equal nnz")
    if len(matrix.values) != matrix.nnz:
        raise ValueError("values length must equal nnz")
    if any(matrix.row_ptr[i] > matrix.row_ptr[i + 1] for i in range(matrix.n)):
        raise ValueError("row_ptr must be nondecreasing")
    for row in range(matrix.n):
        start = matrix.row_ptr[row]
        end = matrix.row_ptr[row + 1]
        cols = matrix.col_idx[start:end]
        if cols != sorted(cols):
            raise ValueError(f"row {row} column indices are not sorted")
        for col in cols:
            if col < 0 or col >= matrix.n:
                raise ValueError(f"column {col} is out of bounds for n={matrix.n}")
            if col > row:
                raise ValueError(f"entry ({row}, {col}) is above the diagonal")


def read_matrix_market_lower(path: Path, name: str | None = None) -> CsrMatrix:
    entries, n = _read_matrix_market_entries(path)
    lower_entries = {key: value for key, value in entries.items() if key[0] >= key[1]}
    return build_lower_csr(name or path.stem, n, lower_entries)


def _read_matrix_market_entries(path: Path) -> Tuple[Dict[Tuple[int, int], float], int]:
    with path.open("r", encoding="utf-8") as handle:
        header = handle.readline().strip().split()
        if len(header) != 5 or header[0] != "%%MatrixMarket":
            raise ValueError(f"{path} is not a Matrix Market coordinate file")
        _, object_type, storage, field, symmetry = [part.lower() for part in header]
        if object_type != "matrix" or storage != "coordinate":
            raise ValueError("only Matrix Market coordinate matrices are supported")
        if field == "complex":
            raise ValueError("complex Matrix Market input is not supported")
        if symmetry not in {"general", "symmetric"}:
            raise ValueError(f"unsupported Matrix Market symmetry: {symmetry}")

        shape = None
        for line in handle:
            line = line.strip()
            if not line or line.startswith("%"):
                continue
            shape = line.split()
            break
        if shape is None or len(shape) != 3:
            raise ValueError(f"{path} is missing Matrix Market dimensions")
        nrows, ncols, _ = map(int, shape)
        if nrows != ncols:
            raise ValueError(f"{path} must be square for SpTRSV preprocessing")

        entries: Dict[Tuple[int, int], float] = {}
        for line in handle:
            line = line.strip()
            if not line or line.startswith("%"):
                continue
            parts = line.split()
            if field == "pattern":
                if len(parts) < 2:
                    raise ValueError(f"invalid pattern entry in {path}: {line}")
                raw_i, raw_j = map(int, parts[:2])
                value = 1.0
            else:
                if len(parts) < 3:
                    raise ValueError(f"invalid numeric entry in {path}: {line}")
                raw_i, raw_j = map(int, parts[:2])
                value = float(parts[2])
            row = raw_i - 1
            col = raw_j - 1
            if row < 0 or row >= nrows or col < 0 or col >= ncols:
                raise ValueError(f"entry ({raw_i}, {raw_j}) is out of bounds")
            entries[(row, col)] = entries.get((row, col), 0.0) + value
            if symmetry == "symmetric" and row != col:
                entries[(col, row)] = entries.get((col, row), 0.0) + value

    return entries, nrows


def build_lower_csr(
    name: str, n: int, entries: Dict[Tuple[int, int], float]
) -> CsrMatrix:
    rows: List[List[Tuple[int, float]]] = [[] for _ in range(n)]
    diag_filled = 0
    normalized = dict(entries)
    for row in range(n):
        if (row, row) not in normalized:
            normalized[(row, row)] = 1.0
            diag_filled += 1
    for (row, col), value in normalized.items():
        if row < 0 or row >= n or col < 0 or col >= n:
            raise ValueError(f"entry ({row}, {col}) is out of bounds for n={n}")
        if col > row:
            continue
        rows[row].append((col, float(value)))

    row_ptr = [0]
    col_idx: List[int] = []
    values: List[float] = []
    for row in rows:
        for col, value in sorted(row, key=lambda item: item[0]):
            col_idx.append(col)
            values.append(value)
        row_ptr.append(len(col_idx))

    matrix = CsrMatrix(name=name, n=n, row_ptr=row_ptr, col_idx=col_idx, values=values, diag_filled=diag_filled)
    validate_csr(matrix)
    return matrix


def rhs_from_ones(matrix: CsrMatrix) -> List[float]:
    return [
        sum(matrix.values[start:end])
        for start, end in zip(matrix.row_ptr[:-1], matrix.row_ptr[1:])
    ]


def write_rhs_text(path: Path, rhs: List[float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for value in rhs:
            handle.write(f"{value:.17g}\n")


def write_metadata(path: Path, matrix: CsrMatrix, source: Path, rhs_path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "name": matrix.name,
        "source": str(source),
        "n": matrix.n,
        "nnz": matrix.nnz,
        "diag_filled": matrix.diag_filled,
        "index_base": 0,
        "value_type": "double",
        "triangular": "lower",
        "csr_sorted": True,
        "x_true": "ones",
        "rhs": str(rhs_path),
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
