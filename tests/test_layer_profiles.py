"""Tests for the LayerProfile system (the agnostic-middleware seam).

A profile maps a shop's layer dialect onto OMIM's OWN canonical types. The
built-in cabinet profile must reproduce the historical default; custom profiles
load from YAML; foreign vocabulary is rejected; the parser honours a profile.
Synthetic only — no external data.
"""

from __future__ import annotations

import ezdxf
import pytest

from omim.parser.dxf_parser import DXFParser
from omim.parser.models import DEFAULT_LAYER_MAP
from omim.profiles import (
    CANONICAL_LAYER_TYPES,
    LayerProfile,
    UnknownLayerTypeError,
    builtin_profile_names,
    get_builtin_profile,
    load_profile,
)


def test_cabinet_builtin_matches_legacy_default():
    """The cabinet profile must reproduce the pre-profile DEFAULT_LAYER_MAP."""
    cab = get_builtin_profile("cabinet")
    conv = cab.as_conventions()
    for ltype, prefixes in DEFAULT_LAYER_MAP.items():
        assert ltype in conv
        # cabinet may add MARK to engrave; legacy prefixes must all still be present.
        assert set(p.upper() for p in prefixes) <= set(conv[ltype])


def test_cabinet_inference():
    cab = get_builtin_profile("cabinet")
    assert cab.infer("CUT") == "cut"
    assert cab.infer("DRILL_5MM") == "drill"
    assert cab.infer("POCKET_X") == "pocket"
    assert cab.infer("SHEET") == "border"
    assert cab.infer("ENGRAVE") == "engrave"
    assert cab.infer("WHATEVER") == "unknown"


def test_only_canonical_types_allowed():
    """A profile mapping onto a non-canonical (foreign) type is rejected."""
    with pytest.raises(UnknownLayerTypeError):
        LayerProfile("bad", {"OUTSIDE": ["X"]})  # OUTSIDE is not an OMIM type
    # All canonical types ARE allowed.
    LayerProfile("ok", {t: ["X"] for t in CANONICAL_LAYER_TYPES})


def test_longest_prefix_wins():
    p = LayerProfile("t", {"pocket": ["POCKET"], "cut": ["POCKET_THROUGH"]})
    assert p.infer("POCKET_THROUGH_2") == "cut"   # more specific wins
    assert p.infer("POCKET_BLIND") == "pocket"


def test_load_profile_builtin_vs_yaml(tmp_path):
    # built-in name
    assert load_profile("cabinet").name == "cabinet"
    assert load_profile(None).name == "cabinet"  # default
    # yaml path (out-of-tree style)
    y = tmp_path / "cust.yaml"
    y.write_text("name: cust\nprefixes:\n  drill: [BOHR]\n  border: [PLATE]\n",
                 encoding="utf-8")
    prof = load_profile(str(y))
    assert prof.name == "cust"
    assert prof.infer("BOHR_5") == "drill"
    assert prof.infer("PLATE") == "border"


def test_load_profile_unknown_raises():
    with pytest.raises(KeyError):
        load_profile("not_a_profile_and_not_a_file")


def test_builtin_names():
    assert "cabinet" in builtin_profile_names()


def test_parser_honours_profile(tmp_path):
    """DXFParser(profile=...) applies a custom dialect; default == cabinet."""
    y = tmp_path / "c.yaml"
    y.write_text("name: c\nprefixes:\n  drill: [BOHR]\n  border: [PLATE]\n",
                 encoding="utf-8")
    doc = ezdxf.new()
    m = doc.modelspace()
    m.add_lwpolyline([(0, 0), (300, 0), (300, 300), (0, 300)], close=True,
                     dxfattribs={"layer": "PLATE"})
    m.add_circle((150, 150), radius=2, dxfattribs={"layer": "BOHR_5"})
    f = tmp_path / "t.dxf"
    doc.saveas(f)

    r = DXFParser(profile=load_profile(str(y))).parse(f)
    types = {e.inferred_layer_type for e in r.geometry.entities}
    assert types == {"border", "drill"}  # custom dialect resolved, no unknown

    # Default parser still behaves as cabinet (PLATE->border via SHEET? no; PLATE
    # is not a cabinet prefix, so it's unknown — proving the profile mattered).
    r2 = DXFParser().parse(f)
    types2 = {e.inferred_layer_type for e in r2.geometry.entities}
    assert "unknown" in types2  # cabinet doesn't know BOHR/PLATE
