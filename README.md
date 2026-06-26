# HCL-Fing Split 对比实验

本目录用于在 RTX 4090 上对比 Split_SpTRSV、HCL-Fing、cuSPARSE-SpSV
和 MKL SpTRSV。

主实验口径为：

```text
analysis + solve
```

所有方法必须读取 `data/csrbin/` 中同一份预处理后的 lower CSR。Matrix Market
输入只由外层脚本统一转换一次，单个方法不要各自重新解释 `.mtx` 文件。

## 目录职责

```text
HCL-Fing/       HCL-Fing 原项目源码，不放实验数据。
Split_SpTRSV/   Split_SpTRSV 原项目源码，不放实验数据。
data/           统一输入矩阵、RHS 向量和 metadata。
scripts/        实验主控、预处理、sanity check 和画图脚本。
benches/        统一 baseline wrapper 和公共 benchmark 代码。
config/         实验配置，只放配置，不放代码。
results/        结构化 CSV 结果、summary 和 figures。
logs/           原始运行日志和环境记录。
```

`HCL-Fing/` 和 `Split_SpTRSV/` 里面尽量少动原项目源码。允许修改构建设置、
必要的计时输出和统一输入接口；不要把实验结果、矩阵数据、日志写进这两个目录。

## 统一实验入口

正式对比实验不直接使用两个原项目各自的默认入口，而是通过 `benches/` 下的
wrapper 运行：

```text
benches/hcl_fing/        HCL-Fing 统一实验入口
benches/split_sptrsv/    Split_SpTRSV 统一实验入口
benches/cusparse_spsv/   cuSPARSE-SpSV baseline
benches/mkl/             MKL baseline
benches/common/          统一 csrbin 读取、residual、median 和 CSV 工具
```

wrapper 负责统一输入、warmup/repeat/median 计时、residual 检查和 CSV 输出；
算法核心仍然调用 `HCL-Fing/` 和 `Split_SpTRSV/` 中对应项目的实现。这样可以
避免每个项目各自读取矩阵、各自计时、各自输出结果导致实验口径不一致。

## 运行模式

四个方法都支持两种模式：

```text
quick       tiny 小矩阵快速正确性检查。结果只用于确认能运行、残差通过、CSV 正常。
benchmark   正式计时模式。四个方法使用同一套 warmup/repeat/median 规则。
```

quick 模式不作为正式性能结论。benchmark 模式优先读取 `config/experiment.yaml`
中的正式计时配置。

## 计时协议

```text
analysis_ms   分析/准备阶段中位数时间。
solve_ms      analysis/prepare 完成之后，一次完整 solve 所必需操作的端到端中位数时间。
total_k_ms    analysis_ms + k * solve_ms。
statistic     重复计时后取 median，四个方法保持一致。
```

GPU 方法使用 CUDA event 并在计时边界同步，避免异步执行导致时间偏小。CPU 代码如果
触发 GPU 工作，也需要在结束计时前同步。

`solve_ms` 包含一次 solve 必需的 RHS 刷新或拷贝、实际稀疏三角求解、方法内部必要的
GPU/CPU 同步，以及 Split_SpTRSV solve 阶段必需的 SpTRSV1、SpMV、SpTRSV2 和数据传输。

`solve_ms` 不包含文件读取、csrbin 解析、analysis/symbolic/buffer 准备、residual 检查、
CSV 写入和日志打印。

Split_SpTRSV 的主结果 `solve_ms` 使用 wrapper 外层端到端计时：analysis/setup 完成后，
计时开始，调用一次 `silu.trsv()`，等待必要同步完成，计时结束。Split 内部拆分计时项
保留在 `split_*` 字段中，只用于 breakdown，不覆盖主字段 `solve_ms`。

## 配置参数

`config/experiment.yaml` 中的参数含义：

```text
quick_warmup            quick 模式求解预热次数
quick_repeat_solve      quick 模式求解计时重复次数
quick_repeat_analysis   quick 模式分析/准备计时重复次数
warmup                  benchmark 模式求解预热次数
repeat_solve            benchmark 模式求解计时重复次数
repeat_analysis         benchmark 模式分析/准备计时重复次数
statistic               重复计时统计方式，目前固定为 median
precision               数值精度，目前为 double
cuda_arch               CUDA 编译目标架构
timeout_sec             后续批量脚本使用的超时秒数
```

核心 CSV 结果文件为：

```text
results/csv/main_results.csv
```

CSV 写入逻辑：

```text
文件顶部可以有若干行 # 开头的中文注释，说明该结果文件用途和计时口径。
注释行之后第一行固定为字段名。
字段名之后第二行固定为中文字段说明，方便直接查看 CSV。
中文字段说明之后开始是实验结果。
每个方法每完成一次运行，就向文件末尾追加一行结果。
如果 CSV 文件不存在或为空，程序会先写入中文注释、字段名行和中文说明行。
run_tiny_sanity.py 使用 --fresh 时会先删除旧 CSV，再重新生成。
```

`results/csv/README.md` 是结果文件索引，给每个 CSV 写明中文用途、schema 类型和数据行数。

后续如果新增、重跑或手工整理 CSV，统一运行：

```bash
python3 scripts/annotate_results_csv.py
```

该脚本会：

```text
1. 给每个 CSV 顶部补中文文件注释。
2. 给缺少中文字段说明的 CSV 补字段说明行。
3. 根据当前 results/csv/*.csv 重新生成 results/csv/README.md。
4. 对未知字段写出待补充提示，便于及时完善字段含义。
```

字段固定为：

```text
mode,method,matrix,n,nnz,diag_filled,warmup,repeat_solve,repeat_analysis,statistic,analysis_ms,solve_ms,total_1_ms,total_10_ms,total_100_ms,split_internal_sum_ms,split_sptrsv1_ms,split_spmv_ms,split_sptrsv2_ms,split_transfer_ms,residual,residual_pass,status,error,timeout
```

字段含义：

```text
mode              运行模式，quick 或 benchmark
method            方法名
matrix            矩阵名
n                 矩阵维度
nnz               lower CSR 非零元数量
diag_filled       预处理时补齐的缺失对角元数量
warmup            求解正式计时前的预热次数
repeat_solve      求解计时重复次数
repeat_analysis   分析/准备计时重复次数
statistic         重复计时统计方式，目前固定为 median
analysis_ms       分析/准备阶段中位数时间，单位 ms
solve_ms          analysis/prepare 完成后，一次完整 solve 必需操作的端到端中位数时间，单位 ms
total_1_ms        analysis_ms + 1 * solve_ms
total_10_ms       analysis_ms + 10 * solve_ms
total_100_ms      analysis_ms + 100 * solve_ms
split_internal_sum_ms  Split 内部计时项求和，单位 ms；只用于 breakdown，不作为主 solve_ms
split_sptrsv1_ms       Split 第一段三角求解内部时间，单位 ms
split_spmv_ms          Split 中间稀疏矩阵向量乘内部时间，单位 ms
split_sptrsv2_ms       Split 第二段三角求解内部时间，单位 ms
split_transfer_ms      Split solve 阶段内部数据传输时间求和，单位 ms
residual          相对残差 ||Ax-b||/||b||
residual_pass     残差是否通过阈值检查
status            运行状态，ok 表示成功；analysis_order_error 表示 HCL-Fing analysis 生成的调度可能死锁，未进入 solve
error             失败原因或诊断信息
timeout           是否超时
```

## 命令行参数

四个 wrapper 使用同一组核心参数：

```text
--mode quick|benchmark   运行模式
--config PATH            实验配置文件，默认 config/experiment.yaml
--matrix NAME            矩阵名，默认读取 data/csrbin/NAME.csrbin 和 data/rhs/NAME.rhs.txt
--csrbin PATH            显式指定统一 lower CSR 二进制输入
--rhs PATH               显式指定 RHS 文本输入
--output PATH            CSV 输出路径，默认 results/csv/main_results.csv
--x-output PATH          解向量输出路径，主要用于 sanity 检查
--warmup N               覆盖配置中的预热次数
--repeat N               覆盖配置中的求解计时重复次数
--repeat-analysis N      覆盖配置中的分析/准备计时重复次数
```
