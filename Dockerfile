FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN useradd --create-home --uid 10001 appuser
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
RUN python scripts/generate_demo.py && python scripts/validate_data.py && python -m compileall -q src app scripts
RUN chown -R appuser:appuser /app
USER 10001
EXPOSE 8000
CMD ["uvicorn","src.api.main:app","--host","0.0.0.0","--port","8000"]
