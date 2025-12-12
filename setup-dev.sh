#!/bin/bash
# Development setup script for Home Assistant Scheduler integration

set -e

echo "🔧 Setting up development environment..."

# Check if we're in a virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    echo "⚠️  Warning: Not in a virtual environment!"
    echo "   It's recommended to activate your virtual environment first:"
    echo "   source .venv/bin/activate"
    echo ""
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Install development dependencies (includes pre-commit)
echo "📚 Installing development dependencies..."
pip install -r requirements_test.txt

# Install pre-commit hooks
echo "🪝 Installing pre-commit hooks..."
pre-commit install

# Run initial checks
echo "✅ Running initial linting checks..."
python -m ruff check custom_components/ha_scheduler/ tests/

echo "🧪 Running tests..."
pytest tests/ -q

echo ""
echo "✨ Setup complete! Pre-commit hooks are now active."
echo ""
echo "📝 Available commands:"
echo "  - Run linting:        python -m ruff check custom_components/ha_scheduler/ tests/"
echo "  - Auto-fix linting:   python -m ruff check --fix custom_components/ha_scheduler/ tests/"
echo "  - Format code:        python -m ruff format custom_components/ha_scheduler/ tests/"
echo "  - Run tests:          pytest tests/"
echo "  - Run pre-commit:     pre-commit run --all-files"
echo ""
