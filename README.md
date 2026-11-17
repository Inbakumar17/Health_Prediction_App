# Health Prediction App

A patient records app built with **Python (FastAPI)**. It stores blood test results (glucose, haemoglobin, cholesterol), validates every entry, and uses the **Google Gemini API** to predict possible health risks. The prediction is shown in the **Remarks** column.

## Features

| Requirement | How it is done |
|---|---|
| **CRUD** | Create, list, edit and delete records through a REST API (`/api/patients`) and a single web page |
| **User interface** | Dark design blending Newglyph and Blockstream (see `DESIGN.md`): a large headline with three live stat cards, a form on the left, a searchable records table on the right, and a "Rejected entries" log that keeps every validation error with its reason |
| **Validation** | Pydantic validators in `app/schemas.py`; every failing field is reported at once |
| **Persistent storage** | SQLite database (`data/patients.db`) through SQLAlchemy |
| **AI integration** | After a valid record is saved, glucose, haemoglobin, cholesterol and age are sent to Gemini, which returns a risk level and a remark as structured JSON |

## Validation rules

| Field | Rule | Example error |
|---|---|---|
| Full name | Required; letters, spaces, `.` `'` `-` | "Full name can contain letters, spaces, dots, hyphens and apostrophes only." |
| Date of birth | `dd/mm/yyyy` (`dd.mm.yyyy` also accepted); must be a real date; not in the future | "31.11.2001 is not a real date: November 2001 has only 30 days." |
| Email | `name@domain.ending` | "Email domain is incomplete: it needs an ending like .com." |
| Glucose / Haemoglobin / Cholesterol | Numbers within a possible human range | "Glucose must be a number, e.g. 98 or 98.5." |
| Duplicate | Same name + date of birth + email as an existing record | "Duplicate record: … already exists as record #1." |

**Why dots are accepted in dates:** the task's test data uses `28.01.1960` and must not be modified, while the rule says `dd/mm/yyyy`. The app accepts both separators (the same one twice), stores a real date, and always displays `dd/mm/yyyy`.

## Results with the task's test data

| # | Name | Result | Reason |
|---|---|---|---|
| 1 | Robyn Pears | ✅ Saved | High glucose (232) → diabetes risk |
| 2 | John Hunter | ❌ Rejected | `hunter@gmail` has no domain ending such as `.com` |
| 3 | Darryl Tim | ✅ Saved | High glucose, haemoglobin and cholesterol |
| 4 | Peter Larry | ❌ Rejected | `31.11.2001`: November has only 30 days |
| 5 | Sam Kerr | ✅ Saved | Elevated glucose, low haemoglobin |
| 6 | Robyn Pears | ❌ Rejected | Duplicate of record #1 |
| 7 | Madison XI | ✅ Saved | Severely low haemoglobin (7.6) |
| 8 | Kris Wu | ❌ Rejected | Two errors: date of birth in the future (2030) **and** email without `@` |
| 9 | Tenille Singh | ✅ Saved | High cholesterol (310) |
| 10 | Prem Kumar | ✅ Saved | Elevated glucose, high cholesterol |

These ten rows are also an automated test (`tests/test_patients.py`).

## How the AI prediction works

1. `app/routers/patients.py` saves the record **first**, so it is never lost if the AI is unavailable.
2. `app/ai.py` sends the three values and the patient's age to Gemini with a system prompt that contains fixed reference ranges.
3. Gemini must answer in a fixed JSON shape (`AIPrediction` in `app/schemas.py`): `risk_level`, `possible_conditions`, `remark`. Temperature is 0.1, so the same values give the same answer.
4. If Gemini is busy (429/503), the call is retried and then tried on backup models. If it still fails, the record is kept and marked "AI unavailable" with a **Retry AI** button.
5. Editing only the name or email keeps the existing remark. Changing the date of birth or any blood value asks the AI again.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/patients` | List all records |
| GET | `/api/patients/{id}` | One record |
| POST | `/api/patients` | Create (validate → duplicate check → save → AI) |
| PUT | `/api/patients/{id}` | Update |
| DELETE | `/api/patients/{id}` | Delete |
| POST | `/api/patients/{id}/predict` | Run the AI prediction again |

Errors always come back as `{"detail": "...", "errors": {"field": "message"}}`. Interactive API docs are at `/docs`.

## Project structure

```
health-prediction-app/
├── app/
│   ├── main.py            # App setup, static files, error handlers
│   ├── config.py          # Settings from .env
│   ├── database.py        # SQLite connection (SQLAlchemy)
│   ├── models.py          # Patient table
│   ├── schemas.py         # Validation rules + API/AI data shapes
│   ├── errors.py          # One JSON error format for the frontend
│   ├── ai.py              # Gemini prompt, call, retries
│   └── routers/
│       └── patients.py    # CRUD endpoints + AI prediction
├── static/                # index.html, styles.css, app.js
├── DESIGN.md              # Design decisions (colours, fonts, layout)
├── tests/                 # 25 tests: task data, CRUD, validation, AI retries
├── tools/list_models.py   # Lists and tests the Gemini models your key can use
├── data/                  # SQLite database (created on first run)
├── requirements.txt
└── .env.example
```

## Run it

```bash
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

copy .env.example .env          # macOS/Linux: cp .env.example .env
# put your Gemini API key in .env

python -m uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000.

## Run the tests

```bash
pip install -r requirements-dev.txt
python -m pytest
```

The tests use a temporary database and a fake AI, so no API key is needed.

## Note

The remarks are an AI risk prediction for demonstration purposes, not a medical diagnosis.
