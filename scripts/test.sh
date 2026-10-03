#!/bin/bash
# Test script for AI Control Layer
# Runs pytest, ruff linting, and npm tests

set -u
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

# Resolve repo root
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

echo "=== AI Control Layer Test Suite ===" 

tests_failed=0

# 1. Backend pytest
echo ""
echo "[1/3] Running Backend pytest..."
cd Backend
if python -m pytest -q --cov=control_layer --cov-report=term-missing; then
    echo "  ✓ pytest passed"
else
    echo "  ✗ pytest failed"
    tests_failed=1
fi
cd ..

# 2. Backend ruff
echo ""
echo "[2/3] Running Backend ruff check..."
cd Backend
if python -m ruff check src tests; then
    echo "  ✓ ruff check passed"
else
    echo "  ✗ ruff check failed"
    tests_failed=1
fi
cd ..

# 3. Frontend npm test
echo ""
echo "[3/3] Running Frontend tests..."
cd Frontent
if npm test -- --run; then
    echo "  ✓ npm tests passed"
else
    echo "  ✗ npm tests failed"
    tests_failed=1
fi
cd ..

# Summary
echo ""
echo "=== Test Summary ===" 
if [ $tests_failed -eq 1 ]; then
    echo "Some tests failed!"
    exit 1
else
    echo "All tests passed!"
    exit 0
fi
