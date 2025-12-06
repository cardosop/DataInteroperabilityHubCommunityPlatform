#!/bin/bash
# Setup script for Interoperable Data Hub MVP

set -e

echo "🚀 Setting up Interoperable Data Hub MVP..."

# Check Python version
echo "📋 Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
required_version="3.12"
if ! python3 -c "import sys; exit(0 if sys.version_info >= (3, 12) else 1)"; then
    echo "❌ Error: Python 3.12+ required. Found: $python_version"
    exit 1
fi
echo "✅ Python $python_version detected"

# Check Docker
echo "📋 Checking Docker..."
if ! command -v docker &> /dev/null; then
    echo "❌ Error: Docker is not installed"
    exit 1
fi
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "❌ Error: Docker Compose is not installed"
    exit 1
fi
echo "✅ Docker detected"

# Create virtual environment
echo "📦 Creating virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
echo "✅ Virtual environment created"

# Install dependencies
echo "📦 Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt
echo "✅ Dependencies installed"

# Create .env file if it doesn't exist
if [ ! -f ".env.dev" ]; then
    echo "📝 Creating .env.dev from .env.example..."
    cp .env.example .env.dev
    echo "⚠️  Please review and update .env.dev with your configuration"
fi

# Create Django project structure if it doesn't exist
if [ ! -d "hub" ]; then
    echo "📁 Creating Django project structure..."
    django-admin startproject hub .
    echo "✅ Django project created"
fi

# Create apps directory structure
echo "📁 Creating app directories..."
mkdir -p hub/apps/{tenants,users,auth,audit,files,jobs,contracts,assets,dq,compliance,semantic,marketplace}
echo "✅ App directories created"

# Initialize database
echo "🗄️  Starting infrastructure services..."
docker-compose up -d postgres redis minio fuseki

echo "⏳ Waiting for services to be ready..."
sleep 10

# Run migrations (when Django project is ready)
if [ -f "hub/settings.py" ]; then
    echo "🗄️  Running database migrations..."
    python manage.py migrate --noinput || echo "⚠️  Migrations will run after Django setup"
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "📋 Next steps:"
echo "  1. Review and update .env.dev with your configuration"
echo "  2. Start all services: docker-compose up"
echo "  3. Create Django superuser: python manage.py createsuperuser"
echo "  4. Start development server: python manage.py runserver"
echo ""
echo "📚 Documentation:"
echo "  - See openspec/changes/implement-mvp-foundation/ for specifications"
echo "  - See InputDocs/ for detailed requirements"
echo ""

