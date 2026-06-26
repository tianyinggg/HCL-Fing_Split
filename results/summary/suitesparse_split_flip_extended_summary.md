# SuiteSparse Split 翻盘扩展测试

测试矩阵：`Mulvey/finan512`、`Ronis/xenon1`、`Ronis/xenon2`、`Botonakis/thermomech_dK`、`DNVS/shipsec5`。

## quick 正确性

| matrix | cusparse | mkl | hcl_fing | split_sptrsv |
|---|---|---|---|---|
| finan512 | ok | ok | ok | ok |
| xenon1 | ok | ok | ok | ok |
| xenon2 | ok | ok | ok | ok |
| thermomech_dK | ok | ok | ok | ok |
| shipsec5 | ok | ok | ok | ok |

五个矩阵四方法 quick 全部 `ok`，因此全部进入 benchmark。

## benchmark 结果

| matrix | method | analysis_ms | solve_ms | total_100_ms | residual_pass |
|---|---|---:|---:|---:|---|
| finan512 | cusparse_spsv | 2.90434 | 1.2108 | 123.984 | true |
| finan512 | mkl | 1.27056 | 0.150581 | 16.3287 | true |
| finan512 | hcl_fing | 1.01214 | 0.314368 | 32.4489 | true |
| finan512 | split_sptrsv | 7.04095 | 0.196333 | 26.6742 | true |
| xenon1 | cusparse_spsv | 3.66694 | 0.537536 | 57.4205 | true |
| xenon1 | mkl | 0.755859 | 0.201938 | 20.9497 | true |
| xenon1 | hcl_fing | 1.2707 | 0.283712 | 29.6419 | true |
| xenon1 | split_sptrsv | 9.90363 | 0.338222 | 43.7258 | true |
| xenon2 | cusparse_spsv | 4.34894 | 0.84776 | 89.1249 | true |
| xenon2 | mkl | 4.77802 | 0.961372 | 100.915 | true |
| xenon2 | hcl_fing | 2.85837 | 0.364544 | 39.3128 | true |
| xenon2 | split_sptrsv | 20.7588 | 1.01867 | 122.626 | true |
| thermomech_dK | cusparse_spsv | 5.09939 | 1.44739 | 149.839 | true |
| thermomech_dK | mkl | 3.39576 | 1.08451 | 111.847 | true |
| thermomech_dK | hcl_fing | 2.00346 | 0.44288 | 46.2915 | true |
| thermomech_dK | split_sptrsv | 44.6736 | 0.440638 | 88.7374 | true |
| shipsec5 | cusparse_spsv | 42.6951 | 3.75408 | 418.103 | true |
| shipsec5 | mkl | 20.2369 | 3.10992 | 331.229 | true |
| shipsec5 | hcl_fing | 6.74776 | 2.05627 | 212.375 | true |
| shipsec5 | split_sptrsv | 58.5429 | 3.0713 | 365.673 | true |

## Split 是否翻盘

| matrix | solve 最快 | total_100 最快 | Split solve 排名 | Split total_100 排名 | Split/HCL solve | Split/HCL total100 |
|---|---|---|---:|---:|---:|---:|
| finan512 | mkl | mkl | 2 | 2 | 1.601x | 1.216x |
| xenon1 | mkl | mkl | 3 | 3 | 0.839x | 0.678x |
| xenon2 | hcl_fing | hcl_fing | 4 | 4 | 0.358x | 0.321x |
| thermomech_dK | split_sptrsv | hcl_fing | 1 | 2 | 1.005x | 0.522x |
| shipsec5 | hcl_fing | hcl_fing | 2 | 3 | 0.670x | 0.581x |

说明：`Split/HCL > 1` 表示 Split 比 HCL 快，`< 1` 表示 Split 比 HCL 慢。

## 平均值

| method | avg analysis_ms | avg solve_ms | avg total_100_ms |
|---|---:|---:|---:|
| cusparse_spsv | 11.7429 | 1.55951 | 167.694 |
| mkl | 6.08743 | 1.10166 | 116.254 |
| hcl_fing | 2.77849 | 0.692355 | 72.014 |
| split_sptrsv | 28.184 | 1.01303 | 129.487 |

## Split 几何平均加速比

| 对比 | solve_ms | total_100_ms |
|---|---:|---:|
| Split vs cusparse_spsv | 2.009x | 1.537x |
| Split vs mkl | 1.015x | 0.773x |
| Split vs hcl_fing | 0.798x | 0.604x |

结论：Split 有局部翻盘，但没有整体翻盘。`finan512` 上 Split 的 `solve_ms` 和 `total_100_ms` 都快于 HCL；`thermomech_dK` 上 Split 的 `solve_ms` 极小幅快于 HCL，但由于 analysis 很重，`total_100_ms` 仍慢于 HCL。`xenon1`、`xenon2`、`shipsec5` 上 Split 均慢于 HCL。

## 结构诊断

| matrix | n | nnz | levels | avg_parallelism | avg_row_nnz | min_abs_diag |
|---|---:|---:|---:|---:|---:|---:|
| finan512 | 74752 | 335872 | 516 | 145 | 4.49 | 1.0712893568 |
| xenon1 | 48600 | 614860 | 255 | 191 | 12.7 | 7.9140552748e+26 |
| xenon2 | 157464 | 2012076 | 331 | 476 | 12.8 | 7.9140552748e+26 |
| thermomech_dK | 204316 | 1525272 | 644 | 317 | 7.47 | 36255037682.4 |
| shipsec5 | 179860 | 5146478 | 2688 | 66.9 | 28.6 | 0.000548722939432 |
