# Stage 2 转换包独立审计标准

本文件是 Stage 2 任务进入“新增合格清单”的统一审计标准。每次审计都使用同一版本，不得因为某条任务容易通过、框架已接受、样本急缺或审计者偏好而临时加严或放宽。框架的 `accepted`、自动 `final_audit`、Base/Gold replay、QA 均是证据，不替代本审计。

## 1. 审计目标与范围

判断一个 Stage 2 final 包是否满足：

1. 最终 instruction 只包含有效的 Problem Statement（P）和已批准的行为级 addendum；
2. 原始 P2P selectors 原样、原序保留且没有排除；
3. 每条历史 F2P 的产品行为被转换为功能行为检查，测试从公开产品边界触发并观察结果；
4. 不把 R/I、Gold、历史断言或仓库内部实现误当成 P 的额外要求；
5. 包完整，且确定性 Base/Gold 与保留测试验证记录相符。

本审计只检查历史 F2P 覆盖的转换范围。不得因 P 还提到其他功能而要求添加历史 F2P 未覆盖的新测试。可以用仓库、Requirements、Interface、Gold 和历史测试理解行为及构造测试；它们不会自动成为 solver specification。

## 2. 必需证据

审计前确认以下证据存在且属于同一 task / attempt / revision：

- Stage 1 的 `source/problem_statement.md`、原始 `instruction.md`、Requirements、Interface、原始 `tests/config.json`；
- 原始测试源码或 patch、Base/Gold 仓库状态及必要的构建/运行日志；
- 被审 attempt 的 `conversion_trace.json`、最终测试源码、最终 `tests/config.json`、最终 `instruction.md`；
- hard validation、Base/Gold functional replay、原始 P2P replay、最终审计记录；
- 若存在 addendum，须有已批准的行为级文本和批准/审查记录；
- 每条 F2P 的 selector、原始断言、转换后 selector 和实际断言之间的可定位映射。

缺少关键证据时不得猜测：判为 `HOLD`，指出具体缺件；不能把缺证当作通过或任务语义失败。

## 3. 固定审计顺序

### A. 包和结果可复现

- 核对 task ID、attempt、revision、image/repo 与报告一致；final 包文件完整、测试可执行。
- 查看真实测试源码和运行结果，不以 trace、自检文字或日志摘要代替代码。
- 记录 Base / Gold 的 functional selector 结果、P2P selector 结果、excluded 数和最终 instruction 对照。

### B. 最终 instruction 只保留规范

- 以 `source/problem_statement.md` 为规范基准；逐段检查 final instruction。
- final instruction 应与该 P 相同，唯一允许的扩展是已批准且只写可观察行为、不含实现 API/签名的 addendum。
- Requirements、New Interfaces / Interface、仓库说明、Gold 做法、历史测试要求不得泄漏为新的 solver 要求。
- 优先比较规范化前的文本及清晰 diff；保留格式差异可以接受，但任何新增规范句都必须有批准的 addendum 证据。

### C. P2P 原样保留

- 从原始 config 读取整个 `pass_to_pass` selector 序列，并与 final config 逐项逐序比较。
- 原始序列必须完整地作为 final P2P 列表前缀，字符串不得改名、重映射、排序、删除或排除；`excluded` 必须为空，excluded count 必须为 0。
- 原始 P2P 的 replay 失败是阻断问题，除非有独立且明确的环境故障证据；不得通过编辑 P2P 列表“修复”。
- 若转换后为 F2P 的 Base 回归增加 P2P selector，只能追加在全部原始 P2P 之后，并单独标记来源。

### D. 逐条核对历史 F2P 是否保留行为

对每个原始 F2P selector：

1. 读原始测试的输入、状态、动作、断言和边界条件；将“产品可观察行为”和“实现/测试机制”分开。
2. 对每个产品行为找到 P 或批准 addendum 的准确支持文本；如果不受支持，不得作为新 solver 要求。
3. 检查 converted selector 的可执行断言确实触发了同一行为、观察了其结果，并覆盖了原测试中不同的有意义状态/输入；不能只凭 accounting 文案算覆盖。
4. 转换可以改变测试语法、fixture 和中间层。纯 helper 调用、mock 形状、私有容器类型等可以排除，但只有在剥离后没有剩余独立产品行为，并附有仓库/边界证据时才可 drop。
5. 若 P 明确要求一种转换后的输出/状态，测试应独立观察该状态；只测下游布尔决策而该决策可从原始输入直接算出时，不足以证明转换结果存在。
6. Base/Gold 结果应与映射相符：至少一个保留的 P-supported functional selector 应在 Base 失败、Gold 通过。若所有保留行为在 Base 都已满足，需有证据判为 `non_discriminative`，不得伪造差异或把 task 算作成功功能转换。

提出漏测时必须引用：原始 F2P selector、原始断言及其行为、P 支持、转换后的 selector/断言，以及具体缺失的同一行为。不得因 P-only 功能未被历史 F2P 测过而报漏测。

### E. 检查是否绑定特定实现

测试应尽可能通过调用者可见的公共 API、CLI、service、文件/协议边界、持久状态、用户输出或公开错误来触发并观察行为。直接使用原仓库源码作为理解和构造证据是允许的；但“Base 里存在该方法”或“Gold 调用了它”本身不能证明它是公共契约。

对每个有风险的断言，构造一个具体反事实：一个实现内部结构不同、但仍满足 P 的合理实现。检查该实现是否会被 verifier 错误拒绝。至少检查以下类别（只对源码实际出现者审查）：

- 直接调用 underscore/private helper 或 Gold-only helper；
- 依赖未由 P/公开契约指定的字段、模块路径、构造签名、内部对象/容器或文件布局；
- 整个 dict/list/结果精确相等、固定顺序、全局数量、无依据的上限；
- 固定 mock 调用顺序/次数/参数，或仅 spy 内部调用而不检查结果；
- 用测试中的 expected answer 挑选不同 API/解析器；
- 只检查非空错误/警告文本，导致无关废话也通过；
- 因避免固定异常类/英文措辞而放宽成接受任何错误；
- fixture/mock 预先替候选实现完成待测决策或副作用。

对私有入口的明确规则：若测试直接将 repository private helper 当验收入口，审查“私有 helper 被删除/改名，但公共行为不变”的合规实现。若它会被测试拒绝，应改用公共产品路径。只有 P 或既有、可定位的公开契约明确承诺该 callable 时，才允许把它当入口；否则若无公平的公共区分路径，判 `HOLD` 并报告 access-contract gap，不得为制造 Base/Gold 差异而下沉至私有层。

数值、精确字段、固定总数或边界只有在 P/公开契约确实规定时才可作为唯一验收方式。警告/通知要求按 P 中每个事件的最低语义检查；不得无依据地把“每条错误至少有警告”提升成“总调用次数必须恰好等于错误行数”。开放式错误文案无需固定词串，但须检查与触发故障相关的语义；合理改写应通过，无关或语义矛盾文本应失败。

### F. 检查无效/负向样本是否有语义

如果 package 要求负向 QA 或反事实验证：确认被拒绝的样本确实违反 P 的某一项语义，而不是仅与 Gold 有差异；确认合理的替代实现/文案不会被错误拒绝。不要因找不到某一种 mutant 的特定内部写法而判 verifier 失败；看其是否能区分被测的产品语义。

## 4. 一致判决规则

只使用以下三个状态：

- `PASS`：所有硬门槛均有证据通过，且未发现会拒绝 P-conforming 实现或接受明显违背 P 的具体反例。
- `FAIL`：有可复现、可定位的具体缺陷；写明 selector/文件、源码位置、P 依据及反例。单纯风格偏好、没有反事实或规范依据的推测不能判 FAIL。
- `HOLD`：缺少决定性证据，或 P/公开访问契约不足以公平判断；保留任务、不计入合格清单，说明需要补的证据或统一框架决策。HOLD 不是让任务无限重试的理由。

审计标准保持不变。若某类问题在不同任务反复出现，应归档为框架问题，集中修订标准/框架并记录版本；不要只为某个 task 添加特判。

## 5. 每次审计的最小记录格式

将结果写入对应 attempt 的 `review/independent_audit.json`，并保留外审报告。至少包含：

```json
{
  "status": "PASS | FAIL | HOLD",
  "task_id": "instance_...",
  "attempt": "attempt_001",
  "revision": "rev_001",
  "standard": "prompts/independent_audit_standard_cn.md",
  "standard_version": 1,
  "checks": {
    "package_reproducible": "PASS | FAIL | HOLD",
    "instruction_p_only": "PASS | FAIL | HOLD",
    "original_p2p_exact_and_unexcluded": "PASS | FAIL | HOLD",
    "historical_f2p_functional_mapping": "PASS | FAIL | HOLD",
    "base_gold_discrimination": "PASS | FAIL | HOLD",
    "public_observable_surface": "PASS | FAIL | HOLD",
    "alternative_implementation_counterfactual": "PASS | FAIL | HOLD"
  },
  "findings": [
    {
      "severity": "blocking | note",
      "category": "p2p | instruction | f2p_mapping | semantic | binding | replay | artifact | evidence",
      "location": "path:line or selector",
      "evidence": "具体观察到的文件内容/运行结果",
      "criterion": "对应本标准章节和 P/公开契约依据",
      "counterfactual": "可行实现及 verifier 对它的结果"
    }
  ],
  "summary": "简明结论"
}
```

`PASS` 时 `findings` 不得含 blocking 项；`FAIL` 至少一个 finding 必须包含具体反例；`HOLD` 必须点明缺失证据/访问契约问题。只有 `final_audit=PASS`、本标准独立审计 `PASS`、原始 P2P 无排除且完整保留、以及新增名单条目身份无重复时，才能追加到合格清单。
