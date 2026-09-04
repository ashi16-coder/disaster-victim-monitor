import pytest
from fastapi.testclient import TestClient
from app.main import app, _db

client = TestClient(app)

VALID = {"name": "Jane Doe", "age": 30, "location": "Shelter A", "status": "missing"}


@pytest.fixture(autouse=True)
def clear_db():
    _db.clear()


# --- valid data is persisted ---

def test_valid_data_returns_201_and_is_persisted():
    response = client.post("/reports", json=VALID)
    assert response.status_code == 201
    body = response.json()
    assert body["id"] in _db
    assert _db[body["id"]]["name"] == VALID["name"]


# --- invalid input returns useful 4xx errors ---

@pytest.mark.parametrize("bad_payload,expected_field", [
    ({**VALID, "name": ""},        "name"),
    ({**VALID, "name": "   "},     "name"),
    ({**VALID, "age": -1},         "age"),
    ({**VALID, "age": 200},        "age"),
    ({**VALID, "location": ""},    "location"),
    ({**VALID, "status": "hurt"},  "status"),
    ({k: v for k, v in VALID.items() if k != "age"}, "age"),  # missing field
])
def test_invalid_input_returns_422_with_field(bad_payload, expected_field):
    response = client.post("/reports", json=bad_payload)
    assert response.status_code == 422
    fields = [e["loc"][-1] for e in response.json()["detail"]]
    assert expected_field in fields


# --- response does not expose internal fields ---

def test_response_hides_internal_fields():
    response = client.post("/reports", json=VALID)
    body = response.json()
    assert "_internal_flag" not in body
    assert set(body.keys()) == {"id", "name", "age", "location", "status"}
