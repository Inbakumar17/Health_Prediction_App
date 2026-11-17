"""Database table for patient records."""

from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(80))
    dob: Mapped[date] = mapped_column(Date)
    email: Mapped[str] = mapped_column(String(254))
    glucose: Mapped[float] = mapped_column(Float)        # mg/dL
    haemoglobin: Mapped[float] = mapped_column(Float)    # g/dL
    cholesterol: Mapped[float] = mapped_column(Float)    # mg/dL

    # Filled in by the AI after the record is saved
    remarks: Mapped[str] = mapped_column(Text, default="")
    risk_level: Mapped[str] = mapped_column(String(10), default="")  # low / moderate / high
    ai_status: Mapped[str] = mapped_column(String(10), default="pending")  # pending / done / failed

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
