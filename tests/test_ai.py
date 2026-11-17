"""AI retry and fallback behaviour, using a fake Gemini client (no network)."""

import pytest
from google.genai import errors

from app import ai, config
from app.schemas import AIPrediction


class FakeResponse:
    def __init__(self, parsed):
        self.parsed = parsed


class FakeModels:
    def __init__(self, script):
        self.script = list(script)
        self.called: list[str] = []
        self.prompts: list[str] = []

    def generate_content(self, model, contents, config):
        self.called.append(model)
        self.prompts.append(contents)
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return FakeResponse(item)


class FakeClient:
    def __init__(self, script):
        self.models = FakeModels(script)


def api_error(code):
    return errors.APIError(code, {"error": {"code": code, "message": f"error {code}", "status": "X"}})


OK = AIPrediction(risk_level="high", possible_conditions=["Diabetes risk"], remark="High glucose (232 mg/dL).")


@pytest.fixture
def use(monkeypatch):
    monkeypatch.setattr(ai, "RETRY_WAIT_SECONDS", 0)
    monkeypatch.setattr(config, "GEMINI_MODEL", "")

    def _use(script):
        client = FakeClient(script)
        monkeypatch.setattr(ai, "_get_client", lambda: client)
        return client.models

    return _use


def test_prompt_contains_values_and_units(use):
    models = use([OK])
    ai.predict(232, 13.5, 180, 66)
    prompt = models.prompts[0]
    assert "Glucose: 232 mg/dL" in prompt and "Haemoglobin: 13.5 g/dL" in prompt
    assert "Total cholesterol: 180 mg/dL" in prompt and "age: 66" in prompt


def test_retries_when_busy(use):
    models = use([api_error(503), OK])
    assert ai.predict(232, 13.5, 180, 66) == OK
    assert models.called == ["gemini-flash-latest", "gemini-flash-latest"]


def test_skips_retired_model(use):
    models = use([api_error(404), OK])
    assert ai.predict(232, 13.5, 180, 66) == OK
    assert models.called[1] == "gemini-flash-lite-latest"


def test_bad_key_stops_immediately(use):
    models = use([api_error(403)])
    with pytest.raises(ai.AIServiceError, match="403"):
        ai.predict(232, 13.5, 180, 66)
    assert len(models.called) == 1


def test_gives_up_with_clear_message(use):
    use([api_error(503)] * 12)
    with pytest.raises(ai.AIServiceError, match="busy"):
        ai.predict(232, 13.5, 180, 66)
