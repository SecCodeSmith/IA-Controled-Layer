import argparse
import csv
import sys
from pathlib import Path

import joblib
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, f1_score
from sklearn.model_selection import train_test_split
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline

from control_layer.ml.dataset_schema import DatasetRow
from control_layer.ml.features import build_features

_LOGREG_C = 64.0

_MODELS = {
    "logreg": lambda: LogisticRegression(class_weight="balanced", max_iter=2000, C=_LOGREG_C),
    "mlp": lambda: MLPClassifier(hidden_layer_sizes=(64,), max_iter=500),
}


def _build_classifier(model: str, seed: int) -> LogisticRegression | MLPClassifier:
    if model not in _MODELS:
        raise ValueError(f"unknown model: {model!r}, expected one of {sorted(_MODELS)}")
    classifier = _MODELS[model]()
    classifier.random_state = seed
    return classifier


def train_model(
    rows: list[DatasetRow], model: str = "logreg", seed: int = 42
) -> tuple[Pipeline, float]:
    texts = [row.text for row in rows]
    labels = [row.label for row in rows]

    pipeline = Pipeline([("features", build_features()), ("clf", _build_classifier(model, seed))])

    x_train, x_test, y_train, y_test = train_test_split(
        texts, labels, test_size=0.2, random_state=seed, stratify=labels
    )
    pipeline.fit(x_train, y_train)
    predictions = pipeline.predict(x_test)
    f1 = float(f1_score(y_test, predictions, pos_label=1))
    print(classification_report(y_test, predictions))
    print(f"F1 (class=1): {f1:.4f}")
    return pipeline, f1


def _load_dataset(path: Path) -> list[DatasetRow]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [
            DatasetRow(text=row["text"], label=int(row["label"]), category=row["category"])
            for row in reader
        ]


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the prompt-injection classifier.")
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--model", choices=sorted(_MODELS), default="logreg")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--min-f1", type=float, default=0.85)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    rows = _load_dataset(args.dataset)
    pipeline, f1 = train_model(rows, model=args.model, seed=args.seed)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, args.out)

    if f1 < args.min_f1:
        print(f"F1 {f1:.4f} is below the required gate {args.min_f1:.4f}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
