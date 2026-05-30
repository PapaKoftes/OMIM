"""Pure-python / numpy metric implementations for the OMIM benchmarks.

No sklearn dependency. Every metric here is implemented directly so that
results are reproducible from numpy alone (numpy is already a hard dependency).

Conventions
-----------
* Multi-class metrics operate on parallel lists ``y_true`` / ``y_pred`` of
  string class labels.
* ``zero_division=0`` semantics are used everywhere (a class with no support
  or no predictions contributes F1 = 0.0, never an error / NaN), matching the
  policy in docs/09_BENCHMARKS/Evaluation_Metrics.md.
* Multi-label metrics operate on lists of *sets* (or iterables) of labels, with
  the full label space supplied explicitly so absent labels are scored.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

import numpy as np

__all__ = [
    "confusion_matrix",
    "precision_recall_f1_per_class",
    "macro_f1",
    "macro_f1_present",
    "micro_f1",
    "accuracy",
    "binary_rates",
    "hamming_loss",
    "subset_accuracy",
    "multilabel_macro_f1",
    "iou",
    "roc_auc",
]


# ---------------------------------------------------------------------------
# Multi-class metrics
# ---------------------------------------------------------------------------


def _label_space(
    y_true: Sequence[Any],
    y_pred: Sequence[Any],
    labels: Sequence[Any] | None,
) -> list[Any]:
    if labels is not None:
        return list(labels)
    seen: dict[Any, None] = {}
    for v in list(y_true) + list(y_pred):
        seen.setdefault(v, None)
    return sorted(seen.keys(), key=lambda x: str(x))


def confusion_matrix(
    y_true: Sequence[Any],
    y_pred: Sequence[Any],
    labels: Sequence[Any] | None = None,
) -> tuple[list[Any], np.ndarray]:
    """Return ``(labels, matrix)`` where ``matrix[i, j]`` counts samples whose
    true class is ``labels[i]`` and predicted class is ``labels[j]``."""
    label_list = _label_space(y_true, y_pred, labels)
    index = {lab: i for i, lab in enumerate(label_list)}
    n = len(label_list)
    matrix = np.zeros((n, n), dtype=np.int64)
    for t, p in zip(y_true, y_pred):
        if t in index and p in index:
            matrix[index[t], index[p]] += 1
    return label_list, matrix


def precision_recall_f1_per_class(
    y_true: Sequence[Any],
    y_pred: Sequence[Any],
    labels: Sequence[Any] | None = None,
) -> dict[Any, dict[str, float]]:
    """Per-class precision / recall / F1 / support (zero_division=0)."""
    label_list, cm = confusion_matrix(y_true, y_pred, labels)
    out: dict[Any, dict[str, float]] = {}
    tp_all = np.diag(cm)
    pred_sum = cm.sum(axis=0)  # column = predicted
    true_sum = cm.sum(axis=1)  # row = actual
    for i, lab in enumerate(label_list):
        tp = int(tp_all[i])
        fp = int(pred_sum[i] - tp)
        fn = int(true_sum[i] - tp)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if (precision + recall) > 0
            else 0.0
        )
        out[lab] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": int(true_sum[i]),
        }
    return out


def macro_f1(
    y_true: Sequence[Any],
    y_pred: Sequence[Any],
    labels: Sequence[Any] | None = None,
) -> float:
    """Macro-averaged F1 — every class in the label space weighted equally."""
    per_class = precision_recall_f1_per_class(y_true, y_pred, labels)
    if not per_class:
        return 0.0
    return float(np.mean([m["f1"] for m in per_class.values()]))


def macro_f1_present(
    y_true: Sequence[Any],
    y_pred: Sequence[Any],
    labels: Sequence[Any] | None = None,
) -> float:
    """Macro F1 averaged only over classes with non-zero true support.

    The frozen label space has classes the synthetic generator never emits
    (e.g. DADO, RABBET). Including them drags ``macro_f1`` toward zero even when
    every observed class is classified well. ``macro_f1`` (full space) remains
    the spec primary metric; this companion reports the macro over classes that
    actually appear in the ground truth.
    """
    per_class = precision_recall_f1_per_class(y_true, y_pred, labels)
    present = [m["f1"] for m in per_class.values() if m["support"] > 0]
    if not present:
        return 0.0
    return float(np.mean(present))


def micro_f1(
    y_true: Sequence[Any],
    y_pred: Sequence[Any],
    labels: Sequence[Any] | None = None,
) -> float:
    """Micro-averaged F1. For single-label multi-class this equals accuracy
    when the label space covers all observed labels."""
    _, cm = confusion_matrix(y_true, y_pred, labels)
    tp = int(np.diag(cm).sum())
    total_pred = int(cm.sum())  # every sample contributes one prediction
    fp = total_pred - tp
    fn = total_pred - tp
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    if (precision + recall) == 0:
        return 0.0
    return float(2 * precision * recall / (precision + recall))


def accuracy(y_true: Sequence[Any], y_pred: Sequence[Any]) -> float:
    if len(y_true) == 0:
        return 0.0
    correct = sum(1 for t, p in zip(y_true, y_pred) if t == p)
    return correct / len(y_true)


# ---------------------------------------------------------------------------
# Binary metrics
# ---------------------------------------------------------------------------


def binary_rates(
    y_true: Sequence[bool],
    y_pred: Sequence[bool],
    pos_label: bool = True,
) -> dict[str, float]:
    """Confusion counts + binary F1, FPR, FNR, accuracy for a binary task.

    ``pos_label`` is the "positive" class. For BENCH-002 the positive class is
    ``is_manufacturable == True`` is *not* the safety class; we follow the spec
    which treats the manufacturable / not-manufacturable F1 directly and defines
    FNR as "invalid predicted as valid". To keep that mapping explicit we expose
    raw TP/FP/FN/TN against ``pos_label`` and also the spec-oriented rates.
    """
    tp = fp = fn = tn = 0
    for t, p in zip(y_true, y_pred):
        t_pos = t == pos_label
        p_pos = p == pos_label
        if t_pos and p_pos:
            tp += 1
        elif (not t_pos) and p_pos:
            fp += 1
        elif t_pos and (not p_pos):
            fn += 1
        else:
            tn += 1
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    fnr = fn / (fn + tp) if (fn + tp) > 0 else 0.0
    total = tp + fp + fn + tn
    acc = (tp + tn) / total if total > 0 else 0.0
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "fpr": fpr,
        "fnr": fnr,
        "accuracy": acc,
    }


# ---------------------------------------------------------------------------
# Multi-label metrics
# ---------------------------------------------------------------------------


def _to_indicator(
    samples: Iterable[Iterable[Any]],
    label_space: Sequence[Any],
) -> np.ndarray:
    index = {lab: i for i, lab in enumerate(label_space)}
    rows = []
    for labels in samples:
        row = np.zeros(len(label_space), dtype=np.int64)
        for lab in labels:
            if lab in index:
                row[index[lab]] = 1
        rows.append(row)
    if not rows:
        return np.zeros((0, len(label_space)), dtype=np.int64)
    return np.vstack(rows)


def hamming_loss(
    y_true: Iterable[Iterable[Any]],
    y_pred: Iterable[Iterable[Any]],
    label_space: Sequence[Any],
) -> float:
    """Fraction of label slots that disagree across all samples."""
    yt = _to_indicator(y_true, label_space)
    yp = _to_indicator(y_pred, label_space)
    if yt.size == 0:
        return 0.0
    return float(np.mean(yt != yp))


def subset_accuracy(
    y_true: Iterable[Iterable[Any]],
    y_pred: Iterable[Iterable[Any]],
) -> float:
    """Fraction of samples whose predicted label *set* exactly matches truth."""
    yt = [set(s) for s in y_true]
    yp = [set(s) for s in y_pred]
    if not yt:
        return 0.0
    correct = sum(1 for t, p in zip(yt, yp) if t == p)
    return correct / len(yt)


def multilabel_macro_f1(
    y_true: Iterable[Iterable[Any]],
    y_pred: Iterable[Iterable[Any]],
    label_space: Sequence[Any],
) -> dict[str, Any]:
    """Per-label F1 + macro/micro F1 over a fixed label space (zero_division=0)."""
    yt = _to_indicator(y_true, label_space)
    yp = _to_indicator(y_pred, label_space)
    per_label: dict[Any, dict[str, float]] = {}
    f1s: list[float] = []
    micro_tp = micro_fp = micro_fn = 0
    for j, lab in enumerate(label_space):
        if yt.size == 0:
            per_label[lab] = {"precision": 0.0, "recall": 0.0, "f1": 0.0, "support": 0}
            f1s.append(0.0)
            continue
        tcol = yt[:, j]
        pcol = yp[:, j]
        tp = int(np.sum((tcol == 1) & (pcol == 1)))
        fp = int(np.sum((tcol == 0) & (pcol == 1)))
        fn = int(np.sum((tcol == 1) & (pcol == 0)))
        micro_tp += tp
        micro_fp += fp
        micro_fn += fn
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if (precision + recall) > 0
            else 0.0
        )
        per_label[lab] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": int(tp + fn),
        }
        f1s.append(f1)
    macro = float(np.mean(f1s)) if f1s else 0.0
    mp = micro_tp / (micro_tp + micro_fp) if (micro_tp + micro_fp) > 0 else 0.0
    mr = micro_tp / (micro_tp + micro_fn) if (micro_tp + micro_fn) > 0 else 0.0
    micro = 2 * mp * mr / (mp + mr) if (mp + mr) > 0 else 0.0
    return {
        "macro_f1": macro,
        "micro_f1": float(micro),
        "per_label": per_label,
    }


# ---------------------------------------------------------------------------
# Set / localization metrics
# ---------------------------------------------------------------------------


def iou(predicted: Iterable[Any], actual: Iterable[Any]) -> float:
    """Intersection-over-Union of two sets (violation localization).

    Convention: if both sets are empty (nothing to localize, nothing predicted)
    the IoU is 1.0 (perfect agreement on "no violating nodes").
    """
    p = set(predicted)
    a = set(actual)
    if not p and not a:
        return 1.0
    union = p | a
    if not union:
        return 1.0
    return len(p & a) / len(union)


# ---------------------------------------------------------------------------
# Ranking metric — AUROC (rank-based; ties handled via average ranks)
# ---------------------------------------------------------------------------


def roc_auc(y_true: Sequence[Any], scores: Sequence[float]) -> float:
    """Area under the ROC curve via the Mann-Whitney U / rank formulation.

    ``y_true`` is interpreted as binary (truthy = positive). Ties in ``scores``
    receive averaged ranks so the result equals the probability that a random
    positive scores higher than a random negative (ties counting as 0.5).

    Returns 0.5 when only one class is present (undefined ranking → chance).
    """
    y = np.array([1 if bool(v) else 0 for v in y_true], dtype=np.int64)
    s = np.asarray(scores, dtype=np.float64)
    n_pos = int(np.sum(y == 1))
    n_neg = int(np.sum(y == 0))
    if n_pos == 0 or n_neg == 0:
        return 0.5

    # Average ranks (1-based).
    order = np.argsort(s, kind="mergesort")
    ranks = np.empty(len(s), dtype=np.float64)
    sorted_scores = s[order]
    i = 0
    while i < len(sorted_scores):
        j = i
        while j + 1 < len(sorted_scores) and sorted_scores[j + 1] == sorted_scores[i]:
            j += 1
        avg_rank = (i + j) / 2.0 + 1.0  # 1-based average rank for the tie block
        for k in range(i, j + 1):
            ranks[order[k]] = avg_rank
        i = j + 1

    sum_ranks_pos = float(np.sum(ranks[y == 1]))
    auc = (sum_ranks_pos - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)
    return float(auc)
