VENV := .venv
BIN := $(VENV)/bin

.PHONY: install check fmt demo ui

install:
	uv venv --python 3.11 $(VENV)
	uv pip install --python $(BIN)/python -r requirements.txt -e .

check:
	$(BIN)/ruff check .
	$(BIN)/pytest -q

fmt:
	$(BIN)/ruff format .

demo:
	@echo "placeholder: demo is not implemented yet (see docs/DEMO.md)"

ui:
	@echo "placeholder: streamlit run ui/app.py (UI not implemented yet)"
