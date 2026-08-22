# Carlos, as a deployable image.
#
# Two stages, and the split is the point: the builder resolves and installs
# dependencies with the same `uv` and the same lockfile the tests ran under, and
# the runtime carries the result and nothing that made it. An image that ships
# its own build tools is an image whose contents nobody can enumerate.
#
# The version is pinned rather than floating. `uv:python3.12-bookworm-slim`
# without a tag would mean this file builds a different thing next month and
# says the same words about it.
FROM ghcr.io/astral-sh/uv:0.5.11-python3.12-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Dependencies before source, so editing a template does not re-resolve the
# world. `--frozen` refuses to update the lockfile: a build that quietly
# resolves a different dependency set than the tests ran under is a build
# nobody validated.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

COPY src/ ./src/
COPY tools/ ./tools/
COPY templates/ ./templates/
COPY static/ ./static/
COPY catalogue/ ./catalogue/
COPY README.md ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev


FROM python:3.12-slim-bookworm AS runtime

# Not root. Nothing here needs to write outside its own data directory, and an
# application that runs as root because nobody said otherwise is an application
# one bug away from a much worse day.
RUN useradd --create-home --uid 10001 carlos

WORKDIR /app
COPY --from=builder --chown=carlos:carlos /app /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # Every interface, because the thing reaching this is outside the
    # container. See `DEPLOYING.md` for what that does and does not mean.
    CARLOS_HOST=0.0.0.0 \
    CARLOS_PORT=4186 \
    # The database is a file. A named volume mounted here is what makes a
    # patch outlive the container.
    CARLOS_DB=/app/data/db.json

RUN mkdir -p /app/data && chown carlos:carlos /app/data
VOLUME ["/app/data"]

USER carlos
EXPOSE 4186

# The probe the app already had, asked the way an orchestrator asks it. `/healthz`
# answers HEAD as well as GET, and reports which instance answered — so a probe
# that comes back from a container you thought you had replaced says so.
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; \
sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:4186/healthz', timeout=2).status == 200 else 1)"

# `src/main.py` and not `uvicorn` directly, because that entry point is where
# the settings live: the bind, the proxy trust, and the reload that is off. A
# command line here would be a second answer to each of them.
CMD ["python", "src/main.py"]
