FROM python:3.11-slim
RUN pip install --no-cache-dir uv==0.11.24
WORKDIR /app
ENV UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY tests ./tests
COPY schemas ./schemas
COPY episodes ./episodes
RUN uv sync --frozen
COPY Makefile ./
CMD ["sh", "-c", "uv run ruff --version >/dev/null && uv run pytest -q && uv run ledgerforge demo --count 3"]
