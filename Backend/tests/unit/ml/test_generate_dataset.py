from control_layer.ml.generate_dataset import generate_rows


def test_generate_rows_is_deterministic_for_seed() -> None:
    first = generate_rows(seed=42)
    second = generate_rows(seed=42)
    assert first == second


def test_generate_rows_differs_across_seeds() -> None:
    first = generate_rows(seed=42)
    other = generate_rows(seed=7)
    assert first != other


def test_generate_rows_has_expected_row_count_range() -> None:
    rows = generate_rows(seed=42)
    assert 550 <= len(rows) <= 750


def test_generate_rows_is_balanced() -> None:
    rows = generate_rows(seed=42)
    labels = [row.label for row in rows]
    benign = labels.count(0)
    attack = labels.count(1)
    assert benign > 0
    assert attack > 0
    ratio = benign / len(labels)
    assert 0.4 <= ratio <= 0.6


def test_generate_rows_has_no_duplicate_text() -> None:
    rows = generate_rows(seed=42)
    texts = [row.text for row in rows]
    assert len(texts) == len(set(texts))


def test_generate_rows_only_has_binary_labels() -> None:
    rows = generate_rows(seed=42)
    assert {row.label for row in rows} == {0, 1}
