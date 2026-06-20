"""
Health Service

Service layer for health check operations.
Extracts business logic from views for better testability and separation of concerns.
"""

from typing import Any

from django.conf import settings
from django.db import connection

from hub.apps.core.redis_pools import health_check_all_redis_instances
from hub.apps.core.services.base import BaseService


class HealthService(BaseService):
    """
    Service for health check operations.

    Provides business logic for:
    - Database connectivity checks
    - Redis connectivity checks
    - Overall health status determination
    - Circuit breaker status retrieval
    """

    service_name = "health_service"

    def __init__(self, tenant_id: str | None = None, user_id: str | None = None):
        """
        Initialize HealthService.

        Args:
            tenant_id: Optional tenant ID (not used for health checks, but kept for consistency)
            user_id: Optional user ID (not used for health checks, but kept for consistency)
        """
        self.tenant_id = tenant_id
        self.user_id = user_id

    def check_database_health(self) -> dict[str, Any]:
        """
        Check database connectivity.

        Returns:
            Dictionary with 'status' ('connected' or 'error: <message>') and 'healthy' (bool)
        """
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            return {
                "status": "connected",
                "healthy": True,
            }
        except Exception as e:
            return {
                "status": f"error: {e!s}",
                "healthy": False,
                "error": str(e),
            }

    def check_redis_health(self) -> dict[str, Any]:
        """
        Check all Redis instances health.

        Returns:
            Dictionary with:
            - 'instances': Dict mapping instance names to their status
            - 'all_healthy': bool indicating if all instances are healthy
            - 'unhealthy_instances': List of unhealthy instance names
        """
        redis_health = health_check_all_redis_instances()
        instances_status = {}
        all_healthy = True
        unhealthy_instances = []

        for instance_name, instance_status in redis_health.items():
            if instance_status.get("status") == "healthy":
                instances_status[instance_name] = "connected"
            else:
                error_msg = instance_status.get("error", "unknown")
                instances_status[instance_name] = f"error: {error_msg}"
                all_healthy = False
                unhealthy_instances.append(instance_name)

        return {
            "instances": instances_status,
            "all_healthy": all_healthy,
            "unhealthy_instances": unhealthy_instances,
        }

    def check_clamav_health(self) -> dict[str, Any]:
        """
        Phase 277.B.079 — health probe for ClamAV daemon.

        Sends a ``zVERSION`` command to clamd and checks the response
        contains ``ClamAV`` — same probe as the docker-compose
        healthcheck and the Kubernetes exec probe.

        When ``CLAMAV_ENABLED`` is False, returns status=disabled.
        Connection failures return status=unhealthy.
        """
        if not getattr(settings, "CLAMAV_ENABLED", False):
            return {"status": "disabled", "healthy": True}

        host = getattr(settings, "CLAMAV_HOST", "clamav")
        port = int(getattr(settings, "CLAMAV_PORT", 3310))
        timeout = float(getattr(settings, "CLAMAV_TIMEOUT_SECONDS", 10.0))

        try:
            import socket

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(min(timeout, 5.0))
            try:
                sock.connect((host, port))
                sock.sendall(b"zVERSION\n")
                banner = b""
                while True:
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    banner += chunk
                    if b"\n" in banner:
                        break
                banner_str = banner.decode("utf-8", errors="replace").strip()
                if "ClamAV" in banner_str:
                    return {
                        "status": "healthy",
                        "healthy": True,
                        "version": banner_str,
                    }
                return {
                    "status": "unhealthy",
                    "healthy": False,
                    "error": f"Unexpected VERSION response: {banner_str!r}",
                }
            finally:
                sock.close()
        except (TimeoutError, ConnectionRefusedError, OSError) as exc:
            return {
                "status": "unhealthy",
                "healthy": False,
                "error": str(exc),
            }

    def check_baas_health(self) -> dict[str, Any]:
        """
        Check BaaS Postgres and Redis when BAAS_DATABASE_URL / BAAS_REDIS_URL are set.

        Returns:
            Dict with 'postgres', 'redis', 'all_healthy'. Only includes keys for
            configured URLs. When neither is set, returns {'all_healthy': True}.
        """
        result = {"all_healthy": True}
        baas_db_url = getattr(settings, "BAAS_DATABASE_URL", None)
        baas_redis_url = getattr(settings, "BAAS_REDIS_URL", None)
        if not baas_db_url and not baas_redis_url:
            return result
        if baas_db_url and "baas" in getattr(settings, "DATABASES", {}):
            try:
                from django.db import connections

                with connections["baas"].cursor() as cursor:
                    cursor.execute("SELECT 1")
                result["postgres"] = "connected"
            except Exception as e:
                result["postgres"] = f"error: {e}"
                result["all_healthy"] = False
        if baas_redis_url:
            try:
                import redis

                client = redis.from_url(baas_redis_url)
                client.ping()
                client.close()
                result["redis"] = "connected"
            except Exception as e:
                result["redis"] = f"error: {e}"
                result["all_healthy"] = False
        return result

    def get_overall_health_status(self) -> dict[str, Any]:
        """
        Get overall health status including database and Redis.

        Returns:
            Dictionary with:
            - 'status': 'healthy' or 'unhealthy'
            - 'database': Database status
            - 'redis': Redis instances status dictionary
            - 'http_status': HTTP status code (200 for healthy, 503 for unhealthy)
        """
        status = {
            "status": "healthy",
            "database": "unknown",
            "redis": {
                "cache": "unknown",
                "queue": "unknown",
                "events": "unknown",
                "channels": "unknown",
            },
        }

        # Check database
        db_health = self.check_database_health()
        status["database"] = db_health["status"]
        if not db_health["healthy"]:
            status["status"] = "unhealthy"

        # Check Redis
        redis_health = self.check_redis_health()
        status["redis"] = redis_health["instances"]
        if not redis_health["all_healthy"]:
            status["status"] = "unhealthy"

        # Phase 277.B.079 — Check ClamAV when enabled
        if getattr(settings, "CLAMAV_ENABLED", False):
            clamav_health = self.check_clamav_health()
            status["clamav"] = clamav_health
            if not clamav_health.get("healthy", True):
                status["status"] = "degraded"

        # Check BaaS Postgres/Redis when BAAS_*_URL are set
        baas_health = self.check_baas_health()
        if "postgres" in baas_health or "redis" in baas_health:
            status["baas"] = {k: v for k, v in baas_health.items() if k != "all_healthy"}
            if not baas_health.get("all_healthy", True):
                status["status"] = "unhealthy"

        http_status = 200 if status["status"] == "healthy" else 503
        status["http_status"] = http_status

        return status

    def get_circuit_breaker_status(self, service_name: str | None = None) -> dict[str, Any]:
        """
        Get circuit breaker status for all breakers or a specific one.

        Args:
            service_name: Optional service name to get status for specific circuit breaker

        Returns:
            Dictionary with circuit breaker status information

        Raises:
            Exception: If circuit breaker status retrieval fails
        """
        from hub.apps.core.resilience.circuit_breaker import get_circuit_breaker_status

        status = get_circuit_breaker_status(service_name=service_name)

        # Determine overall health based on circuit breaker states
        if isinstance(status, dict) and "error" in status:
            # Single breaker not found
            return {
                "status": "not_found",
                "error": status.get("error"),
                "http_status": 404,
            }

        if service_name:
            # Single breaker status
            breaker_status = status
            overall_healthy = breaker_status.get("state") != "OPEN"
            return {
                "status": "healthy" if overall_healthy else "degraded",
                "circuit_breaker": breaker_status,
                "http_status": 200 if overall_healthy else 503,
            }
        else:
            # All breakers status
            breakers = status
            open_breakers = [
                name
                for name, breaker_status in breakers.items()
                if breaker_status.get("state") == "OPEN"
            ]
            overall_healthy = len(open_breakers) == 0

            return {
                "status": "healthy" if overall_healthy else "degraded",
                "total_breakers": len(breakers),
                "open_breakers": len(open_breakers),
                "open_breaker_names": open_breakers,
                "circuit_breakers": breakers,
                "http_status": 200,
            }
