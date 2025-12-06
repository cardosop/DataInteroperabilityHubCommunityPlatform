#!/bin/bash
# Development Environment Setup Script
# Sets up the complete development environment for the Interoperable Data Hub MVP

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Interoperable Data Hub MVP${NC}"
echo -e "${BLUE}Development Environment Setup${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Function to print status
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Check prerequisites
echo -e "${BLUE}📋 Checking prerequisites...${NC}"

# Check Python
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 is not installed"
    exit 1
fi

python_version=$(python3 --version 2>&1 | awk '{print $2}')
if ! python3 -c "import sys; exit(0 if sys.version_info >= (3, 12) else 1)"; then
    print_error "Python 3.12+ required. Found: $python_version"
    exit 1
fi
print_status "Python $python_version detected"

# Check Docker
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed"
    exit 1
fi
print_status "Docker detected: $(docker --version | awk '{print $3}')"

# Check Docker Compose
if ! docker compose version &> /dev/null && ! command -v docker-compose &> /dev/null; then
    print_error "Docker Compose is not installed"
    exit 1
fi
if docker compose version &> /dev/null; then
    print_status "Docker Compose detected: $(docker compose version --short)"
else
    print_status "Docker Compose detected: $(docker-compose --version | awk '{print $4}')"
fi

echo ""

# Step 1: Create virtual environment
echo -e "${BLUE}📦 Step 1: Setting up Python virtual environment...${NC}"
if [ ! -d "venv" ]; then
    python3 -m venv venv
    print_status "Virtual environment created"
else
    print_info "Virtual environment already exists"
fi

# Activate virtual environment
source venv/bin/activate
print_status "Virtual environment activated"

# Upgrade pip
pip install --upgrade pip --quiet
print_status "pip upgraded"

echo ""

# Step 2: Install Python dependencies
echo -e "${BLUE}📦 Step 2: Installing Python dependencies...${NC}"
if [ -f "requirements.txt" ]; then
    pip install -q -r requirements.txt
    print_status "Production dependencies installed"
else
    print_warning "requirements.txt not found"
fi

if [ -f "requirements-dev.txt" ]; then
    pip install -q -r requirements-dev.txt
    print_status "Development dependencies installed"
else
    print_warning "requirements-dev.txt not found"
fi

echo ""

# Step 3: Create environment file
echo -e "${BLUE}📝 Step 3: Setting up environment configuration...${NC}"
if [ ! -f ".env.dev" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env.dev
        print_status "Created .env.dev from .env.example"
        print_warning "Please review and update .env.dev with your configuration"
    else
        print_warning ".env.example not found, creating basic .env.dev"
        cat > .env.dev << EOF
# Database Configuration
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=hub
POSTGRES_USER=hub
POSTGRES_PASSWORD=hub

# Redis Configuration
REDIS_URL=redis://localhost:6379/0

# MinIO/S3 Configuration
AWS_ACCESS_KEY_ID=minio
AWS_SECRET_ACCESS_KEY=minio123
S3_ENDPOINT_URL=http://localhost:9000
S3_BUCKET_NAME=hub-files

# JWT Configuration
JWT_SECRET_KEY=your-secret-key-change-in-production
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRY=900
JWT_REFRESH_TOKEN_EXPIRY=604800

# Fuseki Configuration
FUSEKI_URL=http://localhost:3030
FUSEKI_DATASET=hub
FUSEKI_ADMIN_PASSWORD=admin

# Service URLs
DATACONTRACT_SERVICE_URL=http://localhost:8080
DQ_SERVICE_URL=http://localhost:8083
COMPLIANCE_SERVICE_URL=http://localhost:8082
SEMANTIC_SERVICE_URL=http://localhost:8081

# Django Settings
DEBUG=True
SECRET_KEY=your-django-secret-key-change-in-production
ALLOWED_HOSTS=localhost,127.0.0.1
EOF
        print_status "Created basic .env.dev"
    fi
else
    print_info ".env.dev already exists"
fi

echo ""

# Step 4: Start Docker services
echo -e "${BLUE}🐳 Step 4: Starting Docker services...${NC}"

# Check if services are already running
if docker compose ps --services --filter "status=running" 2>/dev/null | grep -q postgres; then
    print_info "Docker services appear to be running"
    read -p "Do you want to restart services? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        docker compose down
        print_status "Stopped existing services"
    else
        print_info "Using existing services"
        SKIP_DOCKER=true
    fi
fi

if [ "$SKIP_DOCKER" != "true" ]; then
    print_info "Starting infrastructure services (PostgreSQL, Redis, MinIO, Fuseki)..."
    docker compose up -d postgres redis minio fuseki
    
    print_info "Waiting for services to be healthy..."
    max_attempts=30
    attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if docker compose ps postgres redis minio fuseki 2>/dev/null | grep -q "healthy\|Up"; then
            sleep 2
            if docker compose exec -T postgres pg_isready -U hub > /dev/null 2>&1; then
                print_status "PostgreSQL is ready"
                break
            fi
        fi
        attempt=$((attempt + 1))
        echo -n "."
        sleep 1
    done
    echo ""
    
    if [ $attempt -eq $max_attempts ]; then
        print_error "Services did not become healthy in time"
        print_info "Check service status with: docker compose ps"
        exit 1
    fi
    
    print_status "All infrastructure services are running"
fi

echo ""

# Step 5: Initialize MinIO bucket
echo -e "${BLUE}📦 Step 5: Setting up MinIO bucket...${NC}"
print_info "MinIO Console: http://localhost:9001 (minio/minio123)"
print_info "MinIO API: http://localhost:9000"

# Try to create bucket using MinIO client if available, otherwise provide instructions
if command -v mc &> /dev/null; then
    mc alias set local http://localhost:9000 minio minio123 2>/dev/null || true
    mc mb local/hub-files 2>/dev/null || print_info "Bucket may already exist"
    mc anonymous set download local/hub-files 2>/dev/null || true
    print_status "MinIO bucket configured"
else
    print_warning "MinIO client (mc) not found. Please create 'hub-files' bucket manually:"
    print_info "  1. Open http://localhost:9001"
    print_info "  2. Login with minio/minio123"
    print_info "  3. Create bucket named 'hub-files'"
fi

echo ""

# Step 6: Run database migrations
echo -e "${BLUE}🗄️  Step 6: Running database migrations...${NC}"
if [ -f "hub/manage.py" ]; then
    export DJANGO_SETTINGS_MODULE=hub.settings
    python hub/manage.py migrate --noinput
    print_status "Database migrations completed"
else
    print_warning "Django project not found. Migrations will run when project is initialized."
fi

echo ""

# Step 7: Create test data (optional)
echo -e "${BLUE}📊 Step 7: Setting up test data...${NC}"
read -p "Create test users for development? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if [ -f "hub/manage.py" ]; then
        export DJANGO_SETTINGS_MODULE=hub.settings
        python tests/performance/setup_test_users.py 2>/dev/null || print_warning "Could not create test users automatically"
        print_status "Test users setup completed"
    else
        print_warning "Django project not found. Test users can be created later."
    fi
fi

echo ""

# Summary
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}✅ Development environment setup complete!${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${BLUE}📋 Service URLs:${NC}"
echo "  - API Server: http://localhost:8000"
echo "  - API Docs: http://localhost:8000/api-docs/"
echo "  - MinIO Console: http://localhost:9001"
echo "  - MinIO API: http://localhost:9000"
echo "  - Fuseki: http://localhost:3030"
echo "  - PostgreSQL: localhost:5432"
echo "  - Redis: localhost:6379"
echo ""
echo -e "${BLUE}📋 Next Steps:${NC}"
echo "  1. Review and update .env.dev with your configuration"
echo "  2. Start API server: python hub/manage.py runserver"
echo "  3. Start worker: python hub/manage.py rqworker default"
echo "  4. Create superuser: python hub/manage.py createsuperuser"
echo ""
echo -e "${BLUE}📋 Useful Commands:${NC}"
echo "  - Start all services: docker compose up -d"
echo "  - Stop all services: docker compose down"
echo "  - View logs: docker compose logs -f"
echo "  - Check status: docker compose ps"
echo "  - Run tests: pytest"
echo ""
echo -e "${BLUE}📚 Documentation:${NC}"
echo "  - Local Development: LOCAL_DEVELOPMENT.md"
echo "  - Quick Start: QUICK_START.md"
echo "  - API Documentation: http://localhost:8000/api-docs/"
echo ""

