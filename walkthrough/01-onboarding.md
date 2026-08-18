# 01 — Onboarding

> **Runtime: hermetic.** No port, no network, no browser. If this page passes,
> your checkout is built.

This is the first build. It is a page rather than a README section because a
README section is a claim and this ran on your machine a moment ago.

## What you need

Python 3.12 or newer, and `uv`. The interpreter running this page is the one
the project will use:

```python
>>> import sys
>>> sys.version_info >= (3, 12)
True

```

## Getting the dependencies

```sh
uv sync
```

`uv` lives at `C:\Users\peter\.local\bin\uv.exe` on the machine this was
written on. It resolves as a bare `uv` under Git Bash but **not** under
PowerShell, which needs the absolute path. If a command fails with "uv is not
recognized", that is the shell rather than the project.

The governance corpus is a submodule. On a fresh clone:

```sh
git submodule update --init --recursive
```

Skipping it does not break the app; it breaks the CI gates, which run out of
`governance/qm` and then fail for a reason that has nothing to do with your
change.

## Proving it worked

Every runtime dependency the app declares imports:

```python
>>> import fastapi, jinja2, pydantic, tinydb, uvicorn
>>> from src import catalogue, interop, main, midi, patch_format

```

A bare `python -m unittest discover` fails with `ModuleNotFoundError: No module
named 'fastapi'` — the system interpreter does not have the project's
dependencies. Everything below assumes `uv run`.

## The command

One command runs the tests and these pages:

```sh
uv run pytest tests walkthrough --doctest-glob=*.md
```

Both paths are named on purpose. `testpaths` in `pyproject.toml` would be
ignored the moment pytest is handed a path argument, so a walkthrough wired
that way is collected by nobody and stays green forever.

## Running it

```sh
uv run python src/main.py
```

`http://localhost:8000`, bound on `0.0.0.0:8000`. Two things to know before you
debug anything:

**Auto-reload does not work here, and its log lies.** uvicorn prints
`StatReload detected changes ... Reloading...` and never starts the replacement
process. Restart by hand after any change under `src/`. `templates/` and
`static/` are re-read per request, so those are a browser refresh away.

**Stopping it is not what you think.** `pkill -f` leaves the process bound on
Windows, and `/healthz` will answer from a server started an hour ago while you
believe you are looking at your change. Count the listeners:

```sh
netstat -ano | grep ':8000' | grep -c LISTENING
```

More than one means the answer you are reading may not be from the code in your
tree. Kill by PID with `taskkill //F //PID <pid>`.

## Where to go next

`02-the-catalogue.md` is the data model, and it is the shortest path to
understanding what this app is for.
