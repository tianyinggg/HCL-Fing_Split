# HCL-Fing / Split_SpTRSV 代码创新点研究

本文档基于当前 `/home/HCL-Fing_Split` 代码和已有代表矩阵实验结果，目标是从代码实现中找出可提升、可验证、可发展成自己创新点的方向。本文只做代码研究和方案整理，没有重新运行实验，也没有修改算法核心。

## 1. 当前结论

从已有结果看，HCL-Fing 在能稳定运行时性能非常强，尤其是分析时间和重复求解总时间。Split_SpTRSV 的结构思路有价值，但当前实现中 analysis 成本、数据传输和固定策略阈值明显限制了性能。

更适合发展成创新点的方向不是简单调参，也不是把 HCL、Split、cuSPARSE、MKL 做一个表层组合，而是从 SpTRSV 的底层执行方式重新组织：

> 面向 SpTRSV 的结构化执行表示：把原始 CSR 转换成更适合 GPU 三角求解的派生存储，联合表达行依赖、warp packing、ready 状态和分段边界，让计算、调度、存储和同步成为一个整体设计。

这个方向能解释当前实验现象：

- HCL-Fing 大多数矩阵最快，说明 warp 多行求解路线有价值。
- HCL-Fing 之前出现过 `analysis_order_error`，说明调度安全性是硬问题。
- `finan512` 上 MKL 和 Split 的 solve 优于 HCL，说明固定计算粒度和固定调度并非总是最优。
- Split 在若干矩阵上 solve 能接近或超过 cuSPARSE，但 analysis 和 transfer 过高，说明分段思想需要重构执行存储和数据流。

## 2. HCL-Fing 代码观察

### 2.1 HCL 的核心优势

HCL 多行求解入口在 `HCL-Fing/solver/solve_csr_multirow.cu`。

关键机制：

- 每个 warp 通过 `atomicAdd(row_ctr, 1)` 动态领取一个 warp 任务。
- 一个 warp 内可按 `vect_size` 同时处理多行。
- 行内非零数越少，越容易把多个行装进同一个 warp。
- 求解前用 `cudaMemsetAsync(x, 0xFF, ...)` 把 `x` 初始化为未完成标记。
- 依赖行完成后，等待方从 `x[colidx]` 读取值继续计算。

这解释了 HCL 在低到中等 `nnz/n` 矩阵上的优势：分析开销低，solve kernel 也短，重复求解时收益很明显。

### 2.2 HCL 的主要脆弱点

HCL 当前调度由 `HCL-Fing/analysis/analysis_csr.cu` 生成。

值得注意的实现点：

- `vect_size_calculator` 只按行非零数分桶：`1,2,4,8,16,32`，对角-only 行用特殊 bucket。
- analysis kernel 通过 shared/global `is_solved` 等待依赖完成并计算 level。
- tile size 由全矩阵平均 `nnz / rows` 决定，而不是按 level、row 或依赖形态自适应选择。
- 后处理大量依赖 Thrust：`stable_sort`、`reduce_by_key`、`exclusive_scan`、`stable_sort_by_key`。
- schedule 最终按 `level + vect_size` 分桶，然后生成 `iorder / ibase_row / ivect_size_warp`。

wrapper 中 `benches/hcl_fing/hcl_fing_baseline.cu` 额外做了调度检查：

- 是否漏行、重复行、非法行。
- 每个 warp 是否超过容量。
- 是否存在依赖行没有排在更早 warp。
- 发现风险时输出 `analysis_order_error`，避免死锁或错误结果。

这说明 HCL 原始思路快，但调度正确性并不是天然稳固。当前你修改后的 HCL 已经让代表矩阵默认 benchmark 通过，但这更像修复了一个具体同步/局部依赖问题，还没有形成完整的“可证明安全调度器”。

### 2.3 HCL 可创新点

#### 方向 A：依赖安全的确定性 HCL 调度器

核心思想：

> 把当前 HCL 的“level + vect_size 分桶”升级成“依赖安全 + warp 利用率 + 局部性”共同约束的确定性调度器。

具体做法：

- 先构建 row DAG 的 level 或拓扑序。
- 对每个候选 warp packing 检查依赖是否都来自更早 warp。
- same-warp dependency 单独处理：要么禁止，要么在 warp 内给出明确 lane 顺序。
- 用 schedule checker 从事后诊断变成调度生成器的一部分。
- 生成 schedule 时同时优化 warp 内 lane 利用率、同一 level 的行合并、依赖距离和全局等待概率。

创新性：

- 不只是修 bug，而是把 HCL 的快速 warp 多行求解改造成 correctness-aware schedule。
- 可以作为 HCL-Fing 稳定性问题的系统性解决方案。

有效性预期：

- 降低或消除 `analysis_order_error`。
- 保留 HCL 当前低 solve_ms 优势。
- 对 `ss1 / finan512 / thermomech_dK / shipsec5` 这类以前出过调度问题的矩阵尤其有价值。

风险：

- analysis_ms 可能上升。
- 需要用 `total_k_ms = analysis_ms + k * solve_ms` 证明当 repeat 较大时仍划算。

#### 方向 B：stall-aware 自适应 warp 粒度

当前 HCL 的 `vect_size` 只看行非零数：

- `nnz_row <= 1` 用小粒度；
- `nnz_row <= 16` 逐级增加；
- 更长行使用 32 lane。

问题是，行非零数不是唯一决定因素。真正影响 solve 的还有：

- 依赖是否很深；
- 依赖行是否刚刚完成；
- level 宽度是否足够；
- 行非零分布是否长尾；
- warp 内是否会出现大量 lane 空转。

可做创新：

> 用 row nnz、level width、dependency distance、ready-wait 估计共同决定每行或每个 level 的 `vect_size`，而不是固定按 nnz 分桶。

有效性预期：

- 对 `finan512` 这种 HCL solve 不占优的矩阵可能有效。
- 对高 `nnz/n` 的 `shipsec5` 可以减少 lane 空转或依赖等待。

实现难度：

- 中等。可以先在 wrapper 外生成候选 schedule，不必立即重写求解 kernel。

#### 方向 C：显式 ready flag 替代 x 哨兵

当前 multirow solve 用 `x` 的 bit pattern 判断依赖是否完成：

- solve 前把 `x` 置为 `0xFF`。
- kernel 内用 `__double2hiint(xx) != 0xFFFFFFFF` 判断 ready。

这有几个问题：

- 和 double 表示绑定，扩展到 float 或混合精度不自然。
- ready 状态和数值写入耦合。
- 内存语义依赖 volatile / fence，后续维护难。

可做创新：

> 分离数值数组 `x` 和完成标记 `ready[]`，或使用 packed value-ready 状态，并结合 schedule 约束减少 busy-wait。

有效性预期：

- 提高正确性可解释性和可移植性。
- 可能减少部分全局内存轮询。

注意：

- 仅替换 ready 机制本身更像工程改进；如果和“依赖安全调度器”结合，才更像完整创新。

## 3. Split_SpTRSV 代码观察

### 3.1 Split 的核心思路

Split 的主流程在 `Split_SpTRSV/src/SILU.cpp`。

`SILU::Analyze` 主要步骤：

- `findlevels_csr`
- `analyse_dag_revised`
- `split_dag`
- `setup_execution_devices`
- `setup_device_datastructures`
- `algorithm_analysis`

`SILU::trsv` 主要执行：

- 第一段 SpTRSV。
- 中间 SpMV 更新 RHS。
- 第二段 SpTRSV。
- 多处 host/device 数据传输。

这说明 Split 的思想不是单纯求解一个三角矩阵，而是把矩阵按 DAG/level 切开，用 SpMV 连接两段 SpTRSV。

### 3.2 Split 的主要瓶颈

代码中有几个明显问题：

1. 固定阈值过多

`Split_SpTRSV/include/policy.h` 中有大量固定阈值，例如：

- `MIN_ROWS`
- `MIN_LEVELS`
- `MAX_LEVELS`
- `MAX_COL_LENGTH_THRESHOLD`
- `MAX_ROW_LENGTH_THRESHOLD`
- `WARP_COLWISE_ITERATIONS_THRESHOLD`
- `WARP_ROWISE_ITERATIONS_THRESHOLD`

这些阈值更像旧平台经验规则，不一定适合 RTX 4090、现代 cuSPARSE 和当前统一 CSR 数据。

2. 分段构造成本高

`split_dag` 会重新生成：

- top triangle；
- middle SpMV block；
- bottom triangle；
- 必要时还会转置并重新计算 submatrix levels。

这解释了 Split 的 `analysis_ms` 明显偏高。

3. solve 阶段仍有临时分配和传输

`SILU::trsv` 中 GPU SpMV 路径每次 solve 都查询 SpMV buffer size、`cudaMalloc`、`cudaFree`。

同时存在多处：

- top 解结果 device-to-host；
- SpMV 后 RHS device-to-host；
- CPU SpMV 路径 host-to-device；
- bottom 解结果 device-to-host。

这解释了结果中 Split 在 `aug3dcqp / ACTIVSg70K / finan512 / thermomech_dK` 上 transfer 成为明显瓶颈。

4. 第二段 SpTRSV 可能吞掉收益

结果中 `shipsec5` 的 Split 内部瓶颈是 `split_sptrsv2_ms`，说明 split point 没有让后半段变得足够轻。

### 3.3 Split 可创新点

#### 方向 D：全 GPU 常驻 Split pipeline

核心思想：

> 把 Split 的 top SpTRSV -> SpMV -> bottom SpTRSV 做成常驻 GPU 的 pipeline，analysis 阶段一次性分配 buffer，solve 阶段不再做临时 malloc/free 和不必要的 host/device 中间传输。

具体做法：

- analysis 阶段完成 SpMV buffer size 查询和 buffer 分配。
- 中间 RHS 保持在 device。
- top 解结果如果只给 SpMV 使用，不回传 host。
- bottom 解结果只在 residual 或最终输出时回传。
- 可选使用 CUDA Graph 捕获固定求解流程，减少 kernel/库调用启动开销。

创新性：

- 相比简单调参，这是对 Split 执行路径的系统重构。
- 能直接对应当前实验中的 transfer 和 analysis 瓶颈。

有效性预期：

- 对 `finan512 / thermomech_dK` 这类 Split solve 接近或优于部分基线的矩阵，可能显著提升。
- 对 `aug3dcqp / ACTIVSg70K` 这类小 solve 时间矩阵，减少传输后收益更明显。

风险：

- 需要处理 Split 内部多种方法组合：ELMC、SLFC、SYNC_FREE、cuSPARSE、MKL。
- 初期可以只做 GPU-GPU 路径，不覆盖 CPU 混合路径。

#### 方向 E：架构感知 split point 和方法选择模型

当前 Split 的 `GPUGPUSplit` 主要根据 level 的最大列长度、最大行长度和固定阈值选 split point。

可做创新：

> 用实际矩阵特征和平台校准数据预测每个 split point 的总代价，选择最小化 `analysis_ms + k * solve_ms` 的 split 和方法组合。

候选特征：

- `n`
- `nnz`
- `nnz/n`
- level 数量；
- 最大/平均 level width；
- 最大行非零；
- 最大列依赖长度；
- top/bottom/mvp 的 nnz 比例；
- 预估 transfer 字节数；
- repeat 次数 `k`。

优化目标：

- 单次求解：最小化 `total_1_ms`。
- 多 RHS 或重复求解：最小化 `total_10_ms` / `total_100_ms`。

有效性预期：

- 避免 `shipsec5` 这类 split 后第二段过重。
- 解释并利用 `finan512` 上 Split solve 快于 HCL 的现象。

创新性：

- 相比固定阈值，这是平台和数据驱动的 Split。
- 如果和 HCL 调度器结合，创新性更强。

## 4. 更底层的创新方向

上一节的 HCL-safe scheduler、Split pipeline 和 split point 模型仍然偏工程系统。若要形成更强的“自己的创新点”，应该继续下探到 SpTRSV 的计算、调度、存储和同步表达。

### 4.1 新执行存储：Dependency-Packed CSR

当前统一输入是普通 lower CSR：

- `row_ptr`
- `col_idx`
- `values`

HCL 额外生成：

- `iorder`
- `ibase_row`
- `ivect_size_warp`

Split 额外生成：

- `levelPtr`
- `levelItem`
- `levelItemNewRowIdx`
- top / Mvp / bottom 子矩阵
- CSR / CSC 双格式

这些都是“后挂式元数据”：CSR 是 CSR，调度是调度，依赖状态是另一个数组，Split 又重新构造子矩阵。它们没有形成一个统一的 SpTRSV 执行格式。

可以设计一个新的派生存储：

```text
Dependency-Packed CSR, 简称 DP-CSR

row_perm[]              行执行顺序
pack_ptr[]              每个 warp/CTA pack 的起止位置
pack_type[]             pack 的执行类型：single-row / multi-row / long-row / diagonal-only
lane_width[]            每行或每组使用 1/2/4/8/16/32 lane
dep_ptr[]               每个 pack 的跨 pack 依赖列表
local_dep_mask[]        同 pack 内依赖关系
diag_pos[]              每行对角位置
ready_slot[]            每行 ready 状态位置
value_idx[]             原 CSR 非零重排后的值位置
```

它的核心不是压缩存储体积，而是把“执行需要的信息”提前编码进去：

- 对角位置不再每次从 row end 假设或搜索。
- 同 warp 内可处理的行提前 packed。
- 跨 warp 依赖提前压成 pack-level DAG。
- ready 状态位置和数据位置分离。
- 对长行、短行、对角-only 行使用不同执行模板。

创新点：

> 从通用 CSR 转向 SpTRSV-specific execution format，让存储布局直接服务于依赖调度和 warp 执行。

为什么有价值：

- HCL 现在快，但 schedule 元数据仍然比较粗。
- Split 现在分 top/Mvp/bottom 会制造大量复制和转置。
- DP-CSR 可以让 HCL 的 warp packing 和 Split 的分段边界变成同一种执行表示，不需要反复拆矩阵。

可验证指标：

- analysis_ms 是否增加可控；
- solve_ms 是否下降；
- HCL 的 `analysis_order_error` 是否消失；
- Split 的 split/transpose/data_structures 时间是否下降。

### 4.2 新计算方式：Push/Pull Hybrid SpTRSV

现有两类计算方式：

- HCL 更偏 pull：当前行等待依赖行 `x[colidx]` ready，然后读取依赖值。
- Split 的 sync-free / ELMC 更偏 push：已完成行把贡献通过 atomic 加到后继行。

两种方式各有问题：

- pull 的问题是等待方可能反复轮询全局内存。
- push 的问题是 atomicAdd / atomicSub 多，后继更新冲突大。

可以做一个按结构切换的 hybrid：

```text
短行、依赖少、level 宽：pull
长行、后继少、贡献集中：push
同 pack 内依赖：shared-memory push/pull
跨 pack 依赖：global ready flag
```

更进一步，计算单位不一定是 row，而是 pack：

```text
row-level SpTRSV  ->  pack-level SpTRSV
```

每个 pack 内部用 warp 或 CTA 完成多个行，pack 之间只传递少量 ready 事件。

创新点：

> 把 SpTRSV 的依赖传播从 row-level 改成 pack-level，并在 pack 内自适应选择 push 或 pull。

为什么有价值：

- HCL 当前每行直接等 `x[colidx]`，粒度细。
- Split 当前通过 CSC/CSR kernel 做全局 atomic，粒度也偏细。
- pack-level 可以减少全局 ready 检查次数和 atomic 次数。

适合验证的矩阵：

- `finan512`：HCL solve 不占优，是验证 hybrid 是否改善的关键。
- `shipsec5`：长行和后半段重，是验证 long-row pack 的关键。
- `ss1`：低行非零但规模大，是验证 pack-level 调度开销的关键。

### 4.3 新调度方式：Wait-Cost Aware Warp Packing

HCL 当前 `vect_size` 只由行非零数决定：

```text
nnz_row -> 1/2/4/8/16/32 lane
```

这忽略了一个核心事实：SpTRSV 的成本不只是乘加，还有等待。

更合理的行成本应该是：

```text
cost(row) = compute_cost(row) + wait_cost(row) + memory_cost(row)
```

其中：

- `compute_cost` 来自行非零数；
- `wait_cost` 来自依赖深度、依赖距离、依赖行所在 pack；
- `memory_cost` 来自访问是否连续、是否跨 cache line、是否需要全局 ready。

调度器不应该只问“这一行用几条 lane 算”，还要问：

- 这几行放进同一个 warp 会不会互相等待？
- 这些行的依赖是否来自相邻 pack？
- pack 的 ready 事件是否足够少？
- 长行是否应该单独用一个 warp 或 CTA？

可以设计：

```text
Wait-Cost Aware Warp Packing

输入：CSR + level/dependency feature
输出：pack DAG + lane_width + row_perm
目标：最小化 estimated_solve_time
约束：依赖安全、warp 容量、同 pack 内可执行性
```

创新点：

> 把 warp packing 从 nnz-based 分桶升级为 wait-cost aware 调度。

为什么有价值：

- 这直接针对 HCL 的底层调度，而不是套一个外层 selector。
- 可以解释为什么 `finan512` 这类中等稀疏度矩阵 HCL 不一定最优。
- 可以用现有 wrapper 的 schedule checker 作为正确性约束来源。

### 4.4 新同步协议：Ready Flag 与数值分离

HCL multirow solve 当前用 `x` 的 bit pattern 作为 ready 状态：

```text
cudaMemset(x, 0xFF)
ready = __double2hiint(x[col]) != 0xFFFFFFFF
```

这很快，但从算法设计上不干净：

- 数值和状态耦合；
- 依赖 double bit pattern；
- 很难扩展 float、mixed precision、迭代 refinement；
- 也不方便表达 pack-level ready。

可以设计新的 ready 协议：

```text
ready[row] 或 ready[pack]
version[row] 或 epoch[row]
x[row] 只保存数值
```

如果做多 RHS 或重复求解，可以避免每次清空整个 `x`：

```text
ready_epoch[row] == current_epoch 表示本轮已完成
```

这样每次 solve 只增加 epoch，不必对 `ready` 或 `x` 做全量 memset。

创新点：

> 用 epoch-based ready protocol 替代 x-sentinel，全局 ready 粒度从 row 可升级到 pack。

为什么有价值：

- HCL 每次 solve 现在要 `cudaMemsetAsync(x, 0xFF, n*sizeof(double))`。
- 大矩阵和多 RHS 场景下，全量初始化本身会变成可见成本。
- pack-level ready 可以减少轮询次数。

风险：

- 多一个 ready 数组会增加内存访问。
- 必须通过实验比较 `memset x`、`ready memset`、`epoch` 三种方式。

### 4.5 新分段方式：不显式拆矩阵的 Logical Split

Split 当前 `split_dag` 显式生成 top/Mvp/bottom 三个矩阵，并可能转置。这个 analysis 成本很高。

可以改成逻辑分段：

```text
不复制非零
只记录每个 row/edge 属于 top、mvp、bottom
用 index view 或 edge range 执行
```

也就是：

```text
physical split -> logical split
```

执行时通过 DP-CSR 的 pack/edge metadata 选择需要处理的边，而不是重新构造三个 CSR/CSC。

创新点：

> 把 Split 的矩阵物理切分改成逻辑切分，避免 analysis 阶段大量复制、转置和子矩阵 level 重算。

为什么有价值：

- 直接针对 Split 的 `analysis_ms` 过高。
- 能保留 Split 的结构思想，但去掉最重的工程负担。
- 和 DP-CSR 可以自然结合。

### 4.6 新长行处理：Row-Adaptive CTA Kernel

HCL 的 lane width 最高到 32，也就是一个 warp 处理长行。对 `shipsec5` 这类 `nnz/n` 高的矩阵，某些行可能需要更强的并行度。

可以把行分三类：

```text
短行：多个行 packed 到一个 warp
中行：一个行一个 warp
长行：一个行一个 CTA，甚至多个 CTA 分段规约
```

关键不是简单加一个长行 kernel，而是让调度器决定哪些行值得切换：

- 行非零数；
- 行依赖是否已基本 ready；
- 长行是否在关键路径上；
- 长行后继数量。

创新点：

> 在同一个 SpTRSV 执行格式中混合 row-pack warp kernel 和 long-row CTA kernel。

为什么有价值：

- HCL 当前对所有长行最多给一个 warp。
- Split 在 `shipsec5` 的第二段 SpTRSV 很重，长行/重依赖行可能是关键瓶颈。

## 5. 更准确的主创新表述

如果按底层创新来定义，主线应改成：

> 面向 GPU SpTRSV 的依赖打包执行格式与等待代价感知调度方法。

英文可以写成：

> Dependency-Packed Execution Format and Wait-Cost-Aware Scheduling for GPU Sparse Triangular Solve.

它包含三项真正底层的贡献：

1. **Dependency-Packed CSR**

把 CSR、level、warp packing、ready slot、pack DAG 统一成 SpTRSV-specific execution format。

2. **Wait-Cost-Aware Warp/CTA Scheduling**

不再只按 `nnz_row` 分配 lane，而是按计算量、等待代价、访存连续性和依赖安全共同决定 pack。

3. **Pack-Level Ready Protocol**

把 row-level busy waiting 升级成 pack-level 或 epoch-based ready，同步状态和数值分离。

HCL、Split、cuSPARSE、MKL 在这个主线里只是：

- 对照基线；
- fallback；
- 或者局部执行 kernel 的候选。

它们不是创新本体。

## 6. 最推荐的主创新方向

### 6.1 推荐题目

可以把主创新命名为：

> 面向 GPU SpTRSV 的依赖打包执行格式与等待代价感知调度方法

或者更偏中文论文风格：

> 基于依赖打包存储和等待代价感知调度的 GPU 稀疏三角求解方法

英文表达：

> Dependency-Packed Execution Format and Wait-Cost-Aware Scheduling for GPU SpTRSV

### 6.2 核心创新点

主创新由三部分组成：

1. Dependency-Packed CSR

把普通 CSR 转换成直接服务 SpTRSV 执行的派生格式，统一保存 row order、pack、lane width、diag position、ready slot 和 pack-level dependency。

2. Wait-Cost-Aware Scheduler

基于计算量、等待代价、访存代价和依赖安全约束生成 warp/CTA pack，而不是只按行非零数分桶。

3. Pack-Level Synchronization

用 pack-level 或 epoch-based ready 协议替代 `x` 哨兵轮询，减少全局等待和全量初始化成本。

这三个部分组合起来，比单独优化某一个 kernel 更有说服力：

- 有正确性改进；
- 有性能改进；
- 能解释反例；
- 能兼容现代库基线；
- 能基于当前已有工程逐步实现。

## 7. 不建议作为主创新的方向

以下内容可以做，但不建议单独作为主创新：

1. 只把 Split 阈值调一遍。

这是经验调参，容易被认为不可泛化。

2. 只删除 `cudaMalloc/cudaFree`。

这是有效工程优化，但创新性不足。

3. 只修 HCL 的 volatile / shared memory bug。

这是重要修复，但更像正确性补丁。要升级成“依赖安全调度器”才更像创新。

4. 只比较四个方法然后选择最快。

这是 benchmark selector。如果没有结构模型和算法改进，创新性不够。

## 8. 建议实施路线

### 阶段 1：结构特征提取

新增脚本统计每个矩阵的结构特征：

- `n`
- `nnz`
- `nnz/n`
- `diag_filled`
- level 数量；
- 每 level 行数分布；
- 每行非零分布；
- 依赖距离分布；
- HCL schedule diagnostic；
- Split top/mvp/bottom nnz 比例。

目标是把“为什么某矩阵谁快”变成可量化特征。

### 阶段 2：DP-CSR 原型

先不改所有 kernel，先生成一个 CPU 侧 DP-CSR metadata：

最小可行目标：

- `row_perm`
- `pack_ptr`
- `lane_width`
- `diag_pos`
- `pack_dep_count`
- `pack_dep_ptr`

并用 checker 验证：

- 不漏行；
- 不重复行；
- 不产生非法依赖顺序；
- pack 容量合法。

### 阶段 3：wait-cost 调度器

先实现启发式版本：

- 基础成本：`nnz_row`
- 等待成本：依赖行所在 pack 距离
- 访存成本：row 非零连续性和行长度
- 约束：无 non-prior dependency

### 阶段 4：pack-level solve kernel

在 HCL multirow kernel 基础上改：

- 从 `iorder/ibase_row/ivect_size_warp` 改读 DP-CSR pack metadata。
- 从 `x` 哨兵改成 `ready` 或 `ready_epoch`。
- 先只支持 warp pack，长行 CTA 作为第二步。

### 阶段 5：logical split 和长行 CTA

验证要分三类矩阵：

- HCL 原本强的矩阵；
- HCL 原本不稳定或失败的矩阵；
- Split 或 MKL 能反超 HCL 的矩阵，例如 `finan512`。

指标：

- `status=ok` 比例；
- `analysis_order_error` 消除情况；
- `analysis_ms`；
- `solve_ms`；
- `total_1_ms / total_10_ms / total_100_ms`；
- Split 内部 breakdown；
- selector 命中率。

## 9. 当前最有价值的下一步

最值得马上做的是：

1. 写结构特征提取脚本。
2. 对已有 CSV 自动生成“矩阵结构 -> 方法表现”的对照表。
3. 生成 DP-CSR metadata 原型，不先改 GPU kernel。
4. 用 checker 验证 DP-CSR 的依赖安全性。
5. 再把 HCL multirow kernel 改成读取 DP-CSR pack metadata。

这样做的好处是：先用数据证明创新点确实对应瓶颈，再动代码，避免盲目优化。

## 10. 一句话总结

当前代码里最值得发展的创新点是：

> 不是把 HCL-Fing、Split_SpTRSV、cuSPARSE、MKL 简单组合，而是从 SpTRSV 的底层执行表示出发，设计 Dependency-Packed CSR、等待代价感知 warp/CTA 调度和 pack-level ready 协议，让存储、调度、计算和同步共同服务于 GPU 稀疏三角求解。

这个方向既能继承 HCL 当前的性能优势，也能解释和处理 HCL 不稳定、Split analysis/transfer 过重、MKL/cuSPARSE 在部分矩阵上很强这些现实问题。更重要的是，它的创新核心在底层计算组织方式，而不是外层方法选择。
