# extend the browsertrix-crawler docker image
FROM webrecorder/browsertrix-crawler:latest

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates git \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# NOTE: /app is already used by browsertrix-crawler
WORKDIR /browsertrix-harvester

# NOTE: build isolated virtual environment for CLI, distinct from system python which
#   the base image uses for browsertrix-crawler
COPY pyproject.toml uv.lock* .python-version ./
RUN uv venv .venv
RUN uv sync --frozen --no-dev --no-install-project

# NOTE: install with --no-editable, as we'll call it absolutely in the entrypoint
COPY harvester/ ./harvester/
RUN uv sync --frozen --no-dev --no-editable

COPY tests/ ./tests/

ENTRYPOINT ["/browsertrix-harvester/.venv/bin/harvester"]
CMD []