"""Tests for the DXF parser."""

from pathlib import Path

import pytest

from omim.parser.dxf_parser import DXFParser, _infer_layer_type


class TestLayerTypeInference:
    def test_cut_layers(self):
        assert _infer_layer_type("CUT") == "cut"
        assert _infer_layer_type("Profile") == "cut"
        assert _infer_layer_type("CONTOUR") == "cut"
        assert _infer_layer_type("outline") == "cut"

    def test_drill_layers(self):
        assert _infer_layer_type("DRILL") == "drill"
        assert _infer_layer_type("Hole_5mm") == "drill"
        assert _infer_layer_type("BORE_THROUGH") == "drill"

    def test_pocket_layers(self):
        assert _infer_layer_type("POCKET") == "pocket"
        assert _infer_layer_type("Rout_6mm") == "pocket"
        assert _infer_layer_type("MILL_AREA") == "pocket"

    def test_engrave_layers(self):
        assert _infer_layer_type("ENGRAVE") == "engrave"
        assert _infer_layer_type("text_label") == "engrave"

    def test_unknown_layer(self):
        assert _infer_layer_type("Layer1") == "unknown"
        assert _infer_layer_type("0") == "unknown"


class TestDXFParser:
    def test_file_not_found(self):
        parser = DXFParser()
        result = parser.parse(Path("/nonexistent/file.dxf"))
        assert not result.success
        assert result.errors[0].error_code == "FILE_NOT_FOUND"

    def test_parse_result_structure(self):
        """ParseResult should have correct field defaults."""
        from omim.parser.models import ParseResult

        result = ParseResult(success=True)
        assert result.geometry is None
        assert result.errors == []
