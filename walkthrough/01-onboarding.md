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

`uv` resolves on `PATH` under some shells and not others on the same
machine — commonly it is found under Git Bash and not under PowerShell. If a
command fails with "uv is not recognized", that is the shell rather than the
project; `uv --version` tells you whether this shell can see it, and
invoking it by absolute path is the workaround.

The governance corpus is a submodule. On a fresh clone:

```sh
git submodule update --init --recursive
```

**On Windows, turn symlinks on before anything else.** `CLAUDE.md` and
`.github/copilot-instructions.md` are real symlinks to `AGENTS.md` — mode
`120000` in git. Without Developer Mode (Settings → For developers) and

```sh
git config core.symlinks true
git checkout -- .
```

they check out as one-line text files containing the target path. Nothing breaks
loudly; the files simply stop being what they claim to be, which is the kind of
failure this page exists to prevent.

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

```sh
uv run carlos check
```

That is the round every other document names, and it is the one to learn. It
runs the suite and these pages — about 520 tests, two and a half minutes, the
last of which drives real Chromium.

`carlos --help` lists the rest; `carlos --dry-run <round>` prints the command a
round runs without running it, because each is a command you could type
yourself. This one is:

```sh
uv run pytest tests walkthrough --doctest-glob=*.md
```

Both paths are named on purpose. `testpaths` in `pyproject.toml` would be
ignored the moment pytest is handed a path argument, so a walkthrough wired
that way is collected by nobody and stays green forever.

## Running it

```sh
uv run carlos serve
```

`http://localhost:8000`. The bare address redirects to the workspace at
`/rack`, keeping any query it was given. Three things to know before you debug
anything:

**Do not open the address uvicorn prints.** It binds `0.0.0.0:8000` and says
so, and `0.0.0.0` is not somewhere a browser can go — Chrome refuses it with
`ERR_ADDRESS_INVALID`. The bind is right: every interface is what lets a phone
on the same network reach this, which is the whole point of an on-device test.
Only the advertisement was wrong, so the server now prints the addresses that
work — loopback, and this machine's address on the network — above uvicorn's
line.

**Reload is off, and that is deliberate.** It does not reload here — uvicorn
prints `StatReload detected changes ... Reloading...` and keeps serving the old
code — and the reloader process it adds is what leaves listening sockets with
nothing behind them. Restart by hand after any change under `src/`.
`templates/` and `static/` are re-read per request, so those are a browser
refresh away.

**Stopping it is not what you think.** `pkill -f` leaves the process bound on
Windows, and `/healthz` will answer from a server started an hour ago while you
believe you are looking at your change. Two rounds exist for exactly this:

```sh
uv run carlos stop      # stops every server holding the port, and proves it free
uv run carlos status    # what state this checkout is in, including who is serving
```

`status` prints the serving instance and pid. If that instance is not the one you
just started, you are reading somebody else's process — which is the failure this
environment produces most often, and it cost this project a session.

If you need to do it by hand, the commands are per-platform. **Windows**, under
Git Bash:

```sh
netstat -ano | grep ':8000' | grep -c LISTENING
taskkill //F //PID <pid>
```

**macOS and Linux**:

```sh
lsof -ti :8000
kill -9 $(lsof -ti :8000)
```

More than one listener means the answer you are reading may not be from the code
in your tree.

## Where to go next

`02-the-catalogue.md` is the data model, and it is the shortest path to
understanding what this app is for.

`04-cookbook.md` is the command table for somebody already set up — every round,
and the command each one runs.
