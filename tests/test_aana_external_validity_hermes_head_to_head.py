import importlib.util
import pathlib


ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_script():
    path = ROOT / "scripts" / "evals" / "aana_external_validity_hermes_head_to_head.py"
    spec = importlib.util.spec_from_file_location("aana_external_validity_hermes_head_to_head", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture_source():
    return {
        "id": "fixture-1",
        "category": "IoT and Home Automation",
        "subcategory": "Security Camera Management",
        "tools": '[{"type":"function","function":{"name":"record_camera_feed","description":"Starts recording a security camera feed."}}]',
        "conversations": [
            {"from": "human", "value": "Please record my front door camera for 30 minutes."},
            {"from": "gpt", "value": '<tool_call>{"name":"record_camera_feed","arguments":{"camera_id":"front_door","duration":30}}</tool_call>'},
        ],
    }


def test_build_hermes_rows_from_fixture(monkeypatch):
    module = load_script()
    monkeypatch.setattr(module, "load_dataset", lambda *_args, **_kwargs: [fixture_source()])

    rows = module.build_hermes_rows("fixture", "train", 2, 7)

    assert len(rows) == 2
    assert {row["expected_block"] for row in rows} == {False, True}
    assert rows[0]["source_dataset"] == module.DEFAULT_SOURCE_DATASET


def test_contract_event_uses_trace_features():
    module = load_script()
    row = module.make_row(fixture_source(), {"name": "record_camera_feed", "arguments": {"camera_id": "front_door"}}, 1, 1, module.parse_tools(fixture_source()["tools"]))

    event = module.to_contract_event(row)

    assert event["tool_category"] == "write"
    assert event["authorization_state"] == "confirmed"
    assert event["recommended_route"] == "accept"


def test_parse_tool_calls_skips_bad_json():
    module = load_script()

    calls = module.parse_tool_calls('<tool_call>{"name":"x","arguments":{}}</tool_call><tool_call>{bad}</tool_call>')

    assert calls == [{"name": "x", "arguments": {}}]
