import json

import jsonschema
import pytest

from palimp_sim.generate import generate
from palimp_sim.truth import schema, validate


def test_schema_is_valid() -> None:
    jsonschema.Draft202012Validator.check_schema(schema())


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_ground_truth_matches_schema(seed: int) -> None:
    validate(json.loads(generate("easy", seed)["ground_truth.json"]))


def test_schema_rejects_unknown_verdict() -> None:
    document = json.loads(generate("easy", 1)["ground_truth.json"])
    document["rules"][0]["expected"]["verdict"] = "delete"
    with pytest.raises(jsonschema.ValidationError):
        validate(document)
