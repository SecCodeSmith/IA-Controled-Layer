#!/bin/bash
# Train ML classifier script for AI Control Layer
# Trains the prompt injection classifier with optional pass-through arguments

set -e
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

echo "=== AI Control Layer ML Training ==="

cd Backend
echo "Training prompt injection classifier..."

python -m control_layer.ml.train \
    --dataset "src/control_layer/ml/dataset/prompt_injection_dataset.csv" \
    --out "src/control_layer/ml/artifacts/prompt_injection_classifier.joblib" \
    --extra "src/control_layer/ml/dataset/security_education.csv" \
    --model logreg \
    "$@"

echo "✓ Training complete"
cd ..
