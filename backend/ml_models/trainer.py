"""
Training pipeline for intent classifier.

DEMO SECTION: ML Intent Classification - Training Pipeline
This script trains the ML models. I can train multiple algorithms at once and compare them.
The training process includes cross-validation to make sure models aren't overfitting.
"""
import csv
from pathlib import Path
from typing import List, Tuple, Dict, Optional
from sklearn.model_selection import train_test_split
from backend.utils.logger import logger
from backend.intents import Intent
from .feature_extractor import FeatureExtractor
from .intent_classifier import IntentClassifier


def load_dataset(filepath: Path) -> Tuple[List[str], List[str]]:
    """
    Load dataset from CSV file.
    
    Args:
        filepath: Path to CSV file with 'text' and 'intent' columns
        
    Returns:
        Tuple of (texts, labels)
    """
    texts = []
    labels = []
    
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            texts.append(row['text'])
            labels.append(row['intent'])
    
    logger.info(f"Loaded {len(texts)} examples from {filepath}")
    return texts, labels


def train_intent_classifier(
    train_data_path: Path,
    algorithm: str = "random_forest",
    feature_method: str = "tfidf",
    model_output_dir: Path = None,
    test_size: float = 0.2,
    **model_kwargs
) -> Tuple[IntentClassifier, Dict]:
    """
    Train an intent classifier.
    
    This is the main training function. I split the data into train/validation sets,
    extract features, train the model, and evaluate it. The results show accuracy,
    cross-validation scores, etc.
    
    Args:
        train_data_path: Path to training CSV file (has 'text' and 'intent' columns)
        algorithm: ML algorithm to use ('random_forest', 'svm', 'logistic', etc.)
        feature_method: Feature extraction method ('tfidf', 'bow', 'tfidf_pca')
        model_output_dir: Directory to save the trained model
        test_size: Fraction of data to use for validation (20% by default)
        **model_kwargs: Additional parameters for the model
        
    Returns:
        Tuple of (trained_classifier, training_results)
    """
    logger.info(f"Starting training pipeline: {algorithm} with {feature_method} features")
    
    # Load training data
    texts, labels = load_dataset(train_data_path)
    
    # Split into train/validation if needed
    if test_size > 0:
        texts_train, texts_val, labels_train, labels_val = train_test_split(
            texts, labels, test_size=test_size, random_state=42, stratify=labels
        )
        logger.info(f"Split: {len(texts_train)} train, {len(texts_val)} validation")
    else:
        texts_train, labels_train = texts, labels
        texts_val, labels_val = None, None
    
    # Create and fit feature extractor
    logger.info("Fitting feature extractor...")
    feature_extractor = FeatureExtractor(method=feature_method)
    X_train = feature_extractor.fit_transform(texts_train)
    
    # Train classifier
    logger.info(f"Training {algorithm} classifier...")
    classifier = IntentClassifier(algorithm=algorithm)
    training_results = classifier.train(
        texts=texts_train,
        labels=labels_train,
        feature_extractor=feature_extractor,
        cross_validate=True,
        **model_kwargs
    )
    
    # Evaluate on validation set if available
    if texts_val:
        logger.info("Evaluating on validation set...")
        val_predictions = []
        for text in texts_val:
            val_predictions.append(classifier.predict(text).value)
        
        val_accuracy = sum(p == l for p, l in zip(val_predictions, labels_val)) / len(labels_val)
        training_results['validation_accuracy'] = val_accuracy
        logger.info(f"Validation accuracy: {val_accuracy:.4f}")
    
    # Save model if output directory specified
    if model_output_dir:
        model_output_dir = Path(model_output_dir)
        
        # Save feature extractor
        feature_extractor_path = model_output_dir / f"{feature_method}_extractor.pkl"
        feature_extractor.save(feature_extractor_path)
        
        # Save classifier
        classifier.save(model_output_dir)
        training_results['model_path'] = str(model_output_dir)
    
    return classifier, training_results


def train_multiple_models(
    train_data_path: Path,
    algorithms: List[str] = None,
    feature_methods: List[str] = None,
    models_dir: Path = None
) -> Dict:
    """
    Train multiple model configurations and compare.
    
    Args:
        train_data_path: Path to training CSV file
        algorithms: List of algorithms to try
        feature_methods: List of feature methods to try
        models_dir: Directory to save all models
        
    Returns:
        Dictionary with results for all model configurations
    """
    if algorithms is None:
        algorithms = ["random_forest", "logistic", "svm"]
    
    if feature_methods is None:
        feature_methods = ["tfidf"]
    
    if models_dir:
        models_dir = Path(models_dir)
        models_dir.mkdir(parents=True, exist_ok=True)
    
    all_results = {}
    
    for algorithm in algorithms:
        for feature_method in feature_methods:
            config_name = f"{algorithm}_{feature_method}"
            logger.info(f"\n{'='*50}")
            logger.info(f"Training: {config_name}")
            logger.info(f"{'='*50}")
            
            model_dir = models_dir / config_name if models_dir else None
            
            try:
                classifier, results = train_intent_classifier(
                    train_data_path=train_data_path,
                    algorithm=algorithm,
                    feature_method=feature_method,
                    model_output_dir=model_dir,
                    test_size=0.2
                )
                
                all_results[config_name] = {
                    'algorithm': algorithm,
                    'feature_method': feature_method,
                    **results
                }
                
            except Exception as e:
                logger.error(f"Error training {config_name}: {str(e)}")
                all_results[config_name] = {'error': str(e)}
    
    return all_results


if __name__ == "__main__":
    # Example usage
    import sys
    from pathlib import Path
    
    # Path to training data
    train_data = Path(__file__).parent.parent.parent / "backend" / "data" / "training" / "intent_dataset_train.csv"
    
    if not train_data.exists():
        print(f"Training data not found at {train_data}")
        print("Please run synthetic_data.py first to generate training data")
        sys.exit(1)
    
    # Train a single model
    models_dir = Path(__file__).parent.parent.parent / "models"
    classifier, results = train_intent_classifier(
        train_data_path=train_data,
        algorithm="random_forest",
        feature_method="tfidf",
        model_output_dir=models_dir / "random_forest_tfidf"
    )
    
    print("\nTraining Results:")
    print(results)
    
    # Test prediction
    test_text = "How much for a full detail on a Tesla Model 3?"
    prediction = classifier.predict(test_text)
    print(f"\nTest prediction: '{test_text}' -> {prediction.value}")


