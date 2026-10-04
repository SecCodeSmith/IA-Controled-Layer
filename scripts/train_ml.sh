#!/bin/bash
# Train ML classifier script for AI Control Layer
# Trains the prompt injection classifier with optional pass-through arguments

set -e
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8
export PYTHONPATH=src

echo "=== AI Control Layer ML Training ==="

cd Backend
echo "Training logistic regression classifier..."

python -m control_layer.ml.train \
    --dataset "src/control_layer/ml/dataset/prompt_injection_dataset.csv" \
    --out "src/control_layer/ml/artifacts/prompt_injection_classifier.joblib" \
    --extra "src/control_layer/ml/dataset/security_education.csv" \
    --extra "src/control_layer/ml/dataset/benign_operational.csv" \
    --extra "src/control_layer/ml/dataset/benign_tool_results.csv" \
    --model logreg \
    "$@"

echo "✓ Logistic regression training complete"

echo "Training decision tree classifier with benign supplement..."

python -m control_layer.ml.train \
    --dataset "src/control_layer/ml/dataset/prompt_injection_dataset.csv" \
    --extra "src/control_layer/ml/dataset/benign_operational.csv" \
    --extra "src/control_layer/ml/dataset/benign_tool_results.csv" \
    --out "src/control_layer/ml/artifacts/prompt_injection_tree.joblib" \
    --model tree \
    "$@"

echo "✓ Decision tree training complete"
cd ..
