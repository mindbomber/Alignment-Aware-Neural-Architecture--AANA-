import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from eval_pipeline.mi_pilot import research_citation_pilot_handoffs


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "interoperability_contract.schema.json"


class InteroperabilityContractSchemaTests(unittest.TestCase):
    def test_interoperability_contract_schema_is_valid_draft_2020_12(self):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

        Draft202012Validator.check_schema(schema)

    def test_research_citation_pilot_handoffs_validate_against_schema(self):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema)

        for handoff in research_citation_pilot_handoffs():
            errors = sorted(validator.iter_errors(handoff), key=lambda error: list(error.path))
            self.assertEqual(
                errors,
                [],
                "\n".join(f"{'/'.join(map(str, error.path))}: {error.message}" for error in errors),
            )


if __name__ == "__main__":
    unittest.main()
