"""Ruleset validation and deterministic manifest compilation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class RulesetError(ValueError):
    """Raised when a ruleset cannot be safely compiled."""


def _positive_number(value: Any, path: str, *, allow_zero: bool = False) -> None:
    valid = isinstance(value, (int, float)) and not isinstance(value, bool)
    minimum_ok = value >= 0 if allow_zero and valid else value > 0 if valid else False
    if not minimum_ok:
        qualifier = "non-negative" if allow_zero else "positive"
        raise RulesetError(f"{path} must be a {qualifier} number")


def _known(identifier: str, values: set[str], path: str, kind: str) -> None:
    if values and identifier not in values:
        raise RulesetError(f"{path} references unknown {kind} {identifier!r}")


def validate(config: dict[str, Any], catalog: dict[str, Any]) -> None:
    """Validate supported settings and all catalog-backed identifiers."""
    if config.get("schemaVersion") != 1:
        raise RulesetError("schemaVersion must be 1")

    progression = config.get("progression", {})
    if "levelCap" in progression:
        _positive_number(progression["levelCap"], "progression.levelCap")
    if "xpMultiplier" in progression:
        _positive_number(progression["xpMultiplier"], "progression.xpMultiplier")
    for group in ("pointsPerLevel", "pointCaps", "statsPerLevel"):
        for name, value in progression.get(group, {}).items():
            _positive_number(value, f"progression.{group}.{name}", allow_zero=True)

    items = set(catalog.get("items", []))
    recipes = set(catalog.get("recipes", []))
    creatures = set(catalog.get("creatures", []))
    maps = set(catalog.get("maps", []))
    for item, amount in config.get("items", {}).get("stacks", {}).items():
        _known(item, items, f"items.stacks.{item}", "item")
        _positive_number(amount, f"items.stacks.{item}")
    if "defaultStackMultiplier" in config.get("items", {}):
        _positive_number(config["items"]["defaultStackMultiplier"], "items.defaultStackMultiplier")

    crafting = config.get("crafting", {})
    if "defaultOutputMultiplier" in crafting:
        _positive_number(crafting["defaultOutputMultiplier"], "crafting.defaultOutputMultiplier")
    for recipe, settings in crafting.get("recipes", {}).items():
        _known(recipe, recipes, f"crafting.recipes.{recipe}", "recipe")
        for key in ("craftsPerAction", "outputPerCraft"):
            if key in settings:
                _positive_number(settings[key], f"crafting.recipes.{recipe}.{key}")
        for item, amount in settings.get("ingredients", {}).items():
            _known(item, items, f"crafting.recipes.{recipe}.ingredients.{item}", "item")
            _positive_number(amount, f"crafting.recipes.{recipe}.ingredients.{item}")

    mission_ids: set[str] = set()
    for index, mission in enumerate(config.get("missions", [])):
        prefix = f"missions[{index}]"
        mission_id = mission.get("id")
        if not isinstance(mission_id, str) or not mission_id:
            raise RulesetError(f"{prefix}.id must be a non-empty string")
        if mission_id in mission_ids:
            raise RulesetError(f"{prefix}.id duplicates {mission_id!r}")
        mission_ids.add(mission_id)
        _known(mission.get("map", ""), maps, f"{prefix}.map", "map")
        if not mission.get("goals"):
            raise RulesetError(f"{prefix}.goals must contain at least one goal")
        for goal_index, goal in enumerate(mission["goals"]):
            goal_path = f"{prefix}.goals[{goal_index}]"
            goal_type = goal.get("type")
            if goal_type not in {"craft", "kill", "deliver"}:
                raise RulesetError(f"{goal_path}.type must be craft, kill, or deliver")
            target_key = "creature" if goal_type == "kill" else "item"
            target_catalog = creatures if goal_type == "kill" else items
            _known(goal.get(target_key, ""), target_catalog, f"{goal_path}.{target_key}", target_key)
            _positive_number(goal.get("amount"), f"{goal_path}.amount")
        rewards = mission.get("rewards", {})
        for name, amount in rewards.items():
            if name == "items":
                for reward_index, reward in enumerate(amount):
                    _known(reward.get("item", ""), items, f"{prefix}.rewards.items[{reward_index}].item", "item")
                    _positive_number(reward.get("amount"), f"{prefix}.rewards.items[{reward_index}].amount")
            else:
                _positive_number(amount, f"{prefix}.rewards.{name}", allow_zero=True)


def compile_ruleset(config_path: Path, catalog_path: Path, output_path: Path) -> dict[str, Any]:
    """Validate JSON input and write a stable, checksum-bearing patch manifest."""
    config = json.loads(config_path.read_text(encoding="utf-8"))
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    validate(config, catalog)
    canonical = json.dumps(config, sort_keys=True, separators=(",", ":")).encode()
    manifest = {
        "format": "icarus-ruleset-manifest/v1",
        "rulesetId": config.get("id", config_path.stem),
        "rulesetSha256": hashlib.sha256(canonical).hexdigest(),
        "rules": config,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest

