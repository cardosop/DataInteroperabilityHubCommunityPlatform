#!/bin/bash
#
# Development Run Script
#
# This script runs services in development mode.
#
# Usage:
#   ./scripts/dev_run.sh [service] [--reload]
#

set -euo pipefail

SERVICE="${1:-api}"
RELOAD=false

# Parse arguments
shift || true
while [[ $# -gt 0 ]]; do
    case $1 in
        --reload)
            RELOAD=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

case $SERVICE in
    api)
        cd hub && python manage.py runserver 0.0.0.0:8000
        ;;
    worker)
        cd services/worker && python main.py job_critical job_default job_low
        ;;
    datacontract)
        cd services/datacontract-service && uvicorn main:app --host 0.0.0.0 --port 8080 $([ "$RELOAD" = true ] && echo "--reload" || echo "")
        ;;
    compliance)
        cd services/compliance-service && uvicorn main:app --host 0.0.0.0 --port 8082 $([ "$RELOAD" = true ] && echo "--reload" || echo "")
        ;;
    dq)
        cd services/dq-service && uvicorn main:app --host 0.0.0.0 --port 8083 $([ "$RELOAD" = true ] && echo "--reload" || echo "")
        ;;
    semantic)
        cd services/semantic-service && uvicorn main:app --host 0.0.0.0 --port 8081 $([ "$RELOAD" = true ] && echo "--reload" || echo "")
        ;;
    prefect-integration)
        cd services/prefect-integration && uvicorn main:app --host 0.0.0.0 --port 8084 $([ "$RELOAD" = true ] && echo "--reload" || echo "")
        ;;
    search)
        cd services/search-service && uvicorn main:app --host 0.0.0.0 --port 8085 $([ "$RELOAD" = true ] && echo "--reload" || echo "")
        ;;
    observability)
        cd services/observability-service && uvicorn main:app --host 0.0.0.0 --port 8086 $([ "$RELOAD" = true ] && echo "--reload" || echo "")
        ;;
    webhook)
        cd services/webhook-service && uvicorn main:app --host 0.0.0.0 --port 8087 $([ "$RELOAD" = true ] && echo "--reload" || echo "")
        ;;
    *)
        echo "Unknown service: $SERVICE"
        echo "Available services: api, worker, datacontract, compliance, dq, semantic, prefect-integration, search, observability, webhook"
        exit 1
        ;;
esac

