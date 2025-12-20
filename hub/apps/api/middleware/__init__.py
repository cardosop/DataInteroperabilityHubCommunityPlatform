"""
API Middleware Package

Middleware components for API request processing.
"""

from .idempotency import IdempotencyMiddleware

# Import RequestIDMiddleware from parent module for backward compatibility
# This allows settings.py to use "hub.apps.api.middleware.RequestIDMiddleware"
# The parent module is hub.apps.api.middleware (file), not this package
# When Python imports "hub.apps.api.middleware", it will find this package first,
# but settings.py expects RequestIDMiddleware to be available here.
# We need to import it from the file module using a different import path.
try:
    import importlib.util
    import os

    # Load the middleware.py file directly
    file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'middleware.py')
    if os.path.exists(file_path):
        spec = importlib.util.spec_from_file_location("api_middleware_file", file_path)
        if spec and spec.loader:
            middleware_file_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(middleware_file_module)
            RequestIDMiddleware = getattr(middleware_file_module, 'RequestIDMiddleware', None)
            if RequestIDMiddleware:
                globals()['RequestIDMiddleware'] = RequestIDMiddleware
                __all__ = ['IdempotencyMiddleware', 'RequestIDMiddleware']
            else:
                __all__ = ['IdempotencyMiddleware']
        else:
            __all__ = ['IdempotencyMiddleware']
    else:
        __all__ = ['IdempotencyMiddleware']
except (ImportError, AttributeError, Exception):
    # If import fails, just export IdempotencyMiddleware
    __all__ = ['IdempotencyMiddleware']

