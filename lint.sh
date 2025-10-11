#!/bin/bash

# Run linting checks without modifying code
echo "Running Black check (no changes will be made)..."
uv run black backend/ --check --diff

echo ""
echo "Running isort check (no changes will be made)..."
uv run isort backend/ --check-only --diff

echo ""
echo "Running flake8 linter..."
uv run flake8 backend/ --max-line-length=88 --extend-ignore=E203,W503

echo ""
echo "✨ Linting checks complete!"
