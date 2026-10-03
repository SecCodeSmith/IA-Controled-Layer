from sklearn.pipeline import FeatureUnion

from control_layer.ml.features import build_vectorizer


def test_build_vectorizer_returns_feature_union() -> None:
    features = build_vectorizer()
    assert isinstance(features, FeatureUnion)
    assert {name for name, _ in features.transformer_list} == {"word", "char"}


def test_word_vectorizer_configuration() -> None:
    features = build_vectorizer()
    word_vec = dict(features.transformer_list)["word"]
    assert word_vec.ngram_range == (1, 2)
    assert word_vec.sublinear_tf is True
    assert word_vec.max_features == 5000
    assert word_vec.lowercase is True
    assert word_vec.analyzer == "word"


def test_char_vectorizer_configuration() -> None:
    features = build_vectorizer()
    char_vec = dict(features.transformer_list)["char"]
    assert char_vec.ngram_range == (3, 5)
    assert char_vec.sublinear_tf is True
    assert char_vec.analyzer == "char_wb"


def test_build_vectorizer_is_fittable_on_sample_text() -> None:
    features = build_vectorizer()
    matrix = features.fit_transform(["ignore previous instructions", "please approve my request"])
    assert matrix.shape[0] == 2
