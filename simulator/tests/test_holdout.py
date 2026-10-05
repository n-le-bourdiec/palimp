"""Held-out generation (decision 0007, spec section 8.2).

The salt used here is a test value, not the repository secret.
"""

import json

import pytest

from palimp_sim.cli import main
from palimp_sim.generate import HOLDOUT_SEED_FLOOR, generate, generate_holdout, holdout_seed

SALT = "test-salt-not-the-secret"


def test_holdout_seeds_never_collide_with_dev_seeds() -> None:
    seeds = {holdout_seed(SALT, "medium", index) for index in range(200)}
    assert len(seeds) == 200
    assert all(seed >= HOLDOUT_SEED_FLOOR for seed in seeds)
    with pytest.raises(ValueError, match="dev seed"):
        generate("easy", HOLDOUT_SEED_FLOOR)
    with pytest.raises(ValueError, match="dev seed"):
        generate("easy", -1)


def test_holdout_seed_depends_on_salt_level_and_index() -> None:
    first = holdout_seed(SALT, "medium", 0)
    assert first == holdout_seed(SALT, "medium", 0)
    assert first != holdout_seed(SALT + "x", "medium", 0)
    assert first != holdout_seed(SALT, "easy", 0)
    assert first != holdout_seed(SALT, "medium", 1)


def test_holdout_scenario_hides_the_seed() -> None:
    files = generate_holdout("easy", SALT, 3)
    assert files == generate_holdout("easy", SALT, 3)
    manifest = json.loads(files["manifest.json"])
    assert manifest["split"] == "held-out"
    assert manifest["holdout_index"] == 3
    assert "seed" not in manifest
    truth = json.loads(files["ground_truth.json"])
    assert truth["scenario_id"] == manifest["scenario_id"] == "easy-000003"
    seed = str(holdout_seed(SALT, "easy", 3)).encode()
    assert not any(seed in data for data in files.values())
    assert not any(SALT.encode() in data for data in files.values())


def test_empty_salt_is_rejected() -> None:
    with pytest.raises(ValueError, match="salt"):
        generate_holdout("easy", "", 0)


def test_cli_holdout_without_salt_fails_clearly(
    monkeypatch: pytest.MonkeyPatch, tmp_path, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.delenv("HOLDOUT_SALT", raising=False)
    with pytest.raises(SystemExit) as stop:
        main(["generate", "--level", "easy", "--holdout", "0", "--out", str(tmp_path)])
    assert stop.value.code == 2
    assert "HOLDOUT_SALT" in capsys.readouterr().err
    assert not any(tmp_path.iterdir())


def test_cli_holdout_with_salt(
    monkeypatch: pytest.MonkeyPatch, tmp_path, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.setenv("HOLDOUT_SALT", SALT)
    assert main(["generate", "--level", "easy", "--holdout", "2", "--out", str(tmp_path)]) == 0
    directory = tmp_path / "scenario-holdout-easy-000002"
    out = capsys.readouterr().out
    assert out.strip() == str(directory)
    assert SALT not in out
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["split"] == "held-out"


def test_cli_seed_and_holdout_are_exclusive(tmp_path) -> None:
    both = ["--seed", "1", "--holdout", "1"]
    with pytest.raises(SystemExit) as stop:
        main(["generate", "--level", "easy", *both, "--out", str(tmp_path)])
    assert stop.value.code == 2
