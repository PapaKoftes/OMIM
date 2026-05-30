"""Phase 4 — the Leonardo go/no-go gate, made executable.

Question: does a LEARNED model beat the DETERMINISTIC rule baseline on data the
rules struggle with (real-world mess: jittered diameters, renamed/dropped layers)?

If the GNN does NOT beat the rule "skyline" on a held-out noisy set, then a bigger
model on HPC will not either — ship the rules. If it does, learning earns its place.

This is intentionally honest: both models are evaluated on the SAME held-out test
set, against ground-truth labels from the generation spec. A trivial majority-class
"floor" is included so a mediocre model can't look good in a vacuum.

Run:  python experiments/phase4_model_vs_rules.py

MEASURED RESULT (multi-seed: 3 independent trials, seed_bases 100/200/300):
    CLEAN test:  rules 0.700 ± 0.040   vs   GNN 0.842 ± 0.041
    NOISY test:  rules 0.499 ± 0.053   vs   GNN 0.890 ± 0.048
    GNN lift on NOISY: +0.390 ± 0.056  (GNN beat rules by >0.05 in 3/3 trials)
Interpretation: on clean geometry the rules are already decent and the GNN only
edges them. On REAL-WORLD-LIKE MESS (jittered diameters, renamed/dropped layers,
duplicate entities) the brittle exact-match / layer-keyword rules collapse while a
GNN trained on messy data stays strong — and this holds across every seed, so the
lift is robust, not a lucky run. That is the legitimate case for learning.
CAVEATS: (1) this is SYNTHETIC noise; the real go/no-go is repeating this on actual
third-party DXFs. (2) The noise is aggressive enough that some perturbed panels trip
MFG-002 (spacing) and are skipped by the gatekeeper (logged E-005) — both models are
still scored on the SAME surviving panels, so the comparison is fair, but the noisy
sets are smaller than requested. If the GNN still wins on real DXFs, HPC scale-up is
justified; if not, ship the rules.
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


NOISE = dict(diameter_noise_sigma_mm=0.6, layer_noise=True, duplicate_entity_prob=0.05)


def _gnn_eval(pred, sample_dirs):
    import json
    import os
    P, B = DXFParser(), MGGBuilder()
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


def run_once(seed_base: int) -> dict:
    """One independent trial: distinct seeds for train/clean-test/noisy-test."""
    import tempfile as tf

    train_root, _ = _gen(seed_base + 1, 250, NOISE)
    _, test_clean = _gen(seed_base + 2, 80, {})
    _, test_noisy = _gen(seed_base + 3, 80, NOISE)

    yt_c, yp_c = _rule_baseline_eval(test_clean)
    yt_n, yp_n = _rule_baseline_eval(test_noisy)
    out = {
        "rule_clean": _macro_f1(yt_c, yp_c),
        "rule_noisy": _macro_f1(yt_n, yp_n),
        "floor_noisy": _macro_f1(yt_n, _floor_eval(yt_n)),
        "gnn_clean": None,
        "gnn_noisy": None,
    }
    if not ML_AVAILABLE:
        return out

    from torch_geometric.loader import DataLoader

    from omim.ml.predictor import GNNPredictor
    from omim.ml.trainer import CanonicalSampleDataset, GNNTrainer

    ds = CanonicalSampleDataset(train_root)
    data = [d for d in ds.all() if d is not None]
    split = int(len(data) * 0.85)
    tr = DataLoader(data[:split], batch_size=16, shuffle=True)
    va = DataLoader(data[split:], batch_size=16)
    ck = tf.mkdtemp(prefix="p4ck_")
    GNNTrainer(optimizer_lr=1e-3, max_epochs=60, early_stopping_patience=12,
               class_weights=ds.compute_class_weights()).train(tr, va, checkpoint_dir=ck)
    pred = GNNPredictor(feature_checkpoint=f"{ck}/feature_gnn_best.pt")
    out["gnn_clean"] = _macro_f1(*_gnn_eval(pred, test_clean))
    out["gnn_noisy"] = _macro_f1(*_gnn_eval(pred, test_noisy))
    return out


def _mean_std(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return None, None
    return float(np.mean(xs)), float(np.std(xs))


def main(seed_bases=(100, 200, 300)):
    rows = []
    for sb in seed_bases:
        print(f"--- trial seed_base={sb} ---")
        r = run_once(sb)
        rows.append(r)
        rc, rn, gc, gn = r["rule_clean"], r["rule_noisy"], r["gnn_clean"], r["gnn_noisy"]
        print(f"  rules  clean={rc:.3f} noisy={rn:.3f} | "
              f"gnn clean={gc if gc is None else round(gc,3)} "
              f"noisy={gn if gn is None else round(gn,3)} | floor={r['floor_noisy']:.3f}")

    print("\n================= AGGREGATE over", len(rows), "trials =================")
    rc_m, rc_s = _mean_std([r["rule_clean"] for r in rows])
    rn_m, rn_s = _mean_std([r["rule_noisy"] for r in rows])
    print(f"rules  CLEAN: {rc_m:.3f} ± {rc_s:.3f}")
    print(f"rules  NOISY: {rn_m:.3f} ± {rn_s:.3f}")

    if not ML_AVAILABLE:
        print("\n[ML unavailable: torch_geometric not installed — GNN arm skipped]")
        return

    gc_m, gc_s = _mean_std([r["gnn_clean"] for r in rows])
    gn_m, gn_s = _mean_std([r["gnn_noisy"] for r in rows])
    lifts = [r["gnn_noisy"] - r["rule_noisy"] for r in rows if r["gnn_noisy"] is not None]
    lift_m, lift_s = _mean_std(lifts)
    wins = sum(1 for x in lifts if x > 0.05)
    print(f"GNN    CLEAN: {gc_m:.3f} ± {gc_s:.3f}")
    print(f"GNN    NOISY: {gn_m:.3f} ± {gn_s:.3f}")
    print(f"GNN lift on NOISY: {lift_m:+.3f} ± {lift_s:.3f}  "
          f"(GNN beat rules by >0.05 in {wins}/{len(lifts)} trials)")

    print("\n=== VERDICT (multi-seed) ===")
    if lift_m > 0.05 and wins == len(lifts):
        print("  -> GNN ROBUSTLY beats rules on messy data across every seed. Learning")
        print("     earns its place. GREEN-ish for HPC — but still SYNTHETIC noise;")
        print("     the real gate is repeating this on actual third-party DXFs.")
    elif lift_m > 0.0:
        print("  -> GNN ahead on average but not every seed. Promising, not decisive;")
        print("     close generator gaps / get real data before HPC.")
    else:
        print("  -> GNN does NOT reliably beat rules. SHIP THE RULES. Do not book Leonardo.")


if __name__ == "__main__":
    main()
