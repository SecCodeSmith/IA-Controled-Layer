#!/bin/bash
# Lint script for AI Control Layer
# Runs ruff check and npm lint

set -e
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

echo "=== AI Control Layer Lint ==="

lint_failed=0

# 1. Backend ruff
echo ""
echo "[1/2] Running Backend ruff check..."
cd Backend
if python -m ruff check src tests; then
    echo "  ✓ ruff check passed"
else
    echo "  ✗ ruff check failed"
    lint_failed=1
fi
cd ..

# 2. Frontend npm lint
echo ""
echo "[2/2] Running Frontend lint..."
cd Frontent
if npm run lint; then
    echo "  ✓ npm lint passed"
else
    echo "  ✗ npm lint failed"
    lint_failed=1
fi
cd ..

# Summary
echo ""
echo "=== Lint Summary ==="
if [ $lint_failed -eq 1 ]; then
    echo "Linting issues found!"
    exit 1
else
    echo "All linting passed!"
    exit 0
fi
