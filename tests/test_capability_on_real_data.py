"""The capability test — the ONE test that is allowed to be red (by absence).

Every other test verifies internal consistency: "the code does what the code
says." This one verifies EXTERNAL VALIDITY: "OMIM's output is correct about the
real world." It can only run against a real, human-labelled panel corpus that is
independent of OMIM's own rules — which does not exist in-repo by design (real
production DXFs are private and cannot be committed; see docs/STRATEGY.md).

So this test SKIPS until a real labelled corpus is provided out-of-tree, and that
skip is the project's honest status line: until it runs, the identification claims
are unproven on real data, full stop. When a corpus is dropped at the path below,
it activates and measures the thing that actually matters.

To activate: set OMIM_REAL_CORPUS to a directory containing
``<id>/mgg.json`` + ``<id>/labels.json`` samples whose labels are HUMAN gold
(reviewed via 'omim apply-review'), then run pytest. The test asserts OMIM's
layer-blind feature inference agrees with the human labels above a real bar.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

_CORPUS_ENV = "OMIM_REAL_CORPUS"
_corpus = os.environ.get(_CORPUS_ENV)

pytestmark = pytest.mark.skipif(
    not (_corpus and Path(_corpus).is_dir()),
    reason=(
        f"No real labelled corpus. Set {_CORPUS_ENV}=<dir of reviewed samples> to "
        "activate. Until this runs, identification is UNPROVEN on real data."
    ),
)


def _gold_pairs(corpus_dir: Path):
    """Yield (mgg_path, human_gold_label_by_node) from a reviewed corpus."""
    from omim.labeling import LabelSet, ReviewStatus

    for lf in sorted(corpus_dir.glob("*/labels.json")):
        ls = LabelSet.model_validate_json(lf.read_text(encoding="utf-8"))
        gold = {
            lab.target_id: lab.final_value
            for lab in ls.labels
            if lab.review_status in (ReviewStatus.HUMAN_CONFIRMED,
                                     ReviewStatus.HUMAN_CORRECTED)
            and lab.kind.value == "feature"
        }
        if gold:
            yield lf.parent / "mgg.json", gold


def test_feature_inference_agrees_with_humans_on_real_data():
    """OMIM's geometry-only feature inference must agree with human gold labels
    on real panels above a meaningful bar. THIS is the earned-intelligence test."""
    from omim.graph.mgg import ManufacturingGeometryGraph
    from omim.semantic.classifier import FeatureClassifier
    from omim.semantic.layer_blind import strip_layers

    corpus = Path(_corpus)
    clf = FeatureClassifier()
    total = correct = 0
    for mgg_path, gold in _gold_pairs(corpus):
        mgg = ManufacturingGeometryGraph.from_dict(
            __import__("json").loads(mgg_path.read_text(encoding="utf-8"))
        )
        pred = {
            a.node_id: a.feature_class
            for a in clf.classify(strip_layers(mgg)).feature_annotations
        }
        for node_id, human in gold.items():
            total += 1
            if pred.get(node_id) == human:
                correct += 1

    assert total > 0, "corpus had no human-gold feature labels"
    accuracy = correct / total
    # The bar that earns 'semantic inference' on real data. Tighten as the corpus
    # grows; start honest at 0.70.
    assert accuracy >= 0.70, f"layer-blind real-data feature accuracy {accuracy:.2%}"
