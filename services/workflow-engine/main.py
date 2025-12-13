"""
Workflow Engine Service Entry Point

Main entry point for the workflow engine service that processes workflow instances.
The service polls for workflow instances in DRAFT or RUNNING status and executes them.

Usage:
    python services/workflow-engine/main.py [--poll-interval SECONDS] [--batch-size N]
    
    Example:
        python services/workflow-engine/main.py --poll-interval 5 --batch-size 10
"""
import os
import sys
import django
import threading
import time
import signal
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
import json
import logging

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

# Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hub.settings')

# Setup Django
django.setup()

# Import after Django setup
from django.core.management import call_command
# Import health check functions (use importlib to handle hyphen in module name)
import importlib.util
health_module_path = os.path.join(os.path.dirname(__file__), 'health.py')
spec = importlib.util.spec_from_file_location("health", health_module_path)
health_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(health_module)
healthz = health_module.healthz
ready = health_module.ready

logger = logging.getLogger(__name__)

# Global flag for graceful shutdown
shutdown_flag = threading.Event()


class HealthCheckHandler(BaseHTTPRequestHandler):
    """HTTP request handler for health check endpoints."""
    
    def do_GET(self):
        """Handle GET requests for health check endpoints."""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        
        if path == '/healthz':
            status_code, content = healthz()
            self.send_response(status_code)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(content).encode('utf-8'))
        elif path == '/ready':
            status_code, content = ready()
            self.send_response(status_code)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(content).encode('utf-8'))
        elif path == '/metrics':
            # Prometheus metrics endpoint - use OpenTelemetry Prometheus exporter
            try:
                # Try OpenTelemetry metrics first (for workflow metrics)
                from hub.apps.observability.otel_metrics import REGISTRY, CONTENT_TYPE_LATEST
                from prometheus_client import generate_latest
                
                if REGISTRY is not None:
                    metrics_data = generate_latest(REGISTRY)
                else:
                    # Fallback to default registry if OpenTelemetry not available
                    from prometheus_client import generate_latest as generate_default, REGISTRY as DEFAULT_REGISTRY
                    metrics_data = generate_default(DEFAULT_REGISTRY)
                
                self.send_response(200)
                self.send_header('Content-Type', CONTENT_TYPE_LATEST)
                self.end_headers()
                self.wfile.write(metrics_data)
            except Exception as e:
                logger.error(f"Error generating metrics: {e}", exc_info=True)
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': str(e)}).encode('utf-8'))
        else:
            self.send_response(404)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': 'Not found'}).encode('utf-8'))
    
    def log_message(self, format, *args):
        """Suppress default logging for health checks."""
        pass  # Health check requests are noisy, suppress logging


def start_health_check_server(port=8088):
    """
    Start HTTP server for health check endpoints in a background thread.
    
    Args:
        port: Port to listen on (default: 8088)
    """
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    
    def run_server():
        server.serve_forever()
    
    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    return server


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    shutdown_flag.set()


def main():
    """
    Main entry point for workflow engine service.
    
    Processes workflow instances by polling for DRAFT and RUNNING workflows
    and executing them using the workflow engine.
    
    Also starts a health check HTTP server on port 8088 for Kubernetes probes.
    """
    import argparse
    
    parser = argparse.ArgumentParser(description='Workflow Engine Service')
    parser.add_argument(
        '--poll-interval',
        type=int,
        default=int(os.environ.get('WORKFLOW_ENGINE_POLL_INTERVAL', '5')),
        help='Polling interval in seconds (default: 5)'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=int(os.environ.get('WORKFLOW_ENGINE_BATCH_SIZE', '10')),
        help='Number of workflows to process per batch (default: 10)'
    )
    args = parser.parse_args()
    
    # Initialize OpenTelemetry metrics (required for Prometheus metrics export)
    try:
        from hub.apps.observability.otel_metrics import setup_opentelemetry_metrics
        meter = setup_opentelemetry_metrics()
        if meter:
            logger.info("OpenTelemetry metrics initialized")
        else:
            logger.warning("OpenTelemetry metrics not available or disabled")
    except Exception as e:
        logger.warning(f"Failed to initialize OpenTelemetry metrics: {e}")
    
    # Initialize OpenTelemetry tracing (if enabled)
    try:
        from shared.tracing import setup_opentelemetry_fastapi
        tracer = setup_opentelemetry_fastapi('workflow-engine-service')
        if tracer:
            logger.info("OpenTelemetry tracing initialized")
        else:
            logger.info("OpenTelemetry tracing not enabled")
    except Exception as e:
        logger.warning(f"Failed to initialize OpenTelemetry tracing: {e}")
    
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start health check server in background thread
    health_port = int(os.environ.get('WORKFLOW_ENGINE_HEALTH_PORT', '8088'))
    start_health_check_server(port=health_port)
    logger.info(f"Health check server started on port {health_port}")
    
    # Use Django management command to process workflows
    # The command will run continuously until shutdown signal is received
    try:
        logger.info(
            f"Starting workflow engine service "
            f"(poll_interval={args.poll_interval}s, batch_size={args.batch_size})"
        )
        
        # Run the process_workflows management command
        # Pass shutdown_flag through environment variable or use Django's call_command
        # For now, we'll use call_command which will handle the loop internally
        call_command(
            'process_workflows',
            poll_interval=args.poll_interval,
            batch_size=args.batch_size,
            verbosity=1
        )
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.error(f"Workflow engine service error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("Workflow engine service stopped")


if __name__ == '__main__':
    main()

