"""Surrogate model for ultra-fast AquaCrop response surface screening. (TASK-O05)

Provides a pure-NumPy polynomial Ridge regression model approximating
AquaCrop-OSPy yield (t/ha) and irrigation demand (mm) across soil textures
and climate regimes in < 1 ms per candidate.
"""

from __future__ import annotations

import numpy as np


class PolynomialRidgeSurrogate:
    """Polynomial feature expansion + L2 regularized Ridge Regression (TASK-O05)."""

    def __init__(self, degree: int = 2, alpha: float = 1.0) -> None:
        self.degree = degree
        self.alpha = alpha
        self.weights: np.ndarray | None = None
        self.mean_: np.ndarray | None = None
        self.std_: np.ndarray | None = None

    def _expand_features(self, X: np.ndarray) -> np.ndarray:
        """Expand features with linear, quadratic, and interaction terms + bias."""
        n_samples, n_features = X.shape
        features = [np.ones((n_samples, 1)), X]
        if self.degree >= 2:
            # Quadratic squares
            features.append(X**2)
            # Pairwise interaction terms
            interactions = []
            for i in range(n_features):
                for j in range(i + 1, n_features):
                    interactions.append((X[:, i] * X[:, j])[:, np.newaxis])
            if interactions:
                features.append(np.hstack(interactions))
        return np.hstack(features)

    def fit(self, X: np.ndarray, y: np.ndarray) -> PolynomialRidgeSurrogate:
        """Fit Ridge weights on training data: W = (Phi^T Phi + alpha I)^-1 Phi^T y."""
        X_arr = np.asarray(X, dtype=float)
        y_arr = np.asarray(y, dtype=float)
        if y_arr.ndim == 1:
            y_arr = y_arr[:, np.newaxis]

        # Standardize inputs
        self.mean_ = np.mean(X_arr, axis=0)
        self.std_ = np.std(X_arr, axis=0)
        self.std_[self.std_ == 0] = 1.0

        X_norm = (X_arr - self.mean_) / self.std_
        phi = self._expand_features(X_norm)
        n_cols = phi.shape[1]

        # L2 regularizer matrix (do not penalize bias at index 0)
        reg = self.alpha * np.eye(n_cols)
        reg[0, 0] = 0.0

        self.weights = np.linalg.solve(phi.T @ phi + reg, phi.T @ y_arr)
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Predict target variables from input features."""
        if self.weights is None or self.mean_ is None or self.std_ is None:
            raise ValueError("Surrogate model must be fit before calling predict.")
        X_arr = np.asarray(X, dtype=float)
        X_norm = (X_arr - self.mean_) / self.std_
        phi = self._expand_features(X_norm)
        preds = phi @ self.weights
        return preds.squeeze()

    def score(self, X: np.ndarray, y: np.ndarray) -> float:
        """Compute coefficient of determination R² on evaluation data."""
        y_true = np.asarray(y, dtype=float).squeeze()
        y_pred = self.predict(X).squeeze()
        ss_res = np.sum((y_true - y_pred) ** 2)
        ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
        if ss_tot == 0:
            return 1.0
        return float(1.0 - (ss_res / ss_tot))


def train_crop_surrogate(
    samples_X: np.ndarray,
    samples_y: np.ndarray,
    degree: int = 2,
    alpha: float = 0.5,
) -> PolynomialRidgeSurrogate:
    """Train and return an AquaCrop surrogate model for fast rotation pre-screening."""
    model = PolynomialRidgeSurrogate(degree=degree, alpha=alpha)
    model.fit(samples_X, samples_y)
    return model
