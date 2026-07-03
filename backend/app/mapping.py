import json
from difflib import SequenceMatcher
import httpx
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


SYSTEM_PROMPT = (
    "Map healthcare CSV source columns to the allowed target schema. "
    "Return JSON with a 'mapping' object only. Omit unknown columns."
)


def _validated_mapping(proposed: dict, columns: list[str]) -> dict[str, str]:
    valid: dict[str, str] = {}
    for source, target in proposed.items():
        if source in columns and target in EXPECTED_COLUMNS and target not in valid.values():
            valid[source] = target
    return valid


def openai_mapping(columns: list[str]) -> dict[str, str]:
    settings = get_settings()
    from openai import OpenAI
    client = OpenAI(api_key=settings.openai_api_key, timeout=settings.llm_timeout_seconds)
    response = client.chat.completions.create(
        model=settings.openai_model,
        response_format={"type": "json_object"},
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps({"source_columns": columns, "target_columns": EXPECTED_COLUMNS})},
        ],
    )
    proposed = json.loads(response.choices[0].message.content or "{}").get("mapping", {})
    return _validated_mapping(proposed, columns)


def ollama_mapping(columns: list[str]) -> dict[str, str]:
    settings = get_settings()
    response = httpx.post(
        f"{settings.ollama_base_url.rstrip('/')}/api/chat",
        timeout=settings.llm_timeout_seconds,
        json={
            "model": settings.ollama_model,
            "stream": False,
            "format": "json",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps({"source_columns": columns, "target_columns": EXPECTED_COLUMNS})},
            ],
        },
    )
    response.raise_for_status()
    proposed = json.loads(response.json()["message"]["content"]).get("mapping", {})
    return _validated_mapping(proposed, columns)


def suggest_mapping(columns: list[str]) -> tuple[dict[str, str], dict[str, float], str]:
    settings = get_settings()
    providers: list[tuple[str, object]] = []
    if settings.openai_api_key:
        providers.append(("openai", openai_mapping))
    if settings.ollama_base_url:
        providers.append(("ollama", ollama_mapping))

    attempted = False
    for provider, mapper in providers:
        attempted = True
        try:
            mapping = mapper(columns)
            if mapping:
                return mapping, {source: 0.9 for source in mapping}, provider
        except Exception:
            continue

    mapping, confidence = mock_mapping(columns)
    return mapping, confidence, "mock_fallback" if attempted else "mock"
