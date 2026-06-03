"""Load rule configuration (thresholds, severity, enabled) from data/rules/*.yaml
and map it onto the keyword arguments the rule functions actually expect.

Previously the YAML files existed but the engine ignored them entirely — every
threshold was a hardcoded Python default, and the YAML parameter names did not
even match the function kwargs. This module closes that gap: it parses the YAML,
translates each rule's ``parameters`` into the code's kwarg names via an explicit
alias table, and exposes them so the engine can call ``handler(mgg, **params)``.
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

# Per-rule mapping: YAML parameter name -> rule-function kwarg name.
# Only entries that differ (or need normalising) are listed; matching names pass
# through unchanged. Verified against manufacturing_rules.py / geometric_rules.py.
_PARAM_ALIASES: dict[str, dict[str, str]] = {
    "MFG-001": {"min_edge_clearance_mm": "min_distance_mm"},
    "MFG-002": {"min_drill_wall_mm": "min_wall_thickness_mm"},
    "MFG-003": {"min_tool_radius_mm": "min_corner_radius_mm"},
    "MFG-004": {
        "default_tool_diameter_mm": "tool_diameter_mm",
        "min_pocket_width_ratio": "multiplier",
    },
    "MFG-005": {
        "shelf_pin_diameter_mm": "target_diameter_mm",
        "shelf_pin_spacing_mm": "target_spacing_mm",
        "shelf_pin_tolerance_mm": "spacing_tolerance_mm",
    },
    "MFG-006": {
        "hinge_cup_diameter_mm": "target_diameter_mm",
        "hinge_cup_edge_distance_mm": "target_edge_distance_mm",
        "hinge_cup_tolerance_mm": "edge_tolerance_mm",
    },
    "MFG-007": {
        "max_blind_depth_ratio": "max_depth_ratio",
        "default_panel_thickness_mm": "panel_thickness_mm",
    },
    "MFG-008": {"max_hole_coverage_ratio": "max_density_ratio"},
    "MFG-011": {
        "min_hole_diameter_mm": "min_diameter_mm",
        "max_hole_diameter_mm": "max_diameter_mm",
    },
    "GEO-001": {"closure_tolerance_mm": "tolerance_mm"},
    "GEO-004": {"max_dimension_mm": "coord_max", "min_coordinate_mm": "coord_min"},
    "GEO-006": {
        "position_tolerance_mm": "center_tolerance_mm",
        "size_tolerance_ratio": "radius_tolerance_pct",
    },
}


class RuleConfig:
    """Parsed configuration for one rule."""

    __slots__ = ("rule_id", "enabled", "severity", "params", "confidence_ceiling")

    def __init__(
        self,
        rule_id: str,
        enabled: bool,
        severity: str | None,
        params: dict,
        confidence_ceiling: float | None,
    ) -> None:
        self.rule_id = rule_id
        self.enabled = enabled
        self.severity = severity
        self.params = params
        self.confidence_ceiling = confidence_ceiling


def _translate_params(rule_id: str, raw_params: dict) -> dict:
    """Map YAML parameter names onto the rule function's kwarg names."""
    aliases = _PARAM_ALIASES.get(rule_id, {})
    out: dict = {}
    for key, value in (raw_params or {}).items():
        out[aliases.get(key, key)] = value
    return out


def load_ruleset(rules_dir: str | Path) -> dict[str, RuleConfig]:
    """Load all rule configs from ``*.yaml`` under *rules_dir*, keyed by rule_id.

    Returns an empty dict when the directory is missing/empty (the engine then
    falls back to its hardcoded defaults). Malformed files are skipped with a
    warning, never fatal.
    """
    rules_dir = Path(rules_dir)
    configs: dict[str, RuleConfig] = {}
    if not rules_dir.is_dir():
        return configs
    for yaml_file in sorted(rules_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(yaml_file.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            logger.warning("Skipping malformed rule file %s: %s", yaml_file, exc)
            continue
        for rule in data.get("rules", []) or []:
            rule_id = rule.get("rule_id")
            if not rule_id:
                continue
            configs[rule_id] = RuleConfig(
                rule_id=rule_id,
                enabled=bool(rule.get("enabled", True)),
                severity=rule.get("severity"),
                params=_translate_params(rule_id, rule.get("parameters", {})),
                confidence_ceiling=rule.get("confidence_ceiling"),
            )
    logger.info("Loaded config for %d rules from %s", len(configs), rules_dir)
    return configs
