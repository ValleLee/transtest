"""Read-only, schema-oriented LLM judges.

Judges deliberately have no repository tools.  The orchestrator builds a fixed
evidence bundle and this module asks for one JSON verdict.  A judge can explain
its decision in the JSON, but it cannot edit artifacts or decide the next
pipeline stage.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..model_clients import AnthropicCompatibleClient, OpenAICompatibleClient


def _profile(credentials: dict[str, Any], role: str) -> dict[str, Any]:
    if "base_url" in credentials:
        return credentials
    merged = dict(credentials.get("default", {}))
    merged.update(credentials.get(role, {}))
    return merged


def _client(config: dict[str, Any], credentials: dict[str, Any], role: str):
    profile = _profile(credentials, role)
    backend = profile.get("backend") or config["model"]["backend"]
    kwargs = {
        "base_url": profile["base_url"],
        "api_key": profile["api_key"],
        "model": profile.get("model") or config["model"]["model"],
        # Judges use the dedicated bounded timeout.  The shared .env loader
        # supplies a long agent timeout by default; letting that value override
        # this setting makes a malformed or stalled judge request block QA for
        # many minutes.
        "timeout": int(
            profile.get("judge_request_timeout_seconds")
            or config["model"].get("judge_request_timeout_seconds")
            or profile.get("request_timeout_seconds")
            or config["model"].get("request_timeout_seconds", 300)
        ),
        "max_tokens": int(
            profile.get("judge_max_tokens")
            or config["model"].get("judge_max_tokens")
            or profile.get("max_tokens")
            or config["model"].get("max_tokens", 8192)
        ),
    }
    if backend == "openai_compatible":
        return OpenAICompatibleClient(**kwargs)
    if backend == "anthropic_compatible":
        return AnthropicCompatibleClient(**kwargs)
    raise ValueError(f"unsupported judge backend: {backend}")


def _parse_json(text: str) -> dict[str, Any]:
    raw = str(text or "").strip()
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        # Reasoning-capable providers occasionally wrap the final object in
        # prose/fences or emit a second trailing object. Decode complete JSON
        # values instead of taking the first opening brace through the last
        # closing brace, which turns valid multi-object output into Extra data.
        decoder = json.JSONDecoder()
        candidates: list[dict[str, Any]] = []
        for offset, char in enumerate(raw):
            if char != "{":
                continue
            try:
                candidate, _ = decoder.raw_decode(raw, offset)
            except json.JSONDecodeError:
                continue
            if isinstance(candidate, dict):
                candidates.append(candidate)
        if not candidates:
            raise ValueError(f"judge did not return JSON: {raw[:500]!r}")
        verdicts = [candidate for candidate in candidates if "verdict" in candidate]
        if verdicts:
            value = verdicts[-1]
        elif len(candidates) == 1:
            value = candidates[0]
        else:
            # A few providers split a schema-shaped answer into adjacent
            # objects. Recover only when the object is recognizably a judge
            # payload; arbitrary diagnostics must remain an infra failure.
            schema_keys = {"findings", "unconverted_f2p", "overreach", "mapping_gaps"}
            structured = [candidate for candidate in candidates
                          if schema_keys.intersection(candidate)]
            if structured:
                value = max(structured, key=lambda candidate: len(candidate.keys()))
            else:
                raise ValueError(f"judge returned multiple JSON objects without a verdict; keys={[sorted(candidate) for candidate in candidates]}")
    if not isinstance(value, dict):
        raise ValueError("judge JSON must be an object")
    return value


def _usage(raw: Any) -> dict[str, int] | None:
    """Keep provider token counters without retaining the raw API payload."""
    if not isinstance(raw, dict) or not isinstance(raw.get("usage"), dict):
        return None
    value = raw["usage"]
    details = value.get("prompt_tokens_details") or {}
    cached = value.get("cached_tokens") or value.get("cache_read_input_tokens") or value.get("prompt_cache_hit_tokens")
    if not cached and isinstance(details, dict):
        cached = details.get("cached_tokens", 0)
    try:
        input_tokens = int(value.get("input_tokens") or value.get("prompt_tokens") or 0)
        output_tokens = int(value.get("output_tokens") or value.get("completion_tokens") or 0)
        total_tokens = int(value.get("total_tokens") or input_tokens + output_tokens)
        cached_tokens = int(cached or 0)
    except (TypeError, ValueError):
        return None
    return {"input_tokens": input_tokens, "output_tokens": output_tokens,
            "total_tokens": total_tokens, "cached_tokens": cached_tokens}


def judge(*, config: dict[str, Any], credentials: dict[str, Any], role: str,
          system: str, evidence: dict[str, Any]) -> dict[str, Any]:
    """Run one judge with no tools and return a parsed JSON object."""
    client = _client(config, credentials, role)
    messages = [
        {"role": "system", "content": system +
         "\nReturn the short JSON verdict immediately. Do not include analysis or prose outside JSON."},
        {"role": "user", "content": json.dumps(evidence, ensure_ascii=False, indent=2)},
    ]
    # Prefer provider JSON mode so reasoning models cannot spend the whole
    # completion on analysis without emitting the required verdict object.
    try:
        response = client.generate(messages, [], response_format={"type": "json_object"})
    except (RuntimeError, TypeError):
        # Older gateways may reject response_format; preserve compatibility.
        response = client.generate(messages, [])
    # Some OpenAI-compatible reasoning models put the final text in
    # ``reasoning_content`` when the normal content field is empty.  Judges
    # still require a JSON verdict, but should not fail merely because the
    # provider uses that compatible response shape.
    response_text = response.content or response.reasoning_content
    if not str(response_text or "").strip():
        message = response.raw.get("choices", [{}])[0].get("message", {}) \
            if isinstance(response.raw, dict) else {}
        response_keys = sorted(response.raw) if isinstance(response.raw, dict) else []
        message_keys = sorted(message) if isinstance(message, dict) else []
        usage = response.raw.get("usage") if isinstance(response.raw, dict) else None
        usage_keys = sorted(usage) if isinstance(usage, dict) else []
        raise ValueError(
            "judge response contained no content; "
            f"response_keys={response_keys}, message_keys={message_keys}, "
            f"usage_keys={usage_keys}"
        )
    try:
        result = _parse_json(response_text)
        final_response = response
    except ValueError as first_error:
        # Some reasoning gateways consume the first completion entirely in
        # ``reasoning_content`` and leave ``content`` empty. Independent retries
        # restart that reasoning and fail at the same point. Continue from the
        # completed analysis once and demand the schema-shaped final object.
        continuation = messages + [
            {"role": "assistant", "content": response_text},
            {"role": "user", "content": (
                "Use the analysis above. Now return exactly the JSON verdict "
                "required by the system schema. Do not add reasoning, markdown, "
                "or prose outside the single JSON object."
            )},
        ]
        try:
            final_response = client.generate(
                continuation, [], response_format={"type": "json_object"}
            )
        except (RuntimeError, TypeError):
            final_response = client.generate(continuation, [])
        final_text = final_response.content or final_response.reasoning_content
        try:
            result = _parse_json(final_text)
        except ValueError as continuation_error:
            raise ValueError(
                f"judge reasoning continuation failed: first={first_error!r}; "
                f"continuation={continuation_error!r}"
            ) from continuation_error
        response_text = final_text
    result["raw_response"] = response_text
    usage = _usage(final_response.raw)
    if usage is not None:
        result["model_usage"] = usage
    return result


def write_judgement(path: Path, result: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
