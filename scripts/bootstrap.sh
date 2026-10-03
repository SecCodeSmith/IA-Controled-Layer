#!/bin/bash
# Bootstrap script for AI Control Layer
# Sets up Python environment, Node modules, ML classifier, and Ollama model

set -e
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8
export CTRL_OLLAMA_MODEL=${CTRL_OLLAMA_MODEL:-qwen2.5:7b}

echo "=== AI Control Layer Bootstrap ==="

skipped=()

# 1. Backend Python setup
echo ""
echo "[1/4] Setting up Backend Python environment..."
cd Backend
if python -m pip install -e ".[dev]" > /dev/null 2>&1; then
    echo "  ✓ Backend dependencies installed"
else
    echo "  ✗ Backend pip install failed"
    skipped+=("Backend pip install")
fi
cd ..

# 2. Frontend npm setup
echo ""
echo "[2/4] Setting up Frontend Node modules..."
cd Frontent
if [ -f package-lock.json ]; if [ -f package-lock.json ] && [ ! -d node_modules ]; then
    if npm ci > /dev/null 2>&1; then
        echo "  ✓ Frontend dependencies installed (npm ci)"
    else
        echo "  ✗ Frontend npm ci failed"
        skipped+=("Frontend npm setup")
    fi
else
    if npm install --no-audit --no-fund > /dev/null 2>&1; then
s installed (npm install)"
    else
        echo "  ✗ Frontend npm install failed"
        skipped+=("Frontend npm setup")
    fi
fi
cd ..

# 3. Train ML classifier
echo ""
echo "[3/4] Training ML classifier..."
cd Backend
if python -m control_layer.ml.train \
    --dataset "src/control_layer/ml/dataset/prompt_injection_dataset.csv" \
    --out "src/control_layer/ml/artifacts/prompt_injection_classifier.joblib" \
    --model logreg > /dev/null 2>&1; then
    echo "  ✓ ML classifier trained"
else
    echo "  ✗ ML classifier training failed"
    skipped+=("ML classifier training")
fi
cd ..

# 4. Ollama setup
echo ""
echo "[4/4] Setting up Ollama..."
if command -v ollama &> /dev/null; then
    echo "  Pulling Ollama model: $CTRL_OLLAMA_MODEL..."
    if ollama pull "$CTRL_OLLAMA_MODEL" > /dev/null 2>&1; then
        echo "  ✓ Ollama model pulled"

        echo "  Running warm-up completion..."
        if curl -s -X POST http://localhost:11434/v1/chat/completions \
            -H "Content-Type: application/json" \
            -d "{\"model\":\"$CTRL_OLLAMA_MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"OK\"}],\"stream\":false}" > /dev/null 2>&1; then
            echo "  ✓ Ollama warm-up completed"
        else
            echo "  ⚠ Ollama warm-up failed (not critical)"
            skipped+=("Ollama warm-up")
        fi
    else
        echo "  ⚠ Ollama pull failed (not critical)"
        skipped+=("Ollama setup")
    fi
else
    echo "  ⚠ ollama not found on PATH, skipping model pull"
    skipped+=("Ollama setup")
fi

# Summary
echo ""
echo "=== Bootstrap Complete ==="
if [ ${#skipped[@]} -gt 0 ]; then
    echo "Skipped steps:"
    for item in "${skipped[@]}"; do
        echo "  • $item"
    done
fi
echo "Ready to run: ./scripts/run_dev.sh"
