import pytest
from fastapi.testclient import TestClient
from app.main import app, _db

client = TestClient(app)

VALID = {"name": "Jane Doe", "age": 30, "location": "Shelter A", "status": "missing"}


@pytest.fixture(autouse=True)
def clear_db():
    _db.clear()


def _seed(n: int) -> list:
    ids = []
    for i in range(n):
        r = client.post("/reports", json={**VALID, "name": f"Person {i}"})
        ids.append(r.json()["id"])
    return ids


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
    ({k: v for k, v in VALID.items() if k != "age"}, "age"),
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


# --- list endpoint is paginated ---

def test_list_default_pagination():
    _seed(15)
    response = client.get("/reports")
    assert response.status_code == 200
    assert len(response.json()) == 10  # default limit


def test_list_skip_and_limit():
    _seed(10)
    response = client.get("/reports?skip=5&limit=3")
    assert response.status_code == 200
    assert len(response.json()) == 3


def test_list_invalid_pagination_returns_422():
    assert client.get("/reports?limit=0").status_code == 422
    assert client.get("/reports?skip=-1").status_code == 422


# --- detail endpoint is scoped correctly ---

def test_get_report_returns_correct_record():
    ids = _seed(3)
    for report_id in ids:
        response = client.get(f"/reports/{report_id}")
        assert response.status_code == 200
        assert response.json()["id"] == report_id


def test_get_report_does_not_return_other_records():
    ids = _seed(2)
    r0 = client.get(f"/reports/{ids[0]}").json()
    r1 = client.get(f"/reports/{ids[1]}").json()
    assert r0["id"] != r1["id"]
    assert r0["name"] != r1["name"]


# --- missing records return 404 ---

def test_missing_record_returns_404():
    response = client.get("/reports/nonexistent-id")
    assert response.status_code == 404
    assert "detail" in response.json()


def test_404_after_db_is_empty():
    _seed(1)
    _db.clear()
    response = client.get("/reports/any-id")
    assert response.status_code == 404


# --- partial updates validate fields ---

def test_patch_single_field_updates_only_that_field():
    report_id = _seed(1)[0]
    original = client.get(f"/reports/{report_id}").json()
    response = client.patch(f"/reports/{report_id}", json={"status": "found"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "found"
    assert body["name"] == original["name"]  # untouched


@pytest.mark.parametrize("bad_patch,expected_field", [
    ({"name": ""},       "name"),
    ({"age": -5},        "age"),
    ({"age": 200},       "age"),
    ({"location": " "}, "location"),
    ({"status": "hurt"}, "status"),
])
def test_patch_invalid_field_returns_422(bad_patch, expected_field):
    report_id = _seed(1)[0]
    response = client.patch(f"/reports/{report_id}", json=bad_patch)
    assert response.status_code == 422
    fields = [e["loc"][-1] for e in response.json()["detail"]]
    assert expected_field in fields


def test_patch_empty_body_returns_400():
    report_id = _seed(1)[0]
    response = client.patch(f"/reports/{report_id}", json={})
    assert response.status_code == 400


def test_patch_missing_record_returns_404():
    response = client.patch("/reports/nonexistent", json={"status": "found"})
    assert response.status_code == 404


# --- delete behavior is explicit ---

def test_delete_removes_record_and_returns_200():
    report_id = _seed(1)[0]
    response = client.delete(f"/reports/{report_id}")
    assert response.status_code == 200
    assert response.json()["deleted"] == report_id
    assert report_id not in _db


def test_delete_missing_record_returns_404():
    response = client.delete("/reports/nonexistent")
    assert response.status_code == 404


def test_delete_then_get_returns_404():
    report_id = _seed(1)[0]
    client.delete(f"/reports/{report_id}")
    assert client.get(f"/reports/{report_id}").status_code == 404


# --- database constraints remain valid ---

def test_patch_does_not_corrupt_other_records():
    id1, id2 = _seed(2)
    client.patch(f"/reports/{id1}", json={"status": "found"})
    assert _db[id2]["status"] == "missing"  # id2 untouched


def test_delete_does_not_remove_other_records():
    id1, id2 = _seed(2)
    client.delete(f"/reports/{id1}")
    assert id2 in _db


def test_patch_preserves_internal_fields():
    report_id = _seed(1)[0]
    client.patch(f"/reports/{report_id}", json={"status": "found"})
    assert "_internal_flag" in _db[report_id]  # internal field still in DB

