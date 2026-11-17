"""Runs the exact test data from the task, then Read, Edit and Delete."""

from datetime import date

import pytest

KEYS = ["full_name", "dob", "email", "glucose", "haemoglobin", "cholesterol"]

# Copied from the task unchanged.
TASK_DATA = [
    ("Robyn Pears", "28.01.1960", "robyn@gmail.com", "232", "13.5", "180"),
    ("John Hunter", "10.12.1990", "hunter@gmail", "94", "15", "200"),
    ("Darryl Tim", "12.11.1993", "timd@smh.com.au", "240", "18.6", "326"),
    ("Peter Larry", "31.11.2001", "Larry@hotmail.com", "88", "11.5", "165"),
    ("Sam Kerr", "09.12.2006", "sam@news.com.au", "198", "8.9", "192"),
    ("Robyn Pears", "28.01.1960", "robyn@gmail.com", "232", "13.5", "180"),
    ("Madison XI", "12.09.1998", "madison@hotmail.com", "85", "7.6", "163"),
    ("Kris Wu", "19.10.2030", "Kris.wu.gmail.com", "79", "16.5", "197"),
    ("Tenille Singh", "30.11.1991", "Tenille@yahoo.com", "101", "15", "310"),
    ("Prem Kumar", "28.04.1990", "prem@telstra.com", "155", "12.5", "265"),
]

# Test number -> (expected HTTP status, fields that must be reported)
EXPECTED = {
    1: (201, set()),
    2: (422, {"email"}),            # no domain ending (.com)
    3: (201, set()),
    4: (422, {"dob"}),              # 31 November does not exist
    5: (201, set()),
    6: (409, {"full_name"}),        # duplicate of test 1
    7: (201, set()),
    8: (422, {"dob", "email"}),     # future date AND no '@'
    9: (201, set()),
    10: (201, set()),
}


def as_payload(row):
    return dict(zip(KEYS, row))


def add_all(client):
    return [client.post("/api/patients", json=as_payload(row)) for row in TASK_DATA]


def test_task_data_gives_expected_results(client):
    responses = add_all(client)
    for number, response in enumerate(responses, start=1):
        status, fields = EXPECTED[number]
        assert response.status_code == status, f"Test {number}: {response.text}"
        if fields:
            assert set(response.json()["errors"]) == fields, f"Test {number}: {response.json()}"


def test_error_messages_explain_the_reason(client):
    responses = add_all(client)
    assert ".com" in responses[1].json()["errors"]["email"]
    assert "November 2001 has only 30 days" in responses[3].json()["errors"]["dob"]
    assert "record #1" in responses[5].json()["detail"]
    kris = responses[7].json()["errors"]
    assert "future" in kris["dob"]
    assert "@" in kris["email"]


def test_read_list_after_adding(client):
    add_all(client)
    records = client.get("/api/patients").json()
    assert [r["full_name"] for r in records] == [
        "Robyn Pears", "Darryl Tim", "Sam Kerr", "Madison XI", "Tenille Singh", "Prem Kumar",
    ]
    robyn = records[0]
    assert robyn["dob"] == "28/01/1960"          # always shown as dd/mm/yyyy
    assert robyn["email"] == "robyn@gmail.com"   # stored exactly as entered
    assert robyn["remarks"] and robyn["ai_status"] == "done"
    assert robyn["risk_level"] == "high"


def test_edit_email_keeps_prediction(client, fake_ai):
    add_all(client)
    record = client.get("/api/patients").json()[1]  # Darryl Tim
    calls_before = fake_ai.calls
    body = {**{k: record[k] for k in KEYS}, "email": "gokul@infocare.com"}
    response = client.put(f"/api/patients/{record['id']}", json=body)
    assert response.status_code == 200
    assert response.json()["email"] == "gokul@infocare.com"
    assert response.json()["remarks"] == record["remarks"]
    assert fake_ai.calls == calls_before  # only the email changed: no new AI call


def test_edit_blood_value_gets_new_prediction(client, fake_ai):
    record = client.post("/api/patients", json=as_payload(TASK_DATA[0])).json()
    calls_before = fake_ai.calls
    body = {**{k: record[k] for k in KEYS}, "glucose": "95"}
    response = client.put(f"/api/patients/{record['id']}", json=body)
    assert response.json()["remarks"] == "Test remark for glucose 95."
    assert fake_ai.calls == calls_before + 1


def test_edit_is_validated_too(client):
    record = client.post("/api/patients", json=as_payload(TASK_DATA[0])).json()
    body = {**{k: record[k] for k in KEYS}, "email": "not-an-email"}
    assert client.put(f"/api/patients/{record['id']}", json=body).status_code == 422


def test_delete_then_list(client):
    add_all(client)
    first_id = client.get("/api/patients").json()[0]["id"]
    assert client.delete(f"/api/patients/{first_id}").status_code == 204
    remaining = client.get("/api/patients").json()
    assert len(remaining) == 5
    assert first_id not in [r["id"] for r in remaining]
    assert client.delete(f"/api/patients/{first_id}").status_code == 404


def test_duplicate_allowed_after_original_deleted(client):
    first = client.post("/api/patients", json=as_payload(TASK_DATA[0])).json()
    client.delete(f"/api/patients/{first['id']}")
    assert client.post("/api/patients", json=as_payload(TASK_DATA[5])).status_code == 201


def test_record_saved_even_if_ai_fails(client, fake_ai):
    fake_ai.fail = True
    response = client.post("/api/patients", json=as_payload(TASK_DATA[0]))
    assert response.status_code == 201
    assert response.json()["ai_status"] == "failed"

    fake_ai.fail = False
    retried = client.post(f"/api/patients/{response.json()['id']}/predict").json()
    assert retried["ai_status"] == "done"


@pytest.mark.parametrize("field,value,fragment", [
    ("full_name", "", "required"),
    ("full_name", "R2D2", "letters"),
    ("dob", "1960-01-28", "dd/mm/yyyy"),
    ("dob", "28/13/1960", "month"),
    ("dob", "29/02/2023", "28 days"),
    ("glucose", "abc", "number"),
    ("haemoglobin", "-5", "number"),
    ("cholesterol", "5000", "between"),
    ("email", "a@b@c.com", "one '@'"),
])
def test_validation_rules(client, field, value, fragment):
    body = {**as_payload(TASK_DATA[0]), field: value}
    response = client.post("/api/patients", json=body)
    assert response.status_code == 422
    assert fragment in response.json()["errors"][field]


def test_both_date_separators_accepted(client):
    slash = client.post("/api/patients", json={**as_payload(TASK_DATA[2]), "dob": "12/11/1993"})
    assert slash.status_code == 201
    assert slash.json()["dob"] == "12/11/1993"


def test_today_is_allowed_but_tomorrow_is_not(client):
    today = date.today().strftime("%d/%m/%Y")
    assert client.post("/api/patients", json={**as_payload(TASK_DATA[0]), "dob": today}).status_code == 201
