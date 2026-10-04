import json
from pathlib import Path

import pytest

from control_layer.ml.train import _load_dataset


def test_benign_tool_results_csv_loads() -> None:
    root = Path(__file__).parent.parent.parent.parent
    dataset_path = (
        root / "src" / "control_layer" / "ml" / "dataset" / "benign_tool_results.csv"
    )

    if not dataset_path.exists():
        pytest.skip("benign_tool_results.csv not found")

    rows = _load_dataset(dataset_path)
    assert len(rows) >= 80, f"Expected at least 80 rows, got {len(rows)}"


def test_benign_tool_results_all_rows_label_zero() -> None:
    root = Path(__file__).parent.parent.parent.parent
    dataset_path = (
        root / "src" / "control_layer" / "ml" / "dataset" / "benign_tool_results.csv"
    )

    if not dataset_path.exists():
        pytest.skip("benign_tool_results.csv not found")

    rows = _load_dataset(dataset_path)
    for row in rows:
        assert row.label == 0, f"Expected label=0, got {row.label}"


def test_benign_tool_results_all_rows_category_correct() -> None:
    root = Path(__file__).parent.parent.parent.parent
    dataset_path = (
        root / "src" / "control_layer" / "ml" / "dataset" / "benign_tool_results.csv"
    )

    if not dataset_path.exists():
        pytest.skip("benign_tool_results.csv not found")

    rows = _load_dataset(dataset_path)
    for row in rows:
        assert row.category == "benign_tool_result", (
            f"Expected category=benign_tool_result, got {row.category}"
        )


def test_benign_tool_results_all_json_or_blocked_message() -> None:
    root = Path(__file__).parent.parent.parent.parent
    dataset_path = (
        root / "src" / "control_layer" / "ml" / "dataset" / "benign_tool_results.csv"
    )

    if not dataset_path.exists():
        pytest.skip("benign_tool_results.csv not found")

    rows = _load_dataset(dataset_path)
    invalid_rows = []

    for row in rows:
        is_json = False
        is_blocked = False

        try:
            json.loads(row.text)
            is_json = True
        except (json.JSONDecodeError, ValueError):
            pass

        if row.text.startswith("Blocked by the control layer:"):
            is_blocked = True

        if not (is_json or is_blocked):
            invalid_rows.append(row.text)

    assert not invalid_rows, (
        "Found rows that are neither valid JSON nor "
        "'Blocked by' messages"
    )


def test_benign_tool_results_no_duplicates_vs_base_dataset() -> None:
    root = Path(__file__).parent.parent.parent.parent
    base_path = (
        root / "src" / "control_layer" / "ml" / "dataset" / "prompt_injection_dataset.csv"
    )
    benign_path = (
        root / "src" / "control_layer" / "ml" / "dataset" / "benign_tool_results.csv"
    )

    if not base_path.exists() or not benign_path.exists():
        pytest.skip("Required datasets not found")

    base_rows = _load_dataset(base_path)
    benign_rows = _load_dataset(benign_path)

    base_texts = {row.text for row in base_rows}
    benign_texts = {row.text for row in benign_rows}

    duplicates = base_texts & benign_texts
    assert not duplicates, (
        f"Found {len(duplicates)} duplicate texts in "
        "benign_tool_results vs base dataset"
    )


def test_benign_tool_results_no_duplicates_vs_benign_operational() -> None:
    root = Path(__file__).parent.parent.parent.parent
    operational_path = (
        root / "src" / "control_layer" / "ml" / "dataset" / "benign_operational.csv"
    )
    benign_path = (
        root / "src" / "control_layer" / "ml" / "dataset" / "benign_tool_results.csv"
    )

    if not operational_path.exists() or not benign_path.exists():
        pytest.skip("Required datasets not found")

    operational_rows = _load_dataset(operational_path)
    benign_rows = _load_dataset(benign_path)

    operational_texts = {row.text for row in operational_rows}
    benign_texts = {row.text for row in benign_rows}

    duplicates = operational_texts & benign_texts
    assert not duplicates, (
        f"Found {len(duplicates)} duplicate texts in "
        "benign_tool_results vs benign_operational"
    )


def test_benign_tool_results_no_internal_duplicates() -> None:
    root = Path(__file__).parent.parent.parent.parent
    dataset_path = (
        root / "src" / "control_layer" / "ml" / "dataset" / "benign_tool_results.csv"
    )

    if not dataset_path.exists():
        pytest.skip("benign_tool_results.csv not found")

    rows = _load_dataset(dataset_path)
    texts = [row.text for row in rows]
    unique_texts = set(texts)

    assert len(texts) == len(unique_texts), (
        f"Found {len(texts) - len(unique_texts)} duplicate texts within "
        "benign_tool_results"
    )
