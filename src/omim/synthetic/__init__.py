"""OMIM synthetic data generation.

Generates cabinet-panel DXFs from manufacturing standards (NOT random geometry),
grounded in real manufacturer specs. The deterministic validator is the
gatekeeper: a sample is kept only when its validation outcome matches the
generation spec's intended validity.
"""

from omim.synthetic.dxf_writer import DXFWriter
from omim.synthetic.generator import PanelGenerator
from omim.synthetic.models import (
    FeatureSpec,
    PanelGeneratorConfig,
    PanelSpec,
)

__all__ = [
    "PanelGenerator",
    "PanelGeneratorConfig",
    "PanelSpec",
    "FeatureSpec",
    "DXFWriter",
]
