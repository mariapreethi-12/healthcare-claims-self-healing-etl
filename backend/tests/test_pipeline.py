import json
from app.config import get_settings
from app.mapping import EXPECTED_COLUMNS, mock_mapping, ollama_mapping
from app.pipeline import normalize_and_validate


def test_mock_mapping_handles_known_drift():
    mapping, confidence = mock_mapping(["claim_id", "member_id", "doctor_id", "dx_code", "cpt_code", "total_cost", "date_of_service", "status"])
    assert mapping["member_id"] == "patient_id"
    assert mapping["total_cost"] == "claim_amount"
    assert confidence["dx_code"] > 0.9


def test_validation_rejects_bad_amount_and_date():
    row = {column: "value" for column in EXPECTED_COLUMNS}
    mapping = {column: column for column in EXPECTED_COLUMNS}
    normalized, errors = normalize_and_validate(row, mapping)
    assert "claim_amount must be numeric" in errors
    assert "claim_date must use YYYY-MM-DD" in errors
    assert normalized["claim_amount"] is None


def test_ollama_mapping_validates_model_output(monkeypatch):
    monkeypatch.setattr(get_settings(), "ollama_base_url", "http://ollama:11434")

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            content = {"mapping": {"member_id": "patient_id", "invented": "claim_id"}}
            return {"message": {"content": json.dumps(content)}}

    monkeypatch.setattr("app.mapping.httpx.post", lambda *args, **kwargs: Response())
    assert ollama_mapping(["member_id"]) == {"member_id": "patient_id"}
