"""
Model registry for tracking and managing trained models.

DEMO SECTION: Fine-Tuning/Training - Model Registry
This keeps track of all the models I've trained! It's like a database that stores:
- Which models I've trained
- Their performance metrics (accuracy, F1, etc.)
- When they were created
- Which one is the best

This way I can easily find and use the best model without having to remember
which file it's in. Super useful when training multiple models!
"""
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from backend.utils.logger import logger


class ModelRegistry:
    """Registry for managing model versions and metadata."""
    
    def __init__(self, registry_path: Path = None):
        """
        Initialize model registry.
        
        Args:
            registry_path: Path to registry JSON file
        """
        if registry_path is None:
            registry_path = Path("./models/registry.json")
        self.registry_path = Path(registry_path)
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        self.models = self._load_registry()
    
    def _load_registry(self) -> Dict:
        """Load registry from disk."""
        if self.registry_path.exists():
            try:
                with open(self.registry_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading registry: {str(e)}")
                return {}
        return {}
    
    def _save_registry(self):
        """Save registry to disk."""
        with open(self.registry_path, 'w') as f:
            json.dump(self.models, f, indent=2)
        logger.info(f"Saved registry to {self.registry_path}")
    
    def register_model(
        self,
        model_name: str,
        model_path: Path,
        algorithm: str,
        feature_method: str,
        metrics: Dict,
        metadata: Dict = None
    ) -> str:
        """
        Register a new model version.
        
        When I train a new model, I register it here so I can track it.
        It saves the model's performance metrics, algorithm used, etc.
        This makes it easy to compare different models I've trained.
        
        Args:
            model_name: Name of the model (e.g., 'intent_classifier')
            model_path: Path to model directory (where the .pkl files are)
            algorithm: Algorithm used (e.g., 'random_forest', 'svm')
            feature_method: Feature extraction method (e.g., 'tfidf', 'bow')
            metrics: Model performance metrics (accuracy, F1, etc.)
            metadata: Additional metadata (optional notes about the model)
            
        Returns:
            Version ID (unique identifier for this model version)
        """
        if model_name not in self.models:
            self.models[model_name] = []
        
        version_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        model_entry = {
            'version': version_id,
            'path': str(model_path),
            'algorithm': algorithm,
            'feature_method': feature_method,
            'metrics': metrics,
            'created_at': datetime.now().isoformat(),
            'metadata': metadata or {}
        }
        
        self.models[model_name].append(model_entry)
        
        # Sort by creation date (newest first)
        self.models[model_name].sort(key=lambda x: x['created_at'], reverse=True)
        
        self._save_registry()
        logger.info(f"Registered model {model_name} version {version_id}")
        
        return version_id
    
    def get_latest_model(self, model_name: str) -> Optional[Dict]:
        """Get the latest version of a model."""
        if model_name not in self.models or not self.models[model_name]:
            return None
        
        return self.models[model_name][0]
    
    def get_best_model(self, model_name: str, metric: str = 'accuracy') -> Optional[Dict]:
        """
        Get the best model by a specific metric.
        
        This finds the model with the highest score for a given metric.
        For example, if I want the model with best accuracy, I call this
        with metric='accuracy'. Super useful for automatically selecting
        the best model to use in production!
        
        Args:
            model_name: Name of the model (e.g., 'intent_classifier')
            metric: Metric to use for comparison ('accuracy', 'f1_weighted', etc.)
            
        Returns:
            Best model entry (dict with all model info) or None if no models found
        """
        if model_name not in self.models or not self.models[model_name]:
            return None
        
        models = self.models[model_name]
        
        # Find model with highest metric
        best_model = None
        best_score = -1
        
        for model in models:
            if 'metrics' in model and metric in model['metrics']:
                score = model['metrics'][metric]
                if score > best_score:
                    best_score = score
                    best_model = model
        
        return best_model
    
    def list_models(self, model_name: str = None) -> Dict:
        """List all models or models for a specific name."""
        if model_name:
            return {model_name: self.models.get(model_name, [])}
        return self.models
    
    def get_model_by_version(self, model_name: str, version: str) -> Optional[Dict]:
        """Get a specific model version."""
        if model_name not in self.models:
            return None
        
        for model in self.models[model_name]:
            if model['version'] == version:
                return model
        
        return None


# Global registry instance
_registry: Optional[ModelRegistry] = None

def get_registry(registry_path: Path = None) -> ModelRegistry:
    """Get or create global registry instance."""
    global _registry
    if _registry is None:
        _registry = ModelRegistry(registry_path)
    return _registry


