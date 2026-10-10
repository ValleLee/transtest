# Functional Verifier Transfer：交接与运行指南

本目录是 `Swepro_test_trans` 在 **2026-10-08 首轮实验**的独立交接副本。实验对象是 SWE-bench Pro OS v2：先验证 100 条原始任务的 Base/Gold oracle，再将其中首批 20 条的历史 F2P 转为功能性 verifier，最后对这 20 条做两种 instruction × 两套 verifier 的交叉实验。本目录的 20 条以 `check/stage3/deepseek_miniswe_20_20261008/manifest.json` 冻结的任务 ID 和 accepted attempt 为准。后续新增的合格转换没有纳入。

建议先读 [框架说明.md](框架说明.md) 理解设计，再按下文配置环境。[交接核验记录](docs/交接核验记录.md)列出实际通过的检查和历史审计版本边界。原始的详细实验说明和 Stage 3 语义分析放在 `docs/`。

## 目录

```text
Verifier_transfer_exp/
├── README.md、框架说明.md          # 交接入口
├── .env.example、configs/          # 模型 API 模板、实验参数
├── src/swepro_trans/              # Stage 2/3 框架实现及 CLI
├── prompts/、roles/、scripts/       # 角色提示词和命令入口
├── dataprepare/、task_list/         # Stage 1 准备代码、固定的 100 ID
├── data/dataset_rows.json          # 仅所选 100 条的官方数据行
├── data/stage1/                   # 100 条来源元数据、Base/Gold 预检证据、总审计
├── tasks/<id>/original/           # 100 份不变的原始 Harbor 任务
├── runs/<id>/                     # 只含首批 20 条的 source 和 accepted attempt
├── check/qualified_tasks.txt      # 只含首批 20 条及其 accepted attempt
├── check/frozen_20.json           # 同一清单的机器可读形式
└── check/stage3/deepseek_miniswe_20_20261008/
    └── instances/<id>/{original,converted}/rollout_001/ # 40 份补丁与双复判
```

`runs/<id>/attempts/<attempt>/final/` 是转换后可交给 Harbor 的任务包；`review/`、`intermediate/converter/`、`intermediate/validation/`、`intermediate/qa/` 是对应接受版的可审查证据。`check/stage3/.../aggregate.json` 和 `report.md` 是本轮冻结统计。为减小交接包，没有复制历史失败 attempt、agent 轨迹、Harbor 的完整 job 目录、重复生成的任务副本、镜像、缓存和后续转换名单。每个 Stage 3 rollout 保留了 `harbor_trial_result.json`、候选 patch 与正式复判结果，供异机汇总。

## 1. 环境准备

要求 Linux、Python **3.12+**、Docker CLI/daemon，以及运行模型任务时可用的 OpenAI 兼容 API。Stage 3 还需要 Harbor **0.22.0** CLI；原实验固定源码 commit 为 `4407eb5227a2ff4f0d3f16b2eb48849382fdf276`。官方任务来源固定为 `scaleapi/SWE-bench_Pro-os@66f92766bba642462d4bbe5479e83f91f9211862`。仓库和 Docker 镜像没有内嵌到这个交接包；任务输入、Gold patch、测试、镜像名和 digest 记录已保留。

从本目录执行：

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e '.[dev]'
cp .env.example .env
chmod 600 .env
```

在 `.env` 填入 `DEFAULT_BACKEND=openai_compatible`、`DEFAULT_BASE_URL`、`DEFAULT_MODEL`、`DEFAULT_API_KEY`；可以用文件中的角色变量覆盖某个 Judge、Converter 或 Solver 的模型。**`.env.example` 是要求复制的 API 配置文档；`.env` 的真实凭据由使用者本地填写，不属于 GitHub 交接内容。**框架参数在 `configs/experiment.yaml`；变量填写说明见 [docs/API配置.md](docs/API配置.md)，模型运行机制见 `docs/framework/runtime_environment.md`。

安装 Harbor 0.22.0 可使用固定源码版本：

```bash
git clone https://github.com/laude-institute/harbor.git upstream/harbor
git -C upstream/harbor checkout 4407eb5227a2ff4f0d3f16b2eb48849382fdf276
python3.12 -m venv .venv-harbor
.venv-harbor/bin/python -m pip install -e upstream/harbor
```

Stage 3 命令使用 `.venv-harbor/bin/harbor`，使 Harbor 与框架的依赖环境分开。`upstream/` 在 `.gitignore` 中，由接手者本地安装。如果只检查已有 100/20 数据的完整性，不需要模型 API、Harbor 或 Docker。

```bash
.venv/bin/python scripts/verify_bundle.py
.venv/bin/python -m swepro_trans --help
.venv/bin/python scripts/runtime_check.py
```

`runtime_check.py` 会检查运行模型和 Docker 所需的本机环境；离线完整性检查只查目录、清单、哈希与冻结结果。当前机器若没有 Python 3.12、Docker 镜像或有效模型端点，不能据此声称完成了新一轮容器/模型复跑。

## 2. 读取与复核已有实验

- Stage 1：`task_list/selected_100.txt`、`data/stage1/final_100_report.json`。总审计记录 `READY=100/100`，每条的预检报告在 `data/stage1/<id>/preflight/report.json`。在拉取全部官方镜像后，可运行 `.venv/bin/python dataprepare/audit_stage1.py` 重新审计镜像 digest 与 Base/Gold 结果。
- Stage 2：`check/qualified_tasks.txt` 精确列出 20 个 accepted attempt。查看某条的 `runs/<id>/attempts/<attempt>/review/final_audit.json`、`independent_audit.json`、`intermediate/converter/conversion_trace.json`、`final/tests/`。
- Stage 3：`check/stage3/deepseek_miniswe_20_20261008/report.md`、`aggregate.json`、`semantic_reviews.json`；逐条补丁与复判位于 `instances/`。要重新计算汇总，请先将冻结结果目录复制到临时位置，随后运行 `python -m swepro_trans.stage3 aggregate --output <临时目录>`，以免覆盖冻结文件。

### 对已有任务重新回放

先从 `tasks/<id>/original/task.toml` 找到 `environment.docker_image`，拉取或恢复报告中相同 digest 的镜像。冻结版的 Stage 2 通过记录请查看 `review/final_audit.json`、`review/independent_audit.json` 和 `check/stage3/.../manifest.json`；可执行的离线核对是 `scripts/verify_bundle.py`。对某条接受版进行**新一轮** Docker 回放可使用：

```bash
.venv/bin/python -m swepro_trans validate \
  --task-root tasks/<id> \
  --revision runs/<id>/attempts/<attempt>/intermediate/converter/revisions/<rev> \
  --execute
```

`<id>`、`<attempt>` 从 `check/qualified_tasks.txt` 取；`<rev>` 从对应 `review/final_audit.json` 的 `revision` 字段取。`--execute` 会写回 validation 文件，建议在工作副本上运行。当前代码的审计规则晚于这 20 条接受版，直接重跑 `final-audit` 时，即使用 `--allow-legacy`，部分任务也会因语义证据指纹规则变化而被重新标为 FAIL；这不改动冻结时的审计结论，若要按新规则认证必须重新语义审查和冻结。对原始任务执行 Harbor oracle 可用 `.venv/bin/python scripts/run_official_harbor_oracle.py --instance-id <id>`。

## 3. 用框架跑新一轮

Stage 1 的固定 100 条已经准备好。若从官方来源重新准备它们，在另一个工作副本依次运行：

```bash
.venv/bin/python dataprepare/prepare_swebench_pro_v2.py --ids-file task_list/selected_100.txt
.venv/bin/python dataprepare/pull_selected_images.py --workers 4
.venv/bin/python dataprepare/preflight_selected.py --workers 4
.venv/bin/python dataprepare/audit_stage1.py
```

准备脚本按固定 commit 检出官方任务；拉取源码、数据和镜像需要网络。Docker 预检耗时且会写新证据，不应在唯一的冻结副本上覆盖原报告。

Stage 2 对一条 READY 任务的标准顺序：

```bash
ID="instance_internetarchive__openlibrary-09865f5fb549694d969f0a8e49b9d204ef1853ca-ve8c8d62a2b60610a3c4631f5f23ed866bada9818"
.venv/bin/python -m swepro_trans init --instance-id "$ID"
ATTEMPT="$(find "runs/$ID/attempts" -mindepth 1 -maxdepth 1 -type d -name "attempt_*" -printf "%f\n" | sort | tail -1)"
REV=runs/$ID/attempts/$ATTEMPT/intermediate/converter/revisions/rev_001
.venv/bin/python -m swepro_trans agent --task-root tasks/$ID --revision "$REV"
.venv/bin/python -m swepro_trans pipeline --task-root tasks/$ID --revision "$REV"
# pipeline 完成后另做框架外独立审计，再运行 final-audit --write
```

`pipeline` 按结构/语义、Base/Gold 回放、行为角色、稳定性、正向 QA、负向 QA、acceptance、package 的顺序运行，失败时有界修复并创建新 revision；独立审计仍需由框架外审查生成，不能把 `pipeline` 的通过等同于首批合格清单。完整门禁和产物见 [框架说明.md](框架说明.md)。

Stage 3 只使用 `check/qualified_tasks.txt` 的 20 条。确认 20 个任务镜像和 Harbor 可用后，运行：

```bash
.venv/bin/python -m swepro_trans.stage3 all \
  --harbor .venv-harbor/bin/harbor \
  --output check/stage3/rerun_20 \
  --concurrency 10 --rollouts 1
```

该命令会重新调用模型并写一个**新目录**，不会改动首轮冻结结果。原实验的私有模型服务端未提供可固定的版本和 seed；换模型或端点得到的是新实验，不能与冻结的 40 份补丁混作同一次复现。

## 4. GitHub 交接

`.gitignore` 排除 `.env`、虚拟环境、缓存及未来重跑目录；已冻结的 100/20 数据和 API 模板应纳入版本控制。提交前运行 `scripts/verify_bundle.py`，并检查 `git status` 中没有 `.env`、实际 API key 或新生成的工作文件。历史 manifest 会保留当次实验使用的内网主机信息，不含鉴权凭据。单个最大文件约 3.1 MiB，不需要 Git LFS。已有证据 JSON 中保留了原机器的绝对路径，属于历史记录；代码入口和检查工具会以当前目录定位实际文件。

```bash
git init
git add .
git status --short
git commit -m "Archive functional verifier transfer 100/20 experiment"
# 按目标 GitHub 仓库地址配置 remote 后推送
```

本包保留了原始测试与数据行，使用或再分发时按其上游项目的适用许可处理。
