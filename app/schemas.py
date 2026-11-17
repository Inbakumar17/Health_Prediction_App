"""Input validation and API output shapes.

Every rule the task asks for lives here, so it is easy to show in the interview:
- Full name: letters, spaces, . ' - only
- Date of birth: dd/mm/yyyy (dd.mm.yyyy also accepted), a real calendar date, not in the future
- Email: name@domain.ending, e.g. robyn@gmail.com
- Glucose, haemoglobin, cholesterol: numbers within a possible human range
All failing fields are reported together, so the user can fix everything at once.
"""

import calendar
import re
from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field, field_serializer, field_validator

NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z .'\-]{1,79}$")
DATE_PATTERN = re.compile(r"^(\d{2})([/.])(\d{2})\2(\d{4})$")  # same separator twice
EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}$")
NUMBER_PATTERN = re.compile(r"^\d+(\.\d+)?$")

# Values outside these ranges are impossible for a living person (catches typos like 2320).
VALUE_LIMITS = {
    "glucose": ("Glucose", "mg/dL", 10, 1500),
    "haemoglobin": ("Haemoglobin", "g/dL", 1, 30),
    "cholesterol": ("Cholesterol", "mg/dL", 50, 1000),
}


def parse_dob(value: str) -> date:
    """Turn '28/01/1960' or '28.01.1960' into a date, with a clear message when it can't."""
    text = str(value).strip()
    match = DATE_PATTERN.match(text)
    if not match:
        raise ValueError("Date of birth must be in dd/mm/yyyy format, e.g. 28/01/1960.")
    day, _, month, year = (int(part) if part.isdigit() else part for part in match.groups())
    if not 1 <= month <= 12:
        raise ValueError(f"{text} is not a real date: month must be 01 to 12.")
    days_in_month = calendar.monthrange(year, month)[1]
    if not 1 <= day <= days_in_month:
        raise ValueError(
            f"{text} is not a real date: {calendar.month_name[month]} {year} has only {days_in_month} days."
        )
    dob = date(year, month, day)
    if dob > date.today():
        raise ValueError("Date of birth cannot be in the future.")
    if dob.year < 1900:
        raise ValueError("Date of birth must be after 1900.")
    return dob


def check_email(value: str) -> str:
    email = str(value).strip()
    if "@" not in email:
        raise ValueError("Email must contain '@', e.g. name@gmail.com.")
    if email.count("@") > 1:
        raise ValueError("Email can contain only one '@'.")
    if not EMAIL_PATTERN.match(email):
        domain = email.split("@", 1)[1]
        if "." not in domain:
            raise ValueError("Email domain is incomplete: it needs an ending like .com.")
        raise ValueError("Email format is not valid, e.g. name@gmail.com.")
    return email


def check_number(field: str, value) -> float:
    label, unit, low, high = VALUE_LIMITS[field]
    text = str(value).strip()
    if not NUMBER_PATTERN.match(text):
        raise ValueError(f"{label} must be a number, e.g. 98 or 98.5.")
    number = float(text)
    if not low <= number <= high:
        raise ValueError(f"{label} must be between {low} and {high} {unit}.")
    return number


class PatientIn(BaseModel):
    """What the form sends when creating or editing a record."""

    full_name: str
    dob: date
    email: str
    glucose: float
    haemoglobin: float
    cholesterol: float

    @field_validator("full_name", mode="before")
    @classmethod
    def valid_name(cls, value) -> str:
        name = " ".join(str(value).split())
        if not name:
            raise ValueError("Full name is required.")
        if not NAME_PATTERN.match(name):
            raise ValueError("Full name can contain letters, spaces, dots, hyphens and apostrophes only.")
        return name

    @field_validator("dob", mode="before")
    @classmethod
    def valid_dob(cls, value) -> date:
        return parse_dob(value)

    @field_validator("email", mode="before")
    @classmethod
    def valid_email(cls, value) -> str:
        return check_email(value)

    @field_validator("glucose", "haemoglobin", "cholesterol", mode="before")
    @classmethod
    def valid_number(cls, value, info) -> float:
        return check_number(info.field_name, value)


class RiskLevel(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class AIPrediction(BaseModel):
    """The JSON shape Gemini must return."""

    risk_level: RiskLevel = Field(description="Overall risk from these three values")
    possible_conditions: list[str] = Field(description="Short names, e.g. 'Diabetes risk'. Empty if none")
    remark: str = Field(description="One or two plain sentences, at most 220 characters")


class PatientOut(BaseModel):
    """What the API returns for each record."""

    id: int
    full_name: str
    dob: date
    age: int
    email: str
    glucose: float
    haemoglobin: float
    cholesterol: float
    remarks: str
    risk_level: str
    ai_status: str
    created_at: datetime
    updated_at: datetime

    @field_serializer("dob")
    def show_dob(self, dob: date) -> str:
        return dob.strftime("%d/%m/%Y")


def age_on(dob: date, today: date | None = None) -> int:
    today = today or date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
