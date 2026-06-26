# results/csv 文件说明

本目录保存结构化 CSV 结果。约定如下：

- 每个 CSV 顶部可以有若干 `#` 开头的中文注释行。
- 注释行之后第一行是字段名。
- 字段名之后第二行是中文字段说明。
- 再往后是数据行。
- 新生成或手工整理 CSV 后，运行 `python3 scripts/annotate_results_csv.py` 刷新本索引并补齐文件注释和中文字段说明。
- 文件索引按实验推进时间顺序排列；未知新文件会排在已知文件之后。

## 文件索引

| 顺序 | 阶段 | 文件 | 中文描述 | schema | 数据行数 |
| ---: | --- | --- | --- | --- | ---: |
| 1 | 最早 tiny quick 试跑 | `main_results.csv` | 默认 quick sanity 结果文件；历史追加记录较多，只用于快速检查和回溯。 | 四方法统一结果 schema，25 个字段 | 26 |
| 2 | HCL 修正检查 | `hcl_fix_check.csv` | HCL-Fing wrapper 修正后的专项检查结果，主要用于确认边界和调度保护逻辑。 | 四方法统一结果 schema，25 个字段 | 6 |
| 3 | 小矩阵 quick 干净重跑 | `main_results_clean.csv` | 四个小矩阵 quick sanity 的干净结果文件，不作为正式性能结论。 | 四方法统一结果 schema，25 个字段 | 16 |
| 4 | 小矩阵 benchmark 干净重跑 | `benchmark_results_clean.csv` | 四个小矩阵 benchmark sanity 的干净结果文件，用于验证统一计时协议。 | 四方法统一结果 schema，25 个字段 | 16 |
| 5 | HCL smoke quick | `hcl_smoke_lower4_quick.csv` | HCL smoke lower4 小矩阵 quick 检查结果。 | 四方法统一结果 schema，25 个字段 | 4 |
| 6 | HCL smoke benchmark | `hcl_smoke_lower4_benchmark.csv` | HCL smoke lower4 小矩阵 benchmark 检查结果。 | 四方法统一结果 schema，25 个字段 | 4 |
| 7 | SuiteSparse 早期 quick | `suitesparse_selected_quick.csv` | 早期 SuiteSparse 小批量矩阵 quick 筛选结果。 | 四方法统一结果 schema，25 个字段 | 48 |
| 8 | SuiteSparse batch1 quick | `suitesparse_batch1_quick.csv` | SuiteSparse batch1 十二个候选矩阵 quick 筛选结果。 | 四方法统一结果 schema，25 个字段 | 48 |
| 9 | SuiteSparse batch1 HCL 诊断 | `hcl_schedule_diagnostics_suitesparse_batch1.csv` | SuiteSparse batch1 的 HCL-Fing 调度诊断统计，用于分析 analysis_order_error。 | 矩阵结构/调度诊断 schema，12 个字段 | 12 |
| 10 | SuiteSparse batch1 benchmark | `suitesparse_batch1_benchmark.csv` | SuiteSparse batch1 十二个候选矩阵 benchmark 结果，允许 HCL 缺失结果。 | 四方法统一结果 schema，25 个字段 | 48 |
| 11 | 最终大矩阵 quick 筛选 | `suitesparse_final_large_quick.csv` | 最终大矩阵候选集合 quick 筛选结果，包含可运行性和残差状态。 | 四方法统一结果 schema，25 个字段 | 96 |
| 12 | 最终大矩阵 HCL 诊断 | `hcl_schedule_diagnostics_suitesparse_final_large.csv` | 最终大矩阵候选集合的 HCL-Fing 调度诊断统计。 | 矩阵结构/调度诊断 schema，12 个字段 | 24 |
| 13 | 最终大矩阵 benchmark 原始 | `suitesparse_final_large_benchmark.csv` | 最终大矩阵筛选过程 benchmark 原始结果，保留中间被剔除矩阵。 | 四方法统一结果 schema，25 个字段 | 36 |
| 14 | 最终大矩阵 benchmark 干净主结果 | `suitesparse_final_large_benchmark_clean.csv` | 最终大矩阵 8 个矩阵的干净 benchmark 主结果，用于正式比较结论。 | 四方法统一结果 schema，25 个字段 | 32 |
| 15 | 最终大矩阵鲁棒性状态统计 | `suitesparse_final_large_robustness_status.csv` | 最终大矩阵候选 quick 阶段的四方法鲁棒性状态统计。 | 鲁棒性状态统计 schema，10 个字段 | 12 |
| 16 | 最终大矩阵稳健统计 | `suitesparse_final_large_robust_stats.csv` | 最终大矩阵干净 benchmark 的稳健统计结果，含均值、中位数和截尾均值。 | 稳健统计 schema，14 个字段 | 20 |
| 17 | 最终大矩阵补对角子集分析 | `suitesparse_final_large_diag_filled_subset.csv` | 最终大矩阵 benchmark 按补对角比例分组后的子集统计。 | 补对角子集统计 schema，19 个字段 | 24 |
| 18 | 最终大矩阵结构性能分析 | `suitesparse_final_large_structure_performance.csv` | 最终大矩阵结构特征与性能指标合并表，用于解释性能差异。 | 矩阵结构/调度诊断 schema，37 个字段 | 8 |
| 19 | Split 三矩阵 quick | `suitesparse_split_flip_test_quick.csv` | Split 翻盘三矩阵专项 quick 检查结果。 | 四方法统一结果 schema，25 个字段 | 12 |
| 20 | Split 三矩阵 benchmark | `suitesparse_split_flip_test_benchmark.csv` | Split 翻盘三矩阵专项 benchmark 结果。 | 四方法统一结果 schema，25 个字段 | 8 |
| 21 | Split 三矩阵结构分析 | `suitesparse_split_flip_test_structure.csv` | Split 翻盘三矩阵专项结构特征统计。 | 专项统计 schema，10 个字段 | 3 |
| 22 | Split 五矩阵 quick | `suitesparse_split_flip_extended_quick.csv` | Split 翻盘五矩阵扩展 quick 检查结果。 | 四方法统一结果 schema，25 个字段 | 20 |
| 23 | Split 五矩阵 benchmark | `suitesparse_split_flip_extended_benchmark.csv` | Split 翻盘五矩阵扩展 benchmark 结果。 | 四方法统一结果 schema，25 个字段 | 20 |
| 24 | Split 五矩阵结构分析 | `suitesparse_split_flip_extended_structure.csv` | Split 翻盘五矩阵扩展结构特征统计。 | 矩阵结构/调度诊断 schema，14 个字段 | 5 |
| 25 | 代表矩阵 repeat300 benchmark | `representative_repeat300_benchmark.csv` | 六个代表矩阵 repeat_solve=300 的 benchmark 稳定性测试结果。 | 四方法统一结果 schema，25 个字段 | 24 |
| 26 | HCL 修改后代表矩阵 quick | `hcl_modified_representative_quick.csv` | 用户修改 HCL-Fing 后，六个代表矩阵四方法 quick 检查结果。 | 四方法统一结果 schema，25 个字段 | 24 |
| 27 | HCL 修改后代表矩阵 benchmark | `hcl_modified_representative_benchmark.csv` | 用户修改 HCL-Fing 后，六个代表矩阵四方法 benchmark 结果。 | 四方法统一结果 schema，25 个字段 | 24 |

## 维护规则

- 正式结论优先看带 `clean` 或明确实验批次名的 benchmark 文件。
- `quick` 文件只用于可运行性、残差和 CSV 格式检查，不作为正式性能结论。
- `hcl_schedule_diagnostics_*` 文件只用于 HCL-Fing 调度错误诊断，不是四方法性能结果。
- `structure`、`robust`、`diag_filled` 文件是从原始结果派生的统计表。
- 新文件名应包含实验范围和模式，例如 `suitesparse_xxx_quick.csv` 或 `suitesparse_xxx_benchmark.csv`。
