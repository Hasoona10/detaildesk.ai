"""
Model evaluation pipeline.

DEMO SECTION: Fine-Tuning/Training - Model Evaluation
This module evaluates how well my trained models perform! It:
1. Tests models on test data (data they haven't seen before)
2. Calculates metrics (accuracy, F1 score, precision, recall)
3. Compares ML models vs rule-based vs LLM methods
4. Generates confusion matrices and classification reports

This is super important to make sure my models actually work well!
"""
import csv
from pathlib import Path
from typing import List, Dict, Optional
from backend.utils.logger import logger
from backend.intents import Intent, classify_intent, classify_intent_rule_based, classify_intent_llm
from .metrics import calculate_metrics, generate_classification_report, plot_confusion_matrix, compare_models


def evaluate_on_dataset(
    test_data_path: Path,
    classifier=None,
    method: str = "ml",
    labels: List[str] = None
) -> Dict:
    """
    Evaluate classifier on test dataset.
    
    This function tests a model on test data (data it hasn't seen during training).
    It makes predictions and compares them to the true labels to calculate accuracy.
    
    Args:
        test_data_path: Path to test CSV file with 'text' and 'intent' columns
        classifier: ML classifier instance (if method='ml') - the trained model
        method: Evaluation method ('ml', 'rule', 'llm') - which method to test
        labels: Optional list of all label names (for metrics calculation)
        
    Returns:
        Dictionary with evaluation results (accuracy, F1, precision, recall, etc.)
    """
    import asyncio
    
    # Load test data
    texts = []
    true_labels = []
    
    with open(test_data_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            texts.append(row['text'])
            true_labels.append(row['intent'])
    
    logger.info(f"Evaluating {method} method on {len(texts)} test examples")
    
    # Get predictions - this is where we test the model!
    predictions = []
    
    if method == "ml":
        # Test the trained ML model
        if classifier is None:
            raise ValueError("Classifier required for ML method")
        for text in texts:
            try:
                intent = classifier.predict(text)  # Make prediction
                predictions.append(intent.value)
            except Exception as e:
                logger.error(f"Error predicting {text}: {str(e)}")
                predictions.append("unknown")  # Default to unknown if error
    
    elif method == "rule":
        # Test rule-based method (keyword matching)
        for text in texts:
            intent = classify_intent_rule_based(text)
            predictions.append(intent.value)
    
    elif method == "llm":
        # Test LLM method (OpenAI API) - this is async so we need special handling
        async def get_predictions():
            preds = []
            for text in texts:
                intent = await classify_intent_llm(text)
                preds.append(intent.value)
            return preds
        
        predictions = asyncio.run(get_predictions())
    
    else:
        raise ValueError(f"Unknown method: {method}")
    
    # Calculate metrics - compare predictions to true labels
    if labels is None:
        labels = sorted(set(true_labels + predictions))
    
    # This calculates accuracy, F1, precision, recall, etc.
    metrics = calculate_metrics(true_labels, predictions, labels)
    
    return {
        'method': method,
        'n_samples': len(texts),
        'predictions': predictions,
        'true_labels': true_labels,
        **metrics
    }


def compare_all_methods(
    test_data_path: Path,
    ml_classifier=None,
    output_dir: Path = None
) -> Dict:
    """
    Compare all classification methods (ML, rule-based, LLM).
    
    This is the main comparison function! It tests all three methods on the same
    test data and compares their performance. This helps me decide which method
    to use in production. It also generates confusion matrices and reports.
    
    Args:
        test_data_path: Path to test CSV file (same data for all methods)
        ml_classifier: Trained ML classifier (the model I trained)
        output_dir: Optional directory to save results (confusion matrices, reports)
        
    Returns:
        Comparison results dictionary with best model info and metrics
    """
    logger.info("Comparing all classification methods...")
    
    results = {}
    
    # Evaluate ML model
    if ml_classifier:
        logger.info("Evaluating ML model...")
        try:
            results['ml'] = evaluate_on_dataset(
                test_data_path, 
                classifier=ml_classifier, 
                method='ml'
            )
        except Exception as e:
            logger.error(f"Error evaluating ML model: {str(e)}")
            results['ml'] = {'error': str(e)}
    
    # Evaluate rule-based
    logger.info("Evaluating rule-based method...")
    try:
        results['rule'] = evaluate_on_dataset(test_data_path, method='rule')
    except Exception as e:
        logger.error(f"Error evaluating rule-based: {str(e)}")
        results['rule'] = {'error': str(e)}
    
    # Evaluate LLM (this might take longer)
    logger.info("Evaluating LLM method...")
    try:
        results['llm'] = evaluate_on_dataset(test_data_path, method='llm')
    except Exception as e:
        logger.error(f"Error evaluating LLM: {str(e)}")
        results['llm'] = {'error': str(e)}
    
    # Generate comparison
    comparison = compare_models(results, output_dir)
    
    # Save confusion matrices
    if output_dir:
        output_dir = Path(output_dir)
        for method, result in results.items():
            if 'error' not in result and 'predictions' in result:
                plot_confusion_matrix(
                    result['true_labels'],
                    result['predictions'],
                    output_path=output_dir / f"confusion_matrix_{method}.png",
                    title=f"Confusion Matrix - {method.upper()}"
                )
                
                # Save classification report
                report_path = output_dir / f"classification_report_{method}.txt"
                generate_classification_report(
                    result['true_labels'],
                    result['predictions'],
                    output_path=report_path
                )
    
    return comparison


if __name__ == "__main__":
    # Example usage
    import sys
    from pathlib import Path
    
    test_data = Path(__file__).parent.parent.parent / "backend" / "data" / "evaluation" / "intent_dataset_test.csv"
    models_dir = Path(__file__).parent.parent.parent / "models"
    
    if not test_data.exists():
        print(f"Test data not found at {test_data}")
        print("Please run synthetic_data.py first to generate test data")
        sys.exit(1)
    
    # Load ML classifier if available
    ml_classifier = None
    if (models_dir / "random_forest_tfidf").exists():
        from backend.ml_models.intent_classifier import IntentClassifier
        from backend.ml_models.feature_extractor import FeatureExtractor
        
        feature_extractor = FeatureExtractor.load(
            models_dir / "random_forest_tfidf" / "tfidf_extractor.pkl"
        )
        ml_classifier = IntentClassifier.load(
            models_dir / "random_forest_tfidf",
            feature_extractor
        )
    
    # Compare all methods
    output_dir = Path(__file__).parent.parent.parent / "evaluation_results"
    comparison = compare_all_methods(test_data, ml_classifier, output_dir)
    
    print("\nComparison Results:")
    print(f"Best Model (Accuracy): {comparison['best_model_accuracy']} ({comparison['best_accuracy']:.4f})")
    print(f"Best Model (F1): {comparison['best_model_f1']} ({comparison['best_f1']:.4f})")


