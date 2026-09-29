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
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"
CMD ["uvicorn","src.api.main:app","--host","0.0.0.0","--port","8000"]
