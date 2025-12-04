"""
Worker Service Entry Point

Main entry point for the worker service that processes jobs from Redis queues.
Supports priority queues (job_critical, job_default, job_low) with reserved slots
and starvation prevention.

Usage:
    python services/worker/main.py [queue1] [queue2] ...
    
    Example:
        python services/worker/main.py job_critical job_default job_low
    
    Or use Django management command:
        python manage.py rqworker job_critical job_default job_low
"""
import os
import sys
import django
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
import json

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

# Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hub.settings')

# Setup Django
django.setup()

# Import after Django setup
from django.core.management import call_command
from services.worker.health import healthz, ready


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
            # Prometheus metrics endpoint
            try:
                from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
                metrics_data = generate_latest()
                self.send_response(200)
                self.send_header('Content-Type', CONTENT_TYPE_LATEST)
                self.end_headers()
                self.wfile.write(metrics_data)
            except Exception as e:
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


def start_health_check_server(port=8080):
    """
    Start HTTP server for health check endpoints in a background thread.
    
    Args:
        port: Port to listen on (default: 8080)
    """
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    
    def run_server():
        server.serve_forever()
    
    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    return server


def main():
    """
    Main entry point for worker service.
    
    Processes jobs from priority queues: job_critical (HIGH), job_default (NORMAL), job_low (LOW).
    Worker polls queues in priority order: job_critical first, then job_default, then job_low.
    
    Also starts a health check HTTP server on port 8080 for Kubernetes probes.
    """
    # Start health check server in background thread
    health_port = int(os.environ.get('WORKER_HEALTH_PORT', '8080'))
    start_health_check_server(port=health_port)
    
    # Default queues if none specified (process all priority queues)
    queues = sys.argv[1:] if len(sys.argv) > 1 else ['job_critical', 'job_default', 'job_low']
    
    # Use Django's call_command to run rqworker with proper options
    call_command('rqworker', *queues, verbosity=1)


if __name__ == '__main__':
    main()

