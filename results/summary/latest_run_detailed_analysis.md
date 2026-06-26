# 最近一次四方法代表矩阵结果详细分析

输入文件：

- quick：`results/csv/hcl_modified_representative_quick.csv`
- benchmark：`results/csv/hcl_modified_representative_benchmark.csv`
- 最近一次覆盖式分析：`results/csv/latest_run_analysis.csv`
- 对比基准：`results/csv/representative_repeat300_benchmark.csv`

本报告只分析已有 CSV，没有重新运行实验。

## 1. 实验口径

benchmark 使用正式计时配置：

| 参数 | 值 | 含义 |
|---|---:|---|
| warmup | 5 | 正式计时前预热次数 |
| repeat_solve | 50 | solve 阶段重复计时次数 |
| repeat_analysis | 10 | analysis/prepare 阶段重复计时次数 |
| statistic | median | 使用中位数作为最终时间 |

主口径仍为：

- `analysis_ms`：分析/准备阶段中位时间。
- `solve_ms`：analysis/prepare 完成之后，一次完整 solve 所需端到端中位时间。
- `total_k_ms`：`analysis_ms + k * solve_ms`。

## 2. 数据集结构

| matrix | n | nnz | nnz/n | diag_filled | 数据特点 |
|---|---:|---:|---:|---:|---|
| aug3dcqp | 35,543 | 85,829 | 2.415 | 8,000 | 很稀疏，补对角较多 |
| ACTIVSg70K | 69,999 | 154,313 | 2.205 | 0 | 很稀疏，平均每行非零少 |
| ss1 | 205,282 | 525,873 | 2.562 | 0 | 大规模但行非零仍较少 |
| finan512 | 74,752 | 335,872 | 4.493 | 0 | 中等规模，中等稀疏度 |
| thermomech_dK | 204,316 | 1,525,272 | 7.465 | 0 | 大规模，行非零更多 |
| shipsec5 | 179,860 | 5,146,478 | 28.614 | 0 | 非零最多，单行计算量明显更重 |

数据一致性：

- 六个矩阵均为统一预处理后的 lower CSR。
- `index_base=0`，`value_type=double`，`csr_sorted=true`。
- RHS 使用 `x_true=ones` 生成。
- `aug3dcqp` 补了 8,000 个缺失对角；其他五个矩阵未补对角。

## 3. 正确性结果

| 阶段 | cuSPARSE-SpSV | MKL | HCL-Fing | Split_SpTRSV |
|---|---:|---:|---:|---:|
| quick ok | 6/6 | 6/6 | 6/6 | 6/6 |
| benchmark ok | 6/6 | 6/6 | 6/6 | 6/6 |

最大残差：

| 方法 | benchmark 最大 residual | 判断 |
|---|---:|---|
| cuSPARSE-SpSV | 1.326e-16 | 通过 |
| MKL | 1.362e-16 | 通过 |
| HCL-Fing | 1.510e-16 | 通过 |
| Split_SpTRSV | 5.377e-14 | 通过 |

结论：最近一次结果中四方法全部通过 quick 和 benchmark。Split 的最大残差出现在 `shipsec5`，数量级约 `5e-14`，仍在可接受范围内。

## 4. 平均性能

下表为 6 个矩阵的等权平均，不是按 `n` 或 `nnz` 加权平均。

| 方法 | avg_analysis_ms | avg_solve_ms | avg_total_1_ms | avg_total_10_ms | avg_total_100_ms |
|---|---:|---:|---:|---:|---:|
| cuSPARSE-SpSV | 8.845 | 1.140 | 9.985 | 20.244 | 122.834 |
| MKL | 4.755 | 0.846 | 5.601 | 13.211 | 89.315 |
| HCL-Fing | 2.014 | 0.529 | 2.543 | 7.302 | 54.889 |
| Split_SpTRSV | 24.643 | 0.723 | 25.366 | 31.869 | 96.898 |

平均上 HCL-Fing 当前最好：

- `analysis_ms` 最低，是 MKL 的约 42.4%，是 Split 的约 8.2%。
- `solve_ms` 最低，约比 MKL 快 1.60 倍，比 Split 快 1.37 倍，比 cuSPARSE 快 2.16 倍。
- `total_100_ms` 最低，约比 MKL 快 1.63 倍，比 Split 快 1.77 倍，比 cuSPARSE 快 2.24 倍。

Split_SpTRSV 的 solve 平均值优于 MKL，但 analysis 平均值过高，导致 `total_1_ms` 和 `total_10_ms` 明显吃亏，`total_100_ms` 也没有压过 HCL。

## 5. 逐矩阵性能结论

| matrix | solve 最快 | solve_ms | total_1 最快 | total_10 最快 | total_100 最快 | 主要原因 |
|---|---|---:|---|---|---|---|
| aug3dcqp | cuSPARSE | 0.0331 | MKL | MKL | HCL | cuSPARSE 单次 solve 略快，但 HCL analysis 更低，100 次时 HCL 占优 |
| ACTIVSg70K | HCL | 0.0522 | HCL | HCL | HCL | 低行非零、调度有效，HCL 从 analysis 到 solve 全面占优 |
| ss1 | HCL | 0.2427 | HCL | HCL | HCL | 大规模低行非零，HCL solve 和 analysis 都较低 |
| finan512 | MKL | 0.1668 | HCL | MKL | MKL | MKL solve 很强；HCL analysis 低所以只在一次求解时占优 |
| thermomech_dK | HCL | 0.4406 | HCL | HCL | HCL | HCL solve 略快于 Split，analysis 远低于 Split |
| shipsec5 | HCL | 2.0608 | HCL | HCL | HCL | 非零最多但 HCL analysis 和 solve 都低于其他方法 |

关键例外是 `finan512`：

- MKL `solve_ms=0.1668 ms`，是全方法最快。
- Split `solve_ms=0.1972 ms`，也快于 HCL 的 `0.3417 ms`。
- HCL 只因为 `analysis_ms=1.0598 ms` 较低，在 `total_1_ms` 上略快于 MKL。
- 从 `total_10_ms` 开始，MKL 明显领先。

## 6. HCL-Fing 现象

本轮 HCL-Fing 相比 `representative_repeat300_benchmark.csv` 的状态变化：

| matrix | 旧状态 | 新状态 |
|---|---|---|
| aug3dcqp | ok | ok |
| ACTIVSg70K | ok | ok |
| ss1 | analysis_order_error | ok |
| finan512 | analysis_order_error | ok |
| thermomech_dK | analysis_order_error | ok |
| shipsec5 | analysis_order_error | ok |

这说明用户修改 `/home/HCL-Fing_Split/HCL-Fing` 后，之前触发调度检查错误的 4 个代表矩阵已经可以通过 wrapper 调度检查和 residual 检查。

需要注意：

- 本轮 benchmark 是 `repeat_solve=50`。
- 旧的代表矩阵压力测试是 `repeat_solve=300`。
- 因此当前结果可以说明 HCL 在默认 benchmark 下已经恢复 6/6 可运行，但如果要确认“repeat300 下也稳定”，仍需要用同一套 repeat300 配置再跑一次。

性能上，HCL 当前优势来自两个方面：

- analysis 阶段开销低，六个矩阵平均只有 `2.014 ms`。
- solve 阶段端到端开销低，除了 `finan512` 外，大多数矩阵都能压过 cuSPARSE、MKL 和 Split。

这说明 HCL 在调度有效时确实有很强性能，但最终论文式结论必须把“可运行矩阵集合”和“失败矩阵集合”分开统计。

## 7. Split_SpTRSV 现象

Split 的 solve 阶段在部分矩阵上确实有优势：

| matrix | Split solve_ms | 相对 cuSPARSE | 相对 MKL | 相对 HCL |
|---|---:|---:|---:|---:|
| finan512 | 0.1972 | 快于 cuSPARSE | 慢于 MKL | 快于 HCL |
| thermomech_dK | 0.4533 | 快于 cuSPARSE | 快于 MKL | 略慢于 HCL |
| shipsec5 | 3.1227 | 快于 cuSPARSE | 略慢于 MKL | 慢于 HCL |

但 Split 的 analysis 开销很重：

| matrix | Split analysis_ms | HCL analysis_ms | Split/HCL |
|---|---:|---:|---:|
| aug3dcqp | 2.429 | 0.470 | 5.17x |
| ACTIVSg70K | 5.203 | 0.574 | 9.06x |
| ss1 | 6.759 | 1.283 | 5.27x |
| finan512 | 6.602 | 1.060 | 6.23x |
| thermomech_dK | 52.993 | 2.035 | 26.05x |
| shipsec5 | 73.874 | 6.664 | 11.09x |

所以 Split 更适合看 solve 阶段是否能翻盘，而不是少量求解的 total 时间。当前数据里：

- `finan512` 上 Split solve 明显强于 HCL，但仍输给 MKL。
- `thermomech_dK` 上 Split solve 接近 HCL，并明显强于 cuSPARSE/MKL，但 analysis 太高。
- `shipsec5` 上 Split solve 只小幅优于 cuSPARSE，仍慢于 HCL/MKL。

Split 内部分解显示：

| matrix | solve_ms | internal_sum_ms | internal/solve | 主要瓶颈 |
|---|---:|---:|---:|---|
| aug3dcqp | 0.0923 | 0.0215 | 23.3% | 外层/传输/调度开销占比较高 |
| ACTIVSg70K | 0.1460 | 0.0430 | 29.5% | 外层/传输/调度开销占比较高 |
| ss1 | 0.3238 | 0.3101 | 95.8% | 第一段 SpTRSV 占主导 |
| finan512 | 0.1972 | 0.1097 | 55.7% | 传输和两段 SpTRSV 都有贡献 |
| thermomech_dK | 0.4533 | 0.2541 | 56.1% | 传输和第二段 SpTRSV 较明显 |
| shipsec5 | 3.1227 | 3.0238 | 96.8% | 第二段 SpTRSV 占主导 |

这解释了为什么 Split 没有整体翻盘：

- 小矩阵上外层开销和传输开销吞掉收益。
- `ss1` 上第一段 SpTRSV 太重。
- `shipsec5` 上第二段 SpTRSV 太重。
- `thermomech_dK` 和 `finan512` 最符合 Split 的优势区间，但一个输给 HCL，一个输给 MKL。

## 8. 综合结论

最近一次结果的核心结论：

1. 正确性已经很好：quick 和 benchmark 均为 24/24 `ok`。
2. HCL-Fing 修改后，之前代表矩阵中的 `analysis_order_error` 消失，默认 benchmark 下 HCL 恢复到 6/6 可运行。
3. 在这 6 个代表矩阵上，HCL-Fing 是当前平均性能最好的方法，尤其是 `total_100_ms`。
4. `finan512` 是反例：MKL 最强，Split 次之，HCL 的 solve 不占优。
5. Split_SpTRSV 的核心问题不是所有矩阵 solve 都慢，而是 analysis 成本太高，并且部分矩阵的某一段 SpTRSV 仍是主瓶颈。
6. 如果要把这轮结果作为最终结论，建议再跑一次同样矩阵的 `repeat_solve=300`，验证 HCL 修改后的稳定性是否在更长重复条件下仍成立。
