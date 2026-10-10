# SWE-bench Pro OS v2：实验目标、三阶段框架与首轮结果

> 2026-10-08 11:40 CST 首轮实验快照。本文只讨论 Stage 1 选定并预检的 100 条任务、Stage 2 首批完成转换与审计的 20 条任务，以及 Stage 3 对这 20 条任务的首次验证。统计以本轮冻结任务、补丁和统一交叉复判结果为准。

## 1. 实验要回答什么

官方任务给 solver 的 instruction 包含问题描述（下称 P）、Requirements（R）和 New Interfaces（I）；历史 verifier 由 fail_to_pass（F2P）和 pass_to_pass（P2P）测试构成。R/I 或历史测试可能固定某个实现路径、接口、文案或内部结构，使满足 P 的其他实现被拒绝。本实验尝试把历史 F2P 转成基于公共可观察行为的 functional verifier，并比较两种 instruction 和两套 verifier 对模型补丁的影响。

研究问题有两个层次：**生成条件**——移除 R/I 后，同一模型与 agent 会生成什么补丁；**判定条件**——对同一份补丁，原始 verifier 与 functional verifier 为何给出不同结果。预期的“旧测试拒绝、新测试接受”只是待审查现象，不能直接等同正确解增加；“旧测试接受、新测试拒绝”也不能自动认定新测试有错。补丁语义、P 依据和测试覆盖范围必须逐例核查。

本框架的基本边界是：P 为基础规范；R/I、Gold、历史测试、仓库与环境是转换时理解行为的证据，不能单独变成新正确性要求。转换范围由历史 F2P 限定，原始 P2P selector 字符串和顺序保留。历史 F2P 中若确有 P 遗漏的重要产品行为，控制器可生成经门禁检查的行为级 addendum，进入最终 instruction；这类任务在 Stage 3 中与“仅删 R/I”分层报告。新 verifier 旨在检验其重述的历史行为，实际实现仍可能误收、误拒或改变覆盖深度，需由 QA 和交叉实验检验。

### 1.1 总体 Pipeline

~~~text
┌──────────────────────────────────────────────────────────────┐
│ 官方 SWE-bench Pro OS v2：数据行 + Harbor 任务 + 官方镜像  │
└─────────────────────────────┬────────────────────────────────┘
                              ▼
┌──────────────────────────────────────────────────────────────┐
│ STAGE 1  数据准备                                            │
│ 选样 → 固定来源/镜像 → 原始 Base FAIL、Gold PASS → 总审计    │
│ 输出：original/、P-only source、READY（100/100）             │
└─────────────────────────────┬────────────────────────────────┘
                              │ READY
                              ▼
┌──────────────────────────────────────────────────────────────┐
│ STAGE 2  功能 verifier 转换                                 │
│ 历史 F2P 逐条追踪 → 公共行为测试；原始 P2P 原样保留         │
│ 多轮 revision：结构/语义/回放/稳定性/正负 QA → 打包与复审   │
│ 输出：final/ + 合格清单（本轮 20 项）                        │
└─────────────────────────────┬────────────────────────────────┘
                              │ 冻结原始/转换后任务及 attempt
                              ▼
┌──────────────────────────────────────────────────────────────┐
│ STAGE 3  比较实验                                           │
│ 原 instruction → patch O ─┬─ 旧、新 verifier                │
│ 新 instruction → patch F ─┴─ 旧、新 verifier                │
│ 每份同一 patch 双复判 → 四格矩阵 → 逐条语义审查             │
│ 输出：冻结结果、解释边界、返回 Stage 2 的缺陷证据          │
└──────────────────────────────────────────────────────────────┘
~~~

## 2. Stage 1：固定官方任务和可执行 oracle

### 2.1 方法与核心设计

**选样与固定来源。** Stage 1 要先形成一批可追溯、可重放的原始任务。选样脚本保留通过原始 oracle 的 pilot，再按语言配额和仓库分布补足 100 条；Python、Go、JavaScript 各纳入 2 条官方 HARD。非 HARD 候选按 Gold patch 增加行数分散选取，是为了覆盖不同补丁规模，**不把补丁行数当作难度或模型成功率**。每条任务固定官方来源 commit，保存原始 Harbor task、数据行与任务树 hash、P-only source，以及镜像 digest。这样后续转换和评测可以追溯到同一份任务与环境。

**验证原始 oracle。** 在每条任务的官方镜像中，用同一份原始 `tests/test.sh` 分别回放未修复的 Base 和应用官方 Gold patch 的 Gold。预期是 Base FAIL、Gold PASS：前者说明旧测试确实会拒绝这个未修复版本，后者说明原始任务至少有一个可通过的参考实现。如果任一方向不满足，记录该 ID 并替换，再对补选任务重做准备、镜像与预检；最终总审计还核对 100 个唯一 ID、配额、来源 hash、镜像和逐任务回放结果。这是原始 verifier 的基本有效性门禁，**并不证明 Gold 是唯一正确解**；执行路径是本地 Docker 回放，不是 Stage 3 的完整 Harbor solver rollout。

### 2.2 Pipeline

~~~text
官方 V2 数据行 + 任务来源 commit + 语言/HARD 配额
                         │
                         ▼
               ① SELECT [SCRIPT]
               保留 pilot、选满 100 项并记录理由
                         │
                         ▼
               ② PREPARE [SCRIPT]
               稀疏检出 v2/tasks/<id>
               冻结 tasks/<id>/original/
               保存数据行/任务树 hash 与 P-only source
                         │
                         ▼
               ③ IMAGE [DOCKER]
               复用或拉取官方任务镜像，记录 digest
                         │
                         ▼
               ④ ORIGINAL ORACLE [DOCKER]
               同一原始 tests/test.sh 分别回放
                   ┌─────┴─────┐
                   ▼           ▼
                 Base         Gold
              不打补丁     打原 Gold patch
              必须 FAIL      必须 PASS
                   └─────┬─────┘
                         │
             未满足 ──────┴─────→ 记 rejected ID
                         │        → 补选、准备与预检
                     全部满足
                         ▼
               ⑤ FINAL AUDIT [SCRIPT]
               100 个唯一 ID；配额/任务集合；
               来源 hash、镜像 digest、Base/Gold 结果
                   │                 │
                 FAIL              PASS
                   │                 │
                   └→ 修复/替换     ▼
                              STAGE 1 READY
                              original/ + source + preflight
~~~

### 2.3 结果与指标

[Stage 1 总审计](../../data/stage1/final_100_report.json)记录 `selected_count=100`、`ready_count=100`、状态 `READY`：100/100 个选定任务均在原始测试下 Base FAIL、Gold PASS。语言分布为 Python 40、Go 36、JavaScript 22、TypeScript 2；其中 HARD 任务共 6 条，Python、Go、JavaScript 各 2 条。官方任务来源固定在[准备脚本](../../dataprepare/prepare_swebench_pro_v2.py)所用 commit `66f92766bba642462d4bbe5479e83f91f9211862`。这些数字表示 100 条任务具备进入转换阶段的条件，**不是** Stage 2 已合格数量。

**核心实现。** 选样（固定结果见 `task_list/selected_100.txt` 与 `task_list/selection_report.json`）、[镜像准备](../../dataprepare/pull_selected_images.py)、[Base/Gold 预检](../../dataprepare/preflight_selected.py)、[全量审计](../../dataprepare/audit_stage1.py)。输入与输出分别位于 `tasks/<id>/original/`、`data/stage1/<id>/source/`、`data/stage1/<id>/preflight/`；Stage 2 初始化后，共享 source 被移到 `runs/<id>/source/`，original 保持不变。

## 3. Stage 2：把历史测试转换为功能判定

### 3.1 方法与核心设计

**先划清规范与证据。** Stage 2 从 Stage 1 的 READY 任务中取首批 20 条转换。原 instruction 的问题描述 P 是新任务的基础规范；Requirements（R）、New Interfaces（I）、原 F2P/P2P、Gold、Base 仓库和环境可以帮助理解旧测试，却不能仅凭自身成为新增正确性要求。转换范围也由历史 F2P 限定，不能顺手给原 F2P 未覆盖的 P 条款补测。原始 P2P 的 selector 字符串和顺序保持不变，以保留已有回归保护。

**逐条决定历史 F2P 的去向。** 转换器为每个旧 selector 在 `conversion_trace.json` 中写明原断言、对应行为、P 依据、公共观察面和新测试去向。P 支持且 Base 未满足的行为写成 functional delta；Base 已满足的真实产品行为可改为 converted regression，并与原始 P2P 分开记录。若旧测试涉及 P 未明说但重要的产品行为，先提出 specification gap，由控制器审核行为级 addendum，加入最终 instruction 后再生成相应测试。只固定私有调用、Gold 结构或无独立产品效果的断言，可以有证据地丢弃。这个分类让每条旧 F2P 都有可审查的去向，同时避免把历史实现方式直接搬进新 verifier。

**多层门禁检验“既能分辨，又不过度绑定”。** 每次 revision 先查文件与 selector 映射、P 依据和测试语义；再在干净容器中要求新 verifier 对 Base FAIL、对 Gold PASS，并重复回放以检查稳定性与原始 P2P。正向 QA 尝试构造不同于 Gold、仍满足 P 的实现，要求新 verifier PASS，用来暴露对 Gold 路径的过度绑定；负向 QA 构造相关且非等价的近正确错误实现，要求新 verifier FAIL，用来暴露漏测。失败生成结构化反馈并进入新 revision。只有同一 revision 的门禁、正式打包、final audit 和框架外独立审计都通过，才列入首批合格清单。有限的正负 QA 只是缺陷探针，不代表穷举所有实现。

### 3.2 Pipeline

~~~text
STAGE 1 READY：P / R / I / F2P / P2P / Gold / Repo / Env
                              │
                              ▼
                  ① INIT → attempt_NNN
                  original/ 不变；source 固定
                              │
                              ▼
             ┌────── Converter revision loop ──────┐
             │                                      │
             ▼                                      │
  ② FUNCTIONAL CONVERTER [mini-swe-agent]           │
     P 为基础规范；R/I/Gold/原测试等仅作构造证据     │
     逐条 F2P：原意 → P 依据 → 公共可观察行为        │
     识别实现绑定；保留原始 P2P selector 与顺序     │
     提交测试、conversion_trace、自审、manifest     │
             │                                      │
             ▼                                      │
  ③ ARTIFACT CONTRACT [SCRIPT]                     │
     文件/schema、F2P accounting、P2P 不删改        │
     P 遗漏重要历史行为？→ 行为级 addendum           │
                           → 新 revision ──────────┤
             │ PASS                                 │
             ▼                                      │
  ④ SEMANTIC REVIEW [Judge + deterministic checks] │
     P 支持、可观察效果、Gold/私有接口绑定          │
             │ PASS                                 │
             ▼                                      │
  ⑤ HARD REPLAY [DOCKER]                           │
     Base + 新 tests → FAIL                         │
     原始 Gold + 新 tests → PASS                    │
     原 test_patch 整体应用到临时仓库                │
     新 test.sh/config 选择新 F2P 与保留的 P2P       │
             │ PASS                                 │
             ▼                                      │
  ⑥ BEHAVIOR ROLE AUDIT [SCRIPT]                    │
     functional delta 在 Base FAIL                  │
     converted regression 在 Base PASS              │
             │ PASS                                 │
             ▼                                      │
  ⑦ STABILITY [DOCKER]                             │
     至少两轮 Base/Gold；逐条原始 P2P 均 PASS       │
     Base/Gold 均 PASS → non-discriminative          │
                         → 不发布 final/            │
             │ convertible + PASS                   │
             ▼                                      │
  ⑧ POSITIVE QA [生成 → 双回放 → fresh Judge]       │
     不同于 Gold 且满足 P 的解                       │
     原 verifier PASS/FAIL 只记录                   │
     新 verifier 必须 PASS                          │
             │ PASS                                 │
             ▼                                      │
  ⑨ NEGATIVE QA [生成 → 双回放 → fresh Judge]       │
     相关、非等价、违反 P 的 near-correct mutant    │
     原 verifier PASS/FAIL 只记录                   │
     新 verifier 必须 FAIL                          │
             │ PASS                                 │
             ▼                                      │
  ⑩ ACCEPTANCE [SCRIPT]：同一 revision 门禁齐全   │
             │ PASS                                 │
             ▼                                      │
  ⑪ PACKAGE FINAL [SCRIPT]                         │
     原 task/env/solution + 新 tests                │
     P-only instruction + 可选已审计 addendum       │
             │ PASS                                 │
             ▼                                      │
     final audit + 框架外 independent audit         │
             │ 两者 PASS、原 P2P 排除数 = 0         │
             ▼                                      │
     check/qualified_tasks.txt                     │
                                                    │
  ③—⑪可修复 FAIL → 结构化反馈 → REPAIR rev_NNN+1 ─┘
  框架外复审 FAIL → 挂起该包，保留证据，不自动重转
~~~

正向 QA 完成后才运行负向 QA；它们不是并行分支。

**三类回放的时间与对象。** hard replay 发生在 Stage 2 转换器产出一版候选 `rev_NNN/tests/`、且产物契约和语义审查通过之后，正式打包 `final/` 之前。它将**当前 revision 的 `tests/test.sh` 与 `config.json`** 挂载为 `/tests`，分别在 Base 和应用原始 Gold patch 的仓库上运行；首批可发布任务要求 Base FAIL、Gold PASS。随后 stability 用同一版新测试重复 Base/Gold 回放，并逐条确认保留的 P2P 通过。正负 QA 则在这些门禁通过后，各生成新的候选补丁；对每份补丁分别运行原始 `original/tests/test.sh` 和当前 revision 的新 `tests/test.sh`。旧 verifier 的 PASS/FAIL 是对照记录；QA 是否通过还要看独立 Judge 对补丁语义的判断，以及新 verifier 对正解 PASS、对负例 FAIL。

**最终任务包里有什么。** 打包器把原任务的 `task.toml`、`environment/`、`solution/` 复制到 `final/`，把接受版 revision 的 `tests/` 复制为 `final/tests/`；所以最终执行入口是转换版 `tests/test.sh`，不是原始 `original/tests/test.sh`。首批 20 个 `final/tests/` 均没有原始 `test_patch.patch`，测试脚本也没有引用它。保留在新 `config.json` 里的旧 P2P **selector 只是测试名称，不是测试源码**；原 patch 和原测试命令仍保存在旁边不可变的 `original/tests/`，并没有作为旧 verifier 一起打包进 final。

**原始 test patch 与 P2P 的关系。** 当前 hard replay 只要原任务的 P2P 列表非空，就把原始 `test_patch.patch` **整份应用到一次性容器的仓库**，再运行转换版 `/tests/test.sh`；这一步没有逐条判断每个 P2P 是否真的缺少源码。QA 的新 verifier 分支在原任务含 P2P 时也做同样的临时准备；QA 的旧 verifier 分支则运行原任务的 `tests/test.sh`，由原脚本处理自己的测试准备。这是为了让镜像中可能缺失的历史 P2P 测试源码存在；但原 patch 常同时含旧 F2P 和 P2P 源码，所以旧 F2P 定义也可能暂时进入新 verifier 的回放容器。新 `tests/config.json` 应选择转换后的 F2P、逐字保留的原 P2P，以及必要的 converted regression；旧 F2P 不应作为新判题目标。首批一条 Ansible 任务的原 patch 含 7 个旧 F2P，其转换版回放日志只收集了配置中的 1 个新 F2P、2 个原 P2P 和 1 个 converted regression。这个例子说明该任务的旧 F2P 没被执行，却不能代替对其他 runner 收集范围的逐项检查。

**为什么不能只从补丁里删去 F2P 行。** `config.json` 的 F2P/P2P 是*测试选择器*的划分，原始 `test_patch.patch` 却是对测试源码文件的改动，两者不一定能按行拆开。首批 Qutebrowser 的一个原始 patch 新建了整份测试文件：其中同一个参数化测试函数对应 **358 个旧 F2P selector 和 1 个旧 P2P selector**。从配置里删掉 358 个 F2P 名称，逻辑上的判定集合确实只剩 P2P；但要让这个 P2P 独立运行，仍需提供该函数、参数、fixture 和依赖。如果把整份源码复制进去，宽范围收集又可能执行旧 F2P。因此独立继承 P2P 需要按任务提取/保留必要源码并验证实际收集结果，不能只对原 patch 做文本减法。

**本轮确实验证了旧 P2P。** 新 `config.json` 保留原始 P2P selector；Stage 2 hard replay 与 stability 在临时准备好测试源码后执行当前新 `test.sh`，stability 逐条要求这些 P2P 在 Base 和 Gold 均 PASS。Stage 3 的 functional verifier 复判也按同样原则准备旧 P2P 测试空间。因此“`final/` 没带旧 patch”**不等于**“本轮没有运行 P2P”。

原 patch 不打包进 `final/tests/`，所以**当前 final 包在缺少历史 P2P 源码的干净镜像中，不能仅凭自身保证这些 P2P 可运行**；它依赖外部回放程序临时准备测试源码。若要求转换后任务包独立运行且完全不引入旧 F2P 源码，需要为保留的 P2P 提供独立测试源码或做受控提取，并重新验证与冻结。本轮总结仅描述首批 20 条的实际回放方式，不把“未选择旧 F2P selector”写成“旧 F2P 源码从未进入容器”。

Gold PASS 是**一个**兼容性门禁，不推出所有旧 verifier 能过的补丁都能过新 verifier。positive QA 的原始 verifier 结果仅作对照；可接受条件是 Judge 判定 P-valid 且新 verifier PASS。首轮配置目标为 1 个有效正解和 1 个相关 mutant，上限分别为 3、5 次尝试，找到首个合格样本即可停止。因此 QA 能发现部分缺陷，不能穷举所有正确实现路线。

### 3.3 结果与指标：首批 20 条

首批[合格清单](../../check/qualified_tasks.txt)冻结 **20 个任务、20 个合格 attempt**，其中 Python 19、TypeScript 1；每条都有明确的 attempt 与 revision。清单合计记录 505 个历史 F2P selector、413 个原始 P2P selector，原始 P2P 排除数合计为 0；这两个 selector 总数是旧测试配置项数，**不是**新测试用例数。正式 `final/` 保留原 task.toml、environment、solution，替换 instruction 和 tests；instruction 为移除 R/I 的 P 文本，可附经过门禁的行为级 addendum。进入清单要求包完整、final audit PASS、框架外 independent audit PASS、原始 P2P 排除数为 0，并核查 F2P 转换与 instruction。因而这 20 条是**完成转换且通过审计的产物数**，占 Stage 1 选定 100 条的 20/100；另外 80 条未纳入首批合格结果，不能用 20/100 估计转换方法的总体成功率。

**门禁边界。** 原项目的框架外复审记录（涉及本轮之外的任务，未纳入交接包）记录了自动 accepted 但未进入首批合格清单的语义问题。正向 QA 目标为 1 个有效替代解、负向 QA 目标为 1 个相关 mutant，且找到首个合格样本即可停止；这些检查提高了发现缺陷的机会，并不穷举全部实现路径。因此自动 accepted 或 Gold PASS 不能单独证明 functional verifier 对所有 P-valid 补丁判定正确。

## 4. Stage 3：两组生成、同一补丁双 verifier 复判

### 4.1 方法与核心设计

**固定样本与生成条件。** Stage 3 只取 Stage 2 首批合格清单中的 20 个 instance，并冻结各自的 accepted attempt、原始与转换后任务包、镜像和测试。每个任务用相同 Harbor、mini-swe-agent、模型及运行参数各做一次 solver rollout：原始 instruction（P+R+I）生成 patch O，转换后 instruction（P+可选经审计的 addendum）生成 patch F。17 条任务只删除 R/I，另 3 条还含行为澄清，分析时分层。每组各自生成补丁，因此组间通过数变化描述的是两种生成条件下本批补丁的表现，不能被解释为“同一补丁只换 instruction”的因果效应。

**同一补丁交叉复判。** 对 patch O 和 patch F 分别从干净 Base 仓库起步，在独立容器中运行原始 verifier 与 functional verifier。两套复判对同一补丁使用一致的历史测试空间准备规则，避免补丁改动测试文件导致假性的 test patch 冲突。补丁应用失败、超时和基础设施故障单列，不当作语义 FAIL。每份补丁于是得到一对有效 verdict，可归入双 PASS、仅旧 PASS、仅新 PASS、双 FAIL 四格；其中 verifier 差异是严格的同补丁配对比较。

**用行为证据解释 verdict。** 对两套 verifier 判定不一致的补丁，回看 P、两份 instruction、候选 diff 与完整日志，核对新测试检验的是否真是 P 所要求的公共效果。“旧 FAIL／新 PASS”可能是旧测试误拒，也可能是新测试误收；“旧 PASS／新 FAIL”可能是旧测试漏检，也可能是新测试过严或扩大了覆盖范围。逐例审查后才报告有证据支持的正确解数量。本轮冻结补丁和 verdict 保持原样，发现的 verifier 疑点作为 Stage 2 后续复核证据。

### 4.2 Pipeline

~~~text
合格清单：20 个 instance + 明确的 accepted attempt
                         │
                         ▼
              ① PREPARE / FREEZE [SCRIPT]
              核验 original/、final/、accepted 证据
              固定 instruction、tests、任务/镜像 hash
              固定 Harbor、agent、模型与运行参数
                         │
                         ▼
          ② SOLVER ROLLOUT [同一 Harbor/agent/LLM]
                 ┌───────┴───────┐
                 ▼               ▼
       原始 instruction     转换 instruction
       (P + R + I)          (P + 可选 addendum)
                 │               │
                 ▼               ▼
              patch O         patch F
                 └───────┬───────┘
                         │ 每任务各 1 份；保存 patch/trajectory
                         ▼
              ③ CROSS-REGRADE [独立干净容器]
              对每份同一 patch 分别执行：
                 ┌───────────────┴───────────────┐
                 ▼                               ▼
       原始 verifier                   functional verifier
       原始测试准备规则               同等历史测试空间重置
                 └───────────────┬───────────────┘
                                 │
       patch/test patch 应用失败、超时或基础设施故障
             → 单列无效状态；保留日志，不计语义 FAIL
                                 │ 双有效 verdict
                                 ▼
              ④ PAIRED MATRIX [SCRIPT]
              双 PASS / 仅旧 PASS / 仅新 PASS / 双 FAIL
              原始、转换 instruction 分组并单列 addendum
                                 │
                                 ▼
              ⑤ SEMANTIC REVIEW [逐补丁]
              核查不一致 verdict 的 P 依据、补丁、
              测试日志及公共行为；标记覆盖扩大/误收/误拒
                                 │
                                 ▼
              ⑥ AGGREGATE / FREEZE
              check/stage3/<experiment_id>/manifest、
              patches、logs、aggregate、report
                                 │
                       若发现 verifier defect
                                 ▼
              作为 Stage 2 复核证据；修订并重冻后
              另起复评，不改本轮冻结 verdict
~~~

本轮使用 Harbor 0.22.0、mini-swe-agent 2.4.6、`deepseek-v4-pro-Code-PT-SWE-Pro-o-66`，每组每任务 1 次 rollout，最多 10 个任务并发。模型服务端版本未提供，未固定 seed。Harbor shared mode 的 `trial regrade` 不适用于这批任务，交叉复判由项目 Docker replay 执行；它在干净环境中按原始测试空间规则应用历史 test patch，区分补丁应用/基础设施失败与有效测试 FAIL。40/40 次旧 verifier 独立复判与 Harbor 原生 verdict 相同。评测前的基础设施失败和首次复判准备失误已留档；全部 40 份补丁在统一规则下重新复判，冻结原任务、final 测试及候选补丁未改动。执行和统计入口见 [Stage 3 控制器](../../src/swepro_trans/stage3.py)、[聚合分析](../../src/swepro_trans/stage3_analysis.py)、[Docker replay](../../src/swepro_trans/qa/replay.py)与[测试空间重置](../../src/swepro_trans/qa/stage3_p2p_reset.py)。

### 4.3 结果与指标（冻结首轮）

40/40 次 rollout 正常结束并生成非空补丁，80/80 个旧/新 verifier verdict 有效。以下每行的四格均针对**同一组的同一补丁**配对计算；行间 instruction 比较则涉及各自生成的补丁。

| Instruction | 旧 PASS／新 PASS | 旧 PASS／新 FAIL | 旧 FAIL／新 PASS | 双 FAIL | 旧通过 | 新通过 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 原始，20 份 | 16 | 3 | 1 | 0 | 19/20 | 17/20 |
| 转换后，20 份 | 3 | 0 | 10 | 7 | 3/20 | 13/20 |
| 合计，40 份 | 19 | 3 | 11 | 7 | 22/40 | 30/40 |

仅删 R/I 的 17 个任务：旧 verifier 原始→转换为 16→2，新 verifier 为 15→12。另 3 个含行为澄清任务：旧为 3→1，新为 2→1。一次 rollout、非随机抽取的 20 个任务，只能得出这批样本的描述统计，不能当作稳定的模型成功率或单一因素因果效应。正式 solver 墙钟跨度约 85.5 分钟；原始/转换组分别消耗输入 59,609,625 / 108,441,069 tokens、输出 536,184 / 651,276 tokens（输入量包含缓存命中）。Harbor 的费用字段不可用，不据此估算实际花费。生成结果、哈希、日志和汇总位于 [冻结实验目录](../../check/stage3/deepseek_miniswe_20_20261008/)；机器可读总表是 [aggregate.json](../../check/stage3/deepseek_miniswe_20_20261008/aggregate.json)。

### 4.4 判定不一致的解释

11 份“旧 FAIL／新 PASS”经逐补丁审查，**10 份**有足够 P 层行为证据支持正确；另 1 份 Ansible 转换组补丁错误拒绝合法完整单位名（如 `kilobyte`），新 verifier 漏检，故不能把 11 当作全部“挽救的正确解”。原始 instruction 组唯一旧 FAIL／新 PASS 是 Ansible `human_to_bytes`：补丁拒绝畸形输入，但异常文案不符原 Requirements 中的固定字符串 `Value is not a valid string`；原 instruction 下旧判定成立，删 R/I 后新判定对应保留的 Description。早期机器语义审查将其归因为 selector 不匹配，这一点已由原始 pytest 日志纠正。

3 份“旧 PASS／新 FAIL”中，两份 OpenLibrary 补丁只实现 helper，没有接入作者页或搜索调用路径；新测试发现 P 要求的产品效果缺失。不过新测试从历史 helper 断言延伸到了集成路径，**覆盖深度也增加了**，不能把这两例单纯解释为去除了实现绑定。Qutebrowser 补丁通过启动环境变量向 QtWebEngine 提供 `--lang`，而新测试只检查 `qt_args()` 返回值；独立探针验证了变量设置和既有 flags 保留，尚未验证完整浏览器中语言参数最终生效，语义结论待定。Stage 2 对该任务只接受过 1 份不同于 Gold 的正向 QA 解，且仍走 `qt_args()`；因此当时没有覆盖环境变量路线。

转换组另有 7 份双 FAIL：日志可见的失败包括 Ansible `tty_ify` 输出、OpenLibrary 语言值、Qutebrowser 字体解析等；其中 `sanitize_keys` 导入失败、Wikidata 标签和 locale 回退断言还需进一步区分补丁缺陷与测试绑定。双 FAIL 是两套测试的执行结果，尚非七份补丁全部违反 P 的语义裁定。

Stage 3 暴露的 verifier 疑点应作为 Stage 2 复核证据；若修订测试，须重新通过门禁、冻结 final 并复评相关任务。本轮 80 个冻结 verdict 保持原样。逐项证据与更完整的分析见[落地报告](../stage3/20261008_stage3_two_cohort_cross_verifier_results_cn.md)和[本轮详细分析](../../check/stage3/deepseek_miniswe_20_20261008/20261008_102821_stage3_design_results_analysis_cn.md)。

## 5. 核心 prompt 与可执行机制索引

下表列出首批 20 条转换流程中的 prompt 角色与实现入口，用于理解方法分工；prompt 文本本身不是硬门禁。首轮结论以对应的合格 attempt、审计与 Stage 3 冻结记录为准。

| 角色 | 生效 prompt | 关键约束 |
| --- | --- | --- |
| F2P 转换器 | [converter.md](../../prompts/converter.md) | 逐条恢复历史行为与 P 依据；公共可观察边界；分清 P 行为、Base 回归、P 缺口和实现细节；反事实自审；保留原 P2P。 |
| 语义 Judge | [semantic.md](../../prompts/judges/semantic.md) | 检查实际测试正文、P 支持、Gold/私有接口绑定、产品效果及遗漏的行为义务。 |
| 正向 QA 生成器 | [positive_generator.md](../../prompts/qa/positive_generator.md) | 构造与 Gold 实质不同、仍满足 P 的可运行实现，改变有风险的设计轴。 |
| 正向 QA Judge | [positive.md](../../prompts/judges/positive.md) | 独立核查 P 正确性、相关路径和实质差异；不能仅凭 verifier PASS 判正确。 |
| 负向 QA 生成器 | [negative_generator.md](../../prompts/qa/negative_generator.md) | 构造接近正确、仅违反相关 P 行为的可运行 mutant。 |
| 负向 QA Judge | [negative.md](../../prompts/judges/negative.md) | 核查明确 P 义务与非等价性，排除无关崩溃或等价变更。 |

| 机制 | 实现入口 | 实际作用 |
| --- | --- | --- |
| F2P accounting 与包结构 | [conversion_schema.py](../../src/swepro_trans/conversion_schema.py)、[revision.py](../../src/swepro_trans/validation/revision.py) | 约束每条历史 selector 的去向、P2P 原样保留、文件与 Base/Gold 回放。 |
| 编排、addendum 与修复 | [orchestrator.py](../../src/swepro_trans/pipeline/orchestrator.py)、[repair.py](../../src/swepro_trans/pipeline/repair.py) | 固定门禁次序；反馈失败；规范缺口形成行为级 addendum 和新 revision。 |
| 语义/行为/稳定性 | [semantic.py](../../src/swepro_trans/validation/semantic.py)、[behavior_roles.py](../../src/swepro_trans/validation/behavior_roles.py)、[stability.py](../../src/swepro_trans/validation/stability.py) | 判定 P 依据、Base/Gold 行为角色、重复回放与 P2P 状态。 |
| 正反 QA 与验收 | [QA runner](../../src/swepro_trans/qa/runner.py)、[acceptance.py](../../src/swepro_trans/validation/acceptance.py) | Judge 和 verifier 双条件，核对同一 revision 的门禁。 |
| 发布与合格审核 | [layout.py](../../src/swepro_trans/layout.py)、[final_audit.py](../../src/swepro_trans/validation/final_audit.py) | 写正式 Harbor 包、检查审计证据；框架外 independent audit 由外部流程生成。 |

证据阅读顺序：先看 [Stage 1 总审计](../../data/stage1/final_100_report.json)和[合格清单](../../check/qualified_tasks.txt)，再顺着一个明确 attempt 的 `source/ → revisions/ → validation/ → qa/ → final/ → review/`，最后看 Stage 3 的 [manifest](../../check/stage3/deepseek_miniswe_20_20261008/manifest.json)、[aggregate](../../check/stage3/deepseek_miniswe_20_20261008/aggregate.json)、逐实例 patch 与复判日志。旧设计文档可解释动机；若流程描述与首轮冻结证据不一致，以对应 attempt 和本轮冻结记录为准。
