# Confidence Model

Version: v0.1.0  
Section: 08_PROVENANCE_AND_CONFIDENCE  

See also: [[08_PROVENANCE_AND_CONFIDENCE/Evidence_Requirements]], [[01_FOUNDATION/Authority_Hierarchy]], [[04_ONTOLOGY/Constraint_Taxonomy]]

---

## Purpose

Defines how confidence values are assigned, bounded, and interpreted in OMIM. Confidence is not a probability — it is an epistemic bound expressing the maximum warranted certainty given the inference method used.

---

## Confidence Semantics

```
confidence = 1.0   Geometric mathematical fact (cannot be wrong given correct input)
confidence = 0.95  Standards-derived rule; edge cases exist but standard is clear
confidence = 0.90  Hardware specification; applies to specific hardware, not all cases
confidence = 0.75  Shop convention; well-established but varies across shops
confidence = 0.70  Material heuristic; empirically derived, material variation applies
confidence = 0.65  Machine heuristic; machine-dependent, lowest credibility
confidence = 0.0   UNKNOWN — feature could not be classified
```

**Confidence is not a posterior probability.** It does not express P(feature_class = X | geometry). It expresses: "given this inference method, what is the maximum warranted certainty for any claim produced this way?"

---

## Confidence Assignment Rules

### Rule 1: InferenceMethod determines confidence ceiling

```python
INFERENCE_METHOD_CONFIDENCE_CEILINGS = {
    InferenceMethod.DETERMINISTIC:  1.0,
    InferenceMethod.RULE_BASED:     0.95,   # depends on rule type
    InferenceMethod.HEURISTIC:      0.75,
    InferenceMethod.ML_INFERENCE:   0.60,   # post-v0; never overrides levels 1–5
}
```

Within each method, the specific rule type may further reduce the ceiling:

```python
RULE_TYPE_CONFIDENCE_CEILINGS = {
    "geometric":          1.0,
    "standards_derived":  0.95,
    "hardware_spec":      0.90,
    "shop_convention":    0.75,
    "material_heuristic": 0.70,
    "machine_heuristic":  0.65,
}

def get_confidence_ceiling(inference_method, rule_type=None):
    method_ceiling = INFERENCE_METHOD_CONFIDENCE_CEILINGS[inference_method]
    if rule_type:
        rule_ceiling = RULE_TYPE_CONFIDENCE_CEILINGS.get(rule_type, method_ceiling)
        return min(method_ceiling, rule_ceiling)
    return method_ceiling
```

### Rule 2: Confidence must not exceed its ceiling

Enforced via Pydantic model_validator:

```python
@model_validator(mode="after")
def confidence_ceiling_enforced(self) -> "ProvenanceRecord":
    ceiling = get_confidence_ceiling(self.inference_method)
    if self.confidence > ceiling:
        raise ValueError(
            f"confidence={self.confidence} exceeds ceiling={ceiling} "
            f"for method={self.inference_method}"
        )
    return self
```

### Rule 3: DETERMINISTIC requires confidence == 1.0

```python
if self.inference_method == InferenceMethod.DETERMINISTIC:
    if self.confidence != 1.0:
        raise ValueError("DETERMINISTIC inference_method requires confidence=1.0")
```

---

## Multiple Hypotheses

When classification confidence is below 0.75, alternative hypotheses MUST be recorded:

```python
class FeatureAnnotation(BaseModel):
    feature_class: str
    confidence: float
    alternative_classes: list[AlternativeHypothesis]

# Example: 8mm circle could be DOWEL_HOLE or BLIND_HOLE
annotation = FeatureAnnotation(
    feature_class="DOWEL_HOLE",
    confidence=0.72,
    alternative_classes=[
        AlternativeHypothesis(feature_class="BLIND_HOLE", confidence=0.55, reason="diameter matches DIN7 but context ambiguous"),
        AlternativeHypothesis(feature_class="THROUGH_HOLE", confidence=0.40, reason="no depth information available"),
    ]
)
```

When confidence >= 0.75, `alternative_classes` may be empty (classification is confident enough for single-hypothesis output). Below 0.75 it is **mandatory** to store at least two ranked competing hypotheses.

Multiple hypotheses are stored in `FeatureNode.hypotheses` as a ranked list:

```json
{
  "feature_class": "SHELF_PIN_HOLE",
  "confidence": 0.72,
  "hypotheses": [
    {"feature_class": "SHELF_PIN_HOLE", "confidence": 0.72},
    {"feature_class": "THROUGH_HOLE",   "confidence": 0.18},
    {"feature_class": "DOWEL_HOLE",     "confidence": 0.10}
  ]
}
```

The primary `feature_class` is always the highest-confidence hypothesis.

---

## Confidence Combination Rules

When evidence comes from multiple sources, confidence is combined as follows:

```python
def combine_confidence(sources: list[float]) -> float:
    """
    Combine confidence from independent evidence sources.
    Uses conservative (minimum) combination, not probabilistic multiplication.
    
    Rationale: If any evidence source is weak, the combined claim is weak.
    We do not gain false confidence from multiple weak sources.
    """
    return min(sources)
```

Rationale for minimum (not product): OMIM is conservative by design. Two `0.75` confidence pieces of evidence do not produce `0.9375` confidence — they produce `0.75`. Manufacturing decisions based on OMIM output should not over-trust compounded inference.

---

## Confidence Thresholds for Decision Making

These thresholds govern how OMIM itself applies confidence scores to semantic annotations:

```python
CONFIDENCE_THRESHOLDS = {
    "accept":          0.60,   # Feature class accepted as primary label
    "flag_for_review": 0.30,   # Accept tentative label but mark for human review
    "reject":          0.00,   # Below 0.30: relabel as UNKNOWN_FEATURE
}

def apply_confidence_threshold(annotation: SemanticAnnotation) -> SemanticAnnotation:
    if annotation.confidence >= CONFIDENCE_THRESHOLDS["accept"]:
        annotation.review_status = ReviewStatus.AUTO_VALIDATED
    elif annotation.confidence >= CONFIDENCE_THRESHOLDS["flag_for_review"]:
        annotation.feature_class = annotation.feature_class  # keep tentative label
        annotation.review_status = ReviewStatus.FLAGGED
    else:
        annotation.feature_class = "UNKNOWN_FEATURE"
        annotation.review_status = ReviewStatus.FLAGGED
    return annotation
```

**Threshold semantics**:
- `≥ 0.60`: Auto-validated. Label accepted for dataset inclusion.
- `0.30 – 0.59`: Tentative label kept but `review_status = FLAGGED`. Included in dataset with flag.
- `< 0.30`: Overridden to `UNKNOWN_FEATURE` regardless of top hypothesis. Always flagged.
- Any output with `confidence < 0.30` must have `review_status = "flagged"` (enforced by Pydantic validator).

**OMIM does not make downstream manufacturing decisions** — it reports confidence and thresholds; the consuming system applies its own policy for what confidence level is acceptable for production use.

---

## Heuristic Confidence Computation

For hole classification heuristics, confidence is computed from the strength of the geometry match:

```python
def compute_hole_classification_confidence(
    diameter_mm: float,
    expected_diameter_mm: float,
    diameter_tolerance_mm: float,
    context_match: bool,
    pattern_match: bool
) -> float:
    """
    Heuristic confidence for hole feature classification.

    Base confidence from diameter match:
      distance = abs(diameter_mm - expected_diameter_mm)
      base = max(0, 1 - distance / diameter_tolerance_mm)

    Context bonus:
      +0.05 if geometric context matches expected pattern
      +0.08 if part of a confirmed group pattern (e.g., shelf pin row)

    Returns: min(1.0, base + context_bonus + pattern_bonus)
    """
    distance = abs(diameter_mm - expected_diameter_mm)
    base = max(0.0, 1.0 - distance / diameter_tolerance_mm)
    context_bonus = 0.05 if context_match else 0.0
    pattern_bonus = 0.08 if pattern_match else 0.0
    return min(1.0, base + context_bonus + pattern_bonus)
```

This function is called by hole classifiers in the Semantic Layer. The result is capped at the applicable `confidence_ceiling` for the rule type.

---

## Confidence in ValidationReport

Validation results use confidence differently — they express how certain the rule is, not how certain the result is:

```python
# rule confidence = how reliable is this rule as a constraint?
rule_result = RuleResult(
    rule_id="MFG-001",
    passed=False,
    confidence=0.75,   # shop_convention ceiling — the 8mm threshold itself has 0.75 credibility
    # The measurement is deterministic; the threshold origin is shop convention
)
```

A failed rule with `confidence=0.75` means: "The geometry definitely violates the 8mm clearance threshold, but that threshold is shop convention with 0.75 credibility, not an absolute standard."
