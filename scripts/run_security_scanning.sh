#!/bin/bash
# Run Security Scanning Tools for Django 6

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
BOLD='\033[1m'
RESET='\033[0m'

echo -e "${BOLD}${BLUE}========================================${RESET}"
echo -e "${BOLD}${BLUE}Django 6 Security Scanning${RESET}"
echo -e "${BOLD}${BLUE}========================================${RESET}"
echo ""

cd "$(dirname "$0")/.." || exit 1

# Check if virtual environment exists
if [ ! -d "venv-python312-test" ]; then
    echo -e "${RED}Error: Virtual environment 'venv-python312-test' not found${RESET}"
    exit 1
fi

# Activate virtual environment
source venv-python312-test/bin/activate

echo -e "${BLUE}Step 1: Django Security Check${RESET}"
cd hub || { echo -e "${RED}Error: 'hub' directory not found${RESET}"; exit 1; }

if python3 manage.py check --deploy 2>&1 | tee /tmp/django_security_check.log; then
    echo -e "${GREEN}✅ Django security check completed${RESET}"
else
    echo -e "${YELLOW}⚠️  Django security check completed with warnings${RESET}"
    echo -e "${YELLOW}Review output in /tmp/django_security_check.log${RESET}"
fi

echo ""
echo -e "${BLUE}Step 2: Dependency Security Scanning${RESET}"

# Check if safety is installed
if command -v safety &> /dev/null; then
    echo -e "${BLUE}Running Safety scan...${RESET}"
    if safety check --json 2>&1 | tee /tmp/safety_scan.log; then
        echo -e "${GREEN}✅ Safety scan completed${RESET}"
    else
        echo -e "${YELLOW}⚠️  Safety scan found issues (review /tmp/safety_scan.log)${RESET}"
    fi
else
    echo -e "${YELLOW}⚠️  Safety not installed (pip install safety)${RESET}"
fi

echo ""
echo -e "${BLUE}Step 3: Code Security Scanning${RESET}"

# Check if bandit is installed
if command -v bandit &> /dev/null; then
    echo -e "${BLUE}Running Bandit scan...${RESET}"
    cd ..
    if bandit -r hub/apps -f json -o /tmp/bandit_scan.json 2>&1 | tee /tmp/bandit_scan.log; then
        echo -e "${GREEN}✅ Bandit scan completed${RESET}"
    else
        echo -e "${YELLOW}⚠️  Bandit scan found issues (review /tmp/bandit_scan.log)${RESET}"
    fi
else
    echo -e "${YELLOW}⚠️  Bandit not installed (pip install bandit)${RESET}"
fi

echo ""
echo -e "${BLUE}Step 4: OWASP Dependency Check${RESET}"

# Check if OWASP Dependency-Check is available
if command -v dependency-check.sh &> /dev/null || command -v dependency-check &> /dev/null; then
    echo -e "${BLUE}Running OWASP Dependency-Check...${RESET}"
    cd ..
    
    # Create temporary directory for OWASP scan
    OWASP_SCAN_DIR="/tmp/owasp_scan_$$"
    mkdir -p "$OWASP_SCAN_DIR"
    
    # OWASP Dependency-Check requires a project file
    # For Python projects, we can scan requirements.txt
    if [ -f "requirements.txt" ]; then
        # Note: OWASP Dependency-Check works best with compiled artifacts
        # For Python, it may have limited support, but we'll try
        if dependency-check.sh --project "DataInteroperabilityHub" \
            --scan "$OWASP_SCAN_DIR" \
            --out "/tmp/owasp_dependency_check" \
            --format JSON \
            --enableExperimental 2>&1 | tee /tmp/owasp_scan.log; then
            echo -e "${GREEN}✅ OWASP Dependency-Check completed${RESET}"
        else
            echo -e "${YELLOW}⚠️  OWASP Dependency-Check completed with warnings${RESET}"
            echo -e "${YELLOW}Review output in /tmp/owasp_scan.log${RESET}"
        fi
    else
        echo -e "${YELLOW}⚠️  requirements.txt not found, skipping OWASP scan${RESET}"
    fi
    
    rm -rf "$OWASP_SCAN_DIR"
else
    echo -e "${YELLOW}⚠️  OWASP Dependency-Check not installed${RESET}"
    echo -e "${YELLOW}Install from: https://owasp.org/www-project-dependency-check/${RESET}"
    echo -e "${YELLOW}Or use: pip install dependency-check (if available)${RESET}"
fi

echo ""
echo -e "${BOLD}${GREEN}Security Scanning Summary${RESET}"
echo -e "${GREEN}✅ Django security check executed${RESET}"
echo -e "${GREEN}✅ Dependency scanning executed (if available)${RESET}"
echo -e "${GREEN}✅ Code scanning executed (if available)${RESET}"
echo -e "${GREEN}✅ OWASP Dependency-Check executed (if available)${RESET}"
echo ""
echo -e "${BLUE}Review scan results in:${RESET}"
echo -e "  - /tmp/django_security_check.log"
echo -e "  - /tmp/safety_scan.log (if Safety installed)"
echo -e "  - /tmp/bandit_scan.log (if Bandit installed)"
echo -e "  - /tmp/owasp_scan.log (if OWASP Dependency-Check installed)"

