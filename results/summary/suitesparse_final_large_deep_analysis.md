# SuiteSparse final_large 深度分析

输入文件：`results/csv/suitesparse_final_large_benchmark_clean.csv`、`results/csv/suitesparse_final_large_quick.csv`、`results/csv/hcl_schedule_diagnostics_suitesparse_final_large.csv`。

## 1. 鲁棒性统计

quick 筛选共覆盖 24 个候选矩阵，每个矩阵运行 4 个方法；最终 clean benchmark 使用其中 8 个四方法稳定通过的矩阵。

| scope | method | matrices | ok | ok_rate | analysis_order_error | residual_error | timeout |
|---|---|---:|---:|---:|---:|---:|---:|
| quick_candidates | cusparse_spsv | 24 | 19 | 79.2% | 0 | 5 | 0 |
| quick_candidates | mkl | 24 | 19 | 79.2% | 0 | 5 | 0 |
| quick_candidates | hcl_fing | 24 | 9 | 37.5% | 14 | 1 | 0 |
| quick_candidates | split_sptrsv | 24 | 19 | 79.2% | 0 | 5 | 0 |
| final_clean_benchmark | cusparse_spsv | 8 | 8 | 100.0% | 0 | 0 | 0 |
| final_clean_benchmark | mkl | 8 | 8 | 100.0% | 0 | 0 | 0 |
| final_clean_benchmark | hcl_fing | 8 | 8 | 100.0% | 0 | 0 | 0 |
| final_clean_benchmark | split_sptrsv | 8 | 8 | 100.0% | 0 | 0 | 0 |

benchmark 前的过渡文件里 `bauru5727` 的 HCL-Fing 从 quick 的 `ok` 变成 benchmark 的 `analysis_order_error`，因此 clean 文件将它剔除。最终 clean benchmark 是 32/32 全部 `ok`，无 timeout，残差全部通过。

稳健统计上，HCL-Fing 的 `solve_ms` 几何平均相对 cuSPARSE 为 1.207x，相对 Split_SpTRSV 为 2.112x；`total_100_ms` 几何平均相对 cuSPARSE 为 1.325x，相对 Split_SpTRSV 为 2.414x。

| method | solve_mean_ms | solve_median_ms | solve_geomean_ms | solve_iqr_ms | total100_mean_ms | total100_median_ms |
|---|---:|---:|---:|---:|---:|---:|
| cusparse_spsv | 0.1220 | 0.1115 | 0.1034 | 0.0505 | 14.6882 | 12.7996 |
| mkl | 0.2061 | 0.2239 | 0.1660 | 0.1884 | 22.0690 | 24.5494 |
| hcl_fing | 0.0998 | 0.0893 | 0.0857 | 0.0312 | 11.1595 | 10.3191 |
| split_sptrsv | 0.2025 | 0.1801 | 0.1809 | 0.1814 | 26.6598 | 23.8370 |

solve 最快次数：hcl_fing=6, mkl=1, cusparse_spsv=1。total_100 最快次数：hcl_fing=7, mkl=1。

## 2. diag_filled 子集分析

分组规则：`none` 表示不补对角；`low_0_to_1pct` 表示补对角比例不超过 1%；`high_gt_1pct` 表示补对角比例超过 1%。

| diag_class | matrices | hcl_solve_ms | cusparse_solve_ms | split_solve_ms | hcl_vs_cusparse_solve | hcl_vs_split_solve | hcl_vs_cusparse_total100 |
|---|---:|---:|---:|---:|---:|---:|---:|
| none | 2 | 0.1524 | 0.1751 | 0.2363 | 1.168x | 1.913x | 1.247x |
| low_0_to_1pct | 1 | 0.0748 | 0.0921 | 0.2076 | 1.232x | 2.777x | 1.354x |
| high_gt_1pct | 5 | 0.0837 | 0.1066 | 0.1880 | 1.219x | 2.080x | 1.352x |

观察：补对角多的组并没有让 HCL-Fing 失效；相反，高补对角组通常层数少、平均并行度高，HCL 的调度和求解开销更容易摊开。需要注意，这不说明“补对角越多算法越好”，只说明在本批统一预处理矩阵里，高补对角伴随了更浅的依赖结构。

## 3. 按矩阵结构解释性能差异

| matrix | diag_class | levels | avg_parallelism | avg_row_nnz | fastest_solve | hcl_vs_cusparse_solve | hcl_vs_split_solve |
|---|---|---:|---:|---:|---|---:|---:|
| ACTIVSg70K | none | 17 | 4117.6 | 2.204 | hcl_fing | 1.197x | 2.880x |
| hcircuit | low_0_to_1pct | 23 | 4594.6 | 2.928 | hcl_fing | 1.232x | 2.777x |
| a5esindl | high_gt_1pct | 3 | 20002.7 | 2.833 | mkl | 1.554x | 1.088x |
| aug3dcqp | high_gt_1pct | 2 | 17771.5 | 2.415 | cusparse_spsv | 0.942x | 2.707x |
| a2nnsnsl | high_gt_1pct | 3 | 26672.0 | 2.888 | hcl_fing | 1.552x | 1.461x |
| m133-b3 | high_gt_1pct | 8 | 25025.0 | 2.928 | hcl_fing | 1.039x | 2.885x |
| shar_te2-b3 | high_gt_1pct | 8 | 25025.0 | 2.943 | hcl_fing | 1.140x | 3.137x |
| ss1 | none | 147 | 1396.5 | 2.562 | hcl_fing | 1.139x | 1.270x |

结构解释：

- `ACTIVSg70K`、`hcircuit`、`a2nnsnsl`、`m133-b3`、`shar_te2-b3`、`ss1` 上 HCL-Fing 的 solve 最快；这些矩阵要么层数较少、并行度高，要么规模较大但行非零较低，HCL 的分组调度开销能换来较低单次求解时间。
- `a5esindl` 上 MKL solve 略快，说明这个矩阵虽然高补对角、层数少，但 CPU 单次调用开销和缓存行为在该规模上更有利；HCL 仍接近 MKL，并优于 cuSPARSE 与 Split。
- `aug3dcqp` 上 cuSPARSE solve 略快，HCL 与 cuSPARSE 非常接近；该矩阵最小，`n=35543`、`nnz=85829`、层数只有 2，GPU 侧方法的固定开销占比更高。
- Split_SpTRSV 的 solve 在 8 个矩阵上都慢于 HCL，主要因为 solve 口径包含 SpTRSV1、SpMV、SpTRSV2 和必要传输；其 analysis 也明显更重，`analysis_ms` 平均约 6.41 ms，高于 HCL 的 1.18 ms。
- MKL 在 analysis 上不差，但在大多数矩阵的 solve 上慢于 HCL。对本批 GPU 可并行结构，HCL 的端到端 `total_100_ms` 优势比单次 solve 更稳定。

Spearman 相关性只基于 8 个矩阵，不能当作强统计结论，但能辅助解释：

| target | diag_ratio | num_levels | avg_parallelism | avg_row_nnz | nnz |
|---|---:|---:|---:|---:|---:|
| hcl_fing_solve | 0.3353 | 0.4097 | 0.1796 | 0.5238 | 0.8333 |
| cusparse_spsv_solve | 0.1198 | 0.2169 | 0.1796 | 0.2619 | 0.4762 |
| split_sptrsv_solve | -0.02395 | 0.7591 | -0.2275 | 0.4048 | 0.8095 |
| hcl_vs_cusparse_solve_speedup | -0.04791 | -0.01205 | 0.1916 | 0.07143 | -0.119 |
| hcl_vs_split_solve_speedup | 0.3832 | 0.1566 | 0.2275 | 0.4762 | 0.4524 |

结论：本批 final_large clean 集合里，HCL-Fing 的优势主要来自较低 analysis 开销和较低端到端 solve 开销；优势在 `total_10_ms`、`total_100_ms` 上更稳。Split_SpTRSV 受多阶段 solve 和 analysis 开销影响明显。cuSPARSE 在很小、极浅依赖的矩阵上会接近或超过 HCL，但总体不占优。
