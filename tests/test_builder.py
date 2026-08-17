import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from icarus_ruleset.cli import main

from icarus_ruleset.builder import RulesetError, compile_ruleset, validate


CATALOG = {
    "items": ["Wood", "Floor"],
    "recipes": ["WoodFloor"],
    "creatures": ["Bear"],
    "maps": ["Olympus"],
}


class RulesetTests(unittest.TestCase):
    def test_build_is_deterministic(self):
        config = {
            "schemaVersion": 1,
            "id": "test",
            "items": {"stacks": {"Wood": 100}},
            "crafting": {"recipes": {"WoodFloor": {"outputPerCraft": 4}}},
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_path, catalog_path = root / "rules.json", root / "catalog.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            catalog_path.write_text(json.dumps(CATALOG), encoding="utf-8")
            first = compile_ruleset(config_path, catalog_path, root / "one.json")
            second = compile_ruleset(config_path, catalog_path, root / "two.json")
        self.assertEqual(first, second)
        self.assertEqual(len(first["rulesetSha256"]), 64)

    def test_unknown_identifier_is_rejected(self):
        config = {"schemaVersion": 1, "items": {"stacks": {"Wod": 100}}}
        with self.assertRaisesRegex(RulesetError, "unknown item 'Wod'"):
            validate(config, CATALOG)

    def test_invalid_mission_is_rejected(self):
        config = {
            "schemaVersion": 1,
            "missions": [{
                "id": "hunt",
                "map": "Olympus",
                "goals": [{"type": "kill", "creature": "Bear", "amount": 0}],
            }],
        }
        with self.assertRaisesRegex(RulesetError, "amount must be a positive number"):
            validate(config, CATALOG)

    def test_valid_mission_and_rewards(self):
        config = {
            "schemaVersion": 1,
            "missions": [{
                "id": "hunt",
                "map": "Olympus",
                "goals": [{"type": "kill", "creature": "Bear", "amount": 2}],
                "rewards": {"xp": 100, "items": [{"item": "Wood", "amount": 5}]},
            }],
        }
        validate(config, CATALOG)

    def test_install_copies_pak_and_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            game_root = root / "server"
            (game_root / "Icarus" / "Content").mkdir(parents=True)
            pak = root / "Overhaul_P.pak"
            pak.write_bytes(b"pak data")
            manifest = root / "rules.json"
            manifest.write_text(json.dumps({
                "format": "icarus-ruleset-manifest/v1",
                "rulesetSha256": "abc",
            }), encoding="utf-8")
            with patch("builtins.print"):
                result = main([
                    "install", str(pak), "--game-root", str(game_root),
                    "--manifest", str(manifest),
                ])
            mods = game_root / "Icarus" / "Content" / "Paks" / "mods"
            self.assertEqual(result, 0)
            self.assertEqual((mods / pak.name).read_bytes(), b"pak data")
            self.assertTrue((mods / "Overhaul_P.ruleset.json").is_file())


if __name__ == "__main__":
    unittest.main()
