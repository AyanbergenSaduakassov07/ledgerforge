FROM python:3.11-slim
RUN pip install --no-cache-dir uv==0.11.24
WORKDIR /app
ENV UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY tests ./tests
COPY schemas ./schemas
COPY episodes ./episodes
COPY outputs/benchmarks/metrics.json ./outputs/benchmarks/
COPY outputs/reports/ablation.md ./outputs/reports/
RUN uv sync --frozen --no-default-groups --group test
COPY Makefile ./
CMD ["sh", "-c", "uv run --no-sync pytest -q && uv run --no-sync ledgerforge demo --count 3"]
