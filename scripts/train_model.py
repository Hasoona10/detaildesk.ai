#!/usr/bin/env python3
"""
Script to train intent classification models.

DEMO SECTION: Fine-Tuning/Training - Main Training Script
This is the main script I run to train all my ML models! It does everything:
1. Generates synthetic training data (if needed)
2. Trains multiple models (Random Forest, SVM, Logistic Regression)
3. Finds the best model and saves it
4. Compares ML vs rule-based vs LLM methods

Just run: python scripts/train_model.py
"""
import sys
from pathlib import Path

# Add parent directory to path (so we can import backend modules)
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.data.training.synthetic_data import create_training_dataset
from backend.ml_models.trainer import train_multiple_models, train_intent_classifier
from backend.evaluation.evaluator import compare_all_methods
from backend.ml_models.model_registry import get_registry
from backend.utils.logger import logger
from dotenv import load_dotenv

load_dotenv()


def main():
    """
    Main training pipeline.
    
    This function runs the entire training process from start to finish.
    It's like the "main" function for fine-tuning my models.
    """
    logger.info("Starting model training pipeline...")
    
    # Setup paths - where to find/save data and models
    project_root = Path(__file__).parent.parent
    data_dir = project_root / "backend" / "data" / "training"
    models_dir = project_root / "models"
    test_data_path = project_root / "backend" / "data" / "training" / "intent_dataset_test.csv"
    
    # Step 1: Generate / refresh the detailing synthetic training data.
    train_data_path = data_dir / "intent_dataset_train.csv"
    if not train_data_path.exists() or not test_data_path.exists():
        logger.info("Generating synthetic detailing training data...")
        train_data_path, test_data_path = create_training_dataset(
            data_dir / "intent_dataset.csv",
            examples_per_intent=60,
            train_split=0.8,
        )
    
    # Step 2: Train models
    # I train multiple algorithms to see which one works best
    logger.info("\n" + "="*60)
    logger.info("Training Multiple Models")
    logger.info("="*60)
    
    results = train_multiple_models(
        train_data_path=train_data_path,
        algorithms=["random_forest", "logistic", "svm"],  # Try these 3 algorithms
        feature_methods=["tfidf"],  # Use TF-IDF for feature extraction
        models_dir=models_dir  # Save trained models here
    )
    
    # Step 3: Register best model
    # Find which model performed best and save it to the registry
    registry = get_registry(models_dir / "registry.json")
    best_model_name = None
    best_accuracy = -1
    
    # Loop through all trained models and find the one with highest accuracy
    for config_name, result in results.items():
        if 'error' in result:
            continue  # Skip models that failed to train
        
        # Get accuracy (prefer validation accuracy, fall back to CV mean)
        accuracy = result.get('validation_accuracy', result.get('cv_mean', 0))
        if accuracy > best_accuracy:
            best_accuracy = accuracy
            best_model_name = config_name
    
    if best_model_name:
        logger.info(f"\nBest model: {best_model_name} (accuracy: {best_accuracy:.4f})")
        
        # Register in registry so the system knows which model to use
        algorithm, feature_method = best_model_name.split('_', 1)
        registry.register_model(
            model_name="intent_classifier",
            model_path=models_dir / best_model_name,
            algorithm=algorithm,
            feature_method=feature_method,
            metrics={
                'accuracy': best_accuracy,
                **{k: v for k, v in results[best_model_name].items() 
                   if k not in ['algorithm', 'feature_method']}
            }
        )
    
    # Step 4: Evaluate all methods
    # Compare ML model vs rule-based vs LLM to see which is best overall
    logger.info("\n" + "="*60)
    logger.info("Evaluating All Methods")
    logger.info("="*60)
    
    # Load best ML model so we can use it in comparison
    ml_classifier = None
    if best_model_name:
        from backend.ml_models.intent_classifier import IntentClassifier
        from backend.ml_models.feature_extractor import FeatureExtractor
        
        model_dir = models_dir / best_model_name
        extractor_path = list(model_dir.glob("*_extractor.pkl"))[0]
        feature_extractor = FeatureExtractor.load(extractor_path)
        ml_classifier = IntentClassifier.load(model_dir, feature_extractor)
    
    # Compare all methods (ML, rule-based, LLM) on test data
    evaluation_dir = project_root / "evaluation_results"
    comparison = compare_all_methods(
        test_data_path=test_data_path,
        ml_classifier=ml_classifier,
        output_dir=evaluation_dir  # Save confusion matrices and reports here
    )
    
    logger.info("\n" + "="*60)
    logger.info("Training Complete!")
    logger.info("="*60)
    logger.info(f"Best Model (Accuracy): {comparison['best_model_accuracy']} ({comparison['best_accuracy']:.4f})")
    logger.info(f"Best Model (F1): {comparison['best_model_f1']} ({comparison['best_f1']:.4f})")
    logger.info(f"\nResults saved to: {evaluation_dir}")


if __name__ == "__main__":
    main()


