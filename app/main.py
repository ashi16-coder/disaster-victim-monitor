from fastapi import FastAPI, HTTPException, Query, Header
from pydantic import BaseModel, field_validator
from typing import List, Optional
import uuid

app = FastAPI(title="Victim Report API")

_db: dict = {}


def _get_record_or_404(report_id: str) -> dict:
    record = _db.get(report_id)
    if not record:
        raise HTTPException(status_code=404, detail="Report not found")
    return record


def _assert_owner(record: dict, user_id: str) -> None:
    if record["owner_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access forbidden")


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


class ReportPatch(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    location: Optional[str] = None
    status: Optional[str] = None

    @field_validator("name", "location")
    @classmethod
    def not_blank(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("must not be blank")
        return v.strip() if v else v

    @field_validator("age")
    @classmethod
    def valid_age(cls, v: Optional[int]) -> Optonal[int]:
        if v is not None and (v < 0 or v > 120):
            raise ValueError("must be between 0 and 120")
        return v

    @field_validator("status")
    @classmethod
    def valid_status(cls, v: Optional[str]) -> Optional[str]:
        allowed = {"missing", "found", "deceased"}
        if v is not None and v not in allowed:
            raise ValueError(f"must be one of {allowed}")
        return v


class ReportOut(BaseModel):
    id: str
    name: str
    age: int
    location: str
    status: str
    owner_id: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/reports", response_model=ReportOut, status_code=201)
def create_report(report: ReportIn, x_user_id: str = Header(...)):
    record = {
        "id": str(uuid.uuid4()),
        "owner_id": x_user_id,
        "_internal_flag": False,
        **report.model_dump()
    }
    _db[record["id"]] = record
    return ReportOut(**record)


@app.get("/reports", response_model=List[ReportOut])
def list_reports(
    x_user_id: str = Header(...),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100)
):
    records = [r for r in _db.values() if r["owner_id"] == x_user_id]
    return [ReportOut(**r) for r in records[skip: skip + limit]]


@app.get("/reports/{report_id}", response_model=ReportOut)
def get_report(report_id: str, x_user_id: str = Header(...)):
    record = _get_record_or_404(report_id)
    _assert_owner(record, x_user_id)
    return ReportOut(**record)


@app.patch("/reports/{report_id}", response_model=ReportOut)
def patch_report(report_id: str, patch: ReportPatch, x_user_id: str = Header(...)):
    record = _get_record_or_404(report_id)
    _assert_owner(record, x_user_id)
    updates = patch.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields provided")
    record.update(updates)
    return ReportOut(**record)


@app.delete("/reports/{report_id}", status_code=200)
def delete_report(report_id: str, x_user_id: str = Header(...)):
    record = _get_record_or_404(report_id)
    _assert_owner(record, x_user_id)
    del _db[report_id]
    return {"deleted": report_id}

