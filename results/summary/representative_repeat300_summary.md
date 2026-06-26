# 代表矩阵 repeat_solve=300 benchmark 总结

输入文件：`results/csv/representative_repeat300_benchmark.csv`。

本轮选择 6 个已有矩阵：

| matrix | 代表性 |
|---|---|
| `aug3dcqp` | 小规模、依赖层极浅，cuSPARSE/HCL/MKL 固定开销对比明显 |
| `ACTIVSg70K` | 层数少、并行度高，HCL-Fing 优势代表 |
| `ss1` | 层数中等偏多，final_large 中 HCL 曾通过且表现好 |
| `finan512` | Split_SpTRSV 曾局部翻盘的代表矩阵 |
| `thermomech_dK` | Split solve 与 HCL 接近，但 analysis 很重的代表矩阵 |
| `shipsec5` | 大规模、较稠密、层数很深，Split 未翻盘代表 |

计时规则：

```text
mode = benchmark
warmup = 5
repeat_solve = 300
repeat_analysis = 10
statistic = median
```

注意：CSV schema 仍然固定输出 `total_1_ms`、`total_10_ms`、`total_100_ms`。本轮的“三百次”指用 300 次 solve 测量取 `solve_ms` 中位数；下表中的 `total_300_est_ms` 是按 `analysis_ms + 300 * solve_ms` 额外估算，未写入主 CSV schema。

## 状态统计

| method | ok | analysis_order_error |
|---|---:|---:|
| cuSPARSE-SpSV | 6 | 0 |
| MKL | 6 | 0 |
| HCL-Fing | 2 | 4 |
| Split_SpTRSV | 6 | 0 |

HCL-Fing 在 `ss1`、`finan512`、`thermomech_dK`、`shipsec5` 上触发 `analysis_order_error`。这说明 repeat300 代表矩阵测试再次暴露出 HCL analysis 的调度稳定性问题；本轮不把这些 HCL 行纳入性能排名。

## 逐矩阵结果

| matrix | method | status | analysis_ms | solve_ms | total_100_ms | total_300_est_ms |
|---|---|---|---:|---:|---:|---:|
| aug3dcqp | cuSPARSE-SpSV | ok | 1.6384 | 0.0335 | 4.9888 | 11.6896 |
| aug3dcqp | MKL | ok | 0.2899 | 0.0468 | 4.9700 | 14.3303 |
| aug3dcqp | HCL-Fing | ok | 0.5253 | 0.0340 | 3.9301 | 10.7397 |
| aug3dcqp | Split_SpTRSV | ok | 2.2612 | 0.0988 | 12.1411 | 31.9009 |
| ACTIVSg70K | cuSPARSE-SpSV | ok | 1.7531 | 0.0635 | 8.1019 | 20.7995 |
| ACTIVSg70K | MKL | ok | 1.3378 | 0.3041 | 31.7488 | 92.5710 |
| ACTIVSg70K | HCL-Fing | ok | 0.6723 | 0.0532 | 5.9971 | 16.6467 |
| ACTIVSg70K | Split_SpTRSV | ok | 5.1765 | 0.1510 | 20.2811 | 50.4903 |
| ss1 | cuSPARSE-SpSV | ok | 2.2650 | 0.2876 | 31.0234 | 88.5402 |
| ss1 | MKL | ok | 2.4142 | 0.3374 | 36.1567 | 103.6418 |
| ss1 | HCL-Fing | analysis_order_error | 1.5873 |  |  |  |
| ss1 | Split_SpTRSV | ok | 6.6536 | 0.3260 | 39.2542 | 104.4554 |
| finan512 | cuSPARSE-SpSV | ok | 2.9087 | 1.2042 | 123.3311 | 364.1759 |
| finan512 | MKL | ok | 1.2634 | 0.1477 | 16.0343 | 45.5759 |
| finan512 | HCL-Fing | analysis_order_error | 1.0813 |  |  |  |
| finan512 | Split_SpTRSV | ok | 6.7119 | 0.1997 | 26.6776 | 66.6090 |
| thermomech_dK | cuSPARSE-SpSV | ok | 5.1040 | 1.4140 | 146.5072 | 429.3136 |
| thermomech_dK | MKL | ok | 3.2150 | 1.0738 | 110.5901 | 325.3403 |
| thermomech_dK | HCL-Fing | analysis_order_error | 2.9650 |  |  |  |
| thermomech_dK | Split_SpTRSV | ok | 41.9397 | 0.4416 | 86.0963 | 174.4095 |
| shipsec5 | cuSPARSE-SpSV | ok | 43.1804 | 3.7970 | 422.8796 | 1182.2780 |
| shipsec5 | MKL | ok | 20.2068 | 3.0550 | 325.7076 | 936.7093 |
| shipsec5 | HCL-Fing | analysis_order_error | 6.9289 |  |  |  |
| shipsec5 | Split_SpTRSV | ok | 61.2648 | 3.1526 | 376.5225 | 1007.0380 |

## 性能观察

- `aug3dcqp`：HCL-Fing 的 `total_100_ms` 最快，cuSPARSE 的单次 `solve_ms` 略快。矩阵小且层极浅，固定开销占比较高。
- `ACTIVSg70K`：HCL-Fing 明显最快，符合低层数、高并行度矩阵特征。
- `ss1`：HCL-Fing 本轮触发调度错误；在可比较的三法中，cuSPARSE 的 `solve_ms` 和 `total_100_ms` 最好，Split 接近但略慢。
- `finan512`：HCL-Fing 本轮触发调度错误；在可比较的三法中，MKL 最快，Split 仍明显快于 cuSPARSE，但不如 MKL。
- `thermomech_dK`：HCL-Fing 本轮触发调度错误；Split 的 `solve_ms` 和 `total_100_ms` 均快于 cuSPARSE/MKL，即这轮可比较三法中 Split 胜出。
- `shipsec5`：HCL-Fing 本轮触发调度错误；MKL 最快，Split 快于 cuSPARSE 但慢于 MKL。

## 当前解释

repeat300 使 `solve_ms` 中位数更稳定，也更容易暴露 HCL-Fing analysis 的非稳定调度问题。和之前结果相比，本轮最重要的新信息不是某个方法的平均速度，而是：

```text
HCL-Fing 在部分曾经可运行的代表矩阵上仍可能生成 analysis_order_error。
```

对 Split_SpTRSV 来说，本轮结论更细：

- 在 `thermomech_dK` 上，Split 对非 HCL 三法有明确优势。
- 在 `finan512` 上，Split 仍强于 cuSPARSE，但 MKL 更快。
- 在 `shipsec5` 上，Split 相比 cuSPARSE 有收益，但大而稠密的结构让 MKL 仍占优。
- 在浅层或高并行矩阵 `aug3dcqp`、`ACTIVSg70K` 上，Split 的多阶段开销仍然不划算。

因此，Split 的优势更可能出现在“原始三角求解依赖较重、但拆分后额外 SpMV/传输没有压垮收益”的矩阵上；它不适合层数极浅、并行度已经很高的矩阵。
