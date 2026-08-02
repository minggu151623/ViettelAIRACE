"""Dependency-aware weak-supervision label model used by H39.

The model is deliberately small and deterministic. It extends Dawid-Skene EM
with fractional source-family weights and a residual-agreement penalty so two
correlated labeling functions cannot masquerade as independent evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
from scipy.special import logsumexp


ABSTAIN = -1


@dataclass
class LabelModelResult:
    posterior: np.ndarray
    class_prior: np.ndarray
    confusion: np.ndarray
    source_weights: np.ndarray
    iterations: int
    converged: bool


class DependencyAwareLabelModel:
    """Multiclass EM label model with explicit source-dependence penalties."""

    def __init__(self, n_classes: int, family_weights: Iterable[float] | None = None,
                 smoothing: float = 1.0, dependency_strength: float = 4.0,
                 max_iter: int = 500, tolerance: float = 1e-8, seed: int = 3901):
        self.n_classes = int(n_classes)
        self.family_weights = None if family_weights is None else np.asarray(list(family_weights), dtype=float)
        self.smoothing = float(smoothing)
        self.dependency_strength = float(dependency_strength)
        self.max_iter = int(max_iter)
        self.tolerance = float(tolerance)
        self.seed = int(seed)
        self.result_: LabelModelResult | None = None

    def _validate(self, votes: np.ndarray, anchors: np.ndarray | None) -> tuple[np.ndarray, np.ndarray]:
        values = np.asarray(votes, dtype=np.int64)
        if values.ndim != 2 or not values.shape[0] or not values.shape[1]:
            raise ValueError("votes must be a non-empty [examples, sources] matrix")
        if np.any((values < ABSTAIN) | (values >= self.n_classes)):
            raise ValueError("votes contain an invalid class")
        fixed = np.full(values.shape[0], ABSTAIN, dtype=np.int64) if anchors is None else np.asarray(anchors, dtype=np.int64)
        if fixed.shape != (values.shape[0],) or np.any((fixed < ABSTAIN) | (fixed >= self.n_classes)):
            raise ValueError("anchors must contain one valid class or -1 per example")
        return values, fixed

    def _base_weights(self, n_sources: int) -> np.ndarray:
        weights = np.ones(n_sources, dtype=float) if self.family_weights is None else self.family_weights.copy()
        if weights.shape != (n_sources,) or np.any(weights <= 0):
            raise ValueError("family_weights must contain one positive value per source")
        return weights

    def _initialize(self, votes: np.ndarray, anchors: np.ndarray, weights: np.ndarray) -> np.ndarray:
        rng = np.random.default_rng(self.seed)
        scores = np.full((len(votes), self.n_classes), 0.25, dtype=float)
        scores += rng.uniform(0.0, 1e-3, size=scores.shape)
        for source in range(votes.shape[1]):
            observed = votes[:, source]
            for label in range(self.n_classes):
                scores[:, label] += weights[source] * (observed == label)
        posterior = scores / scores.sum(axis=1, keepdims=True)
        fixed = anchors != ABSTAIN
        posterior[fixed] = np.eye(self.n_classes)[anchors[fixed]]
        return posterior

    def _m_step(self, votes: np.ndarray, posterior: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        prior = posterior.sum(axis=0) + self.smoothing
        prior /= prior.sum()
        confusion = np.empty((votes.shape[1], self.n_classes, self.n_classes), dtype=float)
        for source in range(votes.shape[1]):
            observed = votes[:, source]
            active = observed != ABSTAIN
            for truth in range(self.n_classes):
                counts = np.full(self.n_classes, self.smoothing, dtype=float)
                if active.any():
                    counts += np.bincount(observed[active], weights=posterior[active, truth],
                                          minlength=self.n_classes)
                confusion[source, truth] = counts / counts.sum()
        return prior, confusion

    def _dependency_weights(self, votes: np.ndarray, posterior: np.ndarray,
                            confusion: np.ndarray, base: np.ndarray) -> np.ndarray:
        penalties = np.zeros(votes.shape[1], dtype=float)
        for left in range(votes.shape[1]):
            for right in range(left + 1, votes.shape[1]):
                active = (votes[:, left] != ABSTAIN) & (votes[:, right] != ABSTAIN)
                if active.sum() < 20:
                    continue
                actual = np.mean(votes[active, left] == votes[active, right])
                expected_by_truth = np.sum(confusion[left] * confusion[right], axis=1)
                expected = float(np.mean(posterior[active] @ expected_by_truth))
                residual = max(0.0, float(actual - expected))
                penalties[left] = max(penalties[left], residual)
                penalties[right] = max(penalties[right], residual)
        return base / (1.0 + self.dependency_strength * penalties)

    def _e_step(self, votes: np.ndarray, anchors: np.ndarray, prior: np.ndarray,
                confusion: np.ndarray, weights: np.ndarray) -> np.ndarray:
        logp = np.broadcast_to(np.log(np.clip(prior, 1e-12, 1.0)),
                               (len(votes), self.n_classes)).copy()
        for source in range(votes.shape[1]):
            active = votes[:, source] != ABSTAIN
            if not active.any():
                continue
            observed = votes[active, source]
            likelihood = confusion[source, :, observed]
            logp[active] += weights[source] * np.log(np.clip(likelihood, 1e-12, 1.0))
        logp -= logsumexp(logp, axis=1, keepdims=True)
        posterior = np.exp(logp)
        fixed = anchors != ABSTAIN
        posterior[fixed] = np.eye(self.n_classes)[anchors[fixed]]
        return posterior

    def fit(self, votes: np.ndarray, anchors: np.ndarray | None = None) -> LabelModelResult:
        values, fixed = self._validate(votes, anchors)
        base = self._base_weights(values.shape[1])
        posterior = self._initialize(values, fixed, base)
        converged = False
        prior, confusion = self._m_step(values, posterior)
        # Estimate residual source dependence once from the deterministic
        # initialization. Keeping these penalties fixed prevents the EM target
        # itself from oscillating as posterior agreement changes.
        weights = self._dependency_weights(values, posterior, confusion, base)
        for iteration in range(1, self.max_iter + 1):
            updated = self._e_step(values, fixed, prior, confusion, weights)
            delta = float(np.max(np.abs(updated - posterior)))
            posterior = updated
            if delta <= self.tolerance:
                converged = True
                break
            prior, confusion = self._m_step(values, posterior)
        self.result_ = LabelModelResult(posterior, prior, confusion, weights, iteration, converged)
        return self.result_

    def predict_proba(self, votes: np.ndarray) -> np.ndarray:
        if self.result_ is None:
            raise RuntimeError("fit must be called before predict_proba")
        values, anchors = self._validate(votes, None)
        if values.shape[1] != len(self.result_.source_weights):
            raise ValueError("source count differs from fitted model")
        return self._e_step(values, anchors, self.result_.class_prior,
                            self.result_.confusion, self.result_.source_weights)


def positive_f1(truth: np.ndarray, prediction: np.ndarray) -> float:
    truth, prediction = np.asarray(truth), np.asarray(prediction)
    tp = int(np.sum((truth == 1) & (prediction == 1)))
    fp = int(np.sum((truth == 0) & (prediction == 1)))
    fn = int(np.sum((truth == 1) & (prediction == 0)))
    return 2 * tp / max(1, 2 * tp + fp + fn)


def synthetic_correlated_noise(seed: int = 3901, examples: int = 20_000) -> dict[str, object]:
    """Run the exactly preregistered H39 synthetic gate."""
    rng = np.random.default_rng(seed)
    truth = (rng.random(examples) < 0.35).astype(np.int64)
    shared = rng.random(examples) < 0.42

    def flip(values: np.ndarray, mask: np.ndarray) -> np.ndarray:
        return np.where(mask, 1 - values, values)

    bami_v15 = flip(flip(truth, shared), rng.random(examples) < 0.02)
    bami_v3 = flip(flip(truth, shared), rng.random(examples) < 0.02)
    vietmed = flip(truth, rng.random(examples) >= 0.82)
    qwen = flip(truth, rng.random(examples) >= 0.76)
    h34 = flip(truth, rng.random(examples) >= 0.70)
    votes = np.column_stack([bami_v15, bami_v3, vietmed, qwen, h34])

    majority = (votes.sum(axis=1) >= 3).astype(np.int64)
    anchor_ids = np.concatenate([np.flatnonzero(truth == label)[:250] for label in (0, 1)])
    anchors = np.full(examples, ABSTAIN, dtype=np.int64)
    anchors[anchor_ids] = truth[anchor_ids]
    model = DependencyAwareLabelModel(2, family_weights=[0.5, 0.5, 1.0, 1.0, 1.0], seed=seed)
    result = model.fit(votes, anchors)
    prediction = result.posterior.argmax(axis=1)
    majority_f1 = positive_f1(truth, majority)
    model_f1 = positive_f1(truth, prediction)
    return {
        "seed": seed,
        "examples": examples,
        "anchored_controls": int((anchors != ABSTAIN).sum()),
        "majority_f1": majority_f1,
        "label_model_f1": model_f1,
        "f1_gain": model_f1 - majority_f1,
        "gate_gain_at_least_0_05": model_f1 - majority_f1 >= 0.05,
        "source_weights": result.source_weights.tolist(),
        "class_prior": result.class_prior.tolist(),
        "iterations": result.iterations,
        "converged": result.converged,
    }
