# 修改记录

本文件记录 `/home/HCL-Fing_Split` 工作区内的工程改动。

记录规则：

- 每次修改代码、脚本、配置、文档、数据格式或结果 schema 后，都要在本文件追加一条记录。
- 只记录 `/home/HCL-Fing_Split` 内的改动；外部项目若只读查看，不写入这里。
- 每条记录至少写清楚日期、修改文件、修改内容、验证方式和遗留问题。
- 运行实验只生成结果、不改工程逻辑时，可以记录在对应日志或 CSV；若实验暴露出工程问题并修改了代码，则必须记录在这里。

## 2026-06-25

### HCL-Fing / Split_SpTRSV 代码创新点研究

修改文件：

- `results/summary/code_innovation_opportunities.md`
- `MODIFICATION_LOG.md`

主要内容：

- 基于当前 HCL-Fing、Split_SpTRSV wrapper 和已有代表矩阵结果，整理可形成创新点的代码层面方向。
- 总结 HCL-Fing 的优势来自低 analysis 成本和 warp 多行求解，主要问题是调度安全性、固定 `vect_size` 分桶和 `x` 哨兵式 ready 判断。
- 总结 Split_SpTRSV 的主要问题是固定阈值、分段构造成本、solve 阶段临时 buffer 分配和 host/device 中间传输。
- 建议主创新方向为“依赖安全 HCL 调度 + Split 感知自适应混合执行”。
- 根据用户反馈，进一步把创新点从外层组合/选择下探到底层计算方式、调度、存储和同步：新增 Dependency-Packed CSR、Wait-Cost-Aware Warp/CTA Scheduling、Pack-Level Ready Protocol、Logical Split、Row-Adaptive CTA Kernel 等方向。
- 将推荐主线调整为“面向 GPU SpTRSV 的依赖打包执行格式与等待代价感知调度方法”。

验证：

- 本次只做代码阅读和结果分析，没有重新运行实验。
- 没有修改算法核心、wrapper 计时逻辑或数据格式。

遗留问题：

- 若要声明论文层面的绝对新颖性，还需要继续做相关工作文献对照。
- 下一步建议先实现矩阵结构特征提取和“结构特征 -> 方法表现”自动对照表。

### 用户修改 HCL-Fing 后六个代表矩阵重跑

修改文件：

- `results/csv/hcl_modified_representative_quick.csv`
- `results/csv/hcl_modified_representative_benchmark.csv`
- `results/summary/hcl_modified_representative_rerun_summary.md`
- `results/csv/README.md`
- `scripts/annotate_results_csv.py`
- `logs/cusparse_spsv/*_hcl_modified.log`
- `logs/mkl/*_hcl_modified.log`
- `logs/hcl_fing/*_hcl_modified.log`
- `logs/split_sptrsv/*_hcl_modified.log`
- `results/sanity/x/*_hcl_modified_*.x.txt`
- `MODIFICATION_LOG.md`

主要内容：

- 用户先修改了 `/home/HCL-Fing_Split/HCL-Fing`，本次只负责重新编译 wrapper、重跑实验和整理结果。
- 重新编译四个 wrapper：
  - `benches/cusparse_spsv`
  - `benches/mkl`
  - `benches/hcl_fing`
  - `benches/split_sptrsv`
- 使用 `config/matrices_representative_repeat300.txt` 中 6 个代表矩阵：
  - `aug3dcqp`
  - `ACTIVSg70K`
  - `ss1`
  - `finan512`
  - `thermomech_dK`
  - `shipsec5`
- 先跑 quick，再跑 benchmark。
- benchmark 使用 `config/experiment.yaml` 默认正式参数：
  - `warmup=5`
  - `repeat_solve=50`
  - `repeat_analysis=10`
  - `statistic=median`
- 新增总结文件 `results/summary/hcl_modified_representative_rerun_summary.md`。
- 将新 CSV 登记到 `scripts/annotate_results_csv.py` 和 `results/csv/README.md`。

验证：

- quick：24/24 `status=ok`。
- benchmark：24/24 `status=ok`。
- HCL-Fing 本轮在 `ss1`、`finan512`、`thermomech_dK`、`shipsec5` 上均通过调度检查和 residual 检查。
- benchmark 平均值：
  - cuSPARSE-SpSV: `avg_solve_ms=1.13989`, `avg_total_100_ms=122.834`
  - MKL: `avg_solve_ms=0.845601`, `avg_total_100_ms=89.3154`
  - HCL-Fing: `avg_solve_ms=0.528747`, `avg_total_100_ms=54.8889`
  - Split_SpTRSV: `avg_solve_ms=0.722544`, `avg_total_100_ms=96.8976`

遗留问题：

- 本轮 benchmark 是默认 `repeat_solve=50`，不是上一轮 `repeat_solve=300`。若要确认 HCL 修改是否彻底解决 repeat300 下的稳定性问题，需要再跑同样的 repeat300 条件。

## 2026-06-24

### HCL-Fing repeat300 一致性核查

修改文件：

- `results/summary/hcl_consistency_check_representative_repeat300.md`
- `MODIFICATION_LOG.md`

主要内容：

- 只比对已有 CSV、meta 和日志，不重新跑 benchmark。
- 核查 `finan512`、`thermomech_dK`、`shipsec5` 在以下文件中的 HCL 记录：
  - `results/csv/suitesparse_split_flip_extended_benchmark.csv`
  - `results/csv/representative_repeat300_benchmark.csv`
  - `results/csv/hcl_schedule_diagnostics_suitesparse_batch1.csv`
  - `results/csv/hcl_schedule_diagnostics_suitesparse_final_large.csv`
  - `data/meta/*.json`
  - `logs/hcl_fing/*_benchmark_split_flip_extended.log`
  - `logs/hcl_fing/*_benchmark_repeat300.log`
- 确认两个 benchmark CSV 与 meta 中的 `n`、`nnz`、`diag_filled` 完全一致。
- 确认 `hcl_schedule_diagnostics_*.csv` 不包含这三个矩阵，不能直接用诊断 CSV 对比历史依赖计数。
- repeat300 中 HCL `analysis_order_error` 的依赖计数：
  - `finan512`: `same_warp_dependencies=0`, `non_prior_warp_dependencies=72`
  - `thermomech_dK`: `same_warp_dependencies=313`, `non_prior_warp_dependencies=969`
  - `shipsec5`: `same_warp_dependencies=367`, `non_prior_warp_dependencies=43748`

验证：

- 读取并比对 CSV、meta、HCL 日志。
- 未重新运行任何大实验。

遗留问题：

- 旧的 `status=ok` HCL 行没有记录 `same_warp_dependencies=0` 和 `non_prior_warp_dependencies=0`，因此不能从 CSV 100% 证明旧运行的调度检查计数。
- 更合理判断是同一 csrbin 下 HCL analysis 调度生成存在运行间不稳定；如果要完全排除旧二进制未启用检查，需要当时二进制 hash 或编译日志。

### 六个代表矩阵 repeat_solve=300 benchmark

修改文件：

- `config/matrices_representative_repeat300.txt`
- `results/csv/representative_repeat300_benchmark.csv`
- `results/summary/representative_repeat300_summary.md`
- `results/csv/README.md`
- `scripts/annotate_results_csv.py`
- `logs/cusparse_spsv/*_benchmark_repeat300.log`
- `logs/mkl/*_benchmark_repeat300.log`
- `logs/hcl_fing/*_benchmark_repeat300.log`
- `logs/split_sptrsv/*_benchmark_repeat300.log`
- `results/sanity/x/*_repeat300.x.txt`
- `MODIFICATION_LOG.md`

主要内容：

- 从已有矩阵中选择 6 个代表矩阵运行 benchmark：
  - `aug3dcqp`
  - `ACTIVSg70K`
  - `ss1`
  - `finan512`
  - `thermomech_dK`
  - `shipsec5`
- 本轮统一参数：
  - `mode=benchmark`
  - `warmup=5`
  - `repeat_solve=300`
  - `repeat_analysis=10`
  - `statistic=median`
- 结果写入 `results/csv/representative_repeat300_benchmark.csv`。
- 总结写入 `results/summary/representative_repeat300_summary.md`。
- 将新 CSV 登记到 `scripts/annotate_results_csv.py` 和 `results/csv/README.md`。

验证：

- 24 行结果均写入 CSV。
- cuSPARSE-SpSV、MKL、Split_SpTRSV：6/6 均 `status=ok`、`residual_pass=true`。
- HCL-Fing：2/6 `status=ok`，4/6 `analysis_order_error`。
- HCL-Fing 触发 `analysis_order_error` 的矩阵：
  - `ss1`
  - `finan512`
  - `thermomech_dK`
  - `shipsec5`
- `python3 scripts/annotate_results_csv.py`
- 检查 25 个 CSV：
  - `missing_comments=0`
  - `missing_description_rows=0`
  - `unknown_fields=0`

遗留问题：

- 本轮 repeat300 进一步确认 HCL-Fing analysis 存在调度稳定性问题；这些 HCL 失败行不应纳入性能排名。
- 主 CSV schema 仍只包含 `total_1_ms`、`total_10_ms`、`total_100_ms`；`total_300_est_ms` 只在 summary 中按 `analysis_ms + 300 * solve_ms` 派生展示。

### results/csv 文件索引按时间顺序排列

修改文件：

- `scripts/annotate_results_csv.py`
- `results/csv/README.md`
- `results/csv/*.csv`
- `MODIFICATION_LOG.md`

主要内容：

- 在 `scripts/annotate_results_csv.py` 中增加结果文件的实验时间顺序表。
- 重新生成 `results/csv/README.md`，文件索引改为按实验推进时间顺序排列。
- 索引新增 `顺序` 和 `阶段` 两列，方便区分 tiny、batch1、final large、Split 翻盘专项等不同阶段。
- 未登记的新 CSV 后续会排在已知文件之后，避免打乱已有顺序。

验证：

- `python3 -m py_compile scripts/annotate_results_csv.py`
- `python3 scripts/annotate_results_csv.py`
- 检查 24 个 CSV：
  - `missing_comments=0`
  - `missing_description_rows=0`
  - `unknown_fields=0`

遗留问题：

- 这里的“时间顺序”指实验推进顺序，不依赖文件系统修改时间；因为刷新注释会改变文件 mtime。

### CSV 文件内中文注释补齐

修改文件：

- `scripts/annotate_results_csv.py`
- `scripts/result_schema.py`
- `benches/common/result_csv.h`
- `benches/cusparse_spsv/run_tiny_sanity.py`
- `benches/mkl/run_tiny_sanity.py`
- `benches/hcl_fing/run_tiny_sanity.py`
- `benches/split_sptrsv/run_tiny_sanity.py`
- `results/csv/*.csv`
- `results/csv/README.md`
- `README.md`
- `MODIFICATION_LOG.md`

主要内容：

- 在 `results/csv` 下每个 CSV 文件顶部加入中文注释行：
  - `# 文件说明: ...`
  - `# CSV格式: ...`
  - `# 维护命令: python3 scripts/annotate_results_csv.py`
- 保留 `results/csv/README.md` 作为总索引。
- 修改 `scripts/annotate_results_csv.py`，使其能够识别、维护并更新 CSV 顶部注释行。
- 修改 Python 和 C++ 的统一 CSV 写入逻辑，使后续新建的结果文件默认带通用中文注释。
- 修改四个 `run_tiny_sanity.py`，读取 CSV 时跳过 `#` 注释行。
- README 中更新 CSV 格式规则：顶部注释行之后才是字段名、中文字段说明和数据行。

验证：

- `python3 -m py_compile scripts/annotate_results_csv.py scripts/result_schema.py benches/*/run_tiny_sanity.py`
- `python3 scripts/annotate_results_csv.py`
- 检查 24 个 CSV：
  - `missing_comments=0`
  - `missing_description_rows=0`
  - `unknown_fields=0`
- 重新编译四个 wrapper：
  - `make -C benches/cusparse_spsv`
  - `make -C benches/mkl`
  - `make -C benches/hcl_fing`
  - `make -C benches/split_sptrsv`

遗留问题：

- 带 `#` 注释行的 CSV 用普通脚本读取时需要跳过注释行；本工程内 tiny sanity 读取逻辑已同步处理。

### results/csv 中文索引和字段说明整理

修改文件：

- `scripts/annotate_results_csv.py`
- `results/csv/README.md`
- `results/csv/*.csv`
- `README.md`
- `MODIFICATION_LOG.md`

主要内容：

- 新增 `scripts/annotate_results_csv.py`，用于给结果 CSV 补齐第二行中文字段说明，并自动生成 `results/csv/README.md`。
- 为 `results/csv` 下 24 个 CSV 文件生成中文用途索引，说明每个文件的实验范围、schema 类型和数据行数。
- 为缺少第二行中文说明的派生统计 CSV 补充字段说明。
- README 中增加后续结果文件维护规则：
  - 新增、重跑或手工整理 CSV 后，运行 `python3 scripts/annotate_results_csv.py`。
  - CSV 统一采用第一行字段名、第二行中文字段说明、第三行开始数据的格式。

验证：

- `python3 -m py_compile scripts/annotate_results_csv.py`
- `python3 scripts/annotate_results_csv.py`
- 检查所有 CSV 字段均已有中文说明映射，未知字段数量为 0。

遗留问题：

- 后续如果新增新的派生统计字段，需要同步补充 `scripts/annotate_results_csv.py` 中的字段中文含义。

### Split 翻盘五矩阵扩展测试

修改文件：

- `config/matrices_suitesparse_split_flip_extended.txt`
- `data/raw_mtx/xenon2.mtx`
- `data/raw_mtx/thermomech_dK.mtx`
- `data/raw_mtx/shipsec5.mtx`
- `data/raw_mtx/suitesparse_split_flip_extended_sources.csv`
- `data/csrbin/xenon2.csrbin`
- `data/csrbin/thermomech_dK.csrbin`
- `data/csrbin/shipsec5.csrbin`
- `data/rhs/xenon2.rhs.txt`
- `data/rhs/thermomech_dK.rhs.txt`
- `data/rhs/shipsec5.rhs.txt`
- `data/meta/xenon2.json`
- `data/meta/thermomech_dK.json`
- `data/meta/shipsec5.json`
- `results/csv/suitesparse_split_flip_extended_quick.csv`
- `results/csv/suitesparse_split_flip_extended_benchmark.csv`
- `results/csv/suitesparse_split_flip_extended_structure.csv`
- `results/summary/suitesparse_split_flip_extended_summary.md`
- `logs/*/*_split_flip_extended.log`
- `MODIFICATION_LOG.md`

主要内容：

- 按用户指定测试五个 SuiteSparse 矩阵：
  - `Mulvey/finan512`
  - `Ronis/xenon1`
  - `Ronis/xenon2`
  - `Botonakis/thermomech_dK`
  - `DNVS/shipsec5`
- `finan512`、`xenon1` 复用已有 raw/CSR/RHS/meta。
- 下载并预处理 `xenon2`、`thermomech_dK`、`shipsec5`。
- 对五个矩阵运行四方法 quick 和 benchmark。

验证：

- quick：
  - 五个矩阵四方法均 `status=ok`。
- benchmark：
  - 20 行结果，全部 `status=ok`、`residual_pass=true`。
- 结论：
  - Split_SpTRSV 有局部翻盘，但没有整体翻盘。
  - `finan512` 上 Split 的 `solve_ms` 和 `total_100_ms` 均快于 HCL-Fing。
  - `thermomech_dK` 上 Split 的 `solve_ms` 略快于 HCL-Fing，但 analysis 很重，`total_100_ms` 慢于 HCL-Fing。
  - `xenon1`、`xenon2`、`shipsec5` 上 Split 均慢于 HCL-Fing。

遗留问题：

- `shipsec5` lower CSR 的 `nnz` 超过 500 万，属于本轮中最大矩阵；当前仍只作为五矩阵专项测试，不替代 final_large 主结论。
- Split 的局部优势主要体现在单次 solve，不一定能抵消更重的 analysis 阶段。

## 2026-06-23

### Split 翻盘三矩阵专项测试

修改文件：

- `config/matrices_suitesparse_split_flip_test.txt`
- `data/raw_mtx/finan512.mtx`
- `data/raw_mtx/xenon1.mtx`
- `data/raw_mtx/suitesparse_split_flip_test_sources.csv`
- `data/csrbin/finan512.csrbin`
- `data/csrbin/xenon1.csrbin`
- `data/rhs/finan512.rhs.txt`
- `data/rhs/xenon1.rhs.txt`
- `data/meta/finan512.json`
- `data/meta/xenon1.json`
- `results/csv/suitesparse_split_flip_test_quick.csv`
- `results/csv/suitesparse_split_flip_test_benchmark.csv`
- `results/csv/suitesparse_split_flip_test_structure.csv`
- `results/summary/suitesparse_split_flip_test_summary.md`
- `logs/*/*_split_flip_test.log`
- `MODIFICATION_LOG.md`

主要内容：

- 按用户指定测试三个 SuiteSparse 矩阵：
  - `Norris/lung2`
  - `Mulvey/finan512`
  - `Ronis/xenon1`
- `lung2` 已存在，复用已有 raw/CSR/RHS/meta。
- 下载并预处理 `finan512`、`xenon1`。
- 对三个矩阵运行四方法 quick。
- 只对 quick 四方法均通过的 `finan512` 和 `xenon1` 运行 benchmark。

验证：

- quick：
  - `lung2` 四方法均为 `residual_error`，残差约 `3.956e149`，不进入性能比较。
  - `finan512` 四方法均 `ok`。
  - `xenon1` 四方法均 `ok`。
- benchmark：
  - `finan512`、`xenon1` 共 8 行，全部 `status=ok`、`residual_pass=true`。
- 结论：
  - Split_SpTRSV 没有整体翻盘。
  - `finan512` 上 Split 的 `solve_ms` 快于 HCL-Fing 和 cuSPARSE，但慢于 MKL。
  - `xenon1` 上 Split 慢于 HCL-Fing 和 MKL。
  - 按 `total_100_ms`，Split 两个矩阵都不是最快。

遗留问题：

- `lung2` 属于数值残差失败样本，不适合纳入正式性能比较。
- 该测试只有两个有效 benchmark 矩阵，结论只用于验证 Split 是否在指定样本上翻盘，不应替代 final_large 主结论。

### final_large 鲁棒性、补对角子集和结构性能分析

修改文件：

- `results/csv/suitesparse_final_large_robustness_status.csv`
- `results/csv/suitesparse_final_large_robust_stats.csv`
- `results/csv/suitesparse_final_large_diag_filled_subset.csv`
- `results/csv/suitesparse_final_large_structure_performance.csv`
- `results/summary/suitesparse_final_large_deep_analysis.md`
- `MODIFICATION_LOG.md`

主要内容：

- 基于 `suitesparse_final_large_quick.csv` 统计 24 个候选矩阵的 quick 鲁棒性：
  - cuSPARSE-SpSV：`ok=19/24`
  - MKL：`ok=19/24`
  - HCL-Fing：`ok=9/24`，`analysis_order_error=14/24`
  - Split_SpTRSV：`ok=19/24`
- 基于 `suitesparse_final_large_benchmark_clean.csv` 统计最终 8 个矩阵的稳健时间指标：
  - mean
  - median
  - trimmed mean
  - geomean
  - min/q1/q3/max
  - IQR
  - standard deviation
  - coefficient of variation
- 按 `diag_filled` 分为：
  - `none`
  - `low_0_to_1pct`
  - `high_gt_1pct`
- 输出每个补对角子集内的方法平均时间和 HCL 相对 cuSPARSE/Split/MKL 的加速比。
- 输出每个矩阵的结构-性能表，包含：
  - `num_levels`
  - `avg_parallelism`
  - `avg_row_nnz`
  - `max_row_nnz`
  - `fastest_solve_method`
  - HCL 相对 cuSPARSE 和 Split 的 solve/total100 加速比
- 在中文摘要中解释性能差异：
  - HCL-Fing 在 8 个最终矩阵中 6 个 `solve_ms` 最快，7 个 `total_100_ms` 最快。
  - HCL-Fing 的 `solve_ms` 几何平均相对 cuSPARSE 为 `1.207x`，相对 Split_SpTRSV 为 `2.112x`。
  - HCL-Fing 的 `total_100_ms` 几何平均相对 cuSPARSE 为 `1.325x`，相对 Split_SpTRSV 为 `2.414x`。

验证：

- 所有分析文件均从既有 CSV 派生，没有重新运行 benchmark。
- `suitesparse_final_large_benchmark_clean.csv` 仍为 32 行，全部 `status=ok`、`residual_pass=true`、`timeout=false`。
- `bauru5727` 仍只保留在筛选/过渡结果中，不进入 clean 结论。

遗留问题：

- 结构相关性只基于 8 个最终矩阵，Spearman 相关性仅作辅助解释，不作为强统计结论。
- `diag_filled` 高低与矩阵依赖结构耦合，不能单独解释为补对角本身导致性能变化。

### SuiteSparse 大矩阵 final_large 最终比较实验

修改文件：

- `config/matrices_suitesparse_final_large.txt`
- `config/matrices_suitesparse_final_large_selected.txt`
- `data/raw_mtx/suitesparse_sstats.csv`
- `data/raw_mtx/suitesparse_final_large_sources.csv`
- `data/raw_mtx/*.mtx`
- `data/csrbin/*.csrbin`
- `data/rhs/*.rhs.txt`
- `data/meta/*.json`
- `results/csv/suitesparse_final_large_quick.csv`
- `results/csv/suitesparse_final_large_benchmark.csv`
- `results/csv/suitesparse_final_large_benchmark_clean.csv`
- `results/csv/hcl_schedule_diagnostics_suitesparse_final_large.csv`
- `results/summary/suitesparse_final_large_summary.md`
- `logs/*/*_final_large*.log`
- `MODIFICATION_LOG.md`

主要内容：

- 从 SuiteSparse 官方 `ssstats.csv` 中筛选大矩阵候选。
- 筛选原则：
  - square 矩阵；
  - `n >= 20000`；
  - 原始 `nnz` 控制在可下载、可快速验证的范围；
  - 优先非纯 graph 的数值计算类矩阵；
  - 统一转换为 lower CSR、double、0-based、CSR sorted、缺失对角补 1。
- 先运行 quick 过滤，剔除 residual 失败或 HCL-Fing 调度失败的矩阵。
- `bauru5727` 在 quick 中通过，但 benchmark 中 HCL-Fing 出现 `analysis_order_error`，最终清单已剔除。
- 最终 benchmark 清单固定为 8 个矩阵：
  - `ACTIVSg70K`
  - `hcircuit`
  - `a5esindl`
  - `aug3dcqp`
  - `a2nnsnsl`
  - `m133-b3`
  - `shar_te2-b3`
  - `ss1`
- 最终干净结果文件为 `results/csv/suitesparse_final_large_benchmark_clean.csv`。
- `results/csv/suitesparse_final_large_benchmark.csv` 保留筛选过程中的 benchmark 记录，其中包含被剔除的 `bauru5727`。

验证：

- quick 筛选文件：`results/csv/suitesparse_final_large_quick.csv`
- HCL 诊断文件：`results/csv/hcl_schedule_diagnostics_suitesparse_final_large.csv`
- 最终 benchmark 文件：`results/csv/suitesparse_final_large_benchmark_clean.csv`
- 最终 benchmark 数据行：32 行，覆盖 8 个矩阵 × 4 个方法。
- 最终 benchmark 状态：
  - `ok=32`
  - `analysis_order_error=0`
  - `timeout=0`
  - `residual_pass=true=32`
- benchmark 统一配置：
  - `warmup=5`
  - `repeat_solve=50`
  - `repeat_analysis=10`
  - `statistic=median`
- 最终平均时间记录在 `results/summary/suitesparse_final_large_summary.md`。

遗留问题：

- 本批次为筛选后的共同有效集合，不代表 SuiteSparse 全量分布。
- 若论文或报告需要完整候选筛选口径，需要同时引用 quick 筛选文件和 HCL 诊断文件。
- 部分矩阵补对角较多，例如 `m133-b3`、`shar_te2-b3`、`a2nnsnsl`，正式报告中需要说明统一预处理规则。

### 接受 HCL 缺失结果后运行 SuiteSparse 第一批 benchmark

修改文件：

- `results/csv/suitesparse_batch1_benchmark.csv`
- `logs/cusparse_spsv/*_benchmark_batch1.log`
- `logs/mkl/*_benchmark_batch1.log`
- `logs/hcl_fing/*_benchmark_batch1.log`
- `logs/split_sptrsv/*_benchmark_batch1.log`
- `MODIFICATION_LOG.md`

主要内容：

- 对 SuiteSparse 第一批 12 个矩阵运行四方法 benchmark。
- HCL-Fing 出现 `analysis_order_error` 时接受为缺失结果，不阻塞其他方法和矩阵。
- benchmark 统一配置：
  - `warmup=5`
  - `repeat_solve=50`
  - `repeat_analysis=10`
  - `statistic=median`

验证：

- 结果文件：`results/csv/suitesparse_batch1_benchmark.csv`
- 数据行：48 行，覆盖 12 个矩阵 × 4 个方法。
- 唯一矩阵/方法组合：48 个。
- 状态统计：
  - `ok=39`
  - `analysis_order_error=9`
  - `timeout=0`
- 39 个 `ok` 结果均 `residual_pass=true`。
- 9 个 `analysis_order_error` 均来自 HCL-Fing。
- HCL-Fing 有效矩阵：
  - `1138_bus`
  - `pde2961`
  - `rdb2048`
- HCL-Fing 缺失矩阵：
  - `bcsstk08`
  - `bcsstk11`
  - `bcsstk23`
  - `msc01050`
  - `msc01440`
  - `ex10`
  - `ex29`
  - `cavity05`
  - `raefsky6`

遗留问题：

- HCL-Fing 的 9 个缺失结果不是性能数据，后续做平均或画图时需要按 `status=ok` 过滤。
- 若需要四方法共同集合，只能使用 `1138_bus`、`pde2961`、`rdb2048`。
- `cavity05` 预处理补了 299 个缺失对角，正式报告中需要单独标注。

### 输出 HCL-Fing analysis 调度诊断表

修改文件：

- `results/csv/hcl_schedule_diagnostics_suitesparse_batch1.csv`
- `MODIFICATION_LOG.md`

主要内容：

- 对 SuiteSparse 第一批 12 个矩阵输出 HCL-Fing 调度诊断字段：
  - `matrix`
  - `n`
  - `nnz`
  - `num_levels`
  - `avg_parallelism`
  - `max_level_width`
  - `min_level_width`
  - `avg_row_nnz`
  - `max_row_nnz`
  - `same_warp_dependencies`
  - `non_prior_warp_dependencies`
  - `status`
- `num_levels` 和 level width 由统一 lower CSR 的真实依赖图计算。
- `same_warp_dependencies` 和 `non_prior_warp_dependencies` 来自 HCL wrapper 对实际 analysis 调度的检查。

验证：

- 12 个矩阵均已输出诊断行。
- 9 个 HCL-Fing 失败矩阵全部满足 `non_prior_warp_dependencies > 0`。
- 未发现 `non_prior_warp_dependencies = 0` 但失败的矩阵。

遗留问题：

- 该诊断确认当前失败同属一类：HCL-Fing analysis 生成的 solve order 不满足拓扑依赖。
- 后续若要修复 HCL-Fing 算法，需要重做或约束其 analysis/order 生成逻辑。

### 下载并 quick 过滤 SuiteSparse 第一批候选矩阵

修改文件：

- `config/matrices_suitesparse_batch1.txt`
- `data/raw_mtx/1138_bus.mtx`
- `data/raw_mtx/bcsstk08.mtx`
- `data/raw_mtx/bcsstk11.mtx`
- `data/raw_mtx/bcsstk23.mtx`
- `data/raw_mtx/msc01050.mtx`
- `data/raw_mtx/msc01440.mtx`
- `data/raw_mtx/ex10.mtx`
- `data/raw_mtx/ex29.mtx`
- `data/raw_mtx/pde2961.mtx`
- `data/raw_mtx/rdb2048.mtx`
- `data/raw_mtx/cavity05.mtx`
- `data/raw_mtx/raefsky6.mtx`
- `data/csrbin/*.csrbin`
- `data/rhs/*.rhs.txt`
- `data/meta/*.json`
- `results/csv/suitesparse_batch1_quick.csv`
- `results/csv/suitesparse_selected_quick.csv`
- `logs/*/*_quick_batch1.log`
- `logs/*/*_suitesparse_quick.log`

主要内容：

- 从 SuiteSparse Matrix Collection 下载第一批 12 个候选矩阵，Matrix Market 格式。
- 将原始 `.mtx` 统一转换为 lower CSR、RHS 和 metadata。
- 转换后矩阵规模：
  - `1138_bus`: `n=1138`, `nnz=2596`, `diag_filled=0`
  - `bcsstk08`: `n=1074`, `nnz=7017`, `diag_filled=0`
  - `bcsstk11`: `n=1473`, `nnz=17857`, `diag_filled=0`
  - `bcsstk23`: `n=3134`, `nnz=24156`, `diag_filled=0`
  - `msc01050`: `n=1050`, `nnz=15103`, `diag_filled=0`
  - `msc01440`: `n=1440`, `nnz=23855`, `diag_filled=0`
  - `ex10`: `n=2410`, `nnz=28625`, `diag_filled=0`
  - `ex29`: `n=2870`, `nnz=13312`, `diag_filled=0`
  - `pde2961`: `n=2961`, `nnz=8773`, `diag_filled=0`
  - `rdb2048`: `n=2048`, `nnz=7040`, `diag_filled=0`
  - `cavity05`: `n=1182`, `nnz=16763`, `diag_filled=299`
  - `raefsky6`: `n=3402`, `nnz=69168`, `diag_filled=0`
- 对 12 个矩阵运行四方法 quick sanity。

验证：

- quick 结果文件：
  - `results/csv/suitesparse_batch1_quick.csv`
  - `results/csv/suitesparse_selected_quick.csv`
- 结果共 48 行：
  - `ok=39`
  - `analysis_order_error=9`
  - `timeout=0`
- HCL-Fing 通过矩阵：
  - `1138_bus`
  - `pde2961`
  - `rdb2048`
- HCL-Fing `analysis_order_error` 矩阵：
  - `bcsstk08`
  - `bcsstk11`
  - `bcsstk23`
  - `msc01050`
  - `msc01440`
  - `ex10`
  - `ex29`
  - `cavity05`
  - `raefsky6`

遗留问题：

- 本轮只跑 quick sanity，尚未跑 benchmark。
- 若要做四方法共同有效 benchmark，第一批中只有 `1138_bus`、`pde2961`、`rdb2048` 可进入四方法共同集合。
- `cavity05` 预处理补了 299 个缺失对角，正式分析时需要单独标注。

### 使用 HCL-Fing 自带 smoke 矩阵运行四方法

修改文件：

- `data/csrbin/hcl_smoke_lower4.csrbin`
- `data/rhs/hcl_smoke_lower4.rhs.txt`
- `data/meta/hcl_smoke_lower4.json`
- `results/csv/hcl_smoke_lower4_quick.csv`
- `results/csv/hcl_smoke_lower4_benchmark.csv`
- `logs/cusparse/hcl_smoke_lower4_*.log`
- `logs/mkl/hcl_smoke_lower4_*.log`
- `logs/hcl_fing/hcl_smoke_lower4_*.log`
- `logs/split_sptrsv/hcl_smoke_lower4_*.log`

主要内容：

- 确认 HCL-Fing 原项目随仓库自带的矩阵为 `HCL-Fing/smoke_lower4.mtx`。
- HCL-Fing README 未提供固定 benchmark 矩阵集合，只说明可执行程序接受 `/path/to/matrix.mtx`。
- 将 `HCL-Fing/smoke_lower4.mtx` 转换为统一输入：
  - 矩阵名：`hcl_smoke_lower4`
  - `n=4`
  - `nnz=10`
  - `diag_filled=0`
- 使用该矩阵运行四方法 quick 和 benchmark。

验证：

- quick：
  - 四方法均 `status=ok`
  - 四方法均 `residual=0`
- benchmark：
  - 四方法均 `status=ok`
  - 四方法均 `residual=0`
  - 统一配置为 benchmark 模式默认计时规则

遗留问题：

- `hcl_smoke_lower4` 是 4 阶 smoke test 小矩阵，只能用于接口和正确性检查，不适合作为正式性能结论。

### 新建干净 benchmark 结果文件

修改文件：

- `results/csv/benchmark_results_clean.csv`
- `logs/cusparse/*_benchmark_clean.log`
- `logs/mkl/*_benchmark_clean.log`
- `logs/hcl_fing/*_benchmark_clean.log`
- `logs/split_sptrsv/*_benchmark_clean.log`

主要内容：

- 检查 `results/csv/main_results_clean.csv`，确认 quick sanity 结果结构正常：
  - 16 行 quick 结果
  - `ok=14`
  - `analysis_order_error=2`
  - `timeout=0`
- 新建独立 benchmark 结果文件 `results/csv/benchmark_results_clean.csv`，未覆盖 quick 结果文件和原始 `main_results.csv`。
- 对四个矩阵执行四方法 benchmark：
  - `sherman5`
  - `nos6`
  - `bcsstk21`
  - `bcsstk14`
- benchmark 统一配置：
  - `warmup=5`
  - `repeat_solve=50`
  - `repeat_analysis=10`
  - `statistic=median`
- 结果共 16 行：
  - `ok=14`
  - `analysis_order_error=2`，均来自 HCL-Fing 的 `sherman5` 和 `bcsstk14`
  - `timeout=0`

验证：

- 检查 `results/csv/benchmark_results_clean.csv`：
  - 第一行字段名
  - 第二行中文字段说明
  - 16 条 benchmark 结果
  - 所有结果均为 `mode=benchmark`
  - 所有结果均使用 `5/50/10/median` 计时配置
- 确认无残留 benchmark/wrapper 进程。

遗留问题：

- HCL-Fing 在 `sherman5` 和 `bcsstk14` 上仍是 `analysis_order_error`，无有效 `solve_ms` 和 `total_*_ms`。
- `benchmark_results_clean.csv` 是当前四个小矩阵的正式计时文件；后续扩大矩阵集合时建议另建新文件或明确追加策略。

### 新建干净 quick 结果文件

修改文件：

- `results/csv/main_results_clean.csv`
- `logs/cusparse/*.log`
- `logs/mkl/*.log`
- `logs/hcl_fing/*.log`
- `logs/split_sptrsv/*.log`

主要内容：

- 新建独立干净结果文件 `results/csv/main_results_clean.csv`，未覆盖原 `results/csv/main_results.csv`。
- 重新编译四个 wrapper，确保 CSV 字段说明和当前 schema 一致：
  - `cusparse_spsv`
  - `mkl`
  - `hcl_fing`
  - `split_sptrsv`
- 对四个矩阵执行 quick 模式：
  - `sherman5`
  - `nos6`
  - `bcsstk21`
  - `bcsstk14`
- 结果共 16 行：
  - `ok`：14 行
  - `analysis_order_error`：2 行，均来自 HCL-Fing 的 `sherman5` 和 `bcsstk14`

验证：

- 检查 `results/csv/main_results_clean.csv`：
  - 第一行字段名
  - 第二行中文字段说明
  - 第三行开始为 16 条 quick 结果
- 状态统计：
  - `ok=14`
  - `analysis_order_error=2`
  - `timeout=0`
- 确认无残留 benchmark/wrapper 进程。

遗留问题：

- `main_results_clean.csv` 是 quick sanity 结果，不作为正式性能结论。
- HCL-Fing 在 `sherman5` 和 `bcsstk14` 上仍不能进入有效 solve 计时，当前按 `analysis_order_error` 记录。

### 新增修改记录文件

修改文件：

- `MODIFICATION_LOG.md`

主要内容：

- 新增工程修改记录文件。
- 固定后续改动的记录规则。

验证：

- 未运行程序；这是文档文件新增。

遗留问题：

- 无。

### 将 latest_run_analysis 从 CSV 改为 Markdown 文档报告

修改文件：

- `scripts/write_latest_run_analysis.py`
- `scripts/annotate_results_csv.py`
- `results/summary/latest_run_analysis.md`
- `results/csv/README.md`
- `MODIFICATION_LOG.md`

删除文件：

- `results/csv/latest_run_analysis.csv`

主要内容：

- 纠正 `latest_run_analysis.csv` 仍不像文档的问题。
- 不再把最近一次分析放在 `results/csv/` 中，避免和原始结果 CSV 混淆。
- 新增覆盖式 Markdown 文档：
  - `results/summary/latest_run_analysis.md`
- `scripts/write_latest_run_analysis.py` 改为默认生成 Markdown 报告，而不是 CSV。
- 报告内容补齐为文档结构：
  - 数据来源；
  - 实验口径；
  - 数据集结构分析；
  - quick / benchmark 正确性分析；
  - 四方法整体平均性能；
  - 逐矩阵性能分析；
  - Split_SpTRSV 优势与瓶颈；
  - HCL-Fing 修改前后状态变化；
  - 当前结论；
  - 后续建议。
- `scripts/annotate_results_csv.py` 移除 `latest_run_analysis.csv` 的登记。
- `results/csv/README.md` 刷新后不再列出 `latest_run_analysis.csv`。

验证：

- `python3 -m py_compile scripts/write_latest_run_analysis.py scripts/annotate_results_csv.py`
- 重新生成：
  - `python3 scripts/write_latest_run_analysis.py --quick results/csv/hcl_modified_representative_quick.csv --benchmark results/csv/hcl_modified_representative_benchmark.csv --baseline results/csv/representative_repeat300_benchmark.csv --output results/summary/latest_run_analysis.md`
- 刷新 CSV 索引：
  - `python3 scripts/annotate_results_csv.py`
- 已确认：
  - `results/summary/latest_run_analysis.md` 存在；
  - `results/csv/latest_run_analysis.csv` 已删除；
  - `results/csv/README.md` 不再登记该 CSV。

遗留问题：

- 无。

### 调整 latest_run_analysis.md 为 detailed 风格

修改文件：

- `scripts/write_latest_run_analysis.py`
- `results/summary/latest_run_analysis.md`
- `MODIFICATION_LOG.md`

主要内容：

- 按 `results/summary/latest_run_detailed_analysis.md` 的阅读风格调整 `latest_run_analysis.md`。
- 报告开头改为直接列出输入文件，而不是单独写“数据来源”章节。
- 章节顺序调整为：
  - 实验口径；
  - 数据集结构；
  - 正确性结果；
  - 平均性能；
  - 逐矩阵性能结论；
  - HCL-Fing 现象；
  - Split_SpTRSV 现象；
  - 综合结论。
- 表格字段改为更接近旧详细报告的命名，例如 `avg_analysis_ms`、`avg_solve_ms`、`avg_total_100_ms`。
- HCL-Fing 现象提前到 Split 分析之前，便于先看修改前后状态变化。
- 将 `analysis_ms` 对比表述从“倍数”改为百分比，更容易阅读。

验证：

- `python3 -m py_compile scripts/write_latest_run_analysis.py`
- `python3 scripts/write_latest_run_analysis.py --quick results/csv/hcl_modified_representative_quick.csv --benchmark results/csv/hcl_modified_representative_benchmark.csv --baseline results/csv/representative_repeat300_benchmark.csv --output results/summary/latest_run_analysis.md`
- 已确认 `results/summary/latest_run_analysis.md` 新版章节和格式生效。

遗留问题：

- 无。

### 修正 HCL-Fing wrapper 的 CSV 字段说明

修改文件：

- `results/csv/main_results.csv`
- `benches/common/result_csv.h`
- `scripts/result_schema.py`
- `README.md`

主要内容：

- 在主 CSV 第二行加入中文字段说明。
- C++ 和 Python 的 CSV 写入逻辑统一为：第一行字段名，第二行中文说明，第三行开始追加实验结果。
- README 中补充 CSV 追加写入逻辑说明。

验证：

- `python3 -m py_compile scripts/result_schema.py benches/cusparse_spsv/run_tiny_sanity.py benches/mkl/run_tiny_sanity.py benches/hcl_fing/run_tiny_sanity.py benches/split_sptrsv/run_tiny_sanity.py`
- 检查 `results/csv/main_results.csv` 前几行，确认第二行中文说明存在。

遗留问题：

- 无。

### 定位 HCL-Fing 在 sherman5 和 bcsstk14 上超时的原因

修改文件：

- `benches/hcl_fing/hcl_fing_baseline.cu`

主要内容：

- 增加 `HCL_FING_TRACE=1` 下启用的诊断输出。
- 增加 HCL analysis 调度覆盖和依赖顺序检查，用于定位 solve 阶段死等。
- 诊断发现 `sherman5` 和 `bcsstk14` 的 HCL analysis 结果存在依赖反序，进入 `csr_L_solve_multirow` 后可能死等。

验证：

- HCL quick trace：
  - `nos6` 正常，`non_prior_warp_dependencies=0`
  - `bcsstk21` 正常，`non_prior_warp_dependencies=0`
  - `sherman5` 超时，存在 `non_prior_warp_dependencies`
  - `bcsstk14` 超时，存在 `same_warp_dependencies` 和大量 `non_prior_warp_dependencies`
- `compute-sanitizer` 在 tiny 上抓到 HCL analysis kernel 的越界读。

遗留问题：

- 此阶段只定位问题，尚未作为正式保护逻辑。

### 修复 HCL-Fing analysis/solve 边界并增加死锁保护

修改文件：

- `HCL-Fing/analysis/analysis_csr.cu`
- `HCL-Fing/solver/solve_csr_multirow.cu`
- `benches/hcl_fing/hcl_fing_baseline.cu`
- `benches/common/result_csv.h`
- `scripts/result_schema.py`
- `README.md`

主要内容：

- 将 HCL analysis kernel 的边界判断从 `groupId > n` 改为 `groupId >= n`，避免访问 `row_ptr[n + 1]`。
- 在 HCL solve kernel 中先判断 `vect_idx >= n_vects`，再访问 `iorder[base_idx + vect_idx]`，避免 inactive lane 越界读。
- 将 HCL wrapper 的调度检查改为默认保护逻辑：如果发现 analysis 生成的调度存在死锁风险，直接写 CSV：
  - `status=analysis_order_error`
  - `residual_pass=false`
  - `error=HCL analysis schedule may deadlock: ...`
- README 和 schema 说明中补充 `analysis_order_error` 含义。

验证：

- `make -C benches/hcl_fing`
- `compute-sanitizer --tool memcheck --leak-check no benches/hcl_fing/hcl_fing_baseline ... tiny_lower_missing_diag ...`
  - 结果：`ERROR SUMMARY: 0 errors`
- HCL quick 验证：
  - `tiny_lower_missing_diag`：`ok`，`residual=0`
  - `nos6`：`ok`，`residual=2.99708e-18`
  - `bcsstk21`：`ok`，`residual=4.49694e-20`
  - `sherman5`：快速返回 `analysis_order_error`，不再 timeout
  - `bcsstk14`：快速返回 `analysis_order_error`，不再 timeout

遗留问题：

- `sherman5` 和 `bcsstk14` 仍不能作为 HCL-Fing 的有效性能结果；当前行为是明确标记为 `analysis_order_error`，避免 benchmark 卡死。
- `/home/HCL-Fing` 原目录未修改；本修复只在 `/home/HCL-Fing_Split` 内生效。

### 增加最新一次运行分析结果文件

修改文件：

- `scripts/write_latest_run_analysis.py`
- `scripts/annotate_results_csv.py`
- `results/csv/latest_run_analysis.csv`
- `results/csv/README.md`
- `MODIFICATION_LOG.md`

主要内容：

- 新增 `scripts/write_latest_run_analysis.py`，用于根据指定 quick CSV、benchmark CSV 和可选 baseline CSV 生成最近一次运行后的分析结果。
- 新增固定输出文件 `results/csv/latest_run_analysis.csv`，该文件每次生成时覆盖旧内容，只保留一份最新分析。
- `latest_run_analysis.csv` 记录：
  - quick / benchmark 输入文件；
  - 各方法 `status` 统计；
  - benchmark 中各方法 `analysis_ms`、`solve_ms`、`total_100_ms` 平均值；
  - 每个矩阵在 `solve_ms` 和 `total_100_ms` 上的最快方法；
  - 可选 baseline 对比中的 HCL 状态变化和时间差。
- 更新 `scripts/annotate_results_csv.py`，让后续 CSV 注释和 `results/csv/README.md` 能识别 `latest_run_analysis.csv`。

验证：

- 生成命令：
  - `python3 scripts/write_latest_run_analysis.py --quick results/csv/hcl_modified_representative_quick.csv --benchmark results/csv/hcl_modified_representative_benchmark.csv --baseline results/csv/representative_repeat300_benchmark.csv --output results/csv/latest_run_analysis.csv`
- 注释刷新：
  - `python3 scripts/annotate_results_csv.py`
- 已确认 `results/csv/latest_run_analysis.csv` 包含中文注释、字段名、第二行中文字段说明和最新分析数据。

遗留问题：

- 无。后续每次完成一轮实验后，重新运行 `scripts/write_latest_run_analysis.py` 即可覆盖为最新分析。

### 增加最近一次运行的详细结果分析报告

修改文件：

- `results/summary/latest_run_detailed_analysis.md`
- `MODIFICATION_LOG.md`

主要内容：

- 新增最近一次四方法代表矩阵结果的详细分析报告。
- 报告基于已有 CSV，不重新运行实验。
- 分析内容包括：
  - benchmark 计时口径；
  - 六个代表矩阵的数据规模、`nnz/n`、补对角情况；
  - quick 和 benchmark 正确性结果；
  - 四方法平均 `analysis_ms`、`solve_ms`、`total_1/10/100_ms`；
  - 每个矩阵的最快方法和原因解释；
  - HCL-Fing 修改前后 `analysis_order_error -> ok` 的状态变化；
  - Split_SpTRSV 内部分解和性能瓶颈。

验证：

- 只读取并分析：
  - `results/csv/hcl_modified_representative_quick.csv`
  - `results/csv/hcl_modified_representative_benchmark.csv`
  - `results/csv/latest_run_analysis.csv`
  - `results/csv/representative_repeat300_benchmark.csv`
- 未重新运行 quick 或 benchmark。

遗留问题：

- 若要确认 HCL 修改后在更长重复条件下也稳定，需要后续再用 `repeat_solve=300` 重新跑同一批代表矩阵。

### 扩展 latest_run_analysis.csv 的分析内容

修改文件：

- `scripts/write_latest_run_analysis.py`
- `results/csv/latest_run_analysis.csv`
- `results/csv/README.md`
- `MODIFICATION_LOG.md`

主要内容：

- 将最近一次结果的结论性分析直接写入 `results/csv/latest_run_analysis.csv`，而不是只放在 summary markdown 中。
- `latest_run_analysis.csv` 现在覆盖生成时会包含：
  - benchmark 计时协议；
  - 六个代表矩阵的 `n`、`nnz`、`nnz/n`、`diag_filled`；
  - quick / benchmark 的总体通过情况；
  - 四方法最大 residual；
  - 四方法 `analysis_ms`、`solve_ms`、`total_1_ms`、`total_10_ms`、`total_100_ms` 等权平均；
  - 每个矩阵在 solve、total_1、total_10、total_100 上的最快方法；
  - 每个矩阵的中文性能解释；
  - Split_SpTRSV 内部分解、analysis 成本和相对 solve 位置；
  - HCL-Fing 相对 repeat300 基准的 `analysis_order_error -> ok` 状态变化；
  - `current=50;baseline=300` 的复验提醒。
- 更新 `scripts/write_latest_run_analysis.py`，保证后续每次重新生成最新分析文件时自动写入上述内容。

验证：

- `python3 -m py_compile scripts/write_latest_run_analysis.py scripts/annotate_results_csv.py`
- 重新生成：
  - `python3 scripts/write_latest_run_analysis.py --quick results/csv/hcl_modified_representative_quick.csv --benchmark results/csv/hcl_modified_representative_benchmark.csv --baseline results/csv/representative_repeat300_benchmark.csv --output results/csv/latest_run_analysis.csv`
- 刷新注释：
  - `python3 scripts/annotate_results_csv.py`
- 已确认 `results/csv/latest_run_analysis.csv` 中包含 `conclusion`、`split_analysis`、`dataset`、`residual`、`winner`、`compare` 等分析行。

遗留问题：

- 无。后续只要用 `scripts/write_latest_run_analysis.py` 覆盖生成，最新分析文件会保留这些结论字段。

### 将 latest_run_analysis.csv 改为纯分析结论表

修改文件：

- `scripts/write_latest_run_analysis.py`
- `scripts/annotate_results_csv.py`
- `results/csv/latest_run_analysis.csv`
- `results/csv/README.md`
- `MODIFICATION_LOG.md`

主要内容：

- 修正上一版 `latest_run_analysis.csv` 仍然像二次运行结果表的问题。
- 将 `latest_run_analysis.csv` 的 schema 从：
  - `section,item,method,matrix,metric,value,unit,note`
  改为：
  - `section,topic,method,matrix,conclusion,evidence,interpretation,next_step`
- 新文件只保留分析结论，不再逐行保存 average、winner、dataset 等运行统计结果。
- 数值只作为 `evidence` 中的证据出现，用来支撑结论。
- `scripts/annotate_results_csv.py` 为该文件增加专门注释：
  - “分析结论文件”
  - “第三行开始是分析内容”
  - “不保存原始运行结果”

验证：

- `python3 -m py_compile scripts/write_latest_run_analysis.py scripts/annotate_results_csv.py`
- `python3 scripts/write_latest_run_analysis.py --quick results/csv/hcl_modified_representative_quick.csv --benchmark results/csv/hcl_modified_representative_benchmark.csv --baseline results/csv/representative_repeat300_benchmark.csv --output results/csv/latest_run_analysis.csv`
- `python3 scripts/annotate_results_csv.py`
- 已确认 `results/csv/latest_run_analysis.csv` 当前为 8 字段、14 行分析内容，字段包含 `conclusion`、`evidence`、`interpretation`、`next_step`。

遗留问题：

- 无。
