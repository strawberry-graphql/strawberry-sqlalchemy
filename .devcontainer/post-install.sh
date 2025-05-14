#!/bin/bash
set -e  # Exit on error

echo "📦 Installing Python dependencies with Poetry..."
poetry config virtualenvs.in-project true
poetry install --no-cache

echo "🔧 Setting up pre-commit hooks..."

pre-commit install --install-hooks
