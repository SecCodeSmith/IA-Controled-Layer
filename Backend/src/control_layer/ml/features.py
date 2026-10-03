from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import FeatureUnion


def build_vectorizer() -> FeatureUnion:
    word_vectorizer = TfidfVectorizer(
        analyzer="word",
        ngram_range=(1, 2),
        sublinear_tf=True,
        max_features=5000,
        lowercase=True,
    )
    char_vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(3, 5),
        sublinear_tf=True,
        max_features=5000,
        lowercase=True,
    )
    return FeatureUnion([("word", word_vectorizer), ("char", char_vectorizer)])


build_features = build_vectorizer
