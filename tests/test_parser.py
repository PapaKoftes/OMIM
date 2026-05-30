"""Tests for the DXF parser."""

from pathlib import Path

import pytest

from omim.parser.dxf_parser import DXFParser, _infer_layer_type


class TestLayerTypeInference:
    def test_cut_layers(self):
        assert _infer_layer_type("CUT") == "cut"
        assert _infer_layer_type("CUT_OUTER") == "cut"
        assert _infer_layer_type("Profile") == "cut"
        assert _infer_layer_type("CONTOUR") == "cut"
        assert _infer_layer_type("OUTLINE") == "cut"
        assert _infer_layer_type("OUTER_EDGE") == "cut"

    def test_drill_layers(self):
        assert _infer_layer_type("DRILL") == "drill"
        assert _infer_layer_type("HOLE_5mm") == "drill"
        assert _infer_layer_type("BORE_THROUGH") == "drill"
        assert _infer_layer_type("PUNCH_3mm") == "drill"

    def test_pocket_layers(self):
        assert _infer_layer_type("POCKET") == "pocket"
        assert _infer_layer_type("GROOVE_6mm") == "pocket"
        assert _infer_layer_type("SLOT_NARROW") == "pocket"
        assert _infer_layer_type("DADO_BACK") == "pocket"
        assert _infer_layer_type("RABBET_EDGE") == "pocket"

    def test_border_layers(self):
        assert _infer_layer_type("BORDER") == "border"
        assert _infer_layer_type("SHEET_SIZE") == "border"
        assert _infer_layer_type("STOCK") == "border"
        assert _infer_layer_type("MATERIAL_OUTLINE") == "border"

    def test_engrave_layers(self):
        assert _infer_layer_type("ENGRAVE") == "engrave"
        assert _infer_layer_type("ETCH_PATTERN") == "engrave"
        assert _infer_layer_type("SCORE_LINE") == "engrave"

    def test_unknown_layer(self):
        assert _infer_layer_type("Layer1") == "unknown"
        assert _infer_layer_type("0") == "unknown"

    def test_prefix_not_substring(self):
        """Layer matching uses prefix, not substring."""
        # "RECUT" should NOT match "cut" because "CUT" is not a prefix of "RECUT"
        assert _infer_layer_type("RECUT") == "unknown"
        # But "CUT_LAYER" should match because "CUT" is a prefix
        assert _infer_layer_type("CUT_LAYER") == "cut"


class TestDXFParser:
    def test_file_not_found(self):
        parser = DXFParser()
        result = parser.parse(Path("/nonexistent/file.dxf"))
        assert not result.success
        assert result.errors[0].error_code == "DXF_NOT_FOUND"

    def test_parse_result_structure(self):
        """ParseResult should have correct field defaults."""
        from omim.parser.models import ParseResult

        result = ParseResult(success=True)
        assert result.geometry is None
        assert result.errors == []
        assert result.warnings == []

    def test_parse_error_has_recoverable(self):
        """ParseError should have a recoverable field."""
        from omim.parser.models import ParseError

        err = ParseError(error_code="DXF_NOT_FOUND", message="test")
        assert err.recoverable is False
