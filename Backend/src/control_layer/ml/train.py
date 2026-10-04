import argparse
import csv
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import joblib
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, f1_score
from sklearn.model_selection import train_test_split
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.tree import DecisionTreeClassifier

from control_layer.ml.dataset_schema import DatasetRow
from control_layer.ml.features import build_features

_LOGREG_C = 64.0

_MODELS = {
    "logreg": lambda: LogisticRegression(class_weight="balanced", max_iter=2000, C=_LOGREG_C),
    "mlp": lambda: MLPClassifier(hidden_layer_sizes=(64,), max_iter=500),
    "tree": lambda: DecisionTreeClassifier(
        max_depth=12, min_samples_leaf=2, class_weight="balanced"
    ),
}


def _build_classifier(
    model: str, seed: int
) -> LogisticRegression | MLPClassifier | DecisionTreeClassifier:
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


def train_with_feedback(
    base_rows: list[DatasetRow],
    feedback_rows: list[DatasetRow],
    model: str = "tree",
    seed: int = 42,
    verbose: bool = False,
) -> tuple[Pipeline, float]:
    base_texts = [row.text for row in base_rows]
    base_labels = [row.label for row in base_rows]

    # Split base dataset into train/test
    x_base_train, x_base_test, y_base_train, y_base_test = train_test_split(
        base_texts, base_labels, test_size=0.2, random_state=seed, stratify=base_labels
    )

    # Drop feedback rows that duplicate base holdout texts
    base_test_set = set(x_base_test)
    filtered_feedback = [row for row in feedback_rows if row.text not in base_test_set]

    # Prepare training data: base train + filtered feedback
    x_train = x_base_train + [row.text for row in filtered_feedback]
    y_train = y_base_train + [row.label for row in filtered_feedback]

    # Build and train pipeline
    pipeline = Pipeline([("features", build_features()), ("clf", _build_classifier(model, seed))])
    pipeline.fit(x_train, y_train)

    # Evaluate F1 on base holdout only
    predictions = pipeline.predict(x_base_test)
    f1 = float(f1_score(y_base_test, predictions, pos_label=1))

    if verbose:
        print(classification_report(y_base_test, predictions))
        print(f"F1 (class=1): {f1:.4f}")

    return pipeline, f1


def _write_meta(
    out_path: Path,
    model_type: str,
    f1: float,
    n_base: int,
    n_feedback: int,
    version: int = 0,
) -> None:
    meta = {
        "model_type": model_type,
        "trained_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "f1": f1,
        "n_base": n_base,
        "n_feedback": n_feedback,
        "version": version,
    }
    meta_path = Path(str(out_path) + ".meta.json")
    with meta_path.open("w", encoding="utf-8") as f:
        json.dump(meta, f)


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
    parser.add_argument(
        "--extra",
        type=Path,
        action="append",
        dest="extra_datasets",
        default=[],
        help="Optional extra dataset CSV (repeatable)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    base_rows = _load_dataset(args.dataset)

    # Load extra datasets if provided
    feedback_rows: list[DatasetRow] = []
    if args.extra_datasets:
        for extra_path in args.extra_datasets:
            feedback_rows.extend(_load_dataset(extra_path))

    # Use train_with_feedback if feedback is provided, otherwise use train_model
    if feedback_rows:
        pipeline, f1 = train_with_feedback(
            base_rows, feedback_rows, model=args.model, seed=args.seed
        )
        n_feedback = len(feedback_rows)
    else:
        pipeline, f1 = train_model(base_rows, model=args.model, seed=args.seed)
        n_feedback = 0

    args.out.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, args.out)

    # Write metadata sidecar
    _write_meta(args.out, args.model, f1, len(base_rows), n_feedback, version=0)

    if f1 < args.min_f1:
        print(f"F1 {f1:.4f} is below the required gate {args.min_f1:.4f}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
