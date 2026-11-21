.PHONY: install lint test demo verify walkthrough web bench ablation figures clean

install:
	uv sync --frozen

lint:
	uv run ruff check .
	uv run ruff format --check .

test:
	uv run pytest -q

demo:
	uv run ledgerforge demo --count 3

# One command for judges: offline, no API keys, no GPU.
verify: install lint test demo

walkthrough:
	uv run python -m ledgerforge.walkthrough

web:
	uv run --frozen --group web streamlit run src/ledgerforge/web.py

bench:
	uv run ledgerforge bench
	uv run python -m ledgerforge.benchmark.analyze

figures:
	uv run python -m ledgerforge.benchmark.figures

ablation:
	uv run python -m ledgerforge.benchmark.ablation

clean:
	rm -rf outputs/trajectories/*.jsonl episodes/generated private/generated .pytest_cache .ruff_cache
