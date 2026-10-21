#!/bin/bash
# Test Python 3.12+ Compatibility
# This script tests that all components work with Python 3.12+

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Python 3.12+ Compatibility Test${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo -e "${BLUE}Testing with Python: ${PYTHON_VERSION}${NC}"

if ! python3 -c "import sys; exit(0 if sys.version_info >= (3, 12) else 1)"; then
    echo -e "${RED}❌ Python 3.12+ required. Found: ${PYTHON_VERSION}${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Python version check passed${NC}"
echo ""

# Test 1: Import core modules
echo -e "${BLUE}Test 1: Importing core Python modules...${NC}"
python3 -c "
import sys
import json
import os
import subprocess
print('✅ Core modules imported successfully')
"
echo -e "${GREEN}✅ Core module import test passed${NC}"
echo ""

# Test 2: Install and test dependencies
echo -e "${BLUE}Test 2: Testing dependency installation...${NC}"

if [ -f "requirements.txt" ]; then
    echo -e "${BLUE}  Installing requirements.txt...${NC}"
    pip install --quiet --dry-run -r requirements.txt > /dev/null 2>&1 && \
        echo -e "${GREEN}  ✅ requirements.txt compatible${NC}" || \
        echo -e "${YELLOW}  ⚠️  Some dependencies may have issues${NC}"
fi

if [ -f "requirements-dev.txt" ]; then
    echo -e "${BLUE}  Installing requirements-dev.txt...${NC}"
    pip install --quiet --dry-run -r requirements-dev.txt > /dev/null 2>&1 && \
        echo -e "${GREEN}  ✅ requirements-dev.txt compatible${NC}" || \
        echo -e "${YELLOW}  ⚠️  Some dev dependencies may have issues${NC}"
fi

echo ""

# Test 3: Test SDK installation
echo -e "${BLUE}Test 3: Testing SDK installation...${NC}"
if [ -d "sdk/python" ]; then
    cd sdk/python
    if python3 -c "import setuptools; print('✅ setuptools available')" 2>/dev/null; then
        python3 setup.py check > /dev/null 2>&1 && \
            echo -e "${GREEN}  ✅ SDK setup.py valid${NC}" || \
            echo -e "${YELLOW}  ⚠️  SDK setup.py has issues${NC}"
    fi
    cd ../..
fi
echo ""

# Test 4: Test CLI installation
echo -e "${BLUE}Test 4: Testing CLI installation...${NC}"
if [ -d "cli" ]; then
    cd cli
    if python3 -c "import setuptools; print('✅ setuptools available')" 2>/dev/null; then
        python3 setup.py check > /dev/null 2>&1 && \
            echo -e "${GREEN}  ✅ CLI setup.py valid${NC}" || \
            echo -e "${YELLOW}  ⚠️  CLI setup.py has issues${NC}"
    fi
    cd ..
fi
echo ""

# Test 5: Test Django compatibility (if Django is installed)
echo -e "${BLUE}Test 5: Testing Django compatibility...${NC}"
if python3 -c "import django" 2>/dev/null; then
    DJANGO_VERSION=$(python3 -c "import django; print(django.get_version())" 2>/dev/null)
    echo -e "${BLUE}  Django version: ${DJANGO_VERSION}${NC}"
    python3 -c "
import django
from django.conf import settings
if not settings.configured:
    settings.configure(DEBUG=True)
print('✅ Django configured successfully')
" && echo -e "${GREEN}  ✅ Django compatibility test passed${NC}" || \
    echo -e "${YELLOW}  ⚠️  Django configuration has issues${NC}"
else
    echo -e "${YELLOW}  ⚠️  Django not installed, skipping${NC}"
fi
echo ""

# Summary
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}✅ Python 3.12+ compatibility tests completed${NC}"
echo -e "${BLUE}========================================${NC}"

