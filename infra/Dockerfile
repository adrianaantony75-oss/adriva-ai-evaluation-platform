FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends libpq5 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/requirements.lock.txt ./requirements.lock.txt
RUN pip install --no-cache-dir -r requirements.lock.txt
COPY backend ./backend
COPY benchmarks/fixtures ./benchmarks/fixtures
RUN pip install --no-deps ./backend && useradd --create-home adriva && mkdir /app/artifacts && chown adriva:adriva /app/artifacts
USER adriva
ENV ADRIVA_ARTIFACT_ROOT=/app/artifacts
CMD ["uvicorn", "adriva.api.app:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
