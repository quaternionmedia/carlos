"""Numbers the app and its tooling both have to agree about.

Small on purpose, and importing nothing: `tools/cli.py` needs the port to say
what is running and to stop it, and importing `src.main` to learn one integer
would drag FastAPI into a command whose job is to print a line.
"""

from __future__ import annotations

# 4186 Hz is C8, the top note of a piano.
#
# Predictable rather than free-floating, for the reason `Settings` gives: this
# is a thing you open in a browser. Chosen to stay out of the way of the ports a
# developer already has something on - 3000, 4000 and 4200, 5000, 5173, 8000,
# 8080, 8888 - because the machine running Carlos is usually the machine running
# everything else, and a workspace that will not start because a Vite server got
# there first is a bad first thirty seconds.
#
# `CARLOS_PORT` moves it, and `carlos dev --port` moves it for one run.
DEFAULT_PORT = 4186
