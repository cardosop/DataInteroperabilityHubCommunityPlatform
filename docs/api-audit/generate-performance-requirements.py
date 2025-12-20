#!/usr/bin/env python3
"""
Generate Performance Requirements Document

This script creates a comprehensive performance requirements document for all APIs,
including:
- Response time targets (P50, P95, P99)
- Throughput targets
- Timeout values
- Caching requirements

Usage:
    python generate-performance-requirements.py > docs/api-audit/api-performance-requirements.md
"""

import re
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class PerformanceRequirement:
    """Represents performance requirements for an API endpoint"""
    endpoint: str
    method: str
    category: str
    priority: str
    # Response time targets (milliseconds)
    p50_target: Optional[int] = None
    p95_target: Optional[int] = None
    p99_target: Optional[int] = None
    # Throughput targets (requests per second)
    throughput_target: Optional[int] = None
    # Timeout values (seconds)
    client_timeout: Optional[int] = None
    server_timeout: Optional[int] = None
    # Caching requirements
    cacheable: bool = False
    cache_ttl: Optional[int] = None  # Time to live in seconds
    cache_strategy: str = ""  # e.g., "public", "private", "no-cache"
    # Additional notes
    notes: str = ""


class PerformanceRequirementsGenerator:
    """Generate comprehensive performance requirements document"""
    
    def __init__(self):
        self.requirements: Dict[str, PerformanceRequirement] = {}
        self.categories: Dict[str, List[str]] = defaultdict(list)
        
    def load_from_requirements_matrix(self, file_path: str):
        """Load APIs from consolidated requirements matrix"""
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Extract endpoints from table format
        pattern = r'\|\s+`(/api/v1/[^`]+)`\s+\|\s+(\w+)\s+\|\s+([^|]+)\s+\|\s+([^|]+)\s+\|\s+([^|]+)\s+\|\s+([^|]+)\s+\|\s+([^|]+)'
        
        current_category = ""
        for line in content.split('\n'):
            # Track current category
            if line.startswith('### ') and 'APIs' in line:
                current_category = line.replace('### ', '').replace(' APIs', '').strip()
            
            # Extract endpoint from table
            match = re.search(pattern, line)
            if match:
                path, method, description, priority, status, sources, performance = match.groups()
                
                # Parse performance target (e.g., "< 500ms p95")
                p95_target = None
                if performance and '<' in performance:
                    perf_match = re.search(r'< (\d+)\s*ms', performance)
                    if perf_match:
                        p95_target = int(perf_match.group(1))
                
                key = f"{method.upper()} {path.strip()}"
                req = PerformanceRequirement(
                    endpoint=path.strip(),
                    method=method.strip().upper(),
                    category=current_category,
                    priority=priority.strip(),
                    p95_target=p95_target
                )
                
                # Set defaults based on method and category
                self._set_default_performance(req)
                
                self.requirements[key] = req
                self.categories[current_category].append(key)
    
    def load_from_current_inventory(self, file_path: str):
        """Load APIs from current inventory and add missing ones"""
        with open(file_path, 'r') as f:
            content = f.read()
        
        pattern = r'\|\s+(\w+)\s+\|\s+`(/api/v1/[^`]+)`\s+\|\s+`?([^|`]+)`?\s+\|\s+([^|]+)\s+\|\s+([^|]+)'
        
        current_category = ""
        for line in content.split('\n'):
            if line.startswith('### ') and not line.startswith('####'):
                current_category = line.replace('### ', '').strip()
            
            match = re.search(pattern, line)
            if match:
                method, path, view, action, endpoint_type = match.groups()
                key = f"{method.strip().upper()} {path.strip()}"
                
                # Only add if not already in requirements
                if key not in self.requirements:
                    req = PerformanceRequirement(
                        endpoint=path.strip(),
                        method=method.strip().upper(),
                        category=current_category,
                        priority="P1"  # Default for existing APIs
                    )
                    self._set_default_performance(req)
                    self.requirements[key] = req
                    self.categories[current_category].append(key)
    
    def _set_default_performance(self, req: PerformanceRequirement):
        """Set default performance targets based on method and category"""
        method = req.method
        category = req.category.lower()
        
        # Response time targets based on HTTP method
        if method == "GET":
            if "{id}" in req.endpoint:  # Single resource
                req.p50_target = req.p50_target or 100
                req.p95_target = req.p95_target or 300
                req.p99_target = req.p99_target or 500
            else:  # List
                req.p50_target = req.p50_target or 200
                req.p95_target = req.p95_target or 500
                req.p99_target = req.p99_target or 1000
            req.cacheable = True
            req.cache_ttl = 300  # 5 minutes default
            req.cache_strategy = "private"
        elif method == "POST":
            req.p50_target = req.p50_target or 300
            req.p95_target = req.p95_target or 1000
            req.p99_target = req.p99_target or 2000
            req.cacheable = False
        elif method in ["PUT", "PATCH"]:
            req.p50_target = req.p50_target or 200
            req.p95_target = req.p95_target or 500
            req.p99_target = req.p99_target or 1000
            req.cacheable = False
        elif method == "DELETE":
            req.p50_target = req.p50_target or 100
            req.p95_target = req.p95_target or 300
            req.p99_target = req.p99_target or 500
            req.cacheable = False
        
        # Category-specific adjustments
        if "auth" in category or "authentication" in category:
            if method == "POST" and "login" in req.endpoint:
                req.p95_target = 500
                req.p99_target = 1000
                req.throughput_target = 100  # Lower for auth
            elif method == "POST" and "refresh" in req.endpoint:
                req.p95_target = 200
                req.p99_target = 500
        elif "ai" in category or "ml" in category:
            req.p95_target = req.p95_target or 15000  # 15 seconds for AI operations
            req.p99_target = req.p99_target or 30000  # 30 seconds
            req.client_timeout = 60  # 60 second timeout
            req.server_timeout = 45
        elif "transformation" in category:
            req.p95_target = req.p95_target or 5000  # 5 seconds
            req.p99_target = req.p99_target or 10000
            req.client_timeout = 120  # 2 minute timeout
            req.server_timeout = 100
        elif "compliance" in category or "dq" in category or "data-quality" in category:
            req.p95_target = req.p95_target or 60000  # 60 seconds
            req.p99_target = req.p99_target or 120000  # 2 minutes
            req.client_timeout = 180
            req.server_timeout = 150
        elif "search" in category:
            req.p95_target = req.p95_target or 200
            req.p99_target = req.p99_target or 500
            req.cacheable = True
            req.cache_ttl = 60  # 1 minute for search results
        elif "marketplace" in category:
            if "preview" in req.endpoint:
                req.p95_target = req.p95_target or 2000
                req.p99_target = req.p99_target or 5000
            else:
                req.p95_target = req.p95_target or 300
                req.p99_target = req.p99_target or 500
        
        # Throughput defaults
        if not req.throughput_target:
            if method == "GET":
                req.throughput_target = 1000  # 1000 req/s for GET
            elif method == "POST":
                req.throughput_target = 500  # 500 req/s for POST
            else:
                req.throughput_target = 800  # 800 req/s for PUT/PATCH/DELETE
        
        # Timeout defaults
        if not req.client_timeout:
            req.client_timeout = 30  # 30 seconds default
        if not req.server_timeout:
            req.server_timeout = 25  # 25 seconds default (5s buffer)
    
    def generate_document(self) -> str:
        """Generate comprehensive performance requirements document"""
        doc = []
        doc.append("# API Performance Requirements")
        doc.append("")
        doc.append("**Document Version**: 1.0.0")
        doc.append("**Last Updated**: 2025-12-13")
        doc.append("**Task**: 0.4.4 - Document performance requirements")
        doc.append("")
        doc.append("---")
        doc.append("")
        doc.append("## Overview")
        doc.append("")
        doc.append("This document defines comprehensive performance requirements for all API endpoints,")
        doc.append("including:")
        doc.append("- **Response Time Targets**: P50, P95, P99 percentiles")
        doc.append("- **Throughput Targets**: Requests per second (RPS)")
        doc.append("- **Timeout Values**: Client and server timeout configurations")
        doc.append("- **Caching Requirements**: Cacheability, TTL, and cache strategies")
        doc.append("")
        doc.append(f"**Total APIs Documented**: {len(self.requirements)}")
        doc.append("")
        doc.append("---")
        doc.append("")
        doc.append("## Performance Targets by Category")
        doc.append("")
        
        # Generate by category
        for category in sorted(self.categories.keys()):
            if not category:
                continue
            
            doc.append(f"### {category}")
            doc.append("")
            doc.append("| Method | Endpoint | P50 | P95 | P99 | Throughput | Client Timeout | Server Timeout | Cacheable | Cache TTL |")
            doc.append("|--------|----------|-----|-----|-----|------------|----------------|----------------|-----------|-----------|")
            
            for key in sorted(self.categories[category]):
                req = self.requirements[key]
                p50 = f"{req.p50_target}ms" if req.p50_target else "N/A"
                p95 = f"{req.p95_target}ms" if req.p95_target else "N/A"
                p99 = f"{req.p99_target}ms" if req.p99_target else "N/A"
                throughput = f"{req.throughput_target} req/s" if req.throughput_target else "N/A"
                client_to = f"{req.client_timeout}s" if req.client_timeout else "N/A"
                server_to = f"{req.server_timeout}s" if req.server_timeout else "N/A"
                cacheable = "Yes" if req.cacheable else "No"
                cache_ttl = f"{req.cache_ttl}s" if req.cache_ttl else "N/A"
                
                # Truncate endpoint if too long
                endpoint_display = req.endpoint
                if len(endpoint_display) > 50:
                    endpoint_display = endpoint_display[:47] + "..."
                
                doc.append(f"| {req.method} | `{endpoint_display}` | {p50} | {p95} | {p99} | {throughput} | {client_to} | {server_to} | {cacheable} | {cache_ttl} |")
            
            doc.append("")
        
        # Summary statistics
        doc.append("---")
        doc.append("")
        doc.append("## Performance Targets Summary")
        doc.append("")
        doc.append("### By HTTP Method")
        doc.append("")
        by_method = defaultdict(lambda: {'count': 0, 'p95_sum': 0, 'p95_count': 0})
        for req in self.requirements.values():
            by_method[req.method]['count'] += 1
            if req.p95_target:
                by_method[req.method]['p95_sum'] += req.p95_target
                by_method[req.method]['p95_count'] += 1
        
        doc.append("| Method | Count | Avg P95 Target |")
        doc.append("|--------|-------|----------------|")
        for method in ["GET", "POST", "PUT", "PATCH", "DELETE"]:
            if method in by_method:
                stats = by_method[method]
                avg_p95 = stats['p95_sum'] / stats['p95_count'] if stats['p95_count'] > 0 else 0
                doc.append(f"| {method} | {stats['count']} | {avg_p95:.0f}ms |")
        doc.append("")
        
        # Caching summary
        doc.append("### Caching Summary")
        doc.append("")
        cacheable_count = sum(1 for req in self.requirements.values() if req.cacheable)
        doc.append(f"- **Cacheable Endpoints**: {cacheable_count} ({cacheable_count*100//len(self.requirements)}%)")
        doc.append(f"- **Non-Cacheable Endpoints**: {len(self.requirements) - cacheable_count}")
        doc.append("")
        
        # Timeout summary
        doc.append("### Timeout Summary")
        doc.append("")
        doc.append("| Timeout Type | Default | Range |")
        doc.append("|--------------|---------|-------|")
        doc.append("| Client Timeout | 30s | 10s - 180s |")
        doc.append("| Server Timeout | 25s | 5s - 150s |")
        doc.append("| AI/ML Operations | 60s | 30s - 120s |")
        doc.append("| Transformation Operations | 120s | 60s - 300s |")
        doc.append("| Compliance/DQ Operations | 180s | 60s - 300s |")
        doc.append("")
        
        # Throughput summary
        doc.append("### Throughput Summary")
        doc.append("")
        doc.append("| Operation Type | Target Throughput |")
        doc.append("|----------------|-------------------|")
        doc.append("| GET (List) | 1000 req/s |")
        doc.append("| GET (Single) | 1000 req/s |")
        doc.append("| POST (Create) | 500 req/s |")
        doc.append("| PUT/PATCH (Update) | 800 req/s |")
        doc.append("| DELETE | 800 req/s |")
        doc.append("| Authentication | 100 req/s |")
        doc.append("| AI/ML Operations | 10 req/s |")
        doc.append("| Transformation Operations | 50 req/s |")
        doc.append("")
        
        # Caching strategies
        doc.append("---")
        doc.append("")
        doc.append("## Caching Requirements")
        doc.append("")
        doc.append("### Cache Strategy Guidelines")
        doc.append("")
        doc.append("1. **Public Cache**: For public, non-sensitive data")
        doc.append("   - Use for: Public marketplace listings, public asset metadata")
        doc.append("   - Cache-Control: `public, max-age={ttl}`")
        doc.append("")
        doc.append("2. **Private Cache**: For user-specific data")
        doc.append("   - Use for: User assets, user contracts, user datasets")
        doc.append("   - Cache-Control: `private, max-age={ttl}`")
        doc.append("")
        doc.append("3. **No Cache**: For mutable or sensitive data")
        doc.append("   - Use for: Authentication endpoints, write operations, real-time data")
        doc.append("   - Cache-Control: `no-cache, no-store, must-revalidate`")
        doc.append("")
        doc.append("### Cache TTL Guidelines")
        doc.append("")
        doc.append("| Data Type | Recommended TTL |")
        doc.append("|-----------|-----------------|")
        doc.append("| Static metadata | 1 hour (3600s) |")
        doc.append("| User-specific data | 5 minutes (300s) |")
        doc.append("| Search results | 1 minute (60s) |")
        doc.append("| Real-time data | No cache (0s) |")
        doc.append("| Computed metrics | 5 minutes (300s) |")
        doc.append("")
        
        # Performance monitoring
        doc.append("---")
        doc.append("")
        doc.append("## Performance Monitoring")
        doc.append("")
        doc.append("### Metrics to Track")
        doc.append("")
        doc.append("1. **Response Time Percentiles**: P50, P95, P99")
        doc.append("2. **Throughput**: Requests per second (RPS)")
        doc.append("3. **Error Rate**: Percentage of failed requests")
        doc.append("4. **Timeout Rate**: Percentage of requests that timeout")
        doc.append("5. **Cache Hit Rate**: Percentage of cache hits")
        doc.append("")
        doc.append("### Alerting Thresholds")
        doc.append("")
        doc.append("| Metric | Warning | Critical |")
        doc.append("|--------|---------|---------|")
        doc.append("| P95 Response Time | > 1.5x target | > 2x target |")
        doc.append("| P99 Response Time | > 1.5x target | > 2x target |")
        doc.append("| Error Rate | > 1% | > 5% |")
        doc.append("| Timeout Rate | > 0.1% | > 1% |")
        doc.append("| Cache Hit Rate | < 50% | < 30% |")
        doc.append("")
        
        # Implementation guidelines
        doc.append("---")
        doc.append("")
        doc.append("## Implementation Guidelines")
        doc.append("")
        doc.append("### Response Time Optimization")
        doc.append("")
        doc.append("1. **Database Query Optimization**: Use indexes, query optimization, connection pooling")
        doc.append("2. **Caching**: Implement Redis/Memcached for frequently accessed data")
        doc.append("3. **Pagination**: Use cursor-based or offset-based pagination for large datasets")
        doc.append("4. **Async Processing**: Use background jobs for long-running operations")
        doc.append("5. **CDN**: Use CDN for static assets and API responses when appropriate")
        doc.append("")
        doc.append("### Throughput Optimization")
        doc.append("")
        doc.append("1. **Horizontal Scaling**: Scale API servers horizontally")
        doc.append("2. **Load Balancing**: Use load balancers to distribute traffic")
        doc.append("3. **Connection Pooling**: Reuse database connections")
        doc.append("4. **Rate Limiting**: Implement rate limiting to prevent overload")
        doc.append("5. **Queue Management**: Use message queues for async operations")
        doc.append("")
        doc.append("### Timeout Configuration")
        doc.append("")
        doc.append("1. **Client Timeout**: Should be slightly longer than server timeout")
        doc.append("2. **Server Timeout**: Should account for worst-case processing time")
        doc.append("3. **Database Timeout**: Should be shorter than server timeout")
        doc.append("4. **External Service Timeout**: Should be shorter than server timeout")
        doc.append("")
        doc.append("### Caching Implementation")
        doc.append("")
        doc.append("1. **Cache Keys**: Use consistent, unique cache keys")
        doc.append("2. **Cache Invalidation**: Implement proper cache invalidation strategies")
        doc.append("3. **Cache Warming**: Pre-populate cache for frequently accessed data")
        doc.append("4. **Cache Headers**: Set appropriate Cache-Control headers")
        doc.append("5. **ETags**: Use ETags for conditional requests")
        doc.append("")
        
        doc.append("---")
        doc.append("")
        doc.append("**Document Status**: ✅ Complete")
        doc.append(f"**Total APIs Documented**: {len(self.requirements)}")
        doc.append("")
        doc.append("**Next Steps**:")
        doc.append("1. Implement performance monitoring for all endpoints")
        doc.append("2. Set up alerting based on performance thresholds")
        doc.append("3. Optimize endpoints that exceed performance targets")
        doc.append("4. Review and update performance targets based on production metrics")
        
        return "\n".join(doc)


if __name__ == "__main__":
    generator = PerformanceRequirementsGenerator()
    
    # Load from requirements matrix
    requirements_file = "docs/api-audit/api-requirements-matrix-consolidated.md"
    print(f"Loading requirements from {requirements_file}...", file=__import__('sys').stderr)
    generator.load_from_requirements_matrix(requirements_file)
    print(f"Loaded {len(generator.requirements)} APIs from requirements", file=__import__('sys').stderr)
    
    # Load from current inventory
    inventory_file = "docs/api-audit/current-api-inventory.md"
    print(f"Loading current inventory from {inventory_file}...", file=__import__('sys').stderr)
    generator.load_from_current_inventory(inventory_file)
    print(f"Total APIs: {len(generator.requirements)}", file=__import__('sys').stderr)
    
    # Generate document
    document = generator.generate_document()
    print(document)

