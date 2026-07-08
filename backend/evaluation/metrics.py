"""
Evaluation metrics for intent classification.
"""
from typing import List, Dict, Tuple
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    classification_report, confusion_matrix, ConfusionMatrixDisplay
)
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from backend.intents import Intent
from backend.utils.logger import logger


def calculate_metrics(
    y_true: List[str],
    y_pred: List[str],
    labels: List[str] = None
) -> Dict:
    """
    Calculate classification metrics.
    
    Args:
        y_true: True labels
        y_pred: Predicted labels
        labels: List of all label names (for ordering)
        
    Returns:
        Dictionary with metrics
    """
    if labels is None:
        labels = sorted(set(y_true + y_pred))
    
    accuracy = accuracy_score(y_true, y_pred)
    precision = precision_score(y_true, y_pred, labels=labels, average='weighted', zero_division=0)
    recall = recall_score(y_true, y_pred, labels=labels, average='weighted', zero_division=0)
    f1 = f1_score(y_true, y_pred, labels=labels, average='weighted', zero_division=0)
    
    # Per-class metrics
    per_class_precision = precision_score(y_true, y_pred, labels=labels, average=None, zero_division=0)
    per_class_recall = recall_score(y_true, y_pred, labels=labels, average=None, zero_division=0)
    per_class_f1 = f1_score(y_true, y_pred, labels=labels, average=None, zero_division=0)
    
    metrics = {
        'accuracy': float(accuracy),
        'precision_weighted': float(precision),
        'recall_weighted': float(recall),
        'f1_weighted': float(f1),
        'per_class': {
            label: {
                'precision': float(p),
                'recall': float(r),
                'f1': float(f)
            }
            for label, p, r, f in zip(labels, per_class_precision, per_class_recall, per_class_f1)
        }
    }
    
    return metrics


def generate_classification_report(
    y_true: List[str],
    y_pred: List[str],
    labels: List[str] = None,
    output_path: Path = None
) -> str:
    """
    Generate detailed classification report.
    
    Args:
        y_true: True labels
        y_pred: Predicted labels
        labels: List of all label names
        output_path: Optional path to save report
        
    Returns:
        Classification report string
    """
    if labels is None:
        labels = sorted(set(y_true + y_pred))
    
    report = classification_report(y_true, y_pred, labels=labels, zero_division=0)
    
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            f.write(report)
        logger.info(f"Saved classification report to {output_path}")
    
    return report


def plot_confusion_matrix(
    y_true: List[str],
    y_pred: List[str],
    labels: List[str] = None,
    output_path: Path = None,
    title: str = "Confusion Matrix"
):
    """
    Plot and save confusion matrix.
    
    Args:
        y_true: True labels
        y_pred: Predicted labels
        labels: List of all label names (ordered)
        output_path: Optional path to save figure
        title: Plot title
    """
    if labels is None:
        labels = sorted(set(y_true + y_pred))
    
    cm = confusion_matrix(y_true, y_pred, labels=labels)
    
    # Create figure
    fig, ax = plt.subplots(figsize=(10, 8))
    disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=labels)
    disp.plot(ax=ax, cmap='Blues', values_format='d')
    ax.set_title(title, fontsize=14, fontweight='bold')
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        logger.info(f"Saved confusion matrix to {output_path}")
    else:
        plt.show()
    
    plt.close()


def compare_models(
    results: Dict[str, Dict],
    output_dir: Path = None
) -> Dict:
    """
    Compare multiple model results.
    
    Args:
        results: Dictionary mapping model names to their metrics
        output_dir: Optional directory to save comparison report
        
    Returns:
        Comparison summary dictionary
    """
    comparison = {
        'models': list(results.keys()),
        'best_accuracy': None,
        'best_f1': None,
        'best_model_accuracy': None,
        'best_model_f1': None,
        'all_metrics': results
    }
    
    # Find best model by accuracy
    best_acc = -1
    best_f1 = -1
    best_model_acc = None
    best_model_f1 = None
    
    for model_name, metrics in results.items():
        if 'error' in metrics:
            continue
        
        acc = metrics.get('accuracy', 0)
        f1 = metrics.get('f1_weighted', 0)
        
        if acc > best_acc:
            best_acc = acc
            best_model_acc = model_name
        
        if f1 > best_f1:
            best_f1 = f1
            best_model_f1 = model_name
    
    comparison['best_accuracy'] = best_acc
    comparison['best_f1'] = best_f1
    comparison['best_model_accuracy'] = best_model_acc
    comparison['best_model_f1'] = best_model_f1
    
    # Generate comparison report
    if output_dir:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Save comparison as JSON
        import json
        comparison_path = output_dir / "model_comparison.json"
        with open(comparison_path, 'w') as f:
            json.dump(comparison, f, indent=2)
        
        # Save text report
        report_path = output_dir / "comparison_report.txt"
        with open(report_path, 'w') as f:
            f.write("Model Comparison Report\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"Best Model (Accuracy): {best_model_acc} ({best_acc:.4f})\n")
            f.write(f"Best Model (F1): {best_model_f1} ({best_f1:.4f})\n\n")
            f.write("\nAll Models:\n")
            f.write("-" * 50 + "\n")
            for model_name, metrics in results.items():
                if 'error' in metrics:
                    f.write(f"{model_name}: ERROR - {metrics['error']}\n")
                else:
                    f.write(f"{model_name}:\n")
                    f.write(f"  Accuracy: {metrics.get('accuracy', 0):.4f}\n")
                    f.write(f"  F1 (weighted): {metrics.get('f1_weighted', 0):.4f}\n")
                    f.write(f"  Precision (weighted): {metrics.get('precision_weighted', 0):.4f}\n")
                    f.write(f"  Recall (weighted): {metrics.get('recall_weighted', 0):.4f}\n\n")
        
        logger.info(f"Saved comparison report to {output_dir}")
    
    return comparison


