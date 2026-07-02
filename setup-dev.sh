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

# Warn when the local Python lags CI (CI tests 3.13 and 3.14)
PY_MINOR=$(python -c 'import sys; print(sys.version_info.minor)')
if [ "$PY_MINOR" -lt 13 ]; then
    echo "⚠️  Python 3.$PY_MINOR detected; CI runs 3.13 and 3.14."
fi

# Install development dependencies (includes pre-commit).
# --upgrade matters: requirements are unpinned floors, and a stale venv can
# mask bugs that only occur with the holidays/homeassistant versions users
# actually run.
echo "📚 Installing development dependencies (latest versions)..."
pip install --upgrade -r requirements_test.txt

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
