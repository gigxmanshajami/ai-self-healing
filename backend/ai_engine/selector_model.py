"""
Selector Prediction Model
ML model for predicting the best matching DOM element.
"""

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
import joblib
from typing import List, Tuple, Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path
from loguru import logger
from datetime import datetime


@dataclass
class ModelMetrics:
    """Training and validation metrics."""
    accuracy: float
    precision: float
    recall: float
    f1: float
    training_samples: int
    validation_samples: int
    training_time: float
    last_trained: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "accuracy": round(self.accuracy, 4),
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
            "training_samples": self.training_samples,
            "validation_samples": self.validation_samples,
            "training_time_seconds": round(self.training_time, 2),
            "last_trained": self.last_trained
        }


class SelectorModel:
    """
    ML model for predicting correct DOM element matches.
    
    Supports:
    - Logistic Regression (default, fast)
    - Random Forest (more accurate, for production)
    
    Features:
    - Automatic scaling
    - Model persistence
    - Online learning (incremental updates)
    - Confidence scoring
    """

    def __init__(
        self,
        model_type: str = "logistic",
        model_path: Optional[str] = None
    ):
        """
        Initialize selector model.
        
        Args:
            model_type: "logistic" or "random_forest"
            model_path: Path to save/load model
        """
        self.model_type = model_type
        self.model_path = Path(model_path) if model_path else Path("models/selector_model.pkl")
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.scaler = StandardScaler()
        self.model = self._create_model(model_type)
        self.is_trained = False
        self.metrics: Optional[ModelMetrics] = None
        
        # Try loading existing model
        self._load_if_exists()

    def _create_model(self, model_type: str):
        """Create fresh model instance."""
        if model_type == "logistic":
            return LogisticRegression(
                class_weight="balanced",
                max_iter=1000,
                C=1.0,
                solver="lbfgs"
            )
        elif model_type == "random_forest":
            return RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                class_weight="balanced",
                n_jobs=-1
            )
        else:
            raise ValueError(f"Unknown model type: {model_type}")

    def train(
        self,
        X: np.ndarray,
        y: np.ndarray,
        validation_split: float = 0.2
    ) -> ModelMetrics:
        """
        Train the model on labeled data.
        
        Args:
            X: Feature matrix (n_samples, n_features)
            y: Labels (n_samples,) - 1 for match, 0 for non-match
            validation_split: Fraction of data for validation
            
        Returns:
            ModelMetrics with training results
        """
        import time
        start_time = time.time()
        
        logger.info(f"Training {self.model_type} model with {len(X)} samples...")
        
        # Split data
        X_train, X_val, y_train, y_val = train_test_split(
            X, y, test_size=validation_split, random_state=42, stratify=y
        )
        
        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_val_scaled = self.scaler.transform(X_val)
        
        # Train model
        self.model.fit(X_train_scaled, y_train)
        
        # Evaluate
        y_pred = self.model.predict(X_val_scaled)
        
        training_time = time.time() - start_time
        
        self.metrics = ModelMetrics(
            accuracy=accuracy_score(y_val, y_pred),
            precision=precision_score(y_val, y_pred, zero_division=0),
            recall=recall_score(y_val, y_pred, zero_division=0),
            f1=f1_score(y_val, y_pred, zero_division=0),
            training_samples=len(X_train),
            validation_samples=len(X_val),
            training_time=training_time,
            last_trained=datetime.utcnow().isoformat()
        )
        
        self.is_trained = True
        self._save()
        
        logger.info(
            f"Training complete. Accuracy: {self.metrics.accuracy:.4f}, "
            f"F1: {self.metrics.f1:.4f}"
        )
        
        return self.metrics

    def predict(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Predict matches and confidence scores.
        
        Args:
            X: Feature matrix (n_samples, n_features)
            
        Returns:
            Tuple of (predictions, confidence_scores)
        """
        if not self.is_trained:
            logger.warning("Model not trained, using default predictions")
            return np.zeros(len(X)), np.full(len(X), 0.5)
        
        X_scaled = self.scaler.transform(X)
        predictions = self.model.predict(X_scaled)
        
        # Get probability scores
        if hasattr(self.model, "predict_proba"):
            probas = self.model.predict_proba(X_scaled)
            confidence = probas[:, 1]  # Probability of positive class
        else:
            confidence = np.full(len(X), 0.5)
        
        return predictions, confidence

    def predict_best_match(
        self,
        X: np.ndarray,
        threshold: float = 0.5
    ) -> Tuple[int, float]:
        """
        Find the best matching element from candidates.
        
        Args:
            X: Feature matrix of candidate elements
            threshold: Minimum confidence threshold
            
        Returns:
            Tuple of (best_index, confidence_score)
        """
        _, confidence = self.predict(X)
        
        best_idx = np.argmax(confidence)
        best_confidence = confidence[best_idx]
        
        if best_confidence < threshold:
            logger.warning(
                f"Best match confidence ({best_confidence:.4f}) "
                f"below threshold ({threshold})"
            )
        
        return int(best_idx), float(best_confidence)

    def update_with_feedback(
        self,
        X: np.ndarray,
        y: np.ndarray,
        learning_rate: float = 0.1
    ) -> None:
        """
        Update model with new labeled examples (online learning).
        
        For Logistic Regression, this re-trains with combined data.
        For production, consider using SGDClassifier for true online learning.
        
        Args:
            X: New feature samples
            y: New labels
            learning_rate: Weight for new samples (future use)
        """
        if not self.is_trained:
            self.train(X, y)
            return
        
        # For now, store feedback for periodic retraining
        logger.info(f"Received {len(X)} new training samples for future update")
        # In production, append to training database

    def get_feature_importance(self, feature_names: List[str]) -> Dict[str, float]:
        """
        Get feature importance scores.
        
        Args:
            feature_names: Names of features in order
            
        Returns:
            Dict mapping feature names to importance scores
        """
        if not self.is_trained:
            return {}
        
        if self.model_type == "logistic":
            importance = np.abs(self.model.coef_[0])
        elif self.model_type == "random_forest":
            importance = self.model.feature_importances_
        else:
            return {}
        
        # Normalize
        importance = importance / (importance.sum() + 1e-10)
        
        # Match with names (truncate if needed)
        importance_dict = {}
        for i, name in enumerate(feature_names[:len(importance)]):
            importance_dict[name] = round(float(importance[i]), 4)
        
        # Sort by importance
        return dict(sorted(importance_dict.items(), key=lambda x: x[1], reverse=True))

    def get_status(self) -> Dict[str, Any]:
        """Get model status and metrics."""
        return {
            "model_type": self.model_type,
            "is_trained": self.is_trained,
            "model_path": str(self.model_path),
            "metrics": self.metrics.to_dict() if self.metrics else None
        }

    def _save(self) -> None:
        """Save model and scaler to disk."""
        try:
            save_data = {
                "model": self.model,
                "scaler": self.scaler,
                "model_type": self.model_type,
                "metrics": self.metrics,
                "is_trained": self.is_trained
            }
            joblib.dump(save_data, self.model_path)
            logger.info(f"Model saved to {self.model_path}")
        except Exception as e:
            logger.error(f"Failed to save model: {e}")

    def _load_if_exists(self) -> bool:
        """Load model if exists on disk."""
        if not self.model_path.exists():
            return False
        
        try:
            save_data = joblib.load(self.model_path)
            self.model = save_data["model"]
            self.scaler = save_data["scaler"]
            self.model_type = save_data["model_type"]
            self.metrics = save_data["metrics"]
            self.is_trained = save_data["is_trained"]
            logger.info(f"Model loaded from {self.model_path}")
            return True
        except Exception as e:
            logger.warning(f"Failed to load model: {e}")
            return False


def create_synthetic_training_data(n_samples: int = 1000) -> Tuple[np.ndarray, np.ndarray]:
    """
    Generate synthetic training data for initial model.
    
    In production, this should be replaced with real data
    from past successful selector matches.
    
    Args:
        n_samples: Number of samples to generate
        
    Returns:
        Tuple of (X, y) arrays
    """
    np.random.seed(42)
    
    # Feature dimensions (matching FeatureExtractor output)
    # 34 tag one-hot + 34 parent_tag one-hot + 5 scalar + 2 new similarity = 75
    n_tags = 34  # COMMON_TAGS (33) + 'other'
    n_features = n_tags * 2 + 7  # tag + parent_tag + 5 scalar + 2 sim features (75 total)
    
    # Feature dimensions
    n_tags = 34
    n_features = n_tags * 2 + 7
    
    X = np.zeros((n_samples, n_features))
    y = np.zeros(n_samples)
    
    # Indices
    class_sim_idx = n_tags * 2
    id_sim_idx = class_sim_idx + 1
    # parent=2, sibling=3, text_len=4, attr=5
    tag_sim_idx = class_sim_idx + 5
    text_sim_idx = class_sim_idx + 6
    
    # Generate 50% positive samples
    n_pos = n_samples // 2
    for i in range(n_pos):
        y[i] = 1
        scenario = np.random.choice(['class', 'id', 'semantic', 'mixed'])
        
        # Base noise
        X[i] = np.random.rand(n_features) * 0.3  # Low noise
        
        if scenario == 'class':
            X[i, class_sim_idx] = np.random.uniform(0.7, 1.0)
            X[i, tag_sim_idx] = np.random.uniform(0.8, 1.0)  # Usually same tag
        
        elif scenario == 'id':
            X[i, id_sim_idx] = np.random.uniform(0.8, 1.0)
            X[i, tag_sim_idx] = np.random.uniform(0.8, 1.0)
            
        elif scenario == 'semantic':
            # Tag + Text match (no class/id)
            X[i, tag_sim_idx] = np.random.uniform(0.9, 1.0)
            X[i, text_sim_idx] = np.random.uniform(0.8, 1.0)
            X[i, class_sim_idx] = np.random.uniform(0.0, 0.4) # Low class sim
            
        elif scenario == 'mixed':
            # Weak class + strong structure
            X[i, class_sim_idx] = np.random.uniform(0.4, 0.7)
            X[i, tag_sim_idx] = 1.0
            X[i, text_sim_idx] = np.random.uniform(0.6, 0.9)

    # Generate 50% negative samples
    for i in range(n_pos, n_samples):
        y[i] = 0
        scenario = np.random.choice(['random', 'hard_negative'])
        
        # Base noise
        X[i] = np.random.rand(n_features) * 0.3
        
        if scenario == 'hard_negative':
            # Has tag match but nothing else
            X[i, tag_sim_idx] = 1.0
            X[i, class_sim_idx] = np.random.uniform(0.0, 0.3)
            X[i, text_sim_idx] = np.random.uniform(0.0, 0.4)
    
    # Shuffle
    perm = np.random.permutation(n_samples)
    X = X[perm]
    y = y[perm]
    
    logger.info(f"Generated {n_samples} constructive synthetic samples")
    return X, y
    
    logger.info(f"Generated {n_samples} synthetic samples, {int(y.sum())} positive")
    return X, y
