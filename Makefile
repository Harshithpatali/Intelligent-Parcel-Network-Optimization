.PHONY: install demo validate test run-api run-dashboard train optimize docker
install:
	python -m pip install -r requirements.txt
demo:
	python scripts/generate_demo.py
validate:
	python scripts/validate_data.py
test:
	pytest -q
run-api:
	uvicorn src.api.main:app --reload --port 8000
run-dashboard:
	streamlit run app/streamlit_app.py
train:
	python scripts/train_forecaster.py
optimize:
	python scripts/run_optimization.py
docker:
	docker compose up --build
