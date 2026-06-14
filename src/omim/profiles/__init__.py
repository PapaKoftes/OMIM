"""OMIM layer profiles — the agnostic-middleware seam.

A LayerProfile translates a shop's layer-name dialect into OMIM's own canonical
layer-type vocabulary. The cabinet/Blum default ships built in; customer profiles
load from YAML out-of-tree. The public repo never carries a customer's dialect.
"""

from omim.profiles.builtins import (
    DEFAULT_PROFILE_NAME,
    builtin_profile_names,
    get_builtin_profile,
    load_profile,
)
from omim.profiles.layer_profile import (
    CANONICAL_LAYER_TYPES,
    LayerProfile,
    UnknownLayerTypeError,
)

__all__ = [
    "CANONICAL_LAYER_TYPES",
    "DEFAULT_PROFILE_NAME",
    "LayerProfile",
    "UnknownLayerTypeError",
    "builtin_profile_names",
    "get_builtin_profile",
    "load_profile",
]
