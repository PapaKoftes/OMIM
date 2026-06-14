"""LayerProfile — the agnostic-middleware seam.

The single most important architectural lesson from validating OMIM against a real
shop corpus: **layer conventions are per-shop, not universal.** One shop's drill
layer is ``BOHR_5``, another's is ``DRILL``, another's is ``5MM_HOLES``. If OMIM
hard-codes one convention it overfits the first customer and breaks on the second.

So OMIM does NOT *contain* a convention — it *translates* one. A ``LayerProfile``
maps a shop's layer-name dialect onto OMIM's OWN, stable type vocabulary
(cut / drill / pocket / border / engrave / toolpath / cleanup). The profile is the
swappable adapter; the MGG + features + validation behind it are universal.

  shop DXF dialect  ->  [ LayerProfile: their names -> OMIM types ]  ->  MGG ...
     (per-customer)            (per-customer, loadable from YAML)        (universal)

The built-in ``cabinet`` profile (Blum / 32mm system) ships as ONE default
adapter — not "the truth". Customer profiles load from a YAML path and are meant
to live out-of-tree; the public repo never carries a customer's dialect.
"""

from __future__ import annotations

from pathlib import Path

import yaml

# OMIM's OWN canonical layer-type vocabulary. A profile may only map onto these
# (plus the implicit "unknown"). This list is the stable contract every domain
# and the parser agree on — it never changes per customer.
CANONICAL_LAYER_TYPES: tuple[str, ...] = (
    "cut",        # part outline / through-cut / inner-cut contours
    "drill",      # drilled holes
    "pocket",     # pockets / grooves / slots (milled, not through)
    "border",     # stock sheet / panel boundary
    "engrave",    # shallow marking / decorative cuts
    "toolpath",   # CAM toolpaths (not a manufacturable feature; informational)
    "cleanup",    # remnant / cleanup passes (not a feature)
)


class UnknownLayerTypeError(ValueError):
    """A profile maps a prefix onto a type that is not in CANONICAL_LAYER_TYPES."""


class LayerProfile:
    """Maps a shop's layer-name prefixes onto OMIM's canonical layer types.

    Matching is case-insensitive prefix matching (the same rule the parser has
    always used). Longest matching prefix wins, so a specific ``POCKET_DEEP`` can
    override a general ``POCKET`` if both are present.
    """

    def __init__(self, name: str, prefixes: dict[str, list[str]]) -> None:
        self.name = name
        # Validate every mapped type is canonical (catch typos / foreign vocab).
        bad = set(prefixes) - set(CANONICAL_LAYER_TYPES)
        if bad:
            raise UnknownLayerTypeError(
                f"profile {name!r} maps onto non-canonical type(s) {sorted(bad)}; "
                f"allowed: {list(CANONICAL_LAYER_TYPES)}"
            )
        # Store as upper-case prefixes for case-insensitive matching.
        self._prefixes: dict[str, list[str]] = {
            ltype: [p.upper() for p in plist] for ltype, plist in prefixes.items()
        }

    def infer(self, layer_name: str) -> str:
        """Return the canonical OMIM type for *layer_name*, or 'unknown'.

        Longest-prefix-wins so the most specific convention takes precedence.
        """
        upper = (layer_name or "").upper().strip()
        best_type = "unknown"
        best_len = -1
        for ltype, prefixes in self._prefixes.items():
            for prefix in prefixes:
                if upper.startswith(prefix) and len(prefix) > best_len:
                    best_type, best_len = ltype, len(prefix)
        return best_type

    def as_conventions(self) -> dict[str, list[str]]:
        """Return the prefix map in the ParserConfig.layer_conventions shape."""
        return {ltype: list(plist) for ltype, plist in self._prefixes.items()}

    # -- construction ------------------------------------------------------

    @classmethod
    def from_dict(cls, data: dict) -> LayerProfile:
        name = data.get("name", "custom")
        prefixes = data.get("prefixes") or data.get("layer_conventions") or {}
        return cls(name=name, prefixes=prefixes)

    @classmethod
    def from_yaml(cls, path: str | Path) -> LayerProfile:
        """Load a profile from a YAML file (intended for out-of-tree customer profiles)."""
        path = Path(path)
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        data.setdefault("name", path.stem)
        return cls.from_dict(data)
