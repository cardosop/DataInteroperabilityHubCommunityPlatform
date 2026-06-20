#!/usr/bin/env python3
"""
Comprehensive Postman Collection Checker Script

This script checks Postman collections to:
- Search for Postman collection files
- Parse Postman collections (v2.0, v2.1 format)
- Extract endpoint URLs from requests
- Validate collection accuracy against endpoint inventory

Usage:
    python scripts/check_postman_collections.py [--collections-dir COLLECTIONS_DIR]
                                                [--inventory INVENTORY_FILE] [--output OUTPUT_FILE]
"""

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class PostmanRequest:
    """Represents a request found in a Postman collection"""

    name: str
    method: str
    endpoint: str
    collection_file: str
    folder: str = ""
    raw_url: str = ""


@dataclass
class CollectionValidationResult:
    """Validation result for a Postman collection"""

    collection_file: str
    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    requests: list[PostmanRequest] = field(default_factory=list)
    valid_requests: int = 0
    invalid_requests: int = 0


class PostmanCollectionChecker:
    """Checks Postman collections for accuracy and validity"""

    # Postman collection schema URLs
    POSTMAN_SCHEMAS = [
        "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        "https://schema.getpostman.com/json/collection/v2.0.0/collection.json",
    ]

    def __init__(
        self,
        collections_dir: str = ".",
        endpoint_inventory_file: str = "docs/api-audit/endpoint-inventory-current.json",
        base_path: str = ".",
    ):
        self.base_path = Path(base_path)
        self.collections_dir = self.base_path / collections_dir
        self.endpoint_inventory_file = self.base_path / endpoint_inventory_file

        if not self.endpoint_inventory_file.exists():
            raise FileNotFoundError(
                f"Endpoint inventory file not found: {self.endpoint_inventory_file}"
            )

        # Load endpoint inventory
        self.known_endpoints: dict[str, set[str]] = {}  # endpoint_path -> set of methods
        self._load_endpoint_inventory()

        # All collections found
        self.collections: list[dict[str, Any]] = []

        # All requests found
        self.requests: list[PostmanRequest] = []

    def _load_endpoint_inventory(self):
        """Load endpoint inventory from JSON file"""
        try:
            with open(self.endpoint_inventory_file, encoding="utf-8") as f:
                inventory_data = json.load(f)

            # Handle different inventory formats
            if "inventory" in inventory_data:
                endpoints = inventory_data["inventory"].get("endpoints", [])
            elif "endpoints" in inventory_data:
                endpoints = inventory_data["endpoints"]
            else:
                endpoints = []

            for endpoint_info in endpoints:
                if isinstance(endpoint_info, dict):
                    # Handle different endpoint formats
                    endpoint_path = (
                        endpoint_info.get("full_path")
                        or endpoint_info.get("endpoint_path")
                        or endpoint_info.get("path", "")
                    )
                    methods = endpoint_info.get("methods", [])

                    if endpoint_path:
                        normalized = self.normalize_endpoint(endpoint_path)
                        if normalized not in self.known_endpoints:
                            self.known_endpoints[normalized] = set()
                        if isinstance(methods, list):
                            self.known_endpoints[normalized].update(m.upper() for m in methods)
                        elif isinstance(methods, str):
                            self.known_endpoints[normalized].add(methods.upper())

        except Exception as e:
            print(f"Warning: Error loading endpoint inventory: {e}", file=sys.stderr)

    def normalize_endpoint(self, endpoint: str) -> str:
        """Normalize endpoint path for comparison"""
        # Remove protocol and host
        endpoint = re.sub(r"https?://[^/]+", "", endpoint)
        # Remove Postman variables {{base_url}}, etc.
        endpoint = re.sub(r"\{\{[^}]+\}\}", "", endpoint)
        # Remove query parameters
        endpoint = endpoint.split("?")[0]
        # Remove fragments
        endpoint = endpoint.split("#")[0]
        # Normalize trailing slash (but preserve root paths)
        if (
            endpoint
            and not endpoint.endswith("/")
            and "/api/" in endpoint
            and endpoint != "/api/v1"
        ):
            endpoint += "/"
        # Clean up multiple slashes
        endpoint = re.sub(r"/+", "/", endpoint)
        return endpoint

    def is_postman_collection(self, file_path: Path) -> bool:
        """Check if a JSON file is a Postman collection"""
        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)

            # Check for Postman collection schema
            if isinstance(data, dict):
                # Check info.schema for Postman schema URL
                info = data.get("info", {})
                schema = info.get("schema", "")
                if schema in self.POSTMAN_SCHEMAS:
                    return True

                # Check for Postman collection structure (has 'item' array)
                if "item" in data and isinstance(data["item"], list):
                    return True

                # Check for _postman_id (Postman v2.0+)
                if "_postman_id" in info or "_postman_id" in data:
                    return True

            return False
        except (json.JSONDecodeError, Exception):
            return False

    def find_collection_files(self) -> list[dict[str, Any]]:
        """Find all Postman collection files"""
        collections = []

        if not self.collections_dir.exists():
            return collections

        # Search for JSON files
        for json_file in self.collections_dir.rglob("*.json"):
            try:
                # Try to get relative path, fall back to absolute if not subpath
                try:
                    relative_path = str(json_file.relative_to(self.base_path))
                except ValueError:
                    relative_path = str(json_file)

                if self.is_postman_collection(json_file):
                    collections.append(
                        {
                            "file": relative_path,
                            "absolute_path": str(json_file),
                            "name": json_file.stem,
                        }
                    )
            except Exception as e:
                print(f"Error checking {json_file}: {e}", file=sys.stderr)

        self.collections = collections
        return collections

    def parse_collection(self, collection_file: str) -> list[PostmanRequest]:
        """Parse a Postman collection file and extract requests"""
        requests = []

        try:
            file_path = Path(collection_file)
            if not file_path.is_absolute():
                file_path = self.base_path / collection_file

            with open(file_path, encoding="utf-8") as f:
                collection_data = json.load(f)

            # Try to get relative path for collection_file
            try:
                relative_path = str(file_path.relative_to(self.base_path))
            except ValueError:
                relative_path = str(file_path)

            # Extract requests recursively from items
            self._extract_requests_recursive(
                collection_data.get("item", []), requests, relative_path, ""
            )

        except json.JSONDecodeError as e:
            print(f"Error parsing JSON in {collection_file}: {e}", file=sys.stderr)
        except Exception as e:
            print(f"Error processing {collection_file}: {e}", file=sys.stderr)

        return requests

    def _extract_requests_recursive(
        self,
        items: list[dict[str, Any]],
        requests: list[PostmanRequest],
        collection_file: str,
        folder_path: str,
    ):
        """Recursively extract requests from Postman collection items"""
        for item in items:
            if not isinstance(item, dict):
                continue

            # Check if this is a request (has 'request' key)
            if "request" in item:
                request_data = item["request"]
                method = request_data.get("method", "GET").upper()
                url_data = request_data.get("url", {})

                # Extract URL
                if isinstance(url_data, str):
                    raw_url = url_data
                    endpoint = self.normalize_endpoint(url_data)
                elif isinstance(url_data, dict):
                    raw_url = url_data.get("raw", "")
                    if not raw_url:
                        # Build from host and path
                        host = url_data.get("host", [])
                        path = url_data.get("path", [])
                        if host and path:
                            host_str = host[0] if isinstance(host, list) else str(host)
                            path_str = "/".join(str(p) for p in path if p)
                            raw_url = f"{host_str}/{path_str}"
                    endpoint = self.normalize_endpoint(raw_url)
                else:
                    continue

                request = PostmanRequest(
                    name=item.get("name", "Unnamed Request"),
                    method=method,
                    endpoint=endpoint,
                    collection_file=collection_file,
                    folder=folder_path,
                    raw_url=raw_url,
                )
                requests.append(request)

            # Check if this is a folder (has 'item' key)
            elif "item" in item:
                folder_name = item.get("name", "")
                new_folder_path = f"{folder_path}/{folder_name}" if folder_path else folder_name
                self._extract_requests_recursive(
                    item["item"], requests, collection_file, new_folder_path
                )

    def extract_endpoints_from_collections(self) -> list[dict[str, Any]]:
        """Extract all endpoints from all collections"""
        endpoints = []
        seen = set()

        # Ensure collections are found
        if not self.collections:
            self.find_collection_files()

        for collection_info in self.collections:
            collection_file = collection_info["file"]
            requests = self.parse_collection(collection_file)

            for request in requests:
                key = (collection_file, request.endpoint, request.method)
                if key not in seen:
                    seen.add(key)
                    endpoints.append(
                        {
                            "endpoint": request.endpoint,
                            "method": request.method,
                            "collection_file": collection_file,
                            "request_name": request.name,
                            "folder": request.folder,
                            "raw_url": request.raw_url,
                        }
                    )
                    self.requests.append(request)

        return endpoints

    def validate_endpoint_exists(self, endpoint: str, method: str) -> dict[str, Any]:
        """Validate that endpoint exists in inventory"""
        normalized = self.normalize_endpoint(endpoint)

        result = {"is_valid": False, "errors": [], "warnings": []}

        if normalized in self.known_endpoints:
            # Check if method is supported
            supported_methods = self.known_endpoints[normalized]
            if method in supported_methods:
                result["is_valid"] = True
            else:
                result["is_valid"] = False
                result["errors"].append(
                    f"Method {method} not supported for endpoint {normalized}. "
                    f"Supported methods: {', '.join(sorted(supported_methods))}"
                )
        else:
            result["is_valid"] = False
            result["errors"].append(f"Endpoint not found in inventory: {normalized}")

        return result

    def validate_collection(self, collection_file: str) -> CollectionValidationResult:
        """Validate a single Postman collection"""
        result = CollectionValidationResult(
            collection_file=collection_file, is_valid=True, errors=[], warnings=[], requests=[]
        )

        try:
            requests = self.parse_collection(collection_file)
            result.requests = requests

            if not requests:
                result.warnings.append("No requests found in collection")

            for request in requests:
                validation = self.validate_endpoint_exists(request.endpoint, request.method)

                if validation["is_valid"]:
                    result.valid_requests += 1
                else:
                    result.invalid_requests += 1
                    result.is_valid = False
                    result.errors.extend(
                        [
                            f"{request.name} ({request.method} {request.endpoint}): {error}"
                            for error in validation["errors"]
                        ]
                    )
                    result.warnings.extend(
                        [
                            f"{request.name} ({request.method} {request.endpoint}): {warning}"
                            for warning in validation["warnings"]
                        ]
                    )

        except Exception as e:
            result.is_valid = False
            result.errors.append(f"Error validating collection: {e!s}")

        return result

    def validate_all_collections(self) -> dict[str, Any]:
        """Validate all Postman collections comprehensively"""
        print("🔍 Finding Postman collection files...")
        collections = self.find_collection_files()
        print(f"   Found {len(collections)} Postman collections")

        print("🔍 Extracting endpoints from collections...")
        endpoints = self.extract_endpoints_from_collections()
        print(f"   Found {len(endpoints)} endpoint references")

        print("✅ Validating collections...")
        validation_results = []

        for collection_info in collections:
            collection_file = collection_info["file"]
            result = self.validate_collection(collection_file)
            validation_results.append(result)

        # Calculate summary
        total_collections = len(validation_results)
        valid_collections = sum(1 for r in validation_results if r.is_valid)
        invalid_collections = total_collections - valid_collections
        total_requests = sum(len(r.requests) for r in validation_results)
        valid_requests = sum(r.valid_requests for r in validation_results)
        invalid_requests = sum(r.invalid_requests for r in validation_results)

        return {
            "summary": {
                "generated_at": datetime.now().isoformat(),
                "total_collections": total_collections,
                "valid_collections": valid_collections,
                "invalid_collections": invalid_collections,
                "total_requests": total_requests,
                "valid_requests": valid_requests,
                "invalid_requests": invalid_requests,
                "known_endpoints_in_inventory": len(self.known_endpoints),
            },
            "collections": [
                {
                    "collection_file": result.collection_file,
                    "is_valid": result.is_valid,
                    "errors": result.errors,
                    "warnings": result.warnings,
                    "requests": [asdict(req) for req in result.requests],
                    "valid_requests": result.valid_requests,
                    "invalid_requests": result.invalid_requests,
                }
                for result in validation_results
            ],
            "endpoints": endpoints,
        }

    def generate_report(self, results: dict[str, Any], output_file: str):
        """Generate JSON report"""
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        print(f"\n📊 Report generated: {output_path}")
        print(f"   Total collections: {results['summary']['total_collections']}")
        print(f"   Valid collections: {results['summary']['valid_collections']}")
        print(f"   Invalid collections: {results['summary']['invalid_collections']}")
        print(f"   Total requests: {results['summary']['total_requests']}")
        print(f"   Valid requests: {results['summary']['valid_requests']}")
        print(f"   Invalid requests: {results['summary']['invalid_requests']}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Check Postman collections for endpoint accuracy")
    parser.add_argument(
        "--collections-dir",
        default=".",
        help="Directory containing Postman collection files (default: .)",
    )
    parser.add_argument(
        "--inventory",
        default="docs/api-audit/endpoint-inventory-current.json",
        help="Endpoint inventory JSON file (default: docs/api-audit/endpoint-inventory-current.json)",
    )
    parser.add_argument(
        "--output",
        default="docs/api-audit/postman-collections-audit.json",
        help="Output JSON report file (default: docs/api-audit/postman-collections-audit.json)",
    )
    parser.add_argument("--base-path", default=".", help="Base path of the project (default: .)")

    args = parser.parse_args()

    try:
        checker = PostmanCollectionChecker(
            collections_dir=args.collections_dir,
            endpoint_inventory_file=args.inventory,
            base_path=args.base_path,
        )

        results = checker.validate_all_collections()
        checker.generate_report(results, args.output)

        # Exit with error code if there are invalid collections
        if results["summary"]["invalid_collections"] > 0:
            sys.exit(1)

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
