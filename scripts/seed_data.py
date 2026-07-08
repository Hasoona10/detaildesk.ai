#!/usr/bin/env python3
"""
Comprehensive data seeding script for the AI Detailing Receptionist.

Seeds three layers:
- RAG knowledge (business_data.json -> ChromaDB)
- Intent classifier examples (intent_data.json sanity check)
- Evaluation queries (eval_queries.json sanity check)
"""
import sys
from pathlib import Path
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.rag import seed_vectordb, load_business_data, make_chunks
from backend.utils.logger import logger
from dotenv import load_dotenv

load_dotenv()


def seed_rag_knowledge(business_data_path: Path, business_id: str = "oc_elite_detailing", clear_existing: bool = False):
    """
    Layer 1: Seed RAG knowledge (business_data → vector DB)
    
    Args:
        business_data_path: Path to business_data.json
        business_id: Business identifier
        clear_existing: Whether to clear existing data
    """
    logger.info("\n" + "="*60)
    logger.info("Layer 1: Seeding RAG Knowledge")
    logger.info("="*60)
    
    try:
        if not business_data_path.exists():
            logger.error(f"Business data file not found: {business_data_path}")
            return False
        
        rag = seed_vectordb(business_data_path, business_id, clear_existing)
        
        logger.info("✓ RAG knowledge seeded successfully")
        return True
        
    except Exception as e:
        logger.error(f"✗ Error seeding RAG knowledge: {str(e)}")
        return False


def verify_intent_data(intent_data_path: Path):
    """
    Layer 2: Verify intent classifier data exists.
    
    Args:
        intent_data_path: Path to intent_data.json
    """
    logger.info("\n" + "="*60)
    logger.info("Layer 2: Intent Classifier Data")
    logger.info("="*60)
    
    try:
        if not intent_data_path.exists():
            logger.warning(f"Intent data file not found: {intent_data_path}")
            logger.info("  → Intent data will be generated during model training")
            return False
        
        with open(intent_data_path, 'r', encoding='utf-8') as f:
            intent_data = json.load(f)
        
        logger.info(f"✓ Found {len(intent_data)} labeled intent examples")
        
        # Count by intent
        intent_counts = {}
        for item in intent_data:
            intent = item.get('intent', 'unknown')
            intent_counts[intent] = intent_counts.get(intent, 0) + 1
        
        logger.info("  Intent distribution:")
        for intent, count in sorted(intent_counts.items()):
            logger.info(f"    - {intent}: {count} examples")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Error verifying intent data: {str(e)}")
        return False


def verify_eval_queries(eval_queries_path: Path):
    """
    Layer 3: Verify evaluation queries exist.
    
    Args:
        eval_queries_path: Path to eval_queries.json
    """
    logger.info("\n" + "="*60)
    logger.info("Layer 3: Evaluation/Test Queries")
    logger.info("="*60)
    
    try:
        if not eval_queries_path.exists():
            logger.warning(f"Evaluation queries file not found: {eval_queries_path}")
            return False
        
        with open(eval_queries_path, 'r', encoding='utf-8') as f:
            queries = json.load(f)
        
        logger.info(f"✓ Found {len(queries)} evaluation queries")
        logger.info("  Sample queries:")
        for i, query in enumerate(queries[:5], 1):
            logger.info(f"    {i}. {query}")
        if len(queries) > 5:
            logger.info(f"    ... and {len(queries) - 5} more")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Error verifying eval queries: {str(e)}")
        return False


def main():
    """Main seeding pipeline."""
    logger.info("="*60)
    logger.info("AI Detailing Receptionist - Data Seeding Pipeline")
    logger.info("="*60)
    
    # Setup paths
    project_root = Path(__file__).parent.parent
    backend_dir = project_root / "backend"
    data_dir = backend_dir / "data"
    business_data_path = backend_dir / "business_data.json"
    intent_data_path = data_dir / "intent_data.json"
    eval_queries_path = data_dir / "eval_queries.json"
    
    import os
    business_id = os.getenv("DEFAULT_BUSINESS_ID", "oc_elite_detailing")
    
    # Create data directory if it doesn't exist
    data_dir.mkdir(parents=True, exist_ok=True)
    
    # Check if user wants to clear existing data
    clear_existing = False
    if len(sys.argv) > 1 and sys.argv[1] == "--clear":
        clear_existing = True
        logger.info("Will clear existing vector database data")
    
    results = {
        'rag_knowledge': False,
        'intent_data': False,
        'eval_queries': False
    }
    
    # Layer 1: Seed RAG knowledge
    results['rag_knowledge'] = seed_rag_knowledge(
        business_data_path,
        business_id=business_id,
        clear_existing=clear_existing
    )
    
    # Layer 2: Verify intent data
    results['intent_data'] = verify_intent_data(intent_data_path)
    
    # Layer 3: Verify eval queries
    results['eval_queries'] = verify_eval_queries(eval_queries_path)
    
    # Summary
    logger.info("\n" + "="*60)
    logger.info("Seeding Summary")
    logger.info("="*60)
    logger.info(f"RAG Knowledge: {'✓' if results['rag_knowledge'] else '✗'}")
    logger.info(f"Intent Data: {'✓' if results['intent_data'] else '✗'}")
    logger.info(f"Eval Queries: {'✓' if results['eval_queries'] else '✗'}")
    
    if all(results.values()):
        logger.info("\n✓ All data layers seeded successfully!")
    else:
        logger.info("\n⚠ Some data layers need attention (see above)")
    
    logger.info("\nNext steps:")
    logger.info("1. Train ML model: python scripts/train_model.py")
    logger.info("2. Start server: python run.py")
    logger.info("3. Test queries: Use eval_queries.json for evaluation")


if __name__ == "__main__":
    main()


