import json
from difflib import SequenceMatcher
from .config import get_settings

EXPECTED_COLUMNS = [
    "claim_id", "patient_id", "provider_id", "diagnosis_code",
    "procedure_code", "claim_amount", "claim_date", "claim_status",
]

KNOWN_DRIFT = {
    "member_id": "patient_id",
    "doctor_id": "provider_id",
    "dx_code": "diagnosis_code",
    "cpt_code": "procedure_code",
    "total_cost": "claim_amount",
    "date_of_service": "claim_date",
    "status": "claim_status",
    "claim_number": "claim_id",
}


def mock_mapping(columns: list[str]) -> tuple[dict[str, str], dict[str, float]]:
    mapping, confidence = {}, {}
    for source in columns:
        normalized = source.strip().lower().replace(" ", "_").replace("-", "_")
        if normalized in EXPECTED_COLUMNS:
            target, score = normalized, 1.0
        elif normalized in KNOWN_DRIFT:
            target, score = KNOWN_DRIFT[normalized], 0.98
        else:
            matches = [(candidate, SequenceMatcher(None, normalized, candidate).ratio()) for candidate in EXPECTED_COLUMNS]
            target, score = max(matches, key=lambda item: item[1])
            if score < 0.55:
                continue
        if target not in mapping.values():
            mapping[source] = target
            confidence[source] = score
    return mapping, confidence


def suggest_mapping(columns: list[str]) -> tuple[dict[str, str], dict[str, float], str]:
    settings = get_settings()
    if not settings.openai_api_key:
        mapping, confidence = mock_mapping(columns)
        return mapping, confidence, "mock"
    try:
        from openai import OpenAI
        client = OpenAI(api_key=settings.openai_api_key)
        response = client.chat.completions.create(
            model=settings.openai_model,
            response_format={"type": "json_object"},
            temperature=0,
            messages=[
                {"role": "system", "content": "Map healthcare CSV source columns to the allowed target schema. Return JSON with a 'mapping' object only. Omit unknown columns."},
                {"role": "user", "content": json.dumps({"source_columns": columns, "target_columns": EXPECTED_COLUMNS})},
            ],
        )
        proposed = json.loads(response.choices[0].message.content or "{}").get("mapping", {})
        valid = {s: t for s, t in proposed.items() if s in columns and t in EXPECTED_COLUMNS}
        return valid, {source: 0.9 for source in valid}, "openai"
    except Exception:
        mapping, confidence = mock_mapping(columns)
        return mapping, confidence, "mock_fallback"
