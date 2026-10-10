# 测试转换框架搭建工作规范

## 1. 项目目标

Swepro_test_trans的目标是将 SWE-Bench Pro v2 中的 historical F2P 测试转换为面向功能行为的 functional verifier，而不是验证某一种特定参考实现。

转换后的 verifier 应优先检查：

- public API；
- observable output；
- externally visible state change；
- externally observable error semantics。

应尽量避免不必要地绑定：

- private helper；
- 内部状态；
- Gold-specific 文件结构；
- Gold-specific algorithm；
- mock call shape；
- 其他 implementation detail。

基本原则：

- historical F2P 定义本次转换的 scope，即“哪些行为需要被转换和验证”；
- P 中即使明确命名了新类型，也不能单凭 P 增加 historical F2P 未覆盖的测试；只有已有 F2P 的行为义务涉及该类型时，才在转换中保留其行为检查。
- Problem Statement 定义功能语义边界；
- Requirements / Interface 与 historical tests 属于 construction evidence，需要结合仓库事实审慎参考；
- Gold 是一个已知正确实现，可用于 construction 和 validation evidence，但不得反向成为 specification；
- 不得因为 Gold 中存在某种实现方式，就把该实现方式写进 verifier；
- 不得仅因为 Problem Statement 中存在额外行为，就新增没有 historical F2P seed 支持的测试要求。
- 审计提出 `mapping_gaps` 或 `under_conversion` 时，必须指出具体的 source F2P selector、原始断言和转换后缺失的同一行为；仅由 P 描述、但没有任何历史 F2P 断言覆盖的行为属于本次转换范围之外，即使 trace 把它列为 obligation 也不能要求新增测试。
- 不得从 P 推导出比历史 F2P 实际触发或观察的行为更宽的转换后置条件。例如，缓存恢复测试覆盖异常处理和通知时，不能仅依据 P 的“继续正常操作”再要求增加浏览请求不被拦截的测试。
- 断言“已变化 / 已注册 / 已更新”等决策结果后，还要确认被观察的最终副作用确实受该结果控制，或只消费已注册的对象；测试替身无条件执行、默认处理全部输入所产生的结果，不能单独证明该决策正确。
- 对映射或结果字典，除非有效 Problem Statement 明确要求闭合的精确结果，否则不要把整个结果与夹具字典精确比较；逐项断言 P 要求的可观察字段和值，并保留 P 允许的额外字段。

对每条 historical F2P，按以下顺序处理：

- P 已描述的新功能：改写到公共或可观察边界；
- P 未描述、但 Base 已经具有的公开产品行为：保留为 converted regression，不扩写 P；
- P 未描述、Base 也缺失的重要产品行为：补充最小行为级 P，再改写测试；
- 剥离实现机制后只剩 Gold 新类、方法、私有字段、缓存、mock 形状或测试 plumbing：才允许有证据地排除。

## 2. Failure Classification

遇到失败时，先收集 evidence，再分类。不要看到失败就立即修改 verifier 或框架。
判断 scope：

```text
instance-specific
framework-level
```

### instance-specific

如果问题只来自当前 repo、当前构建方式、当前数据特征或当前任务本身，并没有足够证据说明它能够泛化到其他任务：

- 记录问题；
- 在当前任务范围内处理；
- 不污染通用框架。

### framework-level

只有当 evidence 表明问题来自 VerifierTrans 的通用能力缺失或错误，并且合理预期会影响其他任务时，才允许修改共享框架。

单个 instance 在修改后能够通过，本身不能证明该修改属于 framework-level repair。


## 3. 通用框架修改规则

严禁使用以下信息做硬编码特判：

- `instance_id`；
- repo 名称；
- exact commit；
- 当前 historical test 的具体名称；
- 当前任务特有路径；
- 当前任务特有 artifact 名称。

共享框架修改应体现可泛化能力，具有跨任务意义。

在修改共享框架前，应能够回答：

1. 当前观察到的现象是什么？
2. 根因是什么？
3. 为什么这不是当前 instance 的偶然特性？
4. 修改后的规则如何适用于其他任务？没有引入退化？

如果无法回答，应继续调查，不要仓促修改共享框架。


## 4. 转换流程

每个新的任务默认从：读取已验证的任务数据开始。

不要默认复用旧 attempt。

使用单一 Converter，但区分两个工作模式：

```text
BUILD
  首次生成 functional verifier

REPAIR
  根据 Judge、Hard Validator、replay 或 QA evidence 修复 verifier
```

Converter 可以按需探索完整仓库和允许使用的 construction evidence，但必须对所有 historical F2P seed 做逐条 accounting。

每个 verifier revision 应保持以下 gate 顺序：

```text
Semantic Judge
↓
Deterministic Hard Validator
↓
Base / Gold converted-F2P replay
↓
Base / Gold P2P replay
↓
Stability check
```

后面的 gate PASS 不能作为跳过前面 gate 的理由。


## 5. Functional Verifier 转换原则

转换的目标不是简单重写原测试语法，而是保留原 historical F2P 的行为意图，同时尽量摆脱 implementation binding。

优先寻找能够从真实 public / observable surface 触发和观测行为的方式，例如：

- public API；
- CLI；
- HTTP / service interface；
- 文件输入输出；
- externally visible state；
- observable exception / error；
- 用户可见输出。

避免仅为了复现原 F2P 而直接断言：

- private method；
- private field；
- internal cache；
- 内部容器内容；
- mock call count / exact call shape；
- Gold 新增的内部文件或 helper；
- 只对某个实现路径成立的内部状态。

如果某个 symbol 本身就是产品真实公共契约，则可以验证它；“出现在 Gold 或 historical test 中”本身不足以证明它是公共契约。若 P 要求适当的用户可见错误但未指定措辞，检查触发后新发的消息是否与故障相关，并至少用两种合理改写和一种本地化/不同表达作正向反事实；用无意义泛化文案和关键词堆砌作负向反事实。语法极性必须按语义判断（禁止式 modal prohibition）：对于空主机列表，`Hosts must not be empty` / `Hosts may not be empty` 是有效的禁止式说明，不能仅因出现 `not` 就判为否定错误；`Hosts are not empty` 才是对当前空输入作出相矛盾的事实陈述。P 的标题或正文明确要求新增的公共类／类型属于任务契约；即使 Base 旧入口已经能产生部分相同输出，也不能把这个新增契约一概归为实现细节或据此宣称任务没有功能差异。verifier 应对该类型做行为验证，而不只是检查名称存在。P 没规定的模块路径、工厂方法、构造参数和内部表示仍不得从 R/I/Gold 偷渡为唯一正确接口；若必须指定访问方式，应先确认其公共契约依据，或设计容纳多种公开访问方式的测试，并在审计中记录。


### Historical P2P 保留边界

原始 `tests/config.json` 中的 `pass_to_pass` 是已确认的回归集合，转换时必须逐项、按原顺序、原 selector 字符串保留。不得改名、映射到类限定节点、删除、排除或在 P2P 账本中另造替代 selector。Converter 只改写 historical F2P；由 F2P 转换出的 Base 回归可以追加到原始 P2P 列表之后，但不能改变原列表本身。原始 P2P 在 Base/Gold 重放中失败时，记录为任务/环境证据，不能通过改写 P2P 来消除失败。

`conversion_trace.json` 的 `p2p_accounting` 使用 `policy: preserve_original_verbatim` 和空的 `excluded` 列表。P2P 账本不能含有 `retained` 重映射、P2P 转换回归或排除记录。

## 6. Positive QA

Core verifier 通过后执行 Positive QA。

Positive candidate 应是：

> 功能正确，但实现结构相对于 Gold 有明显差异的 alternative implementation。

Candidate 必须先经过 deterministic precheck，再进入 LLM Solution Judge。

一个 VALID Positive 至少需要满足当前任务定义的 acceptance 条件，例如：

- current verifier PASS；
- P2P PASS；
- Solution Judge 判定 VALID；
- historical F2P replay 已执行并记录。

historical F2P 在 Positive 上 PASS 或 FAIL 可以作为 evidence 记录，但不得单独决定 Positive validity。

Positive QA 的目的，是检查当前 verifier 是否错误地把 Gold 的实现结构当成唯一正确答案。


## 7. Negative QA

Negative candidate 应是 near-correct mutant：

- 每个 mutant 尽量只违反一个明确的 F2P functional semantic；
- unrelated behavior 尽量保持正确；
- 必须能够明确说明它违反了哪一条功能语义；
- 应先通过 candidate deterministic precheck，再进入后续判断。

qualified Negative 必须被当前 verifier 拒绝。

每条任务确认 1 个命中已转换 F2P 功能语义的 qualified Negative 即可；
max_mutation_attempts 是寻找这 1 个合格样本的重试上限，不代表必须确认多个 mutant。

Negative QA 的目的，是确认 verifier 不只是“宽松到什么都能过”，而确实能够区分关键功能错误。


## 8. Repair Routing

如果 evidence 表明是：

```text
verifier semantic issue
```

则回到：

```text
Converter REPAIR
```

不要通过修改 runner、Docker、路径或 framework 逻辑去掩盖 verifier semantic 问题。

如果 evidence 表明问题来自：

```text
path
Docker
artifact
schema
module-root
service bootstrap
execution environment
packaging
等等
```

则：

1. 先完成 failure classification；
2. 判断是 instance-specific还是framework-level ；
3. 只有 framework-level 才修改共享框架；
4. 尽量复用已有 artifact / candidate；
5. 从最早必要阶段恢复，不无条件全部重跑；
6. 不得把 infrastructure failure 误判成 verifier semantic failure。


## 9. Framework Issue 文档

每发现并确认一个 framework issue，或完成一个 framework repair，都应在：

```text
process/
```

写入带 UTC 时间戳的 Markdown 记录。

至少记录：

```text
现象
关键 evidence
failure classification
根因
为什么属于 framework issue
影响范围
通用修复
修改文件
验证方法
测试结果
残余风险
```

如果只是 instance-specific / repo-specific / data-specific 问题，也可以记录，但必须明确标注其 scope，不得据此向共享框架加入特判。


## 10. Progress Reporting

不要逐条汇报无意义的 shell command。

应在有实质信息的节点进行汇报，例如：

- Prepare / Preflight 结果；
- Semantic Judge PASS / FAIL；
- Hard Validator PASS / FAIL；
- Base / Gold replay 结果；
- P2P 结果；
- verifier revision 变化；
- Positive / Negative QA 结果；
- failure classification；
- confirmed framework issue；
- framework repair；
- final acceptance status。

推荐简洁格式：

```text
当前阶段:
状态: PASS | FAIL | RUNNING
关键 evidence:
failure category:
scope:
是否修改框架:
下一步:
```

如果只是长时间运行的命令，可以在有状态变化或出现 blocker 时再汇报。


## 11. 安全与边界

除非当前任务获得明确授权，否则：

- 不输出 `.env` 或其他 secret；
- 不在日志、报告、测试输出中打印 API key；
- 不删除无关 Docker container / image；
- 不删除其他任务的 runs；
- 不删除旧项目或无关工作目录；
- 不修改当前任务授权范围之外的资源。

清理资源时，只清理能够确认由当前任务创建且不再需要的临时资源。


## 12. Acceptance 原则

不得为了宣布成功而弱化验收条件。

如果任务未满足当前 Goal 中的全部 success criteria：

- 如实标记为未完成或 blocked；
- 列出已完成 gate；
- 列出失败 gate；
- 给出关键 evidence；
- 说明 blocker；
- 说明继续执行需要什么；
- 不通过降低标准、跳过 QA 或放宽 verifier 来制造“成功”。

最终目标始终是：

> 通过真实 SWE-Bench Pro 任务检验 VerifierTrans 的转换质量和通用性，只把具有跨任务意义的问题沉淀为共享框架能力，而不是为了让单个 instance 特判通过。

## 13. F2P 功能分类与自动规范补充（2026-09-30）

每条 F2P 必须先判断其背后的行为是否是用户可观察、且属于任务要实现的功能：

1. 功能已由 P 支持：通过公开接口或输出 `rewrite`/`merge`；
2. P 没有把它作为本次新增要求、但 Base 已经通过公开边界提供该行为：使用 `base_regression_behavior` 保留为 converted regression，不扩写 P；
3. 功能重要、P 没写且 Base 缺失：记录行为级 `specification_gap`，由 controller 自动生成 `specification_addendum.md`，下一轮继续转换，并在最终 instruction 中保留该补充；
4. 纯 Gold/历史实现细节：允许 `drop`，但必须提供 `drop_justification` 和 `drop_evidence`；
5. 不能仅因没有同名 API、使用了新 class、constructor 或 helper 就 drop；应先恢复行为或补充功能语义；
6. 不能仅因相似行为已被另一条 F2P 或 P2P 覆盖就 drop；重复行为应使用 `merge` 映射到共享的公开边界测试，独立边界条件应保留为专门测试。只有剥离实现机制后不剩任何可观察行为时，才属于可 drop 的纯实现细节。

`specification_gap` 是自动 enrichment 状态，不是人工停机状态。最终验收允许有证据的实现细节 drop，但不允许未解释 drop、未解决 gap、漏记 F2P 或隐含实现契约。

## 14. 2026-09-30 自动恢复与规范补充规则

本轮验证后，流程增加三条通用规则：

1. `problem_statement_support` 明确承认行为不在 P 中时，controller 自动把 `behavior_intent` 或 `specification_proposal` 提升为行为级 addendum；下一 revision 必须据此使用公开边界验证。已有合规 addendum 时不重复触发 enrichment。
2. Semantic Judge 的输入包含 addendum，并要求任何 P 缺失行为必须由 addendum 明确补足；addendum 不得出现新 API、模块路径、签名或 Gold 细节。
3. QA agent 在写出完整 patch 和 metadata 后即使达到步数上限，runner 也会恢复候选并继续 Docker replay/Judge；完整候选工件是可恢复交接，不能绕过后续质量门槛。

Acceptance 使用被选 revision 的 `conversion_trace.json`，而不是空的 attempt 初始化 trace。多条历史 F2P 合并为一个功能测试是允许的，前提是每条原始 F2P 都有行为意图、证据、决策和 emitted-test 映射；只有纯实现细节才允许带理由和证据的 `drop`。

## 15. 功能增量与转换回归的确定性分桶（2026-10-03）

Converter 对 `base_behavior_status` 的声明不是最终证据。Hard replay 后必须读取 Base 的逐 selector 结果并自动分桶：

- `functional_delta`：P 支持的公开行为，独立 emitted selector 在 Base 上 `FAILED`、在 Gold 上 `PASSED`；
- `converted_regression`：historical F2P 中的公开产品行为在 Base 上已经 `PASSED`，转换后继续保留，但不算新功能增量；
- `pending_specification`：重要产品行为等待最小行为级 addendum；
- `excluded_implementation`：有证据证明不含独立产品语义的实现细节。

一条 emitted selector 不得同时服务于 `functional_delta` 和 `converted_regression`，否则某个增量断言失败会掩盖回归断言是否真正通过。应拆成可独立执行、可独立归因的测试场景。

发布规则：

- `convertible` 至少需要一个 replay 证明的 `functional_delta`；
- 如果所有保留行为都是 `converted_regression`，任务标记为 `non_discriminative_task`，不得为了制造 Base FAIL 而重新引入 Gold-only API；
- converted regression 仍属于 historical F2P 转换账本和最终 verifier 的必测范围；在 trace 中与原始 P2P 分开记账，在最终 Harbor config 中追加到原始 `pass_to_pass` 列表之后；原列表必须逐项原样保留；
- acceptance 必须要求行为角色审计通过，不能只依赖整个测试进程的 Base FAIL / Gold PASS。

## 16. 最终 Harbor selector 角色与审计协议（2026-10-03）

Historical F2P 是转换输入账本，不等于最终 `fail_to_pass` 清单。Controller 必须由 trace 派生最终 config：

- `changed_or_missing` selector 进入 `fail_to_pass`；
- `already_satisfies` / `base_regression_behavior` selector 追加到保留的原始 `pass_to_pass`；原始 P2P selector 不得重写或排除；
- 两组 selector 不得重叠；
- artifact contract、stability、acceptance 和 final audit 使用同一派生规则。

Semantic Judge 位于 hard replay 之前，不能仅因 replay 为 `not_run` 而拒绝。它必须收到完整 `config.json`、`test.sh`、`run_script.sh`、parser、静态测试源码和顶层 `p2p_accounting`。Judge transport/JSON 协议失败重试同一 revision，不进入 Converter repair。

结构化 replay 结果以 `tests[{name,status}]` 为契约，文件可命名为 `output.json` 或 `parsed_results.json`；跨语言状态 `PASS/PASSED/OK` 与 `FAIL/FAILED/FAILURE` 分别规范化。

