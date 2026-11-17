"""Patient records API: Create, Read, Update, Delete + AI prediction.

Flow for create/update:
1. FastAPI + Pydantic validate the input (app/schemas.py). Bad fields -> 422 with a message per field.
2. Duplicate check: same name + date of birth + email as another record -> 409.
3. Save to the database.
4. Ask the AI for a prediction and store it in "remarks".
   If the AI is down, the record is still saved and can be retried later.
"""

from fastapi import APIRouter, Depends, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import ai
from app.database import get_db
from app.errors import RecordError
from app.models import Patient
from app.schemas import PatientIn, PatientOut, age_on

router = APIRouter(prefix="/api/patients", tags=["patients"])

AI_FIELDS = ("dob", "glucose", "haemoglobin", "cholesterol")  # changing these needs a new prediction


def to_out(patient: Patient) -> PatientOut:
    return PatientOut(
        id=patient.id,
        full_name=patient.full_name,
        dob=patient.dob,
        age=age_on(patient.dob),
        email=patient.email,
        glucose=patient.glucose,
        haemoglobin=patient.haemoglobin,
        cholesterol=patient.cholesterol,
        remarks=patient.remarks,
        risk_level=patient.risk_level,
        ai_status=patient.ai_status,
        created_at=patient.created_at,
        updated_at=patient.updated_at,
    )


def get_or_404(patient_id: int, db: Session) -> Patient:
    patient = db.get(Patient, patient_id)
    if patient is None:
        raise RecordError(404, f"Record #{patient_id} was not found.")
    return patient


def reject_duplicate(data: PatientIn, db: Session, ignore_id: int | None = None) -> None:
    """Same person = same name, date of birth and email (ignoring capital letters)."""
    query = select(Patient).where(
        func.lower(Patient.full_name) == data.full_name.lower(),
        Patient.dob == data.dob,
        func.lower(Patient.email) == data.email.lower(),
    )
    if ignore_id is not None:
        query = query.where(Patient.id != ignore_id)
    existing = db.scalars(query).first()
    if existing:
        message = f"Duplicate record: {existing.full_name} with this date of birth and email already exists as record #{existing.id}."
        raise RecordError(409, message, {"full_name": message})


def apply_ai_prediction(patient: Patient) -> None:
    """Fill remarks from the AI. Never raises: an AI failure is stored on the record instead."""
    try:
        prediction = ai.predict(patient.glucose, patient.haemoglobin, patient.cholesterol, age_on(patient.dob))
    except ai.AIServiceError as exc:
        patient.remarks = str(exc)
        patient.risk_level = ""
        patient.ai_status = "failed"
        return
    patient.remarks = prediction.remark.strip()
    patient.risk_level = prediction.risk_level.value
    patient.ai_status = "done"


@router.get("", response_model=list[PatientOut])
def list_patients(db: Session = Depends(get_db)) -> list[PatientOut]:
    return [to_out(p) for p in db.scalars(select(Patient).order_by(Patient.id)).all()]


@router.get("/{patient_id}", response_model=PatientOut)
def get_patient(patient_id: int, db: Session = Depends(get_db)) -> PatientOut:
    return to_out(get_or_404(patient_id, db))


@router.post("", response_model=PatientOut, status_code=201)
def create_patient(data: PatientIn, db: Session = Depends(get_db)) -> PatientOut:
    reject_duplicate(data, db)
    patient = Patient(**data.model_dump())
    db.add(patient)
    db.commit()  # saved first, so the record is never lost if the AI fails

    apply_ai_prediction(patient)
    db.commit()
    return to_out(patient)


@router.put("/{patient_id}", response_model=PatientOut)
def update_patient(patient_id: int, data: PatientIn, db: Session = Depends(get_db)) -> PatientOut:
    patient = get_or_404(patient_id, db)
    reject_duplicate(data, db, ignore_id=patient_id)

    values = data.model_dump()
    needs_new_prediction = any(getattr(patient, f) != values[f] for f in AI_FIELDS) or patient.ai_status != "done"
    for field, value in values.items():
        setattr(patient, field, value)
    db.commit()

    # Changing only the name or email keeps the existing prediction (no extra AI call).
    if needs_new_prediction:
        apply_ai_prediction(patient)
        db.commit()
    return to_out(patient)


@router.delete("/{patient_id}", status_code=204)
def delete_patient(patient_id: int, db: Session = Depends(get_db)) -> Response:
    db.delete(get_or_404(patient_id, db))
    db.commit()
    return Response(status_code=204)


@router.post("/{patient_id}/predict", response_model=PatientOut)
def retry_prediction(patient_id: int, db: Session = Depends(get_db)) -> PatientOut:
    """Run the AI again, e.g. after it was busy."""
    patient = get_or_404(patient_id, db)
    apply_ai_prediction(patient)
    db.commit()
    return to_out(patient)
