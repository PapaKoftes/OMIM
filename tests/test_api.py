"""API tests for OMIM using FastAPI's TestClient.

No live network is used. The LLM path is exercised in two guarded modes:
  1. No Featherless key configured (default test env) → graceful "unavailable".
  2. Key present but the annotator monkeypatched to raise → graceful degradation
     with NO real network call.
"""

from __future__ import annotations

import io
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from omim.api import llm_service
from omim.api.main import app
from omim.synthetic.dxf_writer import DXFWriter
from omim.synthetic.models import FeatureSpec, PanelSpec

API = "/api/v1"


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def _make_dxf_bytes() -> bytes:
    """Build a small, valid cabinet-panel DXF in-memory and return its bytes."""
    panel = PanelSpec(
        width_mm=600.0,
        height_mm=400.0,
        thickness_mm=18.0,
        boundary_points=[(0, 0), (600, 0), (600, 400), (0, 400)],
        panel_type="side_panel",
    )
    features = [
        FeatureSpec(
            feature_class="PROFILE_CUT",
            entity_type="LWPOLYLINE",
            points=[(0, 0), (600, 0), (600, 400), (0, 400)],
            is_closed=True,
            layer="BORDER",
        ),
        FeatureSpec(
            feature_class="HINGE_CUP_HOLE",
            entity_type="CIRCLE",
            center=(22.5, 100.0),
            radius_mm=17.5,
            layer="HINGE",
        ),
        FeatureSpec(
            feature_class="THROUGH_HOLE",
            entity_type="CIRCLE",
            center=(300.0, 200.0),
            radius_mm=4.0,
            layer="DRILL",
        ),
    ]
    tmp = Path(tempfile.mkdtemp()) / "panel.dxf"
    DXFWriter().write_panel(panel, features, tmp)
    data = tmp.read_bytes()
    tmp.unlink(missing_ok=True)
    return data


@pytest.fixture(scope="module")
def dxf_bytes() -> bytes:
    return _make_dxf_bytes()


def _upload(dxf_bytes: bytes, name: str = "panel.dxf"):
    return {"file": (name, io.BytesIO(dxf_bytes), "application/dxf")}


@pytest.fixture(autouse=True)
def _no_llm_key(monkeypatch):
    """Ensure no Featherless key leaks into tests unless a test sets one."""
    monkeypatch.setattr(llm_service, "llm_configured", lambda: False)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# parse / validate / analyze
# ---------------------------------------------------------------------------


def test_parse(client, dxf_bytes):
    r = client.post(f"{API}/parse", files=_upload(dxf_bytes))
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["geometry"] is not None


def test_parse_rejects_non_dxf(client):
    r = client.post(f"{API}/parse", files={"file": ("x.txt", io.BytesIO(b"hi"), "text/plain")})
    assert r.status_code == 400


def test_validate(client, dxf_bytes):
    r = client.post(f"{API}/validate", files=_upload(dxf_bytes))
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert "validation" in body
    assert body["validation"]["overall_valid"] is True


def test_analyze_shape(client, dxf_bytes):
    r = client.post(f"{API}/analyze", files=_upload(dxf_bytes))
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    # validation present
    assert body["validation"]["layer1_passed"] is True
    # classifications present (Layer 1 passed)
    assert body["annotations"] is not None
    assert len(body["annotations"]["feature_annotations"]) >= 1
    # graph + summary
    assert "graph" in body
    assert body["summary"]["geometry_nodes"] >= 1


def test_analyze_annotate_no_key(client, dxf_bytes):
    """?annotate=true with no Featherless key → graceful unavailable, no crash."""
    r = client.post(f"{API}/analyze?annotate=true", files=_upload(dxf_bytes))
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    llm = body["llm_annotations"]
    assert llm["llm_available"] is False
    assert llm["annotations"] == []
    assert "note" in llm
    # LLM must not have altered validity.
    assert body["validation"]["overall_valid"] is True


def test_analyze_annotate_key_but_network_fails(client, dxf_bytes, monkeypatch):
    """Key present but annotator raises → graceful degradation, no real network."""
    monkeypatch.setattr(llm_service, "llm_configured", lambda: True)

    class _BoomAnnotator:
        async def annotate_feature(self, *args, **kwargs):
            raise RuntimeError("simulated network failure")

    monkeypatch.setattr(llm_service, "LLMAnnotator", _BoomAnnotator)

    r = client.post(f"{API}/analyze?annotate=true", files=_upload(dxf_bytes))
    assert r.status_code == 200
    body = r.json()
    llm = body["llm_annotations"]
    # Reachable=configured, but all calls failed → empty annotations, graceful note.
    assert llm["llm_available"] is True
    assert llm["annotations"] == []
    assert "degraded" in llm["note"].lower() or "failed" in llm["note"].lower()
    # Validity is untouched by the LLM failure.
    assert body["validation"]["overall_valid"] is True


# ---------------------------------------------------------------------------
# /annotate
# ---------------------------------------------------------------------------


def test_annotate_dxf_no_key(client, dxf_bytes):
    r = client.post(f"{API}/annotate", files=_upload(dxf_bytes))
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["llm"]["llm_available"] is False
    assert body["llm"]["advisory"] is True


def test_annotate_requires_input(client):
    r = client.post(f"{API}/annotate")
    assert r.status_code == 400


def test_annotate_mgg_json_body(client, dxf_bytes):
    """The MGG-json body path round-trips through from_dict and degrades."""
    import json

    from omim.graph.builder import MGGBuilder
    from omim.parser.dxf_parser import DXFParser

    tmp = Path(tempfile.mkdtemp()) / "panel.dxf"
    tmp.write_bytes(dxf_bytes)
    try:
        mgg = MGGBuilder().build(DXFParser().parse(tmp).geometry)
    finally:
        tmp.unlink(missing_ok=True)

    r = client.post(f"{API}/annotate", json={"mgg": json.loads(mgg.to_json())})
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["llm"]["advisory"] is True


def test_annotate_invalid_mgg_json(client):
    r = client.post(f"{API}/annotate", json={"mgg": {"bogus": True}})
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# /generate
# ---------------------------------------------------------------------------


def test_generate(client):
    r = client.post(
        f"{API}/generate",
        json={"num_samples": 5, "seed": 7, "invalid_ratio": 0.4},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    m = body["manifest"]
    # valid + invalid == total kept
    assert m["valid_count"] + m["invalid_count"] == m["total_samples"]
    # splits sum to total kept
    splits = m["splits"]
    assert splits["train"] + splits["val"] + splits["test"] == m["total_samples"]


def test_generate_caps_num_samples(client):
    r = client.post(f"{API}/generate", json={"num_samples": 9999})
    assert r.status_code == 422  # exceeds le=50 cap


# ---------------------------------------------------------------------------
# /ontology and /rules
# ---------------------------------------------------------------------------


def test_ontology(client):
    r = client.get(f"{API}/ontology")
    assert r.status_code == 200
    body = r.json()
    assert body["loaded"] is True
    assert len(body["feature_classes"]) > 0
    assert body["version"]


def test_rules(client):
    r = client.get(f"{API}/rules")
    assert r.status_code == 200
    body = r.json()
    assert body["loaded"] is True
    assert body["count"] > 0
    # Each rule carries an id + severity.
    first = body["rules"][0]
    assert "rule_id" in first
    assert "severity" in first
