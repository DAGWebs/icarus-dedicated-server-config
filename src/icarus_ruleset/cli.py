"""Command-line interface for the ruleset builder."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from .builder import RulesetError, compile_ruleset, validate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="icarus-ruleset")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("validate", "build"):
        child = subparsers.add_parser(command)
        child.add_argument("config", type=Path)
        child.add_argument("--catalog", type=Path, required=True)
        if command == "build":
            child.add_argument("--output", type=Path, required=True)
    install = subparsers.add_parser("install", help="install an already-built mod pak")
    install.add_argument("pak", type=Path)
    install.add_argument("--game-root", type=Path, required=True)
    install.add_argument("--manifest", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "install":
            if args.pak.suffix.lower() != ".pak" or not args.pak.is_file():
                raise RulesetError(f"pak must be an existing .pak file: {args.pak}")
            content = args.game_root / "Icarus" / "Content"
            if not content.is_dir():
                raise RulesetError(
                    f"game root does not contain Icarus/Content: {args.game_root}"
                )
            manifest = None
            if args.manifest:
                manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
                if manifest.get("format") != "icarus-ruleset-manifest/v1":
                    raise RulesetError("manifest has an unsupported format")
            destination = content / "Paks" / "mods"
            destination.mkdir(parents=True, exist_ok=True)
            installed_pak = destination / args.pak.name
            shutil.copy2(args.pak, installed_pak)
            print(f"Installed {installed_pak}")
            if args.manifest and manifest is not None:
                installed_manifest = destination / f"{args.pak.stem}.ruleset.json"
                shutil.copy2(args.manifest, installed_manifest)
                print(
                    f"Installed {installed_manifest} "
                    f"({manifest.get('rulesetSha256', 'no checksum')})"
                )
        elif args.command == "validate":
            config = json.loads(args.config.read_text(encoding="utf-8"))
            catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
            validate(config, catalog)
            print(f"Valid ruleset: {args.config}")
        else:
            manifest = compile_ruleset(args.config, args.catalog, args.output)
            print(f"Built {args.output} ({manifest['rulesetSha256']})")
    except (OSError, json.JSONDecodeError, RulesetError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
