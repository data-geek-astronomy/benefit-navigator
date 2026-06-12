.PHONY: install test evals evals-live cli app clean

install:
	pip install -r requirements.txt

test:
	pytest -q

# Deterministic eval layer — free, no API key.
evals:
	python evals/run_evals.py

# Full eval layer — runs the agent + LLM judge. Needs ANTHROPIC_API_KEY.
evals-live:
	python evals/run_evals.py --live

cli:
	python cli.py

app:
	streamlit run app/streamlit_app.py

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache
