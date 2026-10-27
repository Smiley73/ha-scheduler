#!/bin/bash
# Development setup script for Home Assistant Scheduler integration

set -e

if ! command -v uv > /dev/null; then
    echo "❌ uv not found. Install it first: https://docs.astral.sh/uv/getting-started/installation/"
    exit 1
fi

echo "🔧 Setting up development environment..."

# Install exactly what uv.lock says (includes pre-commit)
echo "📚 Installing development dependencies from uv.lock..."
uv sync --locked

# The git hook is shared by all worktrees and hardcodes the interpreter that
# installed it, so only the main checkout installs it.
if [ "$(git rev-parse --git-dir)" != "$(git rev-parse --git-common-dir)" ]; then
    echo "🪝 Linked worktree: leaving the shared pre-commit hook alone."
    if [ ! -e "$(git rev-parse --git-path hooks/pre-commit)" ]; then
        echo "   No hook is installed yet; run this script once in the main checkout."
    fi
else
    echo "🪝 Installing pre-commit hooks..."
    uv run --locked pre-commit install
fi

# Run initial checks
echo "✅ Running initial linting checks..."
uv run --locked python -m ruff check custom_components/ha_scheduler/ tests/

echo "🧪 Running tests..."
uv run --locked pytest tests/ -q

echo ""
echo "✨ Setup complete!"
echo "Commands and workflow: see DEVELOPMENT.md"
