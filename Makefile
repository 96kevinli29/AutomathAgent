.PHONY: setup setup-lean install test lint run benchmark visualize clean

setup: install setup-lean

install:
	pip install -e ".[dev,viz]"

setup-lean:
	cd lean_project && lake exe cache get && lake build

test:
	pytest tests/ -m "not integration" -v

test-integration:
	pytest tests/ -m integration -v

test-all:
	pytest tests/ -v

lint:
	ruff check src/ tests/
	ruff format --check src/ tests/

format:
	ruff format src/ tests/

run:
	python scripts/run_pipeline.py

benchmark:
	python scripts/run_benchmark.py

visualize:
	python scripts/visualize.py

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	rm -rf dist/ build/ *.egg-info/
