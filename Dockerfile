FROM python:3.11-slim
COPY --from=ghcr.io/astral-sh/uv:0.11.24 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY tests ./tests
COPY schemas ./schemas
RUN uv sync --frozen
COPY Makefile ./
CMD ["sh", "-c", "uv run ruff --version >/dev/null && uv run pytest -q && uv run ledgerforge demo --count 3"]
