#!/bin/bash

# Format Python code with Black and isort
echo "Running Black formatter..."
uv run black backend/

echo ""
echo "Running isort to organize imports..."
uv run isort backend/

echo ""
echo "✨ Code formatting complete!"
