# Stage 3 实验设计、结果与异常样本复核

记录时间：2026-10-08 10:28:21（北京时间，UTC+08:00）  
实验 ID：deepseek_miniswe_20_20261008  
状态：40 份补丁的评测判定已冻结；下述语义解释包含对早期自动报告的勘误，未修改冻结任务、补丁或 verifier。

## 1. 实验要回答什么

Stage 2 为 SWE-bench Pro OS v2 任务准备了转换后的 instruction 和 functional verifier。Stage 3 固定任务镜像、base repo、Harbor、agent 与模型，让原始 instruction 和转换后 instruction 各生成一份独立补丁，再将**每一份相同补丁**分别交给原始 verifier 与 functional verifier。

这里有两个不同的比较：

- **Instruction 比较**：同一套 verifier 下比较两种 instruction 生成的不同补丁。它描述本轮条件差异，不能把两份补丁当作同一个解。
- **Verifier 配对比较**：对同一补丁比较两套 verifier 的判定。原始 verifier PASS 并不定义补丁在 Problem Statement 意义下正确；Gold 通过新 verifier 也不保证所有旧 PASS 补丁都通过新 verifier。

20 个任务来自 qualified_tasks.txt；每任务每组一次 rollout。17 个任务只删除 Requirements / New Interfaces，另 3 个还加入经审计的功能行为澄清；这两个子集必须分开解读。

## 2. 实际运行的 pipeline

~~~text
qualified_tasks.txt：冻结 20 个任务、Stage 2 final attempt、镜像与输入哈希
                              │
                              ▼
原始 instruction ── Harbor + mini-swe-agent + 同一模型 ──► patch O
转换后 instruction ── 同一 Harbor / agent / 模型配置 ────► patch C
                              │
                              ▼
每份 patch 在两个独立干净容器中回放
  ├─ 原始 tests/test.sh + 原始测试准备规则
  └─ Stage 2 final/tests/test.sh + 相同历史 P2P 测试准备规则
                              │
                              ▼
补丁应用检查、退出码、结构化 verdict、日志
                              │
                              ▼
同补丁四格矩阵 → 判定不一致逐条语义审查 → 任务及总体汇总
~~~

固定配置：Harbor 0.22.0、mini-swe-agent 2.4.6、模型 deepseek-v4-pro-Code-PT-SWE-Pro-o-66；两组使用相同的任务镜像、agent 参数和任务环境。服务端模型版本与 seed 不可记录。原始任务、Stage 2 final 任务、候选补丁及镜像 ID 均在 manifest.json 中留证。

Harbor 的共享环境任务不能直接用只支持独立 verifier 环境的 trial regrade，本轮由项目的 Docker replay 执行交叉复判。原始 verifier 的 40 次独立复判与 Harbor rollout 自带判定全部一致。首次复判发现候选补丁与历史 test_patch 在测试文件上冲突；回放器随后统一采用原始 verifier 的测试空间重置规则，对全部 40 份补丁重新复判。下文只用统一复判结果。

## 3. 总体结果

40/40 次 solver 正常结束并产生非空补丁；80/80 次交叉 verifier 运行取得有效判定，未把容器或补丁应用错误计为语义 FAIL。

| Instruction 组 | 旧 PASS / 新 PASS | 旧 PASS / 新 FAIL | 旧 FAIL / 新 PASS | 旧 FAIL / 新 FAIL | 旧 verifier 通过 | 新 verifier 通过 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 原始，20 份 | 16 | 3 | 1 | 0 | 19/20（95%） | 17/20（85%） |
| 转换后，20 份 | 3 | 0 | 10 | 7 | 3/20（15%） | 13/20（65%） |
| 合计，40 份 | 19 | 3 | 11 | 7 | 22/40（55%） | 30/40（75%） |

原始 instruction 组的通过集合交集是 16/20：旧 verifier 的 19 份通过 = 16 份双 PASS + 3 份仅旧 PASS；新 verifier 的 17 份通过 = 16 份双 PASS + 1 份仅新 PASS。原始组唯一的旧 FAIL 是 Ansible human_to_bytes，同一补丁在新 verifier 下 PASS。

固定旧 verifier 时，两组通过数为 19/20 → 3/20；固定新 verifier 时为 17/20 → 13/20。仅删除 Requirements / New Interfaces 的 17 项中，旧 verifier 为 16 → 2，新 verifier 为 15 → 12；另 3 项带功能澄清，旧 verifier 为 3 → 1，新 verifier 为 2 → 1。每格每任务只有一次采样，这些是描述统计，不是模型稳定成功率或因果效应估计。

Agent 用量：原始组 input 59,609,625、output 536,184 tokens；转换组 input 108,441,069、output 651,276 tokens。缓存输入分别为 58,695,040 与 107,098,624，已包含在 input 中，不再相加。正式 rollout 墙钟跨度约 85.5 分钟；Harbor 的零 USD 字段不是真实账单。

## 4. 判定不一致的补丁

14 份补丁发生新旧判定不一致：原始组 4 份，转换组 10 份。旧 FAIL / 新 PASS 共 11 份；此前逐补丁审查支持其中 10 份符合保留的功能描述，另 1 份为新 verifier 误收。旧 PASS / 新 FAIL 共 3 份；其中 2 份涉及新测试对产品调用路径的新增检查，Qutebrowser 1 份的完整浏览器语义仍待确认。

### 4.1 原始 instruction 组：4 份不一致

| 任务 | 旧 / 新 | 已核实的原因与解释 |
| --- | --- | --- |
| Ansible human_to_bytes，d62496fe | FAIL / PASS | 补丁对畸形输入抛出 ValueError，但两条重复的“.1 Geggabytes”旧测试要求消息包含“Value is not a valid string”，实际消息包含“can't interpret following string”。这个文案明确来自**原 instruction 的 Requirements**；转换后的 instruction 删去它，仅保留畸形值应被拒绝的 Description。两套判定分别符合两版文本。早期 semantic_reviews.json 把失败写成 selector/collection mismatch，原始 pytest 日志证实该说法错误。 |
| OpenLibrary Wikidata，5fb31263 | PASS / FAIL | 补丁只实现实体资料方法，未把外部资料链接接到作者页。旧 F2P 仅直接检查实体方法；新测试渲染作者页，因此拒绝该补丁。 |
| OpenLibrary work. 查询，72321288 | PASS / FAIL | 补丁只定义查询字段改写函数，未接入搜索方案。旧 F2P 只调用改写函数；新测试检查 WorkSearchScheme 输出给 Solr 的 workQuery。 |
| Qutebrowser locale，ef5ba1a0 | PASS / FAIL | 补丁在启动时向 QTWEBENGINE_CHROMIUM_FLAGS 加入 --lang；新测试只调用已有的 qt_args() 并检查其返回参数，未观察环境变量路径。现有探针只证实变量被写入和原有 flags 被保留；原仓库同时警告该环境变量可能干扰自身参数处理。未运行完整浏览器验证有效 locale，故**不能确认**这是新 verifier 对正确补丁的误拒。 |

两条 OpenLibrary 行需要单独解释实验范围：原始 P 分别描述“作者页显示外部资料”和“用户使用 work. 查询时搜索正常”，因此新测试的产品行为有 P 依据；但历史 F2P **没有执行对应的产品路径**。Wikidata 的转换后 instruction 还加入语言回退及 Scholar 值处理的功能澄清。所以这两次旧 PASS / 新 FAIL 同时反映了测试覆盖深度增加，不能全部解释为“仅去除了实现绑定”。若研究要求新旧 verifier 对旧 F2P 保持严格等价覆盖，这两项须回 Stage 2 重审或单独统计。

### 4.2 转换后 instruction 组：10 份旧 FAIL / 新 PASS

这 10 份都通过新 verifier，且全被旧 verifier 拒绝。既有语义审查认为其中 9 份满足保留的功能描述：典型原因包括旧测试强制导入已删除的 helper / 类名、要求固定 selector 或历史快照，而候选从其他代码路径实现了相应行为。第 10 份是 Ansible human_to_bytes 的转换组补丁：它拒绝了既有合法的 kilobyte、megabyte、gigabyte 等完整单位写法，新 verifier 没测到这一回归。因此“新 PASS”本身不等于正确；本轮全部 11 份旧 FAIL / 新 PASS 中经审查支持的数量为 10。

### 4.3 转换后 instruction 组：7 份双 FAIL

下表是**直接从运行日志可确认的失败断言**，不是对七份补丁完整语义正确性的裁定。序号对应 aggregate.json 的任务顺序。

| 序号与任务 | 功能 verifier 中可复核的失败点 |
| --- | --- |
| #04 Ansible ansible-doc，bec27fb4 | 两个 tty_ify 输出断言失败：候选生成的代码文字以反引号闭合，保留的历史测试预期以单引号闭合。 |
| #05 Ansible no_log，bf98f031 | sanitize 行为测试无法导入 sanitize_keys；是否为候选缺少必要行为，还是新测试绑定函数名，需另做语义审查。 |
| #06 Ansible invalid hosts，cd473dfb | 多个无效/空 hosts 用例失败；日志显示错误消息未被测试认为明确标识 hosts 缺陷，且若干原始回归用例的异常或文案断言失败。 |
| #11 OpenLibrary Amazon language，2abe28b4 | 元数据的语言值输出 eng / fre，而断言期待 english / french；旧、新测试均未通过。 |
| #12 OpenLibrary Wikidata，5fb31263 | 已出现部分链接，但作者页测试中 Wikidata / Wikipedia 链接未带测试要求的对应可访问标签；旧测试因缺少规定的方法名失败。 |
| #16 Qutebrowser font families，5fdc83e5 | from_str / to_str 等 11 项功能测试抛出“str 没有 valid_values”属性，显示候选在调用解析接口时传入了不相容对象。 |
| #19 Qutebrowser locale，ef5ba1a0 | 与原始 instruction 组不同的候选补丁；功能测试的“缺少当前语言包时选择已安装包”用例失败，另有 7 项通过、1 项 xfail。 |

七项中的 #05、#12、#19 尤其不能凭 FAIL 就断言候选违反 P：需要检查测试所要求的接口名、标签和观察路径是否真正属于当前规范。其余各项也只报告了可观察的测试失败事实。

## 5. Stage 2 门禁为何没有预防全部差异

这三项旧 PASS / 新 FAIL 任务的接受版 Stage 2 hard_replay 都实际验证了 Base FAIL、Gold PASS，正反 QA 和最终审查也通过。该门禁仅验证 Gold 及抽样 QA 候选，不证明对所有补丁都有“旧 PASS ⇒ 新 PASS”。

Qutebrowser 的正向 QA 上限是 3 次：第 1 次生成超限，第 2 次找到 1 份 Judge 判 VALID 且新 verifier PASS 的替代解，流程即停止。这份解改变了语言包 fallback 算法，仍通过 qt_args() 传 --lang；没有生成环境变量路径候选。因此 QA 验证了一种实现差异，没有覆盖另一种参数通路。这里首先需要验证 Stage 3 环境变量补丁在真实启动中的效果及参数兼容性，再决定是否修订新 verifier。

OpenLibrary 两例则说明另一类问题：转换器把历史 helper 行为投射到 P 描述的产品路径，使新测试在执行范围上强于旧 F2P。今后应在 Stage 2 的 conversion trace 和复核中显式区分“同一行为换观察点”与“新增了旧测试未覆盖的集成义务”；报告 Stage 3 时也应分开解释。

## 6. 复核入口、限制和下一步

- manifest.json：任务、接受版 attempt、镜像与来源哈希、运行配置；aggregate.json：40 份补丁的逐任务判定和总体矩阵；report.md：最初自动汇总。该英文自动报告中的“confirmed false rejections = 1”沿用 Qutebrowser 的早期判断，按现有证据应改读为**1 份待完整应用验证**。
- semantic_reviews.json：14 份判定不一致补丁的初次审查。Ansible d62496fe 的失败原因以本文件第 4.1 节和原始 pytest 日志为准。每份补丁、两套 replay 的 result.json、runner 日志和 Harbor 轨迹位于 instances/<instance_id>/<instruction 组>/rollout_001/。
- frozen_verifiers/ 与 manifest.json 固定本轮输入；semantic_probes/ 保存 Qutebrowser 有限环境变量探针。原始 / Stage 2 final 测试及本轮 raw verdict 均未因后续解释而修改。
- 下一步若要求严格保持原 F2P 的覆盖范围，应先审计 OpenLibrary 两项转换；若确认 Qutebrowser 环境变量补丁满足完整产品行为，再返回 Stage 2 调整 verifier、重跑门禁、重新冻结并复评。修订后的判定不能直接混入本轮 40 份补丁的冻结统计。

本轮仅有每任务每组一次 rollout；没有固定模型 seed，也没有服务端模型版本。上述 P 语义判断基于补丁、任务描述和有限运行证据，不能替代完整产品级验证。
