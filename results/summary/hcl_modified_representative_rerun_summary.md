# HCL-Fing 修改后六个代表矩阵重跑总结

输入文件：

- `results/csv/hcl_modified_representative_quick.csv`
- `results/csv/hcl_modified_representative_benchmark.csv`

矩阵集合来自：

- `config/matrices_representative_repeat300.txt`

矩阵：

```text
aug3dcqp
ACTIVSg70K
ss1
finan512
thermomech_dK
shipsec5
```

本轮目的：用户修改 `/home/HCL-Fing_Split/HCL-Fing` 后，重新编译四个 wrapper，并按 quick -> benchmark 顺序重跑四方法。

## quick 结果

| method | ok | error |
|---|---:|---:|
| cuSPARSE-SpSV | 6 | 0 |
| MKL | 6 | 0 |
| HCL-Fing | 6 | 0 |
| Split_SpTRSV | 6 | 0 |

结论：quick 阶段 24/24 全部 `status=ok`，HCL-Fing 没有触发 `analysis_order_error`。

## benchmark 规则

本轮 benchmark 使用 `config/experiment.yaml` 默认正式参数：

```text
mode = benchmark
warmup = 5
repeat_solve = 50
repeat_analysis = 10
statistic = median
```

注意：这不是上一轮 `repeat_solve=300` 测试；本轮是配置默认 benchmark。

## benchmark 状态

| method | ok | error |
|---|---:|---:|
| cuSPARSE-SpSV | 6 | 0 |
| MKL | 6 | 0 |
| HCL-Fing | 6 | 0 |
| Split_SpTRSV | 6 | 0 |

结论：benchmark 阶段 24/24 全部 `status=ok`，HCL-Fing 在 `ss1`、`finan512`、`thermomech_dK`、`shipsec5` 上也通过了调度检查和 residual 检查。

## benchmark 平均值

| method | avg_analysis_ms | avg_solve_ms | avg_total_100_ms |
|---|---:|---:|---:|
| cuSPARSE-SpSV | 8.84509 | 1.13989 | 122.834 |
| MKL | 4.75529 | 0.845601 | 89.3154 |
| HCL-Fing | 2.01426 | 0.528747 | 54.8889 |
| Split_SpTRSV | 24.6432 | 0.722544 | 96.8976 |

## 逐矩阵最快方法

| matrix | solve 最快 | solve_ms | total_100 最快 | total_100_ms |
|---|---|---:|---|---:|
| aug3dcqp | cuSPARSE-SpSV | 0.033136 | HCL-Fing | 3.91003 |
| ACTIVSg70K | HCL-Fing | 0.052224 | HCL-Fing | 5.79686 |
| ss1 | HCL-Fing | 0.242688 | HCL-Fing | 25.5517 |
| finan512 | MKL | 0.166804 | MKL | 18.0036 |
| thermomech_dK | HCL-Fing | 0.440640 | HCL-Fing | 46.0987 |
| shipsec5 | HCL-Fing | 2.06080 | HCL-Fing | 212.744 |

## 与 repeat300 现象的区别

上一轮 `representative_repeat300_benchmark.csv` 中 HCL-Fing 在以下矩阵触发 `analysis_order_error`：

```text
ss1
finan512
thermomech_dK
shipsec5
```

本轮用户修改 HCL-Fing 后，这四个矩阵在 quick 和 benchmark 中均变为 `status=ok`，并且 residual 通过。

这说明用户修改很可能改善了 HCL-Fing analysis/调度稳定性。但本轮 benchmark 使用 `repeat_solve=50`，与上一轮 repeat300 不是完全相同的计时压力；如果要确认稳定性彻底解决，还需要再用同样的 `repeat_solve=300` 条件重跑一次。

## 当前结论

- HCL-Fing 修改后在六个代表矩阵上恢复到 6/6 可运行。
- 在这六个矩阵的默认 benchmark 中，HCL-Fing 平均 `solve_ms` 和 `total_100_ms` 最好。
- HCL-Fing 在 4/6 个矩阵上拿到 `total_100_ms` 最快；`finan512` 仍由 MKL 最快，`aug3dcqp` 的单次 solve 由 cuSPARSE 略快。
- Split_SpTRSV 仍在 `finan512`、`thermomech_dK`、`shipsec5` 上相对 cuSPARSE 有优势，但整体仍受较重 analysis 开销影响。
