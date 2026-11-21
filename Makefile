.PHONY: install lint test demo verify walkthrough clean

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

clean:
	rm -rf outputs/trajectories/*.jsonl episodes/generated private/generated .pytest_cache .ruff_cache
