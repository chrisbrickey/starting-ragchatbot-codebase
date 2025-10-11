#!/bin/bash

# Comprehensive quality check script
# Runs all quality checks including formatting, linting, type checking, and tests

set -e  # Exit on first error

echo "================================"
echo "Running Code Quality Checks"
echo "================================"

echo ""
echo "1. Checking code formatting with Black..."
uv run black backend/ --check --diff || {
    echo "❌ Black formatting check failed. Run './format.sh' to fix."
    exit 1
}

echo ""
echo "2. Checking import sorting with isort..."
uv run isort backend/ --check-only --diff || {
    echo "❌ isort check failed. Run './format.sh' to fix."
    exit 1
}

echo ""
echo "3. Running flake8 linter..."
uv run flake8 backend/ --max-line-length=88 --extend-ignore=E203,W503 || {
    echo "❌ flake8 linting failed. Review the errors above."
    exit 1
}

echo ""
echo "4. Running mypy type checker..."
uv run mypy backend/ --ignore-missing-imports || {
    echo "⚠️  mypy found type issues. Review above (non-blocking)."
}

echo ""
echo "5. Running pytest tests..."
uv run pytest backend/tests/ -v || {
    echo "❌ Tests failed. Fix the failing tests."
    exit 1
}

echo ""
echo "================================"
echo "✅ All quality checks passed!"
echo "================================"
