FROM ghcr.io/astral-sh/uv:python3.12-alpine AS base
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --locked

FROM base AS development
WORKDIR /app
COPY ./loader ./loader
CMD ["uv", "run", "python", "-m", "loader.main"]