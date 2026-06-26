# Data Layout

All methods use the same preprocessed lower triangular CSR input from
`data/csrbin/`.

## Preprocessing Rules

```text
lower triangular
0-based
double
CSR sorted by column within each row
missing diagonal entries filled with 1.0
x_true = ones
b = A * x_true
```

## Subdirectories

```text
raw_mtx/    Original SuiteSparse Matrix Market files.
csrbin/     Preprocessed lower CSR binary files.
rhs/        RHS vectors generated from x_true = ones.
meta/       JSON metadata for each preprocessed matrix.
sanity/     Tiny Matrix Market inputs for correctness checks.
```

## CSR Binary Format

Files in `data/csrbin/` use little-endian binary layout:

```text
header:
  magic        8 bytes   "CSRLOW1\0"
  version      uint32    1
  flags        uint32    bit mask
  n            uint64    square matrix dimension
  nnz          uint64    number of stored lower-triangular nonzeros
  diag_filled  uint64    number of missing diagonal entries filled with 1.0

payload:
  row_ptr      uint64[n + 1]
  col_idx      uint32[nnz]
  values       float64[nnz]
```

Flag bits:

```text
0x01  lower triangular
0x02  row-wise sorted column indices
0x04  double values
0x08  0-based indices
```
