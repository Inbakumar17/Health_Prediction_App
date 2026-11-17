"""AI health prediction with the Google Gemini API.

predict() sends the three blood values (plus age) to Gemini and gets back a
risk level, possible conditions and a short remark for the "Remarks" column.

Reliability: busy/rate-limited answers (429, 500, 503, 504) are retried with a
short wait, then backup models are tried; a model this key can't use (404) is
skipped. A wrong key or bad request stops at once with a clear message.
"""

import logging
import time

import httpx
from google import genai
from google.genai import errors, types

from app import config
from app.schemas import AIPrediction

log = logging.getLogger("health_app")

MODELS = ["gemini-flash-latest", "gemini-flash-lite-latest", "gemini-2.5-flash", "gemini-2.0-flash"]
RETRYABLE_CODES = {429, 500, 503, 504}
RETRIES_PER_MODEL = 2
RETRY_WAIT_SECONDS = 2.0  # 2s, then 4s

SYSTEM_PROMPT = """
You are a clinical decision-support assistant. From one adult's blood test
values you predict possible health conditions or disease risks.

REFERENCE RANGES (use these, do not invent others)
- Glucose (mg/dL, assume a random / non-fasting sample):
  below 70 = low (possible hypoglycaemia); 70-140 = normal;
  141-199 = elevated (possible prediabetes); 200 or more = high (possible diabetes).
- Haemoglobin (g/dL, adult): below 8 = severely low (severe anaemia);
  8-11.9 = low (possible anaemia); 12-17.5 = normal;
  above 17.5 = high (possible polycythaemia or dehydration).
- Total cholesterol (mg/dL): below 200 = desirable; 200-239 = borderline high;
  240 or more = high (raised heart disease risk).

RULES
- Use only the values given. Never invent other test results.
- risk_level: "high" if any value is in a high/severe band, "moderate" if any is
  elevated, low or borderline, otherwise "low".
- remark: plain English, at most 220 characters. Start with the main finding and
  name the value, e.g. "High glucose (232 mg/dL) suggests possible diabetes;
  haemoglobin and cholesterol are normal."
- If all values are normal, say "No disease risk detected from these values."
- This is a risk prediction, not a diagnosis: never say "you have".
""".strip()


class AIServiceError(Exception):
    """Gemini could not give a prediction."""


_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        if not config.GEMINI_API_KEY:
            raise AIServiceError("GEMINI_API_KEY is not set in .env.")
        _client = genai.Client(api_key=config.GEMINI_API_KEY)
    return _client


def build_prompt(glucose: float, haemoglobin: float, cholesterol: float, age: int) -> str:
    return (
        f"Patient age: {age}\n"
        f"Glucose: {glucose:g} mg/dL\n"
        f"Haemoglobin: {haemoglobin:g} g/dL\n"
        f"Total cholesterol: {cholesterol:g} mg/dL\n"
        "Predict the possible health conditions or disease risks."
    )


def predict(glucose: float, haemoglobin: float, cholesterol: float, age: int) -> AIPrediction:
    """Ask Gemini for a prediction. Raises AIServiceError if no model can answer."""
    client = _get_client()
    config_ = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        response_mime_type="application/json",
        response_schema=AIPrediction,  # Gemini must answer in exactly this JSON shape
        temperature=0.1,               # low = the same values give the same answer
    )
    prompt = build_prompt(glucose, haemoglobin, cholesterol, age)
    models = list(dict.fromkeys(([config.GEMINI_MODEL] if config.GEMINI_MODEL else []) + MODELS))

    for model in models:
        for attempt in range(RETRIES_PER_MODEL + 1):
            try:
                response = client.models.generate_content(model=model, contents=prompt, config=config_)
            except errors.APIError as exc:
                if exc.code == 404:
                    log.warning("Model %s not available, trying the next one", model)
                    break
                if exc.code not in RETRYABLE_CODES:
                    raise AIServiceError(f"Gemini API error {exc.code}: {exc.message}") from exc
                log.warning("Model %s busy (%s), attempt %d", model, exc.code, attempt + 1)
            except httpx.HTTPError as exc:
                log.warning("Network problem calling Gemini: %s", exc)
            else:
                if response.parsed is not None:
                    return response.parsed
            if attempt < RETRIES_PER_MODEL:
                time.sleep(RETRY_WAIT_SECONDS * (2 ** attempt))

    raise AIServiceError("The AI service is busy right now. The record was saved; use Retry AI later.")
