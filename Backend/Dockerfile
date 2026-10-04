FROM python:3.13-slim

WORKDIR /app

# Copy the entire repo structure (Backend and demo)
COPY Backend/ ./Backend/
COPY demo/ ./demo/

# Set UTF-8 environment
ENV PYTHONIOENCODING=utf-8 \
    PYTHONUTF8=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app/Backend

# Install dependencies
RUN pip install --no-cache-dir -e .

# Train the ML classifiers at build time
RUN python -m control_layer.ml.train \
    --dataset "src/control_layer/ml/dataset/prompt_injection_dataset.csv" \
    --out "src/control_layer/ml/artifacts/prompt_injection_classifier.joblib" \
    --extra "src/control_layer/ml/dataset/security_education.csv" \
    --extra "src/control_layer/ml/dataset/benign_tool_results.csv" \
    --model logreg

RUN python -m control_layer.ml.train \
    --dataset "src/control_layer/ml/dataset/prompt_injection_dataset.csv" \
    --extra "src/control_layer/ml/dataset/benign_operational.csv" \
    --extra "src/control_layer/ml/dataset/benign_tool_results.csv" \
    --out "src/control_layer/ml/artifacts/prompt_injection_tree.joblib" \
    --model tree

# Default to running control layer
CMD ["python", "-m", "uvicorn", "control_layer.presentation.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
