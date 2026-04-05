"""
Cache Decorators

Provides decorators for caching function results and Django views.

Features:
- @cache_result decorator for function results
- @cache_view decorator for Django views
- TTL configuration per cache key pattern
- Automatic cache key generation from function arguments
"""
import functools
import hashlib
import inspect
from typing import Any, Callable, Dict, List, Optional, Tuple

import structlog
from django.core.cache import cache as django_cache
from django.http import HttpRequest, HttpResponse
from django.utils.decorators import method_decorator

from hub.apps.core.caching.cache import (
    CacheKeyGenerator,
    CacheTTLConfig,
    generate_cache_key,
    get_cache_ttl,
)

logger = structlog.get_logger(__name__)


def _default_key_generator(func: Callable, *args: Any, **kwargs: Any) -> str:
    """
    Default cache key generator for functions.

    Generates key from function name and arguments.

    Args:
        func: Function being cached
        *args: Positional arguments
        **kwargs: Keyword arguments

    Returns:
        Generated cache key
    """
    key_generator = CacheKeyGenerator()

    # Include function name
    parts = [func.__module__, func.__qualname__]

    # Include args (skip self/cls for methods)
    if args:
        # For bound methods, skip first arg (self/cls)
        if inspect.ismethod(func) or (args and hasattr(args[0], '__class__') and
                                       func.__name__ in dir(args[0].__class__)):
            parts.extend(str(arg) for arg in args[1:])
        else:
            parts.extend(str(arg) for arg in args)

    # Include kwargs (sorted for consistency)
    if kwargs:
        sorted_kwargs = sorted(kwargs.items())
        parts.extend(f"{k}={v}" for k, v in sorted_kwargs)

    return key_generator.generate(*parts)


def cache_result(
    key_prefix: Optional[str] = None,
    ttl: Optional[int] = None,
    key_generator: Optional[Callable[[Callable, Any], str]] = None,
    cache_none: bool = True
) -> Callable:
    """
    Decorator to cache function results.

    Args:
        key_prefix: Optional prefix for cache keys
        ttl: Time-to-live in seconds (default: from TTL config)
        key_generator: Optional custom key generator function
        cache_none: Whether to cache None results (default: True)

    Returns:
        Decorated function

    Example:
        >>> @cache_result(key_prefix="user", ttl=300)
        ... def get_user(user_id):
        ...     return {"id": user_id, "name": "John"}
        >>> get_user(123)  # Executes function
        {'id': 123, 'name': 'John'}
        >>> get_user(123)  # Returns cached result
        {'id': 123, 'name': 'John'}
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Generate cache key
            if key_generator:
                cache_key = key_generator(func, *args, **kwargs)
            else:
                base_key = _default_key_generator(func, *args, **kwargs)
                if key_prefix:
                    cache_key = generate_cache_key(key_prefix, base_key)
                else:
                    cache_key = base_key

            # Try to get from cache
            # Use a sentinel to distinguish between "cached None" and "not cached"
            _CACHE_SENTINEL = object()
            try:
                cached_result = django_cache.get(cache_key, _CACHE_SENTINEL)
                if cached_result is not _CACHE_SENTINEL:
                    logger.debug(
                        "cache_hit",
                        function=func.__qualname__,
                        key=cache_key,
                        message="Cache hit for function result"
                    )
                    # Unwrap None if it was wrapped
                    if isinstance(cached_result, dict) and cached_result.get("__cached_none__"):
                        return None
                    return cached_result
            except Exception as e:
                logger.warning(
                    "cache_get_error",
                    function=func.__qualname__,
                    key=cache_key,
                    error=str(e),
                    message="Failed to get from cache, executing function"
                )

            # Cache miss — acquire lock to prevent stampede
            lock_key = f"lock:{cache_key}"
            lock_ttl = 30  # seconds

            try:
                from django.core.cache import cache as _lock_cache
                # Try to acquire exclusive lock
                lock_acquired = _lock_cache.add(lock_key, "1", lock_ttl)
            except Exception:
                lock_acquired = True  # Fail open — compute anyway

            if lock_acquired:
                # We own the lock — compute and cache
                try:
                    result = func(*args, **kwargs)
                except Exception:
                    # Release lock on error so others can retry
                    try:
                        _lock_cache.delete(lock_key)
                    except Exception:
                        pass
                    raise

                # Cache result (if not None or cache_none is True)
                if result is not None or cache_none:
                    try:
                        cache_ttl = ttl or get_cache_ttl(cache_key)
                        if result is None:
                            cache_value = {"__cached_none__": True}
                        else:
                            cache_value = result
                        django_cache.set(cache_key, cache_value, timeout=cache_ttl)
                        logger.debug(
                            "cache_set",
                            function=func.__qualname__,
                            key=cache_key,
                            ttl=cache_ttl,
                            message="Cached function result"
                        )
                    except Exception as e:
                        logger.warning(
                            "cache_set_error",
                            function=func.__qualname__,
                            key=cache_key,
                            error=str(e),
                            message="Failed to cache result"
                        )

                # Release lock
                try:
                    _lock_cache.delete(lock_key)
                except Exception:
                    pass

                return result
            else:
                # Another thread holds the lock — wait and retry read
                import time
                for _ in range(10):  # 10 retries x 0.1s = 1s max wait
                    time.sleep(0.1)
                    try:
                        cached_result = django_cache.get(cache_key, _CACHE_SENTINEL)
                        if cached_result is not _CACHE_SENTINEL:
                            if isinstance(cached_result, dict) and cached_result.get("__cached_none__"):
                                return None
                            return cached_result
                    except Exception:
                        pass

                # Lock holder didn't populate cache in time — compute ourselves
                try:
                    result = func(*args, **kwargs)
                except Exception:
                    raise

                if result is not None or cache_none:
                    try:
                        cache_ttl = ttl or get_cache_ttl(cache_key)
                        cache_value = {"__cached_none__": True} if result is None else result
                        django_cache.set(cache_key, cache_value, timeout=cache_ttl)
                    except Exception:
                        pass

                return result

        return wrapper
    return decorator


def cache_view(
    key_prefix: Optional[str] = None,
    ttl: Optional[int] = None,
    vary_on: Optional[List[str]] = None,
    cache_methods: Optional[List[str]] = None
) -> Callable:
    """
    Decorator to cache Django view responses.

    Only caches GET requests by default. Error responses (4xx, 5xx) are not cached.

    Args:
        key_prefix: Optional prefix for cache keys
        ttl: Time-to-live in seconds (default: from TTL config)
        vary_on: List of headers to vary cache on (e.g., ['Accept-Language'])
        cache_methods: List of HTTP methods to cache (default: ['GET'])

    Returns:
        Decorated view function

    Example:
        >>> @cache_view(key_prefix="api", ttl=300)
        ... def my_view(request):
        ...     return JsonResponse({"data": "value"})
    """
    if cache_methods is None:
        cache_methods = ['GET']

    if vary_on is None:
        vary_on = []

    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
            # Only cache specified HTTP methods
            if request.method not in cache_methods:
                return view_func(request, *args, **kwargs)

            # Generate cache key
            key_parts = []

            if key_prefix:
                key_parts.append(key_prefix)

            # Include request path
            key_parts.append(request.path)

            # Include query parameters (sorted for consistency)
            if request.GET:
                query_params = sorted(request.GET.items())
                query_str = "&".join(f"{k}={v}" for k, v in query_params)
                key_parts.append(query_str)

            # Include user ID if authenticated
            if hasattr(request, 'user') and request.user.is_authenticated:
                key_parts.append(f"user:{request.user.id}")

            # Include vary headers
            for header in vary_on:
                header_value = request.META.get(f'HTTP_{header.upper().replace("-", "_")}', '')
                if header_value:
                    key_parts.append(f"{header}:{header_value}")

            cache_key = generate_cache_key(*key_parts)

            # Try to get from cache
            try:
                cached_response = django_cache.get(cache_key)
                if cached_response is not None:
                    logger.debug(
                        "cache_hit",
                        view=view_func.__qualname__,
                        path=request.path,
                        key=cache_key,
                        message="Cache hit for view"
                    )
                    return cached_response
            except Exception as e:
                logger.warning(
                    "cache_get_error",
                    view=view_func.__qualname__,
                    key=cache_key,
                    error=str(e),
                    message="Failed to get from cache, executing view"
                )

            # Execute view
            response = view_func(request, *args, **kwargs)

            # Only cache successful responses (2xx)
            if 200 <= response.status_code < 300:
                try:
                    # Determine TTL
                    cache_ttl = ttl or get_cache_ttl(cache_key)

                    # Cache response
                    django_cache.set(cache_key, response, timeout=cache_ttl)
                    logger.debug(
                        "cache_set",
                        view=view_func.__qualname__,
                        path=request.path,
                        key=cache_key,
                        ttl=cache_ttl,
                        message="Cached view response"
                    )
                except Exception as e:
                    logger.warning(
                        "cache_set_error",
                        view=view_func.__qualname__,
                        key=cache_key,
                        error=str(e),
                        message="Failed to cache response"
                    )
            else:
                logger.debug(
                    "cache_skip",
                    view=view_func.__qualname__,
                    path=request.path,
                    status_code=response.status_code,
                    message="Skipping cache for error response"
                )

            return response

        return wrapper
    return decorator


def cache_method(
    key_prefix: Optional[str] = None,
    ttl: Optional[int] = None,
    key_generator: Optional[Callable[[Callable, Any], str]] = None
) -> Callable:
    """
    Decorator to cache class method results.

    Can be used as a class decorator or method decorator.

    Args:
        key_prefix: Optional prefix for cache keys
        ttl: Time-to-live in seconds (default: from TTL config)
        key_generator: Optional custom key generator function

    Returns:
        Decorated method or class

    Example:
        >>> class MyService:
        ...     @cache_method(key_prefix="service", ttl=300)
        ...     def get_data(self, key):
        ...         return {"data": key}
    """
    return method_decorator(
        cache_result(key_prefix=key_prefix, ttl=ttl, key_generator=key_generator)
    )

