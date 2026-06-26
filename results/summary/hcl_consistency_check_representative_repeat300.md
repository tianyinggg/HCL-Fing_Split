# HCL-Fing 一致性核查：Split 五矩阵扩展 vs repeat300

核查对象：

- `finan512`
- `thermomech_dK`
- `shipsec5`

输入文件：

- `results/csv/suitesparse_split_flip_extended_benchmark.csv`
- `results/csv/representative_repeat300_benchmark.csv`
- `results/csv/hcl_schedule_diagnostics_suitesparse_batch1.csv`
- `results/csv/hcl_schedule_diagnostics_suitesparse_final_large.csv`
- `data/meta/*.json`
- `logs/hcl_fing/*_benchmark_split_flip_extended.log`
- `logs/hcl_fing/*_benchmark_repeat300.log`

本核查只比对已有 CSV、meta 和日志，不重新跑 benchmark。

## 1. 结构字段一致性

| matrix | split_flip_extended n | repeat300 n | meta n | split_flip_extended nnz | repeat300 nnz | meta nnz | split_flip_extended diag_filled | repeat300 diag_filled | meta diag_filled | 是否一致 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| finan512 | 74752 | 74752 | 74752 | 335872 | 335872 | 335872 | 0 | 0 | 0 | 是 |
| thermomech_dK | 204316 | 204316 | 204316 | 1525272 | 1525272 | 1525272 | 0 | 0 | 0 | 是 |
| shipsec5 | 179860 | 179860 | 179860 | 5146478 | 5146478 | 5146478 | 0 | 0 | 0 | 是 |

结论：两个 benchmark CSV 和 `data/meta` 的 `n`、`nnz`、`diag_filled` 完全一致。

## 2. HCL 状态与调度依赖计数

| matrix | split_flip_extended HCL status | split_flip_extended same_warp_dependencies | split_flip_extended non_prior_warp_dependencies | repeat300 HCL status | repeat300 same_warp_dependencies | repeat300 non_prior_warp_dependencies |
|---|---|---:|---:|---|---:|---:|
| finan512 | ok | 空 | 空 | analysis_order_error | 0 | 72 |
| thermomech_dK | ok | 空 | 空 | analysis_order_error | 313 | 969 |
| shipsec5 | ok | 空 | 空 | analysis_order_error | 367 | 43748 |

说明：

- `suitesparse_split_flip_extended_benchmark.csv` 中 HCL 行为 `status=ok`，没有写入 `same_warp_dependencies` 或 `non_prior_warp_dependencies` 字段，因为统一结果 schema 没有这两个字段；成功行也没有把调度检查计数写入 `error`。
- `representative_repeat300_benchmark.csv` 中 HCL 行为 `status=analysis_order_error`，依赖计数写在 `error` 字段中。
- 两个 `hcl_schedule_diagnostics_*.csv` 均不包含这三个矩阵，因此无法从诊断 CSV 直接对比这三个矩阵的历史依赖计数。

## 3. hcl_schedule_diagnostics_*.csv 覆盖情况

| diagnostics 文件 | 是否包含 finan512 | 是否包含 thermomech_dK | 是否包含 shipsec5 |
|---|---|---|---|
| `hcl_schedule_diagnostics_suitesparse_batch1.csv` | 否 | 否 | 否 |
| `hcl_schedule_diagnostics_suitesparse_final_large.csv` | 否 | 否 | 否 |

结论：现有 HCL 诊断 CSV 没有覆盖这三个矩阵。当前能直接比对的是两个 benchmark CSV 的 HCL 行，以及对应 HCL 日志。

## 4. 是否使用了不同 csrbin/meta

没有证据表明使用了不同 csrbin/meta。

`data/meta` 当前记录：

| matrix | source | triangular | index_base | value_type |
|---|---|---|---:|---|
| finan512 | `/home/HCL-Fing_Split/data/raw_mtx/finan512.mtx` | lower | 0 | double |
| thermomech_dK | `/home/HCL-Fing_Split/data/raw_mtx/thermomech_dK.mtx` | lower | 0 | double |
| shipsec5 | `/home/HCL-Fing_Split/data/raw_mtx/shipsec5.mtx` | lower | 0 | double |

两个 benchmark CSV 中的 `n`、`nnz`、`diag_filled` 与 meta 完全一致，因此状态差异不是因为本轮换了矩阵规模、换了 lower CSR，或补对角规则不同。

## 5. HCL status 为什么不同

当前最合理解释：

```text
HCL-Fing analysis 对同一 csrbin 的调度生成存在运行间不稳定或未完全确定性。
```

证据：

- 同一矩阵在两个 benchmark CSV 中结构字段完全一致。
- repeat300 的 HCL 日志明确显示 `analysis_order_error`，并给出非零依赖违规计数。
- `suitesparse_split_flip_extended_benchmark.csv` 中同一矩阵曾经 `status=ok`，残差通过。
- `bauru5727` 之前也出现过 quick 通过、benchmark 触发 `analysis_order_error` 的情况，说明这不是第一次出现同一矩阵跨运行状态变化。

这更像 HCL analysis 阶段的调度生成有 nondeterminism/race/未初始化/顺序敏感问题，而不是输入矩阵变了。

## 6. 是否因为之前未启用调度检查

仅凭 CSV 不能 100% 证明当时二进制是否启用了调度检查，因为成功行不会写出 `same_warp_dependencies=0` 这样的显式证据。

但从工程状态和日志看，更可能不是“之前未启用检查”：

- 当前 HCL wrapper 的逻辑是在 analysis 后、solve 前执行调度检查。
- 如果调度检查失败，写 `status=analysis_order_error` 并跳过 solve。
- `suitesparse_split_flip_extended_benchmark.csv` 的 HCL 行是 `status=ok` 且有 residual，说明当次运行进入并完成了 solve。
- 对应日志只有 `status=ok` 和 residual，没有 `analysis_order_error`。

因此更合理的判断是：

```text
五矩阵扩展那次 HCL analysis 生成的调度通过了检查；
repeat300 这次同一输入下生成的调度没有通过检查。
```

如果要完全排除“旧二进制未启用检查”的可能，需要有当时二进制 hash 或当时编译日志；当前文件里没有这类证据。

## 7. 结论

| 问题 | 核查结论 |
|---|---|
| n 是否一致 | 一致 |
| nnz 是否一致 | 一致 |
| diag_filled 是否一致 | 一致 |
| hcl_non_prior_warp_dependencies 是否一致 | 无法直接判断；旧 ok 行没有记录该字段，repeat300 明确非零 |
| hcl_same_warp_dependencies 是否一致 | 无法直接判断；旧 ok 行没有记录该字段，repeat300 明确记录 |
| HCL status 为什么不同 | 最可能是 HCL analysis 调度生成存在运行间不稳定 |
| 是否因为之前未启用调度检查 | CSV 不能完全证明；但工程证据更支持“之前检查通过，本轮检查失败” |
| 是否因为本轮使用了不同 csrbin/meta | 否；结构字段和 meta 完全一致 |

建议后续如果继续研究 HCL-Fing：

- 对每次 HCL 成功行也写出 `same_warp_dependencies=0`、`non_prior_warp_dependencies=0`，避免后续无法核查。
- 对 HCL analysis 输出加 hash，例如 `iorder`、`jlev` 或 warp 调度摘要 hash。
- 对同一矩阵连续运行 HCL analysis 多次，只做调度检查，不做 solve，确认是否 nondeterministic。
