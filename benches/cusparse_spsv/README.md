# cuSPARSE-SpSV Baseline

Build:

```bash
make -C /home/HCL-Fing_Split/benches/cusparse_spsv
```

Example:

```bash
/home/HCL-Fing_Split/benches/cusparse_spsv/cusparse_spsv_baseline \
  --matrix tiny_lower_missing_diag
```

The baseline reads the shared `data/csrbin/<matrix>.csrbin` and
`data/rhs/<matrix>.rhs.txt` files, measures `cusparseSpSV_analysis` and
host-resident RHS solve time, computes residual outside the timed region, and
appends a row compatible with `scripts/result_schema.py`.
