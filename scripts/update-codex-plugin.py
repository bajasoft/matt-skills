#!/usr/bin/env python3
"""Refresh the local Codex plugin from this repository.

The source repo keeps skills grouped by bucket. Codex plugins discover skills as
direct children of the plugin's `skills/` directory, so this script copies the
published buckets into a flattened plugin layout.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


PLUGIN_NAME = "matt-skills"
PUBLISHED_BUCKETS = ("engineering", "productivity", "misc")
PLUGIN_ONLY_INVOCATION_LINE = "disable-model-invocation: true"
PLUGIN_INVOCATION_REPLACEMENT = "disable-model-invocation: false"


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    plugin_root = args.plugin_path.expanduser().resolve()
    manifest_path = plugin_root / ".codex-plugin" / "plugin.json"

    ensure_existing_plugin(plugin_root, manifest_path)
    copied = refresh_skills(repo_root, plugin_root)
    patched = enable_plugin_invocation(plugin_root)

    if not args.no_cachebuster:
        old_version, new_version = update_cachebuster(
            manifest_path,
            args.cachebuster or default_cachebuster(),
        )
        print(f"Updated plugin version: {old_version} -> {new_version}")

    print(f"Copied {copied} skills into {plugin_root / 'skills'}")
    if patched:
        print(f"Adjusted invocation metadata in {patched} copied skill file(s)")

    if args.reinstall:
        marketplace_name = read_marketplace_name(args.marketplace_path)
        reinstall_plugin(PLUGIN_NAME, marketplace_name)
        print("Start a new Codex thread to pick up the refreshed plugin.")

    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Update the local matt-skills Codex plugin from this repo."
    )
    parser.add_argument(
        "--plugin-path",
        type=Path,
        default=Path.home() / "plugins" / PLUGIN_NAME,
        help="Path to the local plugin root. Defaults to ~/plugins/matt-skills.",
    )
    parser.add_argument(
        "--cachebuster",
        help="Cachebuster token for plugin.json version metadata. Defaults to a UTC timestamp.",
    )
    parser.add_argument(
        "--no-cachebuster",
        action="store_true",
        help="Copy skills without changing plugin.json version metadata.",
    )
    parser.add_argument(
        "--reinstall",
        action="store_true",
        help="Run `codex plugin add matt-skills@<marketplace>` after updating.",
    )
    parser.add_argument(
        "--marketplace-path",
        type=Path,
        default=Path.home() / ".agents" / "plugins" / "marketplace.json",
        help="Marketplace file used to find the marketplace name for --reinstall.",
    )
    return parser.parse_args()


def ensure_existing_plugin(plugin_root: Path, manifest_path: Path) -> None:
    if not manifest_path.is_file():
        raise SystemExit(
            f"Missing plugin manifest: {manifest_path}\n"
            "Create the plugin first, or pass --plugin-path to the existing plugin."
        )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    name = manifest.get("name")
    if name != PLUGIN_NAME:
        raise SystemExit(
            f"Refusing to update plugin named {name!r}; expected {PLUGIN_NAME!r}."
        )

    if plugin_root.anchor and plugin_root == Path(plugin_root.anchor):
        raise SystemExit(f"Refusing to use filesystem root as plugin path: {plugin_root}")


def refresh_skills(repo_root: Path, plugin_root: Path) -> int:
    skills_root = plugin_root / "skills"
    if skills_root.exists():
        if not skills_root.is_dir():
            raise SystemExit(f"Plugin skills path is not a directory: {skills_root}")
        shutil.rmtree(skills_root)
    skills_root.mkdir(parents=True)

    copied = 0
    for bucket in PUBLISHED_BUCKETS:
        bucket_root = repo_root / "skills" / bucket
        if not bucket_root.is_dir():
            raise SystemExit(f"Missing published skill bucket: {bucket_root}")

        for skill_root in sorted(path for path in bucket_root.iterdir() if path.is_dir()):
            if not (skill_root / "SKILL.md").is_file():
                continue
            destination = skills_root / skill_root.name
            shutil.copytree(skill_root, destination)
            copied += 1

    return copied


def enable_plugin_invocation(plugin_root: Path) -> int:
    patched = 0
    for skill_md in sorted((plugin_root / "skills").glob("*/SKILL.md")):
        contents = skill_md.read_text(encoding="utf-8")
        updated = contents.replace(
            PLUGIN_ONLY_INVOCATION_LINE,
            PLUGIN_INVOCATION_REPLACEMENT,
        )
        if updated != contents:
            skill_md.write_text(updated, encoding="utf-8")
            patched += 1
    return patched


def update_cachebuster(manifest_path: Path, cachebuster: str) -> tuple[str, str]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    version = manifest.get("version")
    if not isinstance(version, str) or not version.strip():
        raise SystemExit(f"{manifest_path} must contain a non-empty string version.")

    sanitized = sanitize_cachebuster(cachebuster)
    base_version = version.split("+", 1)[0]
    next_version = f"{base_version}+codex.{sanitized}"
    manifest["version"] = next_version
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return version, next_version


def default_cachebuster() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def sanitize_cachebuster(value: str) -> str:
    sanitized = re.sub(r"[^a-z0-9-]+", "-", value.strip().lower())
    sanitized = re.sub(r"-{2,}", "-", sanitized).strip("-")
    if not sanitized:
        raise SystemExit("Cachebuster must contain at least one letter or digit.")
    return sanitized


def read_marketplace_name(marketplace_path: Path) -> str:
    path = marketplace_path.expanduser().resolve()
    if not path.is_file():
        raise SystemExit(f"Missing marketplace file for --reinstall: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    name = payload.get("name")
    if not isinstance(name, str) or not name.strip():
        raise SystemExit(f"{path} must contain a non-empty string name.")
    return name


def reinstall_plugin(plugin_name: str, marketplace_name: str) -> None:
    command = [*resolve_codex_command(), "plugin", "add", f"{plugin_name}@{marketplace_name}"]
    print(f"Running: {' '.join(command)}")
    try:
        subprocess.run(command, check=True)
    except FileNotFoundError as error:
        raise SystemExit(
            "Could not find `codex` on PATH. The plugin files were refreshed, but "
            "reinstall did not run. Add the Codex CLI or Windows app execution alias "
            "to PATH, then run: codex plugin add matt-skills@personal"
        ) from error
    except OSError as error:
        raise SystemExit(
            f"Could not run `codex`: {error}. The plugin files were refreshed, but "
            "reinstall did not run. If Codex is installed from the Microsoft Store, "
            "make sure the Codex app execution alias is enabled and available in "
            "this terminal, or reinstall manually from the Codex app."
        ) from error
    except subprocess.CalledProcessError as error:
        raise SystemExit(f"`{' '.join(command)}` failed with exit code {error.returncode}.") from error


def resolve_codex_command() -> list[str]:
    path_candidate = shutil.which("codex")

    if sys.platform == "win32":
        local_candidate = find_windows_local_codex()
        if local_candidate is not None:
            return [str(local_candidate)]

        if path_candidate is not None:
            return [path_candidate]

    if path_candidate is not None:
        return [path_candidate]

    return ["codex"]


def find_windows_local_codex() -> Path | None:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        return None

    bin_root = Path(local_app_data) / "OpenAI" / "Codex" / "bin"
    if not bin_root.is_dir():
        return None

    candidates = sorted(
        bin_root.glob("*/codex.exe"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
