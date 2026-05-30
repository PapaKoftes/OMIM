"""Semantic layer -- feature classification and LLM annotation."""

from omim.semantic.classifier import FeatureClassifier, SemanticPreconditionError
from omim.semantic.llm_annotator import LLMAnnotator
from omim.semantic.models import (
    AlternativeHypothesis,
    FeatureAnnotation,
    OperationAnnotation,
    SemanticAnnotation,
    SemanticAnnotations,
)

__all__ = [
    "AlternativeHypothesis",
    "FeatureAnnotation",
    "FeatureClassifier",
    "LLMAnnotator",
    "OperationAnnotation",
    "SemanticAnnotation",
    "SemanticAnnotations",
    "SemanticPreconditionError",
]
