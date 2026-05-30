"""Optional-dependency availability checks for the ML layer.

The ML layer (Authority Hierarchy Level 6) is *advisory only* and is an
optional, bounded component of OMIM. Its heavy dependencies (``torch`` and
``torch_geometric``) live in the ``[ml]`` extra and may be absent in a base
install.

This module is the single source of truth for "can we run ML?". Every torch
import in the package is lazy and guarded by the flags computed here, so that:

  * ``import omim.ml`` ALWAYS succeeds, even with no ML dependencies installed.
  * Callers can branch on :data:`ML_AVAILABLE` to gracefully fall back to
    deterministic heuristics (Failure_Modes D-003).

Two independent flags are tracked because the two libraries can be installed
separately (e.g. ``torch`` present but ``torch_geometric`` missing):

  * :data:`TORCH_AVAILABLE`       -- ``import torch`` works.
  * :data:`PYG_AVAILABLE`         -- ``import torch_geometric`` works.
  * :data:`ML_AVAILABLE`          -- both of the above (full GNN stack usable).
"""

from __future__ import annotations

import importlib.util

__all__ = [
    "TORCH_AVAILABLE",
    "PYG_AVAILABLE",
    "SKLEARN_AVAILABLE",
    "ML_AVAILABLE",
    "ml_available",
    "torch_available",
    "pyg_available",
    "require_torch",
    "missing_dependencies",
]


def _module_installed(name: str) -> bool:
    """Return whether *name* can be imported without actually importing it.

    Uses :func:`importlib.util.find_spec` so we never pay the (large) import
    cost of torch just to answer the availability question.
    """
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError, ModuleNotFoundError):
        return False


# Computed once at import time. These are cheap spec lookups, not real imports.
TORCH_AVAILABLE: bool = _module_installed("torch")
PYG_AVAILABLE: bool = _module_installed("torch_geometric")
SKLEARN_AVAILABLE: bool = _module_installed("sklearn")

#: True only when the *full* GNN stack (torch + torch_geometric) is importable.
ML_AVAILABLE: bool = TORCH_AVAILABLE and PYG_AVAILABLE


def torch_available() -> bool:
    """Return whether ``torch`` is importable."""
    return TORCH_AVAILABLE


def pyg_available() -> bool:
    """Return whether ``torch_geometric`` is importable."""
    return PYG_AVAILABLE


def ml_available() -> bool:
    """Return whether the full GNN stack (torch + torch_geometric) is available."""
    return ML_AVAILABLE


def missing_dependencies() -> list[str]:
    """Return the list of ML extras that are NOT installed."""
    missing: list[str] = []
    if not TORCH_AVAILABLE:
        missing.append("torch")
    if not PYG_AVAILABLE:
        missing.append("torch_geometric")
    return missing


def require_torch(feature: str = "this operation") -> None:
    """Raise a clear, actionable error if the GNN stack is unavailable.

    Call this at the top of any function that *cannot* proceed without torch /
    torch_geometric (e.g. instantiating a model, running a forward pass).

    Note: the public entry point :class:`omim.ml.predictor.GNNPredictor` does
    NOT call this -- it degrades gracefully instead (D-003). Use ``require_torch``
    only in code paths where raising is the correct behavior (e.g. the trainer,
    which has no meaningful fallback).
    """
    if ML_AVAILABLE:
        return
    missing = missing_dependencies()
    raise ImportError(
        f"{feature} requires the optional ML dependencies, but the following "
        f"are not installed: {', '.join(missing)}.\n"
        "Install them with:  pip install 'omim[ml]'\n"
        "(The ML layer is advisory-only — the rest of OMIM works without it.)"
    )
