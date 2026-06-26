"""Layer-blind classification — the test of whether OMIM actually *infers*.

The honest worry about OMIM: how much of its "semantic inference" is really just
reading a human's layer-name convention? If you delete every layer name and the
classifier collapses, it's a lookup table, not intelligence. If features still
recover from pure geometry (diameter clustering, the 32mm grid, edge-distance
signatures, shape), the inference is real.

This module makes that test a first-class, runnable capability:

  * ``strip_layers(mgg)`` — return a copy with every layer signal neutralised
    (layer name blanked, inferred_layer_type forced to 'unknown').
  * ``layer_blind_report(mgg)`` — classify both the original (layer-aware) and the
    stripped (geometry-only) graph, and report how much classification survives.

It is also the harness the real-data target plugs into: on a real labelled corpus,
"feature recovery layer-blind" is the metric that earns the word *inference*.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from omim.graph.mgg import ManufacturingGeometryGraph
from omim.semantic.classifier import FeatureClassifier


def strip_layers(mgg: ManufacturingGeometryGraph) -> ManufacturingGeometryGraph:
    """Return a deep copy with all layer-name signal removed.

    Blanks ``layer`` and forces ``inferred_layer_type`` to 'unknown' on every
    geometry node, so the classifier must rely on geometry alone. The outer-
    boundary flag is geometric (not a layer name) and is preserved.
    """
    blind = mgg.copy()
    for _nid, data in blind.geometry_nodes():
        data["layer"] = ""
        data["inferred_layer_type"] = "unknown"
    return blind


@dataclass
class LayerBlindReport:
    """How classification holds up when layer names are removed."""

    total_features: int = 0
    aware_known: int = 0          # non-UNKNOWN under layer-aware classification
    blind_known: int = 0          # non-UNKNOWN under geometry-only classification
    agree: int = 0                # same class with and without layers
    recovered_blind: int = 0      # known under blind (the layer-free signal)
    per_class_blind: dict[str, int] = field(default_factory=dict)

    @property
    def blind_known_ratio(self) -> float:
        return self.blind_known / self.total_features if self.total_features else 0.0

    @property
    def agreement_ratio(self) -> float:
        """Of features the layer-aware path classified, how many the blind path
        reproduced identically — the honest 'how much was really geometry' number."""
        return self.agree / self.aware_known if self.aware_known else 0.0


def layer_blind_report(
    mgg: ManufacturingGeometryGraph,
    classifier: FeatureClassifier | None = None,
) -> LayerBlindReport:
    """Classify *mgg* with and without layer names; quantify what survives."""
    clf = classifier or FeatureClassifier()

    aware = {a.node_id: a.feature_class for a in clf.classify(mgg).feature_annotations}
    blind = {
        a.node_id: a.feature_class
        for a in clf.classify(strip_layers(mgg)).feature_annotations
    }

    rep = LayerBlindReport(total_features=len(aware))
    for nid, aware_cls in aware.items():
        blind_cls = blind.get(nid, "UNKNOWN_FEATURE")
        if aware_cls != "UNKNOWN_FEATURE":
            rep.aware_known += 1
        if blind_cls != "UNKNOWN_FEATURE":
            rep.blind_known += 1
            rep.recovered_blind += 1
            rep.per_class_blind[blind_cls] = rep.per_class_blind.get(blind_cls, 0) + 1
        if aware_cls == blind_cls:
            rep.agree += 1
    return rep
