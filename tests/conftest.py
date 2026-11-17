"""Test setup: a temporary database and a fake AI (no API key or internet needed)."""

import os
import tempfile
from pathlib import Path

os.environ["DATABASE_URL"] = f"sqlite:///{Path(tempfile.mkdtemp()) / 'test.db'}"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import ai  # noqa: E402
from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.schemas import AIPrediction  # noqa: E402


class FakeAI:
    def __init__(self):
        self.calls = 0
        self.fail = False

    def predict(self, glucose, haemoglobin, cholesterol, age):
        self.calls += 1
        if self.fail:
            raise ai.AIServiceError("The AI service is busy right now. The record was saved; use Retry AI later.")
        level = "high" if glucose >= 200 or haemoglobin < 8 or cholesterol >= 240 else "low"
        return AIPrediction(risk_level=level, possible_conditions=[], remark=f"Test remark for glucose {glucose:g}.")


@pytest.fixture
def fake_ai(monkeypatch):
    fake = FakeAI()
    monkeypatch.setattr(ai, "predict", fake.predict)
    return fake


@pytest.fixture
def client(fake_ai):
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with TestClient(app) as test_client:
        yield test_client
