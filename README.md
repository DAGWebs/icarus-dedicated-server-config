# ICARUS dedicated-server ruleset builder

This repository is the first milestone of a configurable multiplayer overhaul for
ICARUS. It turns a human-editable JSON ruleset into a deterministic, validated
manifest. A game-version-specific adapter can consume that manifest to patch
extracted Unreal data tables and package the resulting `.pak`.

> **Important:** compiling `overhaul.json` does **not** change ICARUS. The game
> cannot read this project's manifest. You still need an ICARUS-version-specific
> adapter to turn the rules into cooked Unreal assets and a `.pak`. Reconnect and
> replication fixes require a
> separate investigation. The manifest keeps policy separate from those fragile,
> game-version-specific operations.

## Supported rules

- Level cap, XP multiplier, per-level points, point caps, and per-level stats.
- Default stack multiplier and explicit item stack sizes.
- Default recipe output multiplier, recipe output/batch sizes, and ingredients.
- Craft, kill, and delivery mission goals with currencies, points, XP, and item rewards.
- Catalog-backed item, recipe, creature, and map identifiers to catch typos before packaging.

## Quick start

Python 3.11 or newer is required; the builder has no runtime dependencies.

```bash
python -m icarus_ruleset.cli validate examples/overhaul.json --catalog examples/catalog.json
python -m icarus_ruleset.cli build examples/overhaul.json \
  --catalog examples/catalog.json --output build/overhaul.manifest.json
```

When running directly from a clone, set `PYTHONPATH=src` before these commands,
or install the CLI with `python -m pip install -e .` and use `icarus-ruleset`.

The catalog is deliberately external. Replace the example catalog with identifiers
exported from the same ICARUS game build that will receive the mod. The SHA-256 in
the output is stable for semantically identical JSON and can be compared by the
server and clients in a future loader to detect ruleset mismatches.

## Dedicated-server deployment model

1. Export supported data-table identifiers from the current game version.
2. Validate and compile the administrator's ruleset.
3. Use a version-specific adapter (future work) to translate the manifest into
   table changes and package a versioned `.pak`.
4. Install the identical package on the dedicated server and every client.
5. Rebuild and retest after ICARUS updates; do not assume table layouts are stable.

Keep backups of characters, prospects, and server saves. Test a new ruleset on a
staging server: changes to caps, recipes, inventory stacks, or mission state can be
destructive when rolled back.

## How to make a mod work in game

There are two distinct build products:

1. **Rules manifest (implemented here).** This says what the administrator wants.
2. **Cooked ICARUS `.pak` (not implemented here).** This contains replacements for
   the exact assets/data tables used by a particular ICARUS release. This is the
   file the game loads.

Do not rename `overhaul.manifest.json` to `.pak`; it is not an Unreal archive. To
produce the second product today, a mod developer must inspect legally obtained
game assets, identify the current progression/item/recipe/mission tables, create
modified assets using an ICARUS-compatible Unreal modding workflow, cook them for
the game's platform and engine version, and package them with their original mount
paths. Those table names and schemas are deliberately not guessed in this project:
shipping guesses can corrupt progression or silently do nothing after an update.

Once you have a real `.pak`, stop the server and install it with:

```bash
icarus-ruleset install MyOverhaul_P.pak \
  --game-root /path/to/steamapps/common/IcarusDedicatedServer \
  --manifest build/overhaul.manifest.json
```

The command verifies the game root and copies the archive to
`Icarus/Content/Paks/mods`. It also stores the manifest beside it for operators;
ICARUS itself does not read that sidecar. Run the same command against every
player's ICARUS installation using the **same `.pak` bytes**, then start the server
and test with a new character/prospect first. If the game build has changed, rebuild
the cooked assets instead of reusing the package blindly.

For a server-only result, every changed value would have to be authoritative and
never loaded by a client. Progression, recipes, item stacks, and missions commonly
cross that boundary, so the safe deployment assumption is that both the dedicated
server and all connecting clients need the identical mod. This project does not yet
provide a handshake or automatically reject a mismatched client.

### What is required for automatic JSON-to-`.pak` builds

The next implementation step needs a representative, current set of exported table
schemas (with redistribution-safe fixtures) and the exact Unreal packaging toolchain
used for that ICARUS build. With those inputs, adapters can map each supported JSON
field to a verified table row, test the transformation, cook/package the output, and
record the target game version. Without them, this repository can validate policy
but cannot honestly promise a working in-game overhaul.

## Roadmap

1. Add adapters for verified ICARUS data-table exports and `.pak` packaging tools.
2. Expand mission stages, prerequisites, timers, locations, and reward types based
   on fields confirmed in exported game data.
3. Add a server/client ruleset handshake and useful save/disconnect logging.
4. Investigate reconnect state restoration and reward idempotency separately; these
   may require Unreal executable hooks rather than data-table patches.
