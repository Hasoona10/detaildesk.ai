"""
Trained intent classifier for the auto-detailing receptionist.

This module wraps a few sklearn algorithms (Random Forest, SVM, Logistic Regression,
Gradient Boosting, MLP) and exposes a single `IntentClassifier` class that can be
trained on the detailing intent dataset and then used for fast/cheap intent
prediction at runtime (avoiding the LLM round-trip for the common cases).
"""
import pickle
import joblib
from typing import List, Optional, Dict
from pathlib import Path
import numpy as np
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC
from sklearn.neural_network import MLPClassifier
from sklearn.model_selection import cross_val_score, GridSearchCV
from backend.intents import Intent
from backend.utils.logger import logger


class IntentClassifier:
    """Train and use ML models for auto-detailing intent classification.

    Predicts a `backend.intents.Intent` from a customer utterance (e.g.
    "do you guys do ceramic coating?" -> `Intent.ASK_CERAMIC_COATING`) without
    needing an LLM round-trip.
    """
    
    def __init__(self, algorithm: str = "random_forest"):
        """
        Initialize intent classifier.
        
        Args:
            algorithm: Algorithm to use ('random_forest', 'svm', 'logistic', 'gradient_boosting', 'neural_network')
        """
        self.algorithm = algorithm
        self.model = None
        self.feature_extractor = None
        self.label_encoder = None  # Map intent strings to integers
        self.intent_labels = None  # Map integers back to Intent enums
        
    def _create_model(self, **kwargs):
        """
        Create the appropriate model based on algorithm.
        
        This creates the actual ML model object (Random Forest, SVM, etc.)
        based on which algorithm I chose. Each algorithm has different parameters
        that I can tune to improve performance.
        """
        if self.algorithm == "random_forest":
            return RandomForestClassifier(
                n_estimators=kwargs.get('n_estimators', 100),
                max_depth=kwargs.get('max_depth', 10),
                random_state=42,
                n_jobs=-1
            )
        elif self.algorithm == "svm":
            return SVC(
                kernel=kwargs.get('kernel', 'rbf'),
                C=kwargs.get('C', 1.0),
                probability=True,
                random_state=42
            )
        elif self.algorithm == "logistic":
            return LogisticRegression(
                max_iter=kwargs.get('max_iter', 1000),
                random_state=42,
                n_jobs=-1
            )
        elif self.algorithm == "gradient_boosting":
            return GradientBoostingClassifier(
                n_estimators=kwargs.get('n_estimators', 100),
                learning_rate=kwargs.get('learning_rate', 0.1),
                random_state=42
            )
        elif self.algorithm == "neural_network":
            return MLPClassifier(
                hidden_layer_sizes=kwargs.get('hidden_layer_sizes', (100, 50)),
                max_iter=kwargs.get('max_iter', 500),
                random_state=42,
                learning_rate_init=kwargs.get('learning_rate_init', 0.001)
            )
        else:
            raise ValueError(f"Unknown algorithm: {self.algorithm}")
    
    def train(
        self,
        texts: List[str],
        labels: List[str],
        feature_extractor,
        cross_validate: bool = True,
        cv_folds: int = 5
    ) -> Dict:
        """
        Train the intent classifier.
        
        This is where I train the model on the training data. I use cross-validation
        to make sure the model isn't overfitting. The results show accuracy, F1 score, etc.
        
        Args:
            texts: Training text samples (e.g. "do you do ceramic coating?")
            labels: Training labels (e.g. "ask_ceramic_coating", "book_appointment")
            feature_extractor: Fitted FeatureExtractor instance (text -> vectors)
            cross_validate: Whether to perform cross-validation
            cv_folds: Number of CV folds (default 5)

        Returns:
            Dictionary with training results (accuracy, cv_scores, etc.)
        """
        logger.info(f"Training {self.algorithm} classifier on {len(texts)} examples")
        
        # Store feature extractor - we need this later to make predictions
        self.feature_extractor = feature_extractor
        
        # Create label encoder - convert intent names to integer class ids.
        # For example: "ask_ceramic_coating" -> 0, "book_appointment" -> 1, ...
        unique_labels = sorted(set(labels))
        self.label_encoder = {label: idx for idx, label in enumerate(unique_labels)}
        self.intent_labels = {idx: Intent(label) for idx, label in enumerate(unique_labels)}  # Map back to Intent enum
        
        # Encode labels - convert all text labels to numbers
        y_encoded = np.array([self.label_encoder[label] for label in labels])
        
        # Extract features - convert text to numbers (TF-IDF vectors)
        # This is the key step! Text becomes a matrix of numbers
        X = feature_extractor.transform(texts)
        logger.info(f"Feature matrix shape: {X.shape}")
        
        # Create and train model - THIS IS WHERE THE MAGIC HAPPENS!
        # The model learns patterns from the training data
        self.model = self._create_model()
        self.model.fit(X, y_encoded)  # This is the actual training step
        
        # Calculate training accuracy - how well does it do on training data?
        train_predictions = self.model.predict(X)
        train_accuracy = np.mean(train_predictions == y_encoded)
        logger.info(f"Training accuracy: {train_accuracy:.4f}")
        
        results = {
            'training_accuracy': train_accuracy,
            'n_samples': len(texts),
            'n_features': X.shape[1],
            'n_classes': len(unique_labels)
        }
        
        # Cross-validation - this checks if the model is overfitting
        # It splits the data into folds and tests on each fold
        # This gives a more reliable accuracy estimate than just training accuracy
        if cross_validate:
            logger.info(f"Performing {cv_folds}-fold cross-validation...")
            cv_scores = cross_val_score(self.model, X, y_encoded, cv=cv_folds, scoring='accuracy')
            results['cv_mean'] = cv_scores.mean()  # Average accuracy across all folds
            results['cv_std'] = cv_scores.std()  # Standard deviation (how consistent)
            results['cv_scores'] = cv_scores.tolist()
            logger.info(f"CV accuracy: {cv_scores.mean():.4f} (+/- {cv_scores.std() * 2:.4f})")
        
        return results
    
    def predict(self, text: str) -> Intent:
        """
        Predict intent for a single text.
        
        This is the main function used at runtime: predicts the customer's
        intent (ceramic coating question, booking request, mobile service, etc.)
        from their utterance.
        
        Args:
            text: Input text (customer's message)

        Returns:
            Predicted Intent (e.g. Intent.ASK_CERAMIC_COATING, Intent.BOOK_APPOINTMENT).
        """
        if self.model is None or self.feature_extractor is None:
            raise ValueError("Model must be trained before prediction")
        
        # Extract features
        features = self.feature_extractor.transform([text])
        
        # Predict
        prediction_idx = self.model.predict(features)[0]
        prediction_intent = self.intent_labels[prediction_idx]
        
        return prediction_intent
    
    def predict_proba(self, text: str) -> Dict[Intent, float]:
        """
        Predict intent probabilities for a single text.
        
        Args:
            text: Input text
            
        Returns:
            Dictionary mapping Intent to probability
        """
        if self.model is None or self.feature_extractor is None:
            raise ValueError("Model must be trained before prediction")
        
        # Extract features
        features = self.feature_extractor.transform([text])
        
        # Get probabilities
        probas = self.model.predict_proba(features)[0]
        
        # Map to intents
        result = {}
        for idx, prob in enumerate(probas):
            if idx in self.intent_labels:
                intent = self.intent_labels[idx]
                result[intent] = float(prob)
        
        return result
    
    def save(self, model_dir: Path):
        """Save the trained model to disk."""
        model_dir.mkdir(parents=True, exist_ok=True)
        
        # Save model
        model_path = model_dir / f"{self.algorithm}_model.pkl"
        joblib.dump(self.model, model_path)
        
        # Save metadata
        metadata_path = model_dir / f"{self.algorithm}_metadata.pkl"
        joblib.dump({
            'algorithm': self.algorithm,
            'label_encoder': self.label_encoder,
            'intent_labels': {k: v.value for k, v in self.intent_labels.items()},
            'feature_extractor_method': self.feature_extractor.method if self.feature_extractor else None
        }, metadata_path)
        
        logger.info(f"Saved model to {model_dir}")
    
    @classmethod
    def load(cls, model_dir: Path, feature_extractor) -> 'IntentClassifier':
        """Load a trained model from disk."""
        # Find model file
        model_files = list(model_dir.glob("*_model.pkl"))
        if not model_files:
            raise FileNotFoundError(f"No model file found in {model_dir}")
        
        model_path = model_files[0]
        metadata_path = model_dir / model_path.name.replace("_model.pkl", "_metadata.pkl")
        
        # Load model
        model = joblib.load(model_path)
        
        # Load metadata
        metadata = joblib.load(metadata_path)
        
        # Create classifier instance
        classifier = cls(algorithm=metadata['algorithm'])
        classifier.model = model
        classifier.feature_extractor = feature_extractor
        classifier.label_encoder = metadata['label_encoder']
        classifier.intent_labels = {
            k: Intent(v) for k, v in metadata['intent_labels'].items()
        }
        
        logger.info(f"Loaded {metadata['algorithm']} model from {model_dir}")
        return classifier


