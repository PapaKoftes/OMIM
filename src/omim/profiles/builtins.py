"""Built-in layer profiles that ship with OMIM.

Each is ONE default adapter for a common public convention — not "the" convention.
The ``cabinet`` profile is the historical default (English cabinet-CNC layer
names, Blum / 32mm domain). Customer-specific profiles are NOT shipped here; they
load from a YAML path and live out-of-tree (see LayerProfile.from_yaml).
"""

from __future__ import annotations

from omim.profiles.layer_profile import LayerProfile

# The original DEFAULT_LAYER_MAP, now expressed as a named built-in profile.
# Behaviour-preserving: identical prefixes to the pre-profile parser default.
_CABINET_PREFIXES: dict[str, list[str]] = {
    "cut": ["CUT", "CUT_", "PROFILE", "OUTLINE", "OUTER", "CONTOUR"],
    "drill": ["DRILL", "HOLE", "BORE", "PUNCH"],
    "pocket": ["POCKET", "GROOVE", "SLOT", "DADO", "RABBET"],
    "border": ["BORDER", "SHEET", "STOCK", "MATERIAL"],
    "engrave": ["ENGRAVE", "ETCH", "SCORE", "MARK"],
}

_BUILTINS: dict[str, dict[str, list[str]]] = {
    "cabinet": _CABINET_PREFIXES,
}

#: The default profile name used when none is specified (preserves old behaviour).
DEFAULT_PROFILE_NAME = "cabinet"


def get_builtin_profile(name: str = DEFAULT_PROFILE_NAME) -> LayerProfile:
    """Return a built-in LayerProfile by name, or raise KeyError with the options."""
    if name not in _BUILTINS:
        raise KeyError(f"unknown built-in profile {name!r}; have {list(_BUILTINS)}")
    return LayerProfile(name=name, prefixes=_BUILTINS[name])


def builtin_profile_names() -> list[str]:
    return list(_BUILTINS)


def load_profile(name_or_path: str | None = None) -> LayerProfile:
    """Resolve a profile from a built-in name OR a YAML path.

    - ``None`` -> the default built-in (``cabinet``).
    - a known built-in name -> that built-in.
    - anything else ending in .yaml/.yml that exists -> loaded from disk
      (the out-of-tree customer-profile path).
    """
    from pathlib import Path

    if name_or_path is None:
        return get_builtin_profile()
    if name_or_path in _BUILTINS:
        return get_builtin_profile(name_or_path)
    p = Path(name_or_path)
    if p.suffix.lower() in (".yaml", ".yml") and p.exists():
        return LayerProfile.from_yaml(p)
    raise KeyError(
        f"profile {name_or_path!r} is not a built-in {list(_BUILTINS)} and is not "
        f"an existing .yaml/.yml file"
    )
