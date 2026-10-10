from swepro_trans.agents import judge as judge_module


def test_judge_uses_dedicated_completion_budget(monkeypatch):
    captured = {}

    def fake_client(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(judge_module, "OpenAICompatibleClient", fake_client)
    config = {"model": {"backend": "openai_compatible", "max_tokens": 6144, "judge_max_tokens": 16384}}
    credentials = {"base_url": "http://example.invalid", "api_key": "unused", "model": "example", "max_tokens": "6144"}

    judge_module._client(config, credentials, "semantic_judge")
    assert captured["max_tokens"] == 16384

    credentials["judge_max_tokens"] = "8192"
    judge_module._client(config, credentials, "semantic_judge")
    assert captured["max_tokens"] == 8192
