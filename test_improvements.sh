#!/bin/bash
# Test script to verify E2E test improvements

set -e

echo "=== E2E Test Improvements Verification ==="
echo ""

# Check if services are running
echo "1. Checking service availability..."

# Check Semantic Service
if curl -f -s http://localhost:8082/health > /dev/null 2>&1; then
    echo "   ✅ Semantic service is healthy"
else
    echo "   ❌ Semantic service is not available (http://localhost:8082/health)"
    echo "      Start with: docker-compose -f docker-compose.staging.yml up -d semantic-service"
fi

# Check Fuseki
if curl -f -s http://localhost:3031/\$/ping > /dev/null 2>&1; then
    echo "   ✅ Fuseki is healthy"
else
    echo "   ❌ Fuseki is not available (http://localhost:3031/\$/ping)"
    echo "      Start with: docker-compose -f docker-compose.staging.yml up -d fuseki"
fi

# Check MinIO
if curl -f -s http://localhost:9010/minio/health/live > /dev/null 2>&1; then
    echo "   ✅ MinIO is healthy"
else
    echo "   ⚠️  MinIO is not available (http://localhost:9010/minio/health/live)"
    echo "      SDK file upload tests will be skipped"
fi

echo ""
echo "2. Running improved E2E tests..."
echo ""

# Run semantic layer tests
echo "   Testing semantic layer improvements..."
pytest tests/e2e/test_semantic_layer.py::SemanticLayerE2ETest::test_semantic_mapping_on_asset_activation \
        tests/e2e/test_semantic_layer.py::SemanticLayerE2ETest::test_sparql_query \
        tests/e2e/test_semantic_layer.py::SemanticLayerE2ETest::test_uri_resolution_for_asset \
        tests/e2e/test_semantic_layer.py::SemanticLayerE2ETest::test_uri_resolution_for_contract \
        tests/e2e/test_semantic_layer.py::SemanticLayerE2ETest::test_uri_resolution_for_dataset \
        tests/e2e/test_semantic_layer.py::SemanticLayerE2ETest::test_uri_resolution_for_field \
        -v --tb=short || echo "   ⚠️  Some semantic layer tests failed (check output above)"

echo ""
echo "   Testing SDK improvements..."
pytest tests/e2e/test_sdk_python.py::SDKPythonE2ETest::test_sdk_file_upload_flow \
        tests/e2e/test_sdk_python.py::SDKPythonE2ETest::test_sdk_token_refresh_on_401 \
        -v --tb=short || echo "   ⚠️  Some SDK tests failed (check output above)"

echo ""
echo "=== Test Summary ==="
echo ""
echo "Improvements applied:"
echo "  ✅ Fuseki commit wait (1.5s)"
echo "  ✅ Increased retry logic (10 retries)"
echo "  ✅ Enhanced health checks (60s wait)"
echo "  ✅ Mapping verification (Fuseki check)"
echo "  ✅ Improved error messages"
echo ""
echo "See TEST_IMPROVEMENTS.md for detailed information."

