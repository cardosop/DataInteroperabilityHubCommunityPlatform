# 312.10.6 — Lightweight Dockerfile for CI testing
# shared: common library used by other microservices.
# Not a deployable service — this Dockerfile exists only for CI test isolation.
FROM python:3.12-slim

WORKDIR /app
COPY requirements*.txt ./
RUN pip install --no-cache-dir -r requirements*.txt 2>/dev/null || true
RUN pip install --no-cache-dir pytest pytest-timeout pytest-cov

COPY . .

CMD ["python", "-m", "pytest", "--tb=short", "-v"]
