"""omim.domains.panel — the cabinet/panel CNC domain (original OMIM).

Re-export surface only (no file moves): the DXF parser, MGG builder, the
GEO/MFG rule engine, the heuristic feature classifier, and the synthetic
panel generator. This marks which modules are panel-specific vs. core.
"""

from omim.graph.builder import MGGBuilder
from omim.parser.dxf_parser import DXFParser
from omim.semantic.classifier import FeatureClassifier
from omim.synthetic.generator import PanelGenerator
from omim.synthetic.models import PanelGeneratorConfig
from omim.validation.rule_engine import RuleEngine

__all__ = [
    "DXFParser",
    "MGGBuilder",
    "RuleEngine",
    "FeatureClassifier",
    "PanelGenerator",
    "PanelGeneratorConfig",
]
