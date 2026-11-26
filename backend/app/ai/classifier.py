"""Classifier: TF-IDF + logistic regression, trained per household."""

from __future__ import annotations

import pickle
import random
import warnings
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from scipy.sparse import hstack
from sklearn.exceptions import ConvergenceWarning
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

from .features import TxText, meta_feature, text_feature

# Own assignments weigh more than rule matches; built-in examples weigh the least
WEIGHT_MANUAL = 3.0
WEIGHT_RULE = 1.0
WEIGHT_EXAMPLE = 0.5


@dataclass
class Sample:
    tx: TxText
    category_id: int
    weight: float


@dataclass
class Prediction:
    category_id: int
    confidence: float


class Classifier:
    def __init__(self) -> None:
        self.text_vec = TfidfVectorizer(
            analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True, min_df=1, max_features=60000
        )
        self.word_vec = TfidfVectorizer(analyzer="word", token_pattern=r"[^\s|]{2,}", sublinear_tf=True)  # noqa: S106  # regex, not a password
        self.meta_vec = TfidfVectorizer(analyzer="word", token_pattern=r"\S+", use_idf=False, norm="l2")  # noqa: S106  # regex, not a password
        # saga is much faster than lbfgs with many features, with the same result
        self.clf = LogisticRegression(C=20.0, solver="saga", max_iter=200, tol=1e-3)
        self.classes: list[int] = []

    def _matrix(self, txs: Sequence[TxText], fit: bool = False):
        texts = [text_feature(t) for t in txs]
        metas = [meta_feature(t) for t in txs]
        step = "fit_transform" if fit else "transform"
        parts = [
            getattr(self.text_vec, step)(texts),
            getattr(self.word_vec, step)(texts),
            getattr(self.meta_vec, step)(metas),
        ]
        # Weigh structural features slightly less than the text
        parts[2] = parts[2] * 0.6
        return hstack(parts).tocsr()

    def fit(self, samples: Sequence[Sample]) -> Classifier:
        X = self._matrix([s.tx for s in samples], fit=True)
        y = np.array([s.category_id for s in samples])
        w = np.array([s.weight for s in samples])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", ConvergenceWarning)
            self.clf.fit(X, y, sample_weight=w)
        self.classes = [int(c) for c in self.clf.classes_]
        return self

    def predict(self, txs: Sequence[TxText], exclude: dict[int, set[int]] | None = None) -> list[Prediction]:
        """Best category per transaction, with its probability.

        `exclude` maps a direction (+1/-1) to categories that are not valid for
        transactions in that direction (e.g. no income category for a debit).
        """
        if not txs:
            return []
        proba = self.clf.predict_proba(self._matrix(txs))
        out = []
        for t, p in zip(txs, proba, strict=True):
            if exclude:
                banned = exclude.get(1 if float(t.amount) > 0 else -1, set())
                if banned:
                    p = p.copy()
                    for i, c in enumerate(self.classes):
                        if c in banned:
                            p[i] = 0.0
                    total = p.sum()
                    if total > 0:
                        p = p / total
            i = int(np.argmax(p))
            out.append(Prediction(self.classes[i], float(p[i])))
        return out

    def top(self, t: TxText, n: int = 3) -> list[Prediction]:
        p = self.clf.predict_proba(self._matrix([t]))[0]
        order = np.argsort(p)[::-1][:n]
        return [Prediction(self.classes[i], float(p[i])) for i in order]

    def dumps(self) -> bytes:
        return pickle.dumps(self, protocol=pickle.HIGHEST_PROTOCOL)

    @staticmethod
    def loads(blob: bytes) -> Classifier:
        # The model only ever comes from our own database
        return pickle.loads(blob)  # noqa: S301


def train(samples: Sequence[Sample]) -> Classifier | None:
    if len({s.category_id for s in samples}) < 2:
        return None
    return Classifier().fit(samples)


def cross_validate(samples: Sequence[Sample], folds: int = 5, max_eval: int = 2000) -> float | None:
    """Accuracy on manual assignments that were held out during training."""
    manual = [i for i, s in enumerate(samples) if s.weight == WEIGHT_MANUAL]
    if len(manual) < 20:
        return None
    rng = random.Random(42)  # noqa: S311  # deterministic eval sample, not security-related
    rng.shuffle(manual)
    manual = manual[:max_eval]
    hits = total = 0
    for k in range(folds):
        held = set(manual[k::folds])
        train_set = [s for i, s in enumerate(samples) if i not in held]
        model = train(train_set)
        if model is None:
            continue
        test = [samples[i] for i in held]
        for s, p in zip(test, model.predict([s.tx for s in test]), strict=True):
            hits += p.category_id == s.category_id
            total += 1
    return hits / total if total else None
