# 模型 API 配置

本目录的可公开 API 配置模板是根目录的 [`.env.example`](../.env.example)。复制成 `.env` 后填写本机或机构提供的 OpenAI 兼容端点和凭据：

```bash
cp .env.example .env
chmod 600 .env
```

| 变量 | 用途 |
| --- | --- |
| `DEFAULT_BACKEND` | 本轮框架使用 `openai_compatible` |
| `DEFAULT_BASE_URL` | 模型服务的完整 base URL |
| `DEFAULT_MODEL` | 默认模型名；重新实验应记录实际模型与服务版本 |
| `DEFAULT_API_KEY` | 本地鉴权凭据 |
| `DEFAULT_REQUEST_TIMEOUT_SECONDS`、`DEFAULT_MAX_TOKENS` | 默认请求超时和输出上限 |
| `CONVERTER_MODEL`、`SOLVER_MODEL` | 可选的角色专用模型 |
| `VERIFIER_JUDGE_MODEL`、`SOLUTION_JUDGE_MODEL`、`MUTATION_JUDGE_MODEL` | 可选的 Judge 模型 |

角色变量未填写时继承 `DEFAULT_*`。`configs/experiment.yaml` 负责 prompt 路径、agent 步数、回放与 QA 预算；它不存凭据。配置完成后运行 `.venv/bin/python scripts/runtime_check.py` 检查 Python、Docker、mini-swe-agent 和模型配置。Stage 3 还需 Harbor 0.22.0。

`.env` 已在 `.gitignore` 中；交接到 GitHub 的是模板和此说明。历史 `manifest.json` 可能记录原机器的 API 主机名与绝对路径，用于说明当次实验环境，并不提供可用凭据。
