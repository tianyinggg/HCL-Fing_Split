# 最近一次四方法代表矩阵结果分析

输入文件：

- quick：`results/csv/hcl_modified_representative_quick.csv`
- benchmark：`results/csv/hcl_modified_representative_benchmark.csv`
- 对比基准：`results/csv/representative_repeat300_benchmark.csv`

本报告只分析已有 CSV，没有重新运行实验。该文件由 `scripts/write_latest_run_analysis.py` 覆盖生成，用于保留最近一次分析结论。

## 1. 实验口径

benchmark 使用正式计时配置：

| 参数 | 值 | 含义 |
| --- | --- | --- |
| warmup | 5 | 正式计时前预热次数 |
| repeat_solve | 50 | solve 阶段重复计时次数 |
| repeat_analysis | 10 | analysis/prepare 阶段重复计时次数 |
| statistic | median | 正式结果采用的统计量 |

主口径仍为：

- `analysis_ms`：分析/准备阶段中位时间。
- `solve_ms`：analysis/prepare 完成之后，一次完整 solve 的端到端中位时间。
- `total_k_ms`：`analysis_ms + k * solve_ms`。

注意：quick 只用于正确性和格式检查，不作为正式性能结论。

## 2. 数据集结构

| matrix | n | nnz | nnz/n | diag_filled | 数据特点 |
| --- | --- | --- | --- | --- | --- |
| aug3dcqp | 35543 | 85829 | 2.415 | 8000 | 低行非零 |
| ACTIVSg70K | 69999 | 154313 | 2.205 | 0 | 低行非零 |
| ss1 | 205282 | 525873 | 2.562 | 0 | 低行非零 |
| finan512 | 74752 | 335872 | 4.493 | 0 | 中等行非零 |
| thermomech_dK | 204316 | 1525272 | 7.465 | 0 | 中等行非零 |
| shipsec5 | 179860 | 5146478 | 28.614 | 0 | 高行非零 |

数据一致性：

- 六个矩阵均来自统一预处理后的 lower CSR。
- 输入为 0-based、double、CSR sorted。
- RHS 使用 `x_true=ones` 生成。
- `aug3dcqp` 补了 8000 个缺失对角，解释结果时应单独标注。

结构含义：

- `aug3dcqp`、`ACTIVSg70K`、`ss1` 平均每行非零很少，更偏向低行计算场景。
- `finan512` 属于中等稀疏度，是本轮中 HCL 不占 solve 优势的关键反例。
- `thermomech_dK` 和 `shipsec5` 行计算量更重，尤其 `shipsec5` 的 `nnz/n=28.614`，能暴露分段求解内部瓶颈。

## 3. 正确性结果

- quick：24/24 行 `status=ok`。
- benchmark：24/24 行 `status=ok`。

| 方法 | benchmark 最大 residual | 判断 |
| --- | --- | --- |
| cuSPARSE-SpSV | 1.326e-16 | 通过 |
| MKL | 1.362e-16 | 通过 |
| HCL-Fing | 1.51e-16 | 通过 |
| Split_SpTRSV | 5.377e-14 | 通过 |

结论：四个方法都能读取同一份统一 CSR，完成求解，并通过 residual 检查。Split 的最大残差来自 `shipsec5`，约 `5e-14`，仍然通过。

## 4. 平均性能

下表是 6 个矩阵的等权平均，不按 `n` 或 `nnz` 加权。

| 方法 | avg_analysis_ms | avg_solve_ms | avg_total_1_ms | avg_total_10_ms | avg_total_100_ms |
| --- | --- | --- | --- | --- | --- |
| cuSPARSE-SpSV | 8.8451 | 1.1399 | 9.9850 | 20.2440 | 122.8342 |
| MKL | 4.7553 | 0.8456 | 5.6009 | 13.2113 | 89.3154 |
| HCL-Fing | 2.0143 | 0.5287 | 2.5430 | 7.3017 | 54.8889 |
| Split_SpTRSV | 24.6432 | 0.7225 | 25.3658 | 31.8687 | 96.8976 |

平均上 HCL-Fing 当前最好：

- `analysis_ms` 最低，是 MKL 的约 `42.4%`，是 Split 的约 `8.2%`。
- `solve_ms` 最低，约比 MKL 快 `1.60x`，比 Split 快 `1.37x`，比 cuSPARSE 快 `2.16x`。
- `total_100_ms` 最低，约比 MKL 快 `1.63x`，比 Split 快 `1.77x`，比 cuSPARSE 快 `2.24x`。
- Split_SpTRSV 的 solve 平均值不差，但 analysis 成本过高，导致 total 口径整体被 HCL 压住。

## 5. 逐矩阵性能结论

| matrix | solve 最快 | total_1 最快 | total_10 最快 | total_100 最快 | 主要原因 |
| --- | --- | --- | --- | --- | --- |
| aug3dcqp | cuSPARSE-SpSV (0.0331) | MKL (0.1961) | MKL (0.6116) | HCL-Fing (3.9100) | 单次 solve 非 HCL 最快，但 HCL analysis 更低，重复后 total_100 反超 |
| ACTIVSg70K | HCL-Fing (0.0522) | HCL-Fing (0.6267) | HCL-Fing (1.0967) | HCL-Fing (5.7969) | HCL analysis 和 solve 同时较低，优势贯穿 total_1/10/100 |
| ss1 | HCL-Fing (0.2427) | HCL-Fing (1.5256) | HCL-Fing (3.7098) | HCL-Fing (25.5517) | HCL analysis 和 solve 同时较低，优势贯穿 total_1/10/100 |
| finan512 | MKL (0.1668) | HCL-Fing (1.4015) | MKL (2.9913) | MKL (18.0036) | MKL solve 最强；Split solve 也快于 HCL；HCL 只因 analysis 低在 total_1 略占优 |
| thermomech_dK | HCL-Fing (0.4406) | HCL-Fing (2.4753) | HCL-Fing (6.4411) | HCL-Fing (46.0987) | HCL analysis 和 solve 同时较低，优势贯穿 total_1/10/100 |
| shipsec5 | HCL-Fing (2.0608) | HCL-Fing (8.7245) | HCL-Fing (27.2717) | HCL-Fing (212.7437) | HCL analysis 和 solve 同时较低，优势贯穿 total_1/10/100 |

重点解释：

- `aug3dcqp`：cuSPARSE 单次 solve 略快，MKL 的 `total_1/10` 最好，但 HCL 的 analysis 更低，所以到 `total_100` 反超。
- `finan512`：这是 HCL 的主要反例。MKL 在 solve 和长期 total 上最强，Split solve 也快于 HCL。
- `thermomech_dK`：Split solve 接近 HCL，但 Split analysis 太大，导致 total 无法翻盘。
- `shipsec5`：HCL solve 仍领先；Split 第二段 SpTRSV 代价很高，成为主要瓶颈。

## 6. HCL-Fing 现象

| matrix | 旧状态 | 新状态 | 旧 repeat_solve | 新 repeat_solve | 旧 analysis_ms | 新 analysis_ms |
| --- | --- | --- | --- | --- | --- | --- |
| aug3dcqp | ok | ok | 300 | 50 | 0.5253 | 0.4700 |
| ACTIVSg70K | ok | ok | 300 | 50 | 0.6723 | 0.5745 |
| ss1 | analysis_order_error | ok | 300 | 50 | 1.5873 | 1.2829 |
| finan512 | analysis_order_error | ok | 300 | 50 | 1.0813 | 1.0598 |
| thermomech_dK | analysis_order_error | ok | 300 | 50 | 2.9650 | 2.0347 |
| shipsec5 | analysis_order_error | ok | 300 | 50 | 6.9289 | 6.6637 |

本轮从 `analysis_order_error` 变为 `ok` 的矩阵：`ss1, finan512, thermomech_dK, shipsec5`。

这说明用户修改 `/home/HCL-Fing_Split/HCL-Fing` 后，之前触发调度检查错误的代表矩阵已经可以通过 wrapper 调度检查和 residual 检查。

需要注意：

- 本轮 benchmark 是 `repeat_solve=50`。
- 旧的代表矩阵压力测试是 `repeat_solve=300`。
- 因此当前结果可以说明 HCL 在默认 benchmark 下已经恢复 6/6 可运行，但如果要确认 repeat300 下也稳定，仍需要同条件复验。

性能上，HCL 当前优势来自两个方面：

- analysis 阶段开销低，六个矩阵平均只有 `2.0143 ms`。
- solve 阶段端到端开销低，除了 `finan512` 外，大多数矩阵都能压过 cuSPARSE、MKL 和 Split。

## 7. Split_SpTRSV 现象

| matrix | Split analysis | Split solve | HCL solve | cuSPARSE solve | MKL solve | Split 内部瓶颈 |
| --- | --- | --- | --- | --- | --- | --- |
| aug3dcqp | 2.4290 | 0.0923 | 0.0344 | 0.0331 | 0.0462 | transfer=0.0404 |
| ACTIVSg70K | 5.2027 | 0.1460 | 0.0522 | 0.0633 | 0.3071 | transfer=0.0711 |
| ss1 | 6.7590 | 0.3238 | 0.2427 | 0.2693 | 0.3711 | SpTRSV1=0.3101 |
| finan512 | 6.6016 | 0.1972 | 0.3417 | 1.2153 | 0.1668 | transfer=0.0808 |
| thermomech_dK | 52.9934 | 0.4533 | 0.4406 | 1.4808 | 1.1274 | transfer=0.1894 |
| shipsec5 | 73.8736 | 3.1227 | 2.0608 | 3.7775 | 3.0550 | SpTRSV2=2.6158 |

Split 结论：

- Split solve 快于 cuSPARSE 的矩阵：`finan512, thermomech_dK, shipsec5`。
- Split solve 快于 HCL 的矩阵：`finan512`。
- Split 并不是所有矩阵 solve 都慢，但它的 analysis 成本太高，且部分矩阵存在明显内部分段瓶颈。
- 小矩阵或轻量矩阵上，transfer / 外层调度开销更容易吞掉算法收益。
- `shipsec5` 上 Split 的瓶颈是第二段 SpTRSV，说明 split 后半段仍可能承担大部分依赖链。

## 8. 综合结论

最近一次结果的核心结论：

1. 正确性已经很好：quick 和 benchmark 均为 24/24 `ok`。
2. HCL-Fing 修改后，之前代表矩阵中的 `analysis_order_error` 消失，默认 benchmark 下 HCL 恢复到 6/6 可运行。
3. 在这 6 个代表矩阵上，HCL-Fing 是当前平均性能最好的方法，尤其是 `total_100_ms`。
4. `finan512` 是反例：MKL 最强，Split 次之，HCL 的 solve 不占优。
5. Split_SpTRSV 的核心问题不是所有矩阵 solve 都慢，而是 analysis 成本太高，并且部分矩阵的一段 SpTRSV 仍是主瓶颈。
6. cuSPARSE-SpSV 在 `aug3dcqp` 上单次 solve 最快，说明现代库基线不能低估。
7. 如果要把这轮结果作为最终结论，建议再跑一次同样矩阵的 `repeat_solve=300`，验证 HCL 修改后的稳定性是否在更长重复条件下仍成立。
