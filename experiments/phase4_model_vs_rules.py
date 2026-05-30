"""Phase 4 — the Leonardo go/no-go gate, made executable.

Question: does a LEARNED model beat the DETERMINISTIC rule baseline on data the
rules struggle with (real-world mess: jittered diameters, renamed/dropped layers)?

If the GNN does NOT beat the rule "skyline" on a held-out noisy set, then a bigger
model on HPC will not either — ship the rules. If it does, learning earns its place.

This is intentionally honest: both models are evaluated on the SAME held-out test
set, against ground-truth labels from the generation spec. A trivial majority-class
"floor" is included so a mediocre model can't look good in a vacuum.

Run:  python experiments/phase4_model_vs_rules.py

MEASURED RESULT (seeds 101/202/303, single run — treat as indicative, not final):
    CLEAN test:  rules 0.671  vs  GNN 0.764
    NOISY test:  rules 0.479  vs  GNN 0.864   (GNN lift +0.385)
Interpretation: on clean geometry the rules are already decent and the GNN only
edges them. On REAL-WORLD-LIKE MESS (jittered diameters, renamed/dropped layers,
duplicate entities) the brittle exact-match rules collapse while a GNN trained on
messy data stays strong. That is the legitimate case for learning. CAVEAT: this is
SYNTHETIC noise. The real go/no-go is repeating this on actual third-party DXFs —
if the GNN still wins there, HPC scale-up is justified; if not, ship the rules.
"""

from __future__ import annotations

import tempfile
from collections import Counter

import numpy as np

from omim.graph.builder import MGGBuilder
from omim.ml.availability import ML_AVAILABLE
from omim.ml.features import extract_node_features
from omim.ml.results import FEATURE_CLASSES
from omim.ml.trainer import _node_labels_from_sample
from omim.parser.dxf_parser import DXFParser
from omim.semantic.classifier import FeatureClassifier
from omim.synthetic.generator import PanelGenerator
from omim.synthetic.models import PanelGeneratorConfig

_UNK = FEATURE_CLASSES.index("UNKNOWN_FEATURE")
_CLASS_TO_IDX = {c: i for i, c in enumerate(FEATURE_CLASSES)}


def _macro_f1(y_true: list[int], y_pred: list[int]) -> float:
    """Macro-F1 over classes actually present in y_true (present-class macro-F1)."""
    classes = sorted(set(y_true))
    f1s = []
    for c in classes:
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == c and p == c)
        fp = sum(1 for t, p in zip(y_true, y_pred) if t != c and p == c)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t == c and p != c)
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        f1s.append(2 * prec * rec / (prec + rec) if (prec + rec) else 0.0)
    return float(np.mean(f1s)) if f1s else 0.0


def _gen(seed, n, noise):
    """Generate a dataset; return (samples_root_dir, list_of_sample_dirs)."""
    import glob
    import os
    out = tempfile.mkdtemp(prefix=f"p4_{seed}_")
    cfg = PanelGeneratorConfig(
        random_seed=seed, num_samples=n, invalid_sample_ratio=0.0,  # valid only -> classify-able
        **noise,
    )
    PanelGenerator(cfg).generate_dataset(out)
    root = os.path.join(out, "samples")
    dirs = sorted(os.path.dirname(p) for p in glob.glob(os.path.join(root, "*", "labels.json")))
    return root, dirs


def _rule_baseline_eval(sample_dirs):
    """Deterministic classifier, per node, joined to ground-truth by node order."""
    P, B, C = DXFParser(), MGGBuilder(), FeatureClassifier()
    yt, yp = [], []
    import json
    import os
    for sd in sample_dirs:
        labels = json.loads(open(os.path.join(sd, "labels.json")).read())
        mgg = B.build(P.parse(os.path.join(sd, "geometry.dxf")).geometry)
        node_ids, _ = extract_node_features(mgg)
        y_true = _node_labels_from_sample(node_ids, labels, mgg)
        ann = {a.node_id: a.feature_class for a in C.classify(mgg).feature_annotations}
        for i, nid in enumerate(node_ids):
            yt.append(int(y_true[i]))
            yp.append(_CLASS_TO_IDX.get(ann.get(nid, "UNKNOWN_FEATURE"), _UNK))
    return yt, yp


def _floor_eval(yt):
    """Trivial majority-class predictor."""
    maj = Counter(yt).most_common(1)[0][0]
    return [maj] * len(yt)


def main():
    NOISE = dict(diameter_noise_sigma_mm=0.6, layer_noise=True, duplicate_entity_prob=0.05)
    print("Generating clean train, noisy train, clean test, noisy test ...")
    train_root, train_noisy = _gen(101, 250, NOISE)
    _, test_clean = _gen(202, 80, {})
    _, test_noisy = _gen(303, 80, NOISE)

    print("\n=== DETERMINISTIC RULE BASELINE (the skyline to beat) ===")
    yt_c, yp_c = _rule_baseline_eval(test_clean)
    yt_n, yp_n = _rule_baseline_eval(test_noisy)
    rule_clean = _macro_f1(yt_c, yp_c)
    rule_noisy = _macro_f1(yt_n, yp_n)
    print(f"rules on CLEAN test : macro-F1 = {rule_clean:.3f}  (n={len(yt_c)} nodes)")
    print(f"rules on NOISY test : macro-F1 = {rule_noisy:.3f}  (n={len(yt_n)} nodes)")
    print(f"trivial floor (noisy): macro-F1 = {_macro_f1(yt_n, _floor_eval(yt_n)):.3f}")

    if not ML_AVAILABLE:
        print("\n[ML unavailable: torch_geometric not installed — GNN arm skipped]")
        return

    print("\n=== GNN (trained on NOISY train) ===")
    from torch_geometric.loader import DataLoader

    from omim.ml.predictor import GNNPredictor
    from omim.ml.trainer import CanonicalSampleDataset, GNNTrainer

    ds = CanonicalSampleDataset(train_root)
    data = [d for d in ds.all() if d is not None]
    split = int(len(data) * 0.85)
    tr = DataLoader(data[:split], batch_size=16, shuffle=True)
    va = DataLoader(data[split:], batch_size=16)
    import tempfile as tf
    ck = tf.mkdtemp(prefix="p4ck_")
    GNNTrainer(optimizer_lr=1e-3, max_epochs=60, early_stopping_patience=12,
               class_weights=ds.compute_class_weights()).train(tr, va, checkpoint_dir=ck)

    pred = GNNPredictor(feature_checkpoint=f"{ck}/feature_gnn_best.pt")
    P, B = DXFParser(), MGGBuilder()
    import json
    import os
    def gnn_eval(sample_dirs):
        yt, yp = [], []
        for sd in sample_dirs:
            labels = json.loads(open(os.path.join(sd, "labels.json")).read())
            mgg = B.build(P.parse(os.path.join(sd, "geometry.dxf")).geometry)
            node_ids, _ = extract_node_features(mgg)
            y_true = _node_labels_from_sample(node_ids, labels, mgg)
            pr = {p.node_id: p.feature_class for p in pred.predict_features(mgg).node_predictions}
            for i, nid in enumerate(node_ids):
                yt.append(int(y_true[i]))
                yp.append(_CLASS_TO_IDX.get(pr.get(nid, "UNKNOWN_FEATURE"), _UNK))
        return yt, yp

    gyt_c, gyp_c = gnn_eval(test_clean)
    gyt_n, gyp_n = gnn_eval(test_noisy)
    gnn_clean = _macro_f1(gyt_c, gyp_c)
    gnn_noisy = _macro_f1(gyt_n, gyp_n)
    print(f"GNN on CLEAN test  : macro-F1 = {gnn_clean:.3f}")
    print(f"GNN on NOISY test  : macro-F1 = {gnn_noisy:.3f}")

    print("\n=== VERDICT ===")
    print(f"  CLEAN:  rules {rule_clean:.3f}  vs  GNN {gnn_clean:.3f}")
    print(f"  NOISY:  rules {rule_noisy:.3f}  vs  GNN {gnn_noisy:.3f}")
    lift = gnn_noisy - rule_noisy
    print(f"  GNN lift over rules on NOISY data: {lift:+.3f}")
    if lift > 0.05:
        print("  -> GNN MEANINGFULLY beats rules on messy data. Learning earns")
        print("     its place. GREEN-ish for HPC (still SYNTHETIC noise — verify on real DXFs).")
    elif lift > 0.0:
        print("  -> GNN marginally ahead. Not yet worth HPC; revisit with real data.")
    else:
        print("  -> GNN does NOT beat rules. SHIP THE RULES. Do not book Leonardo.")


if __name__ == "__main__":
    main()
