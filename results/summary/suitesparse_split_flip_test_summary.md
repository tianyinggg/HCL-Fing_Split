# SuiteSparse Split 翻盘测试

测试矩阵：`Norris/lung2`、`Mulvey/finan512`、`Ronis/xenon1`。

## quick 正确性

| matrix | cusparse | mkl | hcl_fing | split_sptrsv | 结论 |
|---|---|---|---|---|---|
| lung2 | residual_error | residual_error | residual_error | residual_error | 不进入性能比较 |
| finan512 | ok | ok | ok | ok | 可 benchmark |
| xenon1 | ok | ok | ok | ok | 可 benchmark |

`lung2` 四方法都是 `residual_error`，残差约 `3.956e149`，不是 Split 单独失败，因此不作为翻盘性能样本。

## benchmark 结果

| matrix | method | analysis_ms | solve_ms | total_100_ms | residual_pass |
|---|---|---:|---:|---:|---|
| finan512 | cusparse_spsv | 2.91325 | 1.20722 | 123.635 | true |
| finan512 | mkl | 1.30205 | 0.150506 | 16.3527 | true |
| finan512 | hcl_fing | 1.02349 | 0.314352 | 32.4587 | true |
| finan512 | split_sptrsv | 12.7495 | 0.219264 | 34.6759 | true |
| xenon1 | cusparse_spsv | 3.66962 | 0.53648 | 57.3176 | true |
| xenon1 | mkl | 4.25521 | 0.206271 | 24.8823 | true |
| xenon1 | hcl_fing | 4.52858 | 0.303504 | 34.879 | true |
| xenon1 | split_sptrsv | 9.32224 | 0.34946 | 44.2683 | true |

## Split 是否翻盘

| matrix | solve 最快 | total_100 最快 | Split solve 排名 | Split total_100 排名 |
|---|---|---|---:|---:|
| finan512 | mkl | mkl | 2 | 3 |
| xenon1 | mkl | mkl | 3 | 3 |

两矩阵平均：

| method | avg solve_ms | avg total_100_ms |
|---|---:|---:|
| cusparse_spsv | 0.871848 | 90.4762 |
| mkl | 0.178388 | 20.6175 |
| hcl_fing | 0.308928 | 33.6688 |
| split_sptrsv | 0.284362 | 39.4721 |

结论：Split 没有整体翻盘。`finan512` 上 Split 的 `solve_ms` 快于 HCL 和 cuSPARSE，但仍慢于 MKL；`xenon1` 上 Split 慢于 HCL 和 MKL。按 `total_100_ms`，Split 两个矩阵都没有最快。

## 数值诊断

| matrix | n | nnz | diag_filled | zero_diag | min_abs_diag | max_abs_row_sum |
|---|---:|---:|---:|---:|---:|---:|
| lung2 | 109460 | 273647 | 0 | 0 | 1.62593921231e-10 | 334.707076218 |
| finan512 | 74752 | 335872 | 0 | 0 | 1.0712893568 | 36.5716843642 |
| xenon1 | 48600 | 614860 | 0 | 0 | 7.9140552748e+26 | 8.5010609506e+28 |
