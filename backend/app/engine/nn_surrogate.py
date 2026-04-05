"""
BOS Pipeline v9.0 �� Neural Network Surrogate Engine

Trains a lightweight neural network surrogate model to approximate
expensive engine computations for real-time prediction.

Architecture: Simple feedforward MLP with:
  - Input normalization
  - 2�C3 hidden layers (ReLU)
  - Output denormalization

Implemented in pure NumPy (no PyTorch/TF dependency) for portability.
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
from numpy.typing import NDArray

ENGINE_VERSION = "9.0.0"


@dataclass
class NNConfig:
    """Neural network configuration."""

    hidden_sizes: List[int] = field(default_factory=lambda: [32, 16])
    learning_rate: float = 0.01
    epochs: int = 500
    batch_size: int = 32
    l2_reg: float = 1e-4
    seed: Optional[int] = None


@dataclass
class NNSurrogateResult:
    """Results from surrogate model training/prediction."""

    predictions: List[float] = field(default_factory=list)
    training_loss_history: List[float] = field(default_factory=list)
    r_squared: Optional[float] = None
    rmse: Optional[float] = None
    mae: Optional[float] = None
    n_parameters: int = 0
    computation_time_ms: float = 0.0
    engine_version: str = ENGINE_VERSION
    errors: List[str] = field(default_factory=list)


class NNSurrogate:
    """
    Simple feedforward neural network in pure NumPy.

    Supports training and prediction for surrogate modeling.
    """

    def __init__(self, input_dim: int, output_dim: int, config: NNConfig):
        self.config = config
        self.rng = np.random.default_rng(config.seed)

        # Build layers
        sizes = [input_dim] + config.hidden_sizes + [output_dim]
        self.weights: List[NDArray] = []
        self.biases: List[NDArray] = []

        for i in range(len(sizes) - 1):
            # He initialization
            std = np.sqrt(2.0 / sizes[i])
            W = self.rng.normal(0, std, (sizes[i], sizes[i + 1]))
            b = np.zeros((1, sizes[i + 1]))
            self.weights.append(W)
            self.biases.append(b)

        # Normalization parameters
        self.x_mean: Optional[NDArray] = None
        self.x_std: Optional[NDArray] = None
        self.y_mean: Optional[NDArray] = None
        self.y_std: Optional[NDArray] = None

    @property
    def n_parameters(self) -> int:
        total = 0
        for W, b in zip(self.weights, self.biases):
            total += W.size + b.size
        return total

    def _relu(self, x: NDArray) -> NDArray:
        return np.maximum(0, x)

    def _relu_grad(self, x: NDArray) -> NDArray:
        return (x > 0).astype(float)

    def _forward(self, X: NDArray) -> Tuple[List[NDArray], List[NDArray]]:
        """Forward pass returning activations and pre-activations."""
        activations = [X]
        pre_activations = []

        current = X
        for i, (W, b) in enumerate(zip(self.weights, self.biases)):
            z = current @ W + b
            pre_activations.append(z)

            if i < len(self.weights) - 1:
                current = self._relu(z)
            else:
                current = z  # Linear output

            activations.append(current)

        return activations, pre_activations

    def predict_raw(self, X: NDArray) -> NDArray:
        """Predict without normalization."""
        activations, _ = self._forward(X)
        return activations[-1]

    def predict(self, X: NDArray) -> NDArray:
        """Predict with normalization."""
        if self.x_mean is not None:
            X_norm = (X - self.x_mean) / (self.x_std + 1e-8)
        else:
            X_norm = X

        y_norm = self.predict_raw(X_norm)

        if self.y_mean is not None:
            return y_norm * (self.y_std + 1e-8) + self.y_mean
        return y_norm

    def fit(self, X: NDArray, y: NDArray) -> List[float]:
        """
        Train the network using mini-batch gradient descent.

        Returns training loss history.
        """
        n = X.shape[0]

        # Normalize
        self.x_mean = X.mean(axis=0, keepdims=True)
        self.x_std = X.std(axis=0, keepdims=True)
        self.y_mean = y.mean(axis=0, keepdims=True)
        self.y_std = y.std(axis=0, keepdims=True)

        X_norm = (X - self.x_mean) / (self.x_std + 1e-8)
        y_norm = (y - self.y_mean) / (self.y_std + 1e-8)

        losses: List[float] = []
        lr = self.config.learning_rate

        for epoch in range(self.config.epochs):
            # Shuffle
            perm = self.rng.permutation(n)
            X_shuffled = X_norm[perm]
            y_shuffled = y_norm[perm]

            epoch_loss = 0.0
            n_batches = 0

            for start in range(0, n, self.config.batch_size):
                end = min(start + self.config.batch_size, n)
                X_batch = X_shuffled[start:end]
                y_batch = y_shuffled[start:end]
                bs = X_batch.shape[0]

                # Forward
                activations, pre_activations = self._forward(X_batch)
                y_pred = activations[-1]

                # Loss: MSE + L2 regularization
                loss = np.mean((y_pred - y_batch) ** 2)
                for W in self.weights:
                    loss += self.config.l2_reg * np.sum(W ** 2)
                epoch_loss += loss
                n_batches += 1

                # Backward
                delta = 2.0 / bs * (y_pred - y_batch)

                for i in range(len(self.weights) - 1, -1, -1):
                    dW = activations[i].T @ delta / bs + 2 * self.config.l2_reg * self.weights[i]
                    db = np.mean(delta, axis=0, keepdims=True)

                    self.weights[i] -= lr * dW
                    self.biases[i] -= lr * db

                    if i > 0:
                        delta = (delta @ self.weights[i].T) * self._relu_grad(pre_activations[i - 1])

            avg_loss = epoch_loss / max(n_batches, 1)
            losses.append(float(avg_loss))

            # Learning rate decay
            if (epoch + 1) % 100 == 0:
                lr *= 0.9

        return losses


def train_surrogate(
    X_train: List[List[float]],
    y_train: List[float],
    X_predict: Optional[List[List[float]]] = None,
    config: Optional[NNConfig] = None,
) -> NNSurrogateResult:
    """
    Train a neural network surrogate and optionally predict.

    Parameters
    ----------
    X_train : Training features
    y_train : Training targets
    X_predict : Points to predict (optional)
    config : Network configuration

    Returns
    -------
    NNSurrogateResult
        Predictions and training diagnostics.
    """
    start_time = time.perf_counter()
    result = NNSurrogateResult()

    if config is None:
        config = NNConfig()

    if len(X_train) < 5:
        result.errors.append("Need at least 5 training samples")
        return result

    X = np.array(X_train, dtype=np.float64)
    y = np.array(y_train, dtype=np.float64).reshape(-1, 1)

    n, d = X.shape
    model = NNSurrogate(d, 1, config)
    result.n_parameters = model.n_parameters

    # Train
    losses = model.fit(X, y)
    result.training_loss_history = [round(l, 8) for l in losses]

    # In-sample metrics
    y_pred_train = model.predict(X)
    residuals = y - y_pred_train
    ss_res = float(np.sum(residuals ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))

    if ss_tot > 0:
        result.r_squared = round(float(1 - ss_res / ss_tot), 6)
    result.rmse = round(float(np.sqrt(np.mean(residuals ** 2))), 6)
    result.mae = round(float(np.mean(np.abs(residuals))), 6)

    # Predictions
    if X_predict is not None:
        Xp = np.array(X_predict, dtype=np.float64)
        y_pred = model.predict(Xp)
        result.predictions = [round(float(v), 6) for v in y_pred.flatten()]
    else:
        result.predictions = [round(float(v), 6) for v in y_pred_train.flatten()]

    result.computation_time_ms = round((time.perf_counter() - start_time) * 1000, 2)
    return result
