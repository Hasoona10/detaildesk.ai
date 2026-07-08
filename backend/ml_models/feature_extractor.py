"""
Feature extraction for intent classification.

DEMO SECTION: ML Intent Classification - Feature Extraction
This is where we convert text into numbers that ML models can understand.
I'm using TF-IDF and Bag-of-Words to turn customer messages into feature vectors.
"""
import pickle
from typing import List, Tuple
from pathlib import Path
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer
from sklearn.decomposition import PCA
import joblib
from backend.utils.logger import logger


class FeatureExtractor:
    """
    Extract features from text for intent classification.
    
    This class handles the feature extraction part - basically turning text into numbers.
    I tried a few different methods: TF-IDF (works best), Bag-of-Words, and TF-IDF with PCA.
    """
    
    def __init__(self, method: str = "tfidf", max_features: int = 5000):
        """
        Initialize feature extractor.
        
        I'm using TF-IDF by default because it worked best in my tests.
        It basically weights words by how important they are (not just counting them).
        
        Args:
            method: Feature extraction method ('tfidf', 'bow', 'tfidf_pca')
            max_features: Maximum number of features (keeping it at 5000 to avoid huge vectors)
        """
        self.method = method
        self.max_features = max_features
        self.vectorizer = None
        self.pca = None
        self._initialize_vectorizer()
    
    def _initialize_vectorizer(self):
        """
        Initialize the appropriate vectorizer based on method.
        
        This sets up the sklearn vectorizer - basically the tool that converts text to numbers.
        """
        if self.method == "tfidf":
            self.vectorizer = TfidfVectorizer(
                max_features=self.max_features,
                ngram_range=(1, 2),  # Unigrams and bigrams
                stop_words='english',
                lowercase=True,
                min_df=2,
                max_df=0.95
            )
        elif self.method == "bow":
            self.vectorizer = CountVectorizer(
                max_features=self.max_features,
                ngram_range=(1, 2),
                stop_words='english',
                lowercase=True,
                min_df=2,
                max_df=0.95
            )
        elif self.method == "tfidf_pca":
            self.vectorizer = TfidfVectorizer(
                max_features=self.max_features * 2,
                ngram_range=(1, 2),
                stop_words='english',
                lowercase=True,
                min_df=2,
                max_df=0.95
            )
            self.pca = PCA(n_components=self.max_features)
        else:
            raise ValueError(f"Unknown method: {self.method}")
    
    def fit(self, texts: List[str]):
        """
        Fit the feature extractor on training data.
        
        Args:
            texts: List of training text samples
        """
        logger.info(f"Fitting feature extractor with method: {self.method}")
        self.vectorizer.fit(texts)
        
        if self.pca:
            # Fit PCA on TF-IDF features
            tfidf_features = self.vectorizer.transform(texts)
            self.pca.fit(tfidf_features.toarray())
            logger.info(f"PCA explained variance ratio: {self.pca.explained_variance_ratio_.sum():.3f}")
    
    def transform(self, texts: List[str]) -> np.ndarray:
        """
        Transform texts to feature vectors.
        
        Args:
            texts: List of text samples
            
        Returns:
            Feature matrix (n_samples, n_features)
        """
        if self.vectorizer is None:
            raise ValueError("Feature extractor must be fitted first")
        
        features = self.vectorizer.transform(texts)
        
        if self.pca:
            features = self.pca.transform(features.toarray())
        
        return features if isinstance(features, np.ndarray) else features.toarray()
    
    def fit_transform(self, texts: List[str]) -> np.ndarray:
        """
        Fit and transform in one step.
        
        Args:
            texts: List of training text samples
            
        Returns:
            Feature matrix
        """
        self.fit(texts)
        return self.transform(texts)
    
    def save(self, filepath: Path):
        """Save the feature extractor to disk."""
        filepath.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({
            'vectorizer': self.vectorizer,
            'pca': self.pca,
            'method': self.method,
            'max_features': self.max_features
        }, filepath)
        logger.info(f"Saved feature extractor to {filepath}")
    
    @classmethod
    def load(cls, filepath: Path) -> 'FeatureExtractor':
        """Load a feature extractor from disk."""
        data = joblib.load(filepath)
        extractor = cls(method=data['method'], max_features=data['max_features'])
        extractor.vectorizer = data['vectorizer']
        extractor.pca = data.get('pca')
        logger.info(f"Loaded feature extractor from {filepath}")
        return extractor

