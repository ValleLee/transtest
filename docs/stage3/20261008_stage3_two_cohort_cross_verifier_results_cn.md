# Stage 3 落地结果：两组 instruction × 两套 verifier

日期：2026-10-08。实验 ID：`deepseek_miniswe_20_20261008`。结果目录：`check/stage3/deepseek_miniswe_20_20261008/`。

## 背景与目标

SWE-bench Pro OS v2 原任务的 instruction 含问题描述及 Requirements、New Interfaces。Stage 2 将后两部分移除，并把测试改为验证可观察的功能行为。Stage 3 固定任务、镜像、agent 和模型，只让两种 instruction 各生成一份解，再把**每份同一补丁**分别交给原始与 functional verifier。这样可以分别观察 instruction 条件变化和同一补丁上的 verifier 判定变化。

本轮使用 `check/qualified_tasks.txt` 的全部 20 个合格任务，每个任务每组一次 rollout，共 40 份候选补丁。17 个任务的 instruction 变化仅为删去 Requirements/New Interfaces；另 3 个加入标明的功能行为澄清，单独列出统计。

## 执行方式与可追溯性

| 项目 | 本轮固定设置 |
| --- | --- |
| Solver | Harbor `0.22.0` + `mini-swe-agent 2.4.6`，Docker 环境，10 个并发任务 |
| 模型 | `deepseek-v4-pro-Code-PT-SWE-Pro-o-66`，OpenAI 兼容接口；服务端未提供可记录的模型版本，未设置 seed |
| 两组输入 | 原始组：`original/instruction.md`；转换组：接受的 `final/instruction.md`。两组使用同一任务镜像、base repo、agent 参数及任务环境配置 |
| 原始 verifier | 冻结的官方原始 `tests/test.sh`，按原任务配置运行 |
| Functional verifier | 冻结的 Stage 2 `final/tests/test.sh`；在干净镜像中应用同一候选补丁，并按官方原始 verifier 的测试空间重置规则准备历史 P2P `test_patch` |
| 来源 | Harbor commit `4407eb5227a2ff4f0d3f16b2eb48849382fdf276`；SWE-bench Pro OS commit `66f92766bba642462d4bbe5479e83f91f9211862` |

执行顺序为：冻结 20 份任务输入及 Docker image ID → Harbor 分别生成两组补丁 → 在两个独立干净容器中应用相同补丁并运行两套 verifier → 检查补丁及测试补丁应用、测试退出码和原生 Harbor verdict → 逐条审查判定变化 → 汇总。Harbor 的共享环境任务不能直接使用只支持独立 verifier 环境的 `trial regrade`，因此交叉复判由本项目的 Docker replay 驱动；**40 次原始 verifier 复判与 Harbor rollout 自带的原始 verifier 判定完全一致**。

运行前排除了两项环境故障：Harbor egress sidecar 的原始 registry 返回 403，遂从 `mirror.gcr.io` 取得**同一固定 base digest**，以原版 Harbor sidecar 文件构建本地镜像；agent 安装将兼容的 `litellm==1.83.0` 固定为约束，以避免现场 Rust 编译超时。agent 仍遵守任务的 `no-network` 策略，仅放行模型主机。原始/最终任务包、任务镜像和候选补丁均未为此修改。最初基础设施失败的尝试和日志保留在实验目录，不计作额外 rollout。

第一次交叉复判发现部分 solver 补丁修改了测试文件；直接应用历史 `test_patch` 会冲突。原始官方 verifier 会先恢复测试空间。回放器对 functional verifier 增加同等准备步骤，并保留首次日志，随后对全部 40 份补丁**统一重新复判**。其中一份 Ansible 补丁的 functional verdict 从 FAIL 变为 PASS；下表只使用统一复判结果。14 份候选补丁与历史 `test_patch` 共涉及 16 处文件路径重叠，均为测试文件，没有生产代码被重置。冻结输入的哈希与本地 image ID 最终逐任务复核通过。

## 量化结果

40/40 次 solver 正常结束，40/40 份补丁非空；每份补丁均取得旧、新 verifier 的有效判定。原始 verifier 的 Harbor 原生判定与独立复判为 40/40 一致，无缺失或基础设施无效项。

| Instruction 组 | 旧 PASS / 新 PASS | 旧 PASS / 新 FAIL | 旧 FAIL / 新 PASS | 旧 FAIL / 新 FAIL | 旧 verifier 通过 | 新 verifier 通过 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 原始，20 份 | 16 | 3 | 1 | 0 | 19/20（95%） | 17/20（85%） |
| 转换后，20 份 | 3 | 0 | 10 | 7 | 3/20（15%） | 13/20（65%） |
| 合计，40 份 | 19 | 3 | 11 | 7 | 22/40（55%） | 30/40（75%） |

原始 instruction 组的通过集合交集是 **16/20**：旧 verifier 通过的 19 份中，16 份也过新 verifier、3 份仅过旧 verifier；旧 verifier 唯一未通过的是 Ansible `human_to_bytes`（`instance_ansible__ansible-d62496fe416623e88b90139dc7917080cb04ce70-v0f01c69f1e2528b935359cfe578530722bca2c59`），其同一补丁通过新 verifier。因此新 verifier 的 17 份通过由 16 份交集加这 1 份组成。

同一 verifier 下比较两组 instruction：原始 verifier 的通过数由 19/20 降为 3/20（差 −80 个百分点）；functional verifier 由 17/20 降为 13/20（差 −20 个百分点）。每任务只有一次 rollout，这些是本次样本的配对描述统计，不是稳定的模型成功率估计。

| Instruction 变化子集 | 任务数 | 旧 verifier：原始 → 转换 | 新 verifier：原始 → 转换 |
| --- | ---: | ---: | ---: |
| 仅删除 Requirements/New Interfaces | 17 | 16 → 2 | 15 → 12 |
| 删除并加入功能行为澄清 | 3 | 3 → 1 | 2 → 1 |

Harbor 记录的 agent 用量如下。`cache tokens` 是另行报告的缓存输入量，不能与 `input tokens` 相加为总输入量。该自定义模型在 Harbor 中的 `cost_usd=0.0` 是不可用的费用字段，未当作真实账单。

| Instruction 组 | Input tokens | 其中 cache tokens | Output tokens | Agent 执行时间总和 | 单次执行时间中位数 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 原始 | 59,609,625 | 58,695,040 | 536,184 | 10,994 秒 | 516 秒 |
| 转换后 | 108,441,069 | 107,098,624 | 651,276 | 13,270 秒 | 464 秒 |

40 次正式 solver 任务从首个开始到最后结束的墙钟跨度为 85.5 分钟；并发执行，所以不能把两组执行时间总和当作墙钟时间。

## 判定变化的语义审查

14 个旧、新 verdict 不一致的补丁均核对了 instruction、候选 diff、两套测试日志及补丁哈希；完整逐条理由在 `semantic_reviews.json`。

| 判定方向 | 数量 | 逐条审查结论 |
| --- | ---: | --- |
| 旧 FAIL / 新 PASS | 11 | 10 份补丁有足够行为证据支持为正确解；1 份虽过新 verifier，却错误拒绝了既有合法的 `kilobyte` 等完整单位写法 |
| 旧 PASS / 新 FAIL | 3 | 2 份补丁确实没有接入用户可见调用路径；1 份 Qutebrowser 补丁走 QtWebEngine 环境变量路径，新 verifier 只观察 `qt_args()` 参数；现有探针未证明完整浏览器行为，语义结论待核实 |

典型旧 verifier 误拒包括：测试在收集阶段强制导入已从新 instruction 移除的接口名（如 `PrioritizedIdentifier`、`luqum_replace_field`、`qcolor_to_qsscolor`）；以及按历史参数化 selector 名或快照判断，未检验候选实现的对外行为。Tutanota 转换组补丁把底层解密异常转成应用异常，删除失效凭据并返回登录状态；旧 verifier 报缺少原生测试 selector，新 verifier 通过。Ansible `human_to_bytes` 的原始 instruction 组补丁则确实执行了两条重复的 `.1 Geggabytes` 测试，但因抛出的 `ValueError` 消息与旧测试要求的固定文案不符而失败；该文案来自原 instruction 的 Requirements，新 instruction 删去该要求，新测试只要求拒绝畸形输入。因此旧判定符合原 instruction，新判定符合转换后保留的 Description。此前 `semantic_reviews.json` 将它写作 selector/collection mismatch 不准确，以原始 pytest 日志和此处更正为准。

两例旧 verifier 误收由 functional verifier 找到：Wikidata 补丁只增加实体方法，未把资料链接渲染到作者页；`work.` 查询补丁只定义改写函数，未接入搜索处理流程。但这两例的新测试也把历史 helper 测试提升到了产品调用路径，检测范围比原 F2P 的断言更深；它们不能单独证明“只去除了实现绑定而未改变覆盖范围”。Qutebrowser 的独立探针确认：正常启动调用的 `init_envvars()` 为缺失语言包的 locale 追加 `QTWEBENGINE_CHROMIUM_FLAGS=--lang=en-US`，且保留原有 flags；[Qt 文档](https://doc.qt.io/qt-6.5/qtwebengine-debugging.html)说明此环境变量可传递 Chromium 参数。不过原仓库的 `_warn_qtwe_flags_envvar()` 明确警告该环境变量可能干扰 qutebrowser 自身的参数处理。探针仅验证变量写入，没有运行完整浏览器或确认有效 locale，因此该补丁是否满足 P 仍待核实；可以确定的是新 verifier 没有观察这条路径。

### 两例 OpenLibrary 的转换范围

| 任务 | 历史 F2P 实际断言 | 新 verifier 实际断言 |
| --- | --- | --- |
| Wikidata 外部资料 | 直接调用 `WikidataEntity` 的私有方法和 `get_external_profiles()`，检查返回的资料列表；没有渲染作者页。 | 渲染完整作者页，检查 Wikipedia、Wikidata 和 Google Scholar 链接是否出现及其语言、标识。 |
| `work.` 查询 | 直接调用 `luqum_replace_field()`，检查它返回的改写字符串；没有调用搜索方案。 | 调用现有 `WorkSearchScheme.q_to_solr_params()`，检查发给 Solr 的 `workQuery` 是否已去掉 `work.` 前缀。 |

两项产品效果分别有原始 P 的“作者页展示外部资料”和“用户查询不再因 `work.` 前缀出错”作依据；Wikidata 接受版 instruction 另含从历史行为提炼的语言回退和 Scholar 值处理澄清。但**P 支持**不等于**旧测试已覆盖**。如果实验要求新旧 verifier 只改变实现约束、不得增强集成覆盖，这两项必须标记为范围扩大并返回 Stage 2 重审；本轮 2 次旧 PASS / 新 FAIL 不能当作纯粹的实现无关化收益。

### Stage 2 Gold 门禁与旧 PASS / 新 FAIL

这三项接受版 Stage 2 修订的实际 `hard_replay` 都记录了 `base_fail_gold_pass`：Base 退出码 1、Gold 退出码 0；正反 QA 与最终审查也均通过。因此转换确实检查了**原始 Gold patch 能通过新 verifier**。门禁验证的是 Gold 和有限的 QA 样例，并未验证所有旧 verifier 通过的补丁；代码中的 positive QA 只要求 Judge 判为有效且 functional verifier 通过，原始 verifier 结果仅作记录。逻辑上 `新(Gold)=PASS` 不能推出对任意补丁都有 `旧(p)=PASS ⇒ 新(p)=PASS`。

| 任务及接受版 Stage 2 回放 | 本轮旧 PASS / 新 FAIL 的原因 |
| --- | --- |
| [Wikidata 作者资料，attempt_009](../../runs/instance_internetarchive__openlibrary-5fb312632097be7e9ac6ab657964af115224d15d-v0f5aece3601a5b4419f7ccec1dbda2071be28ee4/attempts/attempt_009/intermediate/validation/hard_replay/result.json) | Stage 3 补丁仅新增实体方法，未在作者页显示资料链接；旧 verifier 误收。 |
| [OpenLibrary `work.` 查询，attempt_001](../../runs/instance_internetarchive__openlibrary-72321288ea790a3ace9e36f1c05b68c93f7eec43-v0f5aece3601a5b4419f7ccec1dbda2071be28ee4/attempts/attempt_001/intermediate/validation/hard_replay/result.json) | Stage 3 补丁仅定义改写函数，未接入搜索流程；旧 verifier 误收。 |
| [Qutebrowser locale，attempt_006](../../runs/instance_qutebrowser__qutebrowser-ef5ba1a0360b39f9eff027fbdc57f363597c3c3b-v363c8a7e5ccdf6968fc7ab84a2053ac78036691d/attempts/attempt_006/intermediate/validation/hard_replay/result.json) | Stage 3 补丁通过启动时的环境变量传入 `--lang`；新 verifier 只检查 `qt_args()` 返回的参数，漏掉这一通路。 |

故不能把“旧 PASS 全部也应新 PASS”设为无条件门禁，否则会保留旧 verifier 的误收。Qutebrowser 的 `qt_args()` 单一路径断言需要退回 Stage 2 审查；先验证环境变量方案在完整应用中的行为和既有参数兼容性，再决定测试如何修订。修订和重新冻结后须重跑相关 Stage 3 评估，本轮冻结统计保持不变。

### 正向 QA 为何没有覆盖 Qutebrowser 的环境变量路径

Stage 2 的正向 QA 确实生成了替代解，但不是穷举。Qutebrowser 接受版的上限为 3 次：第 1 次生成超限，第 2 次获 Judge `VALID` 且新 verifier 通过，随即停止，实际只确认了 **1 份**有效替代解。该解把 Gold 的静态 fallback 表改为扫描已安装的 `.pak`，仍由 `qt_args()` 返回 `--lang`；Judge 也把 `qt_args()` 当作生产观察边界。转换记录预先将功能面写成 `qutebrowser.config.qtargs.qt_args`，而新测试的 helper 只调用该函数，没有运行 `init_envvars()`。因此 QA 覆盖了**fallback 算法的差异**，没有覆盖**将参数交给 QtWebEngine 的另一条通路**。另两例 OpenLibrary 的正向 QA 也都在首个有效替代解后停止；其旧 PASS / 新 FAIL 属于旧 verifier 对不完整补丁的误收，并非新 verifier 漏检。

预防点在 Stage 2：converter 应从 P 描述的最终效果反查可行的生产通路，审查测试是否把某个函数误当成唯一可观察出口；正向 QA 应按有风险的设计轴生成替代解，并在该轴未被覆盖时继续尝试，而不是只确认“与 Gold 不同”的一个样本。当前 Qutebrowser 应先用这份 Stage 3 补丁做受控启动探针，核查最终生效的语言参数、启用条件、已安装语言包及既有参数兼容性；若确认满足 P，再修订 verifier 以覆盖该实现，执行 Base/Gold、正反 QA、重新冻结和受影响任务复评。

本轮发现的 functional verifier 漏测完整单位名称，以及只观察 `qt_args()` 的覆盖疑点，均保留为 Stage 2 复核证据；为保持本轮冻结实验可复核，没有在复测中修改 `final/tests/`。因此“新 verifier 通过”不能直接等同语义正确，报告的正确解挽救数使用逐补丁审查后的 **10**，不能使用原始的 11 次 verdict 翻转。

## 复核入口与局限

- 实验配置、来源哈希、镜像和网络记录：[manifest.json](../../check/stage3/deepseek_miniswe_20_20261008/manifest.json)。
- Solver、交叉复判、汇总：同目录的 [run_state.json](../../check/stage3/deepseek_miniswe_20_20261008/run_state.json)、[regrade_state.json](../../check/stage3/deepseek_miniswe_20_20261008/regrade_state.json)、[aggregate.json](../../check/stage3/deepseek_miniswe_20_20261008/aggregate.json)、[report.md](../../check/stage3/deepseek_miniswe_20_20261008/report.md)；逐任务补丁、轨迹、原始日志和结果在 `instances/<任务>/<组>/rollout_001/`。
- 判定变化与审查：[semantic_review_queue.json](../../check/stage3/deepseek_miniswe_20_20261008/semantic_review_queue.json)、[semantic_reviews.json](../../check/stage3/deepseek_miniswe_20_20261008/semantic_reviews.json)；Qutebrowser 独立探针在 [semantic_probes/](../../check/stage3/deepseek_miniswe_20_20261008/semantic_probes/)；旧测试准备流程的无效日志及统一重评前结果也在各 rollout 目录中保留。
- 执行代码：`src/swepro_trans/stage3.py`、`stage3_analysis.py`、`qa/replay.py`、`qa/stage3_p2p_reset.py`。重算汇总可运行 `PYTHONPATH=src .venv/bin/python -m swepro_trans.stage3 aggregate --output check/stage3/deepseek_miniswe_20_20261008`。

限制：任务是挑选出的 20 个合格实例，每组仅一次 rollout；未固定模型 seed，服务端版本未公布；3 个 instruction 含额外功能澄清，不能与纯删除任务混为单一干预；补丁级语义审查与有限探针不是所有生产场景的形式化证明。若修复上述 Stage 2 verifier defect，应重新冻结任务并重新运行 Stage 3，不能直接把修订后的 verifier 套到本轮原统计中。
