import io

DRIFT_CSV = b"""claim_id,member_id,doctor_id,dx_code,cpt_code,total_cost,date_of_service,status
C-100,P-10,DR-8,E11.9,99213,145.50,2026-01-12,paid
C-101,P-11,DR-9,I10,99214,-20.00,not-a-date,unknown
"""


def test_upload_approve_and_metrics(client):
    response = client.post("/api/upload", files={"file": ("drift.csv", io.BytesIO(DRIFT_CSV), "text/csv")})
    assert response.status_code == 201
    body = response.json()
    assert body["run"]["status"] == "awaiting_approval"
    run_id = body["run"]["id"]

    response = client.post(f"/api/runs/{run_id}/approve-mapping", json={"mapping": body["run"]["suggested_mapping"]})
    assert response.status_code == 200
    assert response.json()["accepted_records"] == 1
    assert response.json()["rejected_records"] == 1

    metrics = client.get("/api/metrics").json()
    assert metrics["total_claims"] == 1
    assert metrics["rejected_claims"] == 1
    assert metrics["schema_events"] == 7


def test_rejects_non_csv(client):
    response = client.post("/api/upload", files={"file": ("claims.txt", b"hello", "text/plain")})
    assert response.status_code == 400
