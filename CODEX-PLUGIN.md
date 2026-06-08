# Local Codex Plugin Notes

This file documents local changes for using this repo as a Codex plugin. It is
kept separate from `README.md` to avoid conflicts when pulling upstream changes.

## What Was Added

- `scripts/update-codex-plugin.py`
  - Refreshes the local `matt-skills` Codex plugin from this repo.
  - Copies only the published buckets: `engineering`, `productivity`, and `misc`.
  - Flattens copied skills into the plugin's `skills/` directory so Codex can
    discover them.
  - Leaves `personal`, `in-progress`, and `deprecated` out of the plugin.
  - Changes copied `disable-model-invocation: true` lines to
    `disable-model-invocation: false` in the plugin copy only.
  - Updates the plugin manifest version with a Codex cachebuster suffix.

- `mise.toml`
  - Provides a cross-platform Python runtime through Mise.
  - Adds tasks for refreshing and reinstalling the plugin.

- `.gitignore`
  - Ignores Python cache files created when running the updater.

## First-Time Mise Setup

Install Mise by following the official instructions for your OS, then run this
from the repo root:

```bash
mise install
```

That installs the Python version declared in `mise.toml`, so Windows does not
need a separate system Python install.

## Updating The Plugin After Pulling Upstream

After fetching or pulling upstream changes, run:

```bash
mise run update-codex-plugin
```

This updates the local plugin files and bumps the cachebuster in
`~/plugins/matt-skills/.codex-plugin/plugin.json`.

To refresh and reinstall the plugin in Codex in one step:

```bash
mise run reinstall-codex-plugin
```

Start a new Codex thread after reinstalling so the updated skills are loaded.

If `--reinstall` says it cannot find `codex`, the plugin files were still
refreshed. Only the reinstall step failed. On Windows, this can happen when
Codex is installed from the Microsoft Store and the Codex app execution alias is
not visible in the terminal running Mise.

The updater first looks for the runnable Codex CLI under:

```text
%LOCALAPPDATA%\OpenAI\Codex\bin
```

Then it falls back to the `codex` command on `PATH`. Check what your terminal
can see with:

```powershell
where.exe codex
```

If that prints nothing, enable the Codex app execution alias in Windows Settings
or add the directory containing the Codex command to your user `PATH`, then open
a new terminal and run:

```bash
codex plugin add matt-skills@personal
```

## Running Without Mise

The updater uses only the Python standard library. If Python is already
available, this also works:

```bash
python scripts/update-codex-plugin.py
```

On some Linux systems:

```bash
python3 scripts/update-codex-plugin.py
```

## Plugin Location

The default plugin path is:

```text
~/plugins/matt-skills
```

This resolves to the right home directory on Windows and Linux. To update a
plugin in another location:

```bash
mise run update-codex-plugin -- --plugin-path /path/to/matt-skills
```

On Windows:

```powershell
mise run update-codex-plugin -- --plugin-path C:\path\to\matt-skills
```

## Moving The Plugin

You can move the plugin folder, but Codex must know where it lives.

The default personal marketplace file is:

```text
~/.agents/plugins/marketplace.json
```

For the default setup, its `matt-skills` entry points to:

```json
"path": "./plugins/matt-skills"
```

That means Codex expects the plugin at `~/plugins/matt-skills`. If you move the
plugin somewhere else, update or recreate the marketplace entry so it points at
the new location, then reinstall:

```bash
codex plugin add matt-skills@personal
```

Keeping the plugin at `~/plugins/matt-skills` on each machine is the simplest
portable setup.

## Useful Commands

Refresh only:

```bash
mise run update-codex-plugin
```

Refresh and reinstall:

```bash
mise run reinstall-codex-plugin
```

Use a custom cachebuster:

```bash
mise run update-codex-plugin -- --cachebuster my-local-token
```

Update a moved plugin:

```bash
mise run update-codex-plugin -- --plugin-path /path/to/matt-skills
```
