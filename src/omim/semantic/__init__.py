"""Semantic layer — feature classification and LLM annotation."""

from omim.semantic.classifier import FeatureClassifier
from omim.semantic.llm_annotator import LLMAnnotator
from omim.semantic.models import ClassificationResult, FeatureHypothesis, SemanticAnnotation

__all__ = [
    "FeatureClassifier",
    "LLMAnnotator",
    "ClassificationResult",
    "FeatureHypothesis",
    "SemanticAnnotation",
]
