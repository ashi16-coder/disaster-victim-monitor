from fastapi import FastAPI
from pydantic import BaseModel, field_validator
import uuid

app = FastAPI(title="Victim Report API")

_db: dict = {}


class ReportIn(BaseModel):
    name: str
    age: int
    location: str
    status: str  # "missing" | "found" | "deceased"

    @field_validator("name", "location")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be blank")
        return v.strip()

    @field_validator("age")
    @classmethod
    def valid_age(cls, v: int) -> int:
        if v < 0 or v > 120:
            raise ValueError("must be between 0 and 120")
        return v

    @field_validator("status")
    @classmethod
    def valid_status(cls, v: str) -> str:
        allowed = {"missing", "found", "deceased"}
        if v not in allowed:
            raise ValueError(f"must be one of {allowed}")
        return v


class ReportOut(BaseModel):
    id: str
    name: str
    age: int
    location: str
    status: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/reports", response_model=ReportOut, status_code=201)
def create_report(report: ReportIn):
    record = {"id": str(uuid.uuid4()), "_internal_flag": False, **report.model_dump()}
    _db[record["id"]] = record
    return ReportOut(**record)


app = FastAPI(title="Disaster Victim Monitor")


@app.get("/health")
def health_check():
    return {"status": "ok", "message": "Service is healthy"}

