import json
import pathlib
import re

from jsonschema import Draft202012Validator

from aana import sdk
from eval_pipeline.pre_tool_call_gate import gate_pre_tool_call


ROOT = pathlib.Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "agent_tool_precheck.schema.json"
DOCS_PATH = ROOT / "docs" / "agent-action-contract-v1.md"
TS_PATH = ROOT / "sdk" / "typescript" / "src" / "index.ts"
FASTAPI_DOCS_PATH = ROOT / "docs" / "fastapi-service.md"
EXAMPLES_PATH = ROOT / "examples" / "agent_action_contract_cases.json"

FROZEN_FIELDS = [
    "tool_name",
    "tool_category",
    "authorization_state",
    "evidence_refs",
    "risk_domain",
    "proposed_arguments",
    "recommended_route",
]
FROZEN_ROUTES = ["accept", "ask", "defer", "refuse"]
FROZEN_CATEGORIES = ["public_read", "private_read", "write", "unknown"]
FROZEN_AUTH_STATES = ["none", "user_claimed", "authenticated", "validated", "confirmed"]


def load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def test_agent_action_contract_v1_required_fields_are_frozen() -> None:
    schema = load_schema()

    assert schema["title"] == "AANA Agent Action Contract v1"
    assert schema["$id"] == "https://aana.dev/schemas/agent_action_contract_v1.schema.json"
    assert schema["required"] == FROZEN_FIELDS
    assert schema["x-aana-contract-freeze"]["required_field_order"] == FROZEN_FIELDS
    assert "schema_version" not in schema["required"]
    assert schema["properties"]["evidence_refs"]["items"]["required"] == [
        "source_id",
        "kind",
        "trust_tier",
        "redaction_status",
        "freshness",
        "provenance",
    ]


def test_agent_action_contract_v1_route_semantics_are_frozen() -> None:
    schema = load_schema()
    route_enum = schema["properties"]["recommended_route"]["enum"]

    assert route_enum == FROZEN_ROUTES
    assert schema["x-aana-contract-freeze"]["route_order"] == FROZEN_ROUTES
    for route in FROZEN_ROUTES:
        assert route in schema["x-aana-contract-freeze"]["route_semantics"]


def test_agent_action_contract_versioning_rules_are_documented_and_schema_embedded() -> None:
    schema = load_schema()
    docs = DOCS_PATH.read_text(encoding="utf-8")
    versioning_rules = "\n".join(schema["x-aana-contract-freeze"]["versioning_rules"])

    for phrase in (
        "Future v2/v3",
        "fail closed",
        "new schema id",
        "must stay backward-compatible",
    ):
        assert phrase in docs
    for phrase in (
        "v1 required fields must not be removed",
        "Future v2/v3 schemas may add optional fields",
        "New route or enum values must be opt-in",
    ):
        assert phrase in versioning_rules


def test_python_typescript_schema_and_docs_share_frozen_enums() -> None:
    schema = load_schema()
    ts_source = TS_PATH.read_text(encoding="utf-8")
    docs = DOCS_PATH.read_text(encoding="utf-8")

    assert schema["properties"]["tool_category"]["enum"] == FROZEN_CATEGORIES
    assert schema["properties"]["authorization_state"]["enum"] == FROZEN_AUTH_STATES
    assert sdk.TOOL_CATEGORIES == set(FROZEN_CATEGORIES)
    assert sdk.AUTHORIZATION_STATES == set(FROZEN_AUTH_STATES)
    assert sdk.TOOL_PRECHECK_ROUTES == set(FROZEN_ROUTES)

    for route in FROZEN_ROUTES:
        assert re.search(rf'"{route}"', ts_source)
        assert f"`{route}`" in docs or route in docs
    for field in FROZEN_FIELDS:
        assert field in ts_source
        assert f"`{field}`" in docs


def test_fastapi_docs_reference_public_contract_and_routes() -> None:
    docs = FASTAPI_DOCS_PATH.read_text(encoding="utf-8")

    assert "Agent Action Contract v1" in docs
    assert "POST /pre-tool-check" in docs
    assert "POST /agent-check" in docs
    assert "GET /health" in docs
    assert "token auth" in docs.lower()


def test_canonical_examples_are_schema_valid_and_match_expected_routes() -> None:
    schema = load_schema()
    validator = Draft202012Validator(schema)
    examples = json.loads(EXAMPLES_PATH.read_text(encoding="utf-8"))["cases"]

    assert {case["name"] for case in examples} == {
        "safe_public_read_accept",
        "private_read_accept_authenticated",
        "private_read_ask_user_claimed",
        "write_accept_confirmed",
        "unsafe_write_refuse_no_auth",
        "unknown_tool_defer",
    }

    for case in examples:
        errors = sorted(validator.iter_errors(case["event"]), key=lambda error: list(error.path))
        assert not errors, f"{case['name']} schema errors: {[error.message for error in errors]}"
        result = gate_pre_tool_call(case["event"])
        assert result["recommended_action"] == case["expected_route"], case["name"]
        if case["expected_route"] == "accept":
            assert result["gate_decision"] == "pass"
            assert result["hard_blockers"] == []
        else:
            assert result["gate_decision"] == "fail"
            assert result["hard_blockers"]
