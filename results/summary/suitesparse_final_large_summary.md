# SuiteSparse final_large benchmark summary

Benchmark rule: mode=benchmark, warmup=5, repeat_solve=50, repeat_analysis=10, statistic=median.

## Matrix set

| matrix | n | lower_nnz | diag_filled |
|---|---:|---:|---:|
| ACTIVSg70K | 69999 | 154313 | 0 |
| hcircuit | 105676 | 309410 | 48 |
| a5esindl | 60008 | 170008 | 25004 |
| aug3dcqp | 35543 | 85829 | 8000 |
| a2nnsnsl | 80016 | 231123 | 35008 |
| m133-b3 | 200200 | 586229 | 200200 |
| shar_te2-b3 | 200200 | 589261 | 200199 |
| ss1 | 205282 | 525873 | 0 |

## Method averages, ms

| method | avg analysis_ms | avg solve_ms | avg total_1_ms | avg total_10_ms | avg total_100_ms |
|---|---:|---:|---:|---:|---:|
| cusparse_spsv | 2.49277 | 0.121954 | 2.61472 | 3.71231 | 14.6882 |
| mkl | 1.46279 | 0.206062 | 1.66885 | 3.5234 | 22.069 |
| hcl_fing | 1.18252 | 0.09977 | 1.28229 | 2.18022 | 11.1595 |
| split_sptrsv | 6.40936 | 0.202505 | 6.61187 | 8.43441 | 26.6598 |

## Geometric mean speedups

| metric | hcl_fing vs cusparse | split_sptrsv vs cusparse | hcl_fing vs split_sptrsv | mkl vs cusparse |
|---|---:|---:|---:|---:|
| analysis_ms | 2.04444 | 0.437098 | 4.67731 | 2.26939 |
| solve_ms | 1.2075 | 0.571775 | 2.11184 | 0.623088 |
| total_1_ms | 1.992 | 0.44407 | 4.48579 | 2.02488 |
| total_10_ms | 1.71698 | 0.483408 | 3.55181 | 1.25461 |
| total_100_ms | 1.32542 | 0.549144 | 2.41362 | 0.727644 |
