"""Real DXF corpus grounding for OMIM.

This package ingests real-world cabinet / CNC DXF corpora, extracts empirical
distributions of manufacturing dimensions, validates them against manufacturer
catalog ground truth (Blum / Hettich / Häfele / System 32 / DIN / EN), and
emits a grounding profile the synthetic generator can consume.

Trust hierarchy (see data/grounding/README.md):
  - Tier 1: catalog-derived reference profile (shipped; authoritative spec).
  - Tier 2: empirical profile from an ingested real corpus.
  - Tier 3: community / unvetted corpora pending license + annotation review.
"""

from omim.corpus.catalog_ground_truth import (
    CATALOG_REFERENCES,
    KNOWN_FEATURE_DIAMETERS_MM,
    VALID_PANEL_THICKNESSES_MM,
    cluster_diameter,
    feature_for_diameter,
)
from omim.corpus.distribution_extractor import (
    cluster_diameters,
    extract_distributions,
)
from omim.corpus.ingest import (
    CorpusIngestor,
    CorpusStatistics,
    HoleMeasurement,
    PanelMeasurement,
)
from omim.corpus.reference_profile import (
    build_reference_profile,
    load_grounding_profile,
    write_reference_profile,
)
from omim.corpus.validator import (
    CatalogValidationReport,
    CheckResult,
    validate_against_catalog,
)

__all__ = [
    "CATALOG_REFERENCES",
    "KNOWN_FEATURE_DIAMETERS_MM",
    "VALID_PANEL_THICKNESSES_MM",
    "cluster_diameter",
    "feature_for_diameter",
    "CorpusIngestor",
    "CorpusStatistics",
    "HoleMeasurement",
    "PanelMeasurement",
    "extract_distributions",
    "cluster_diameters",
    "validate_against_catalog",
    "CatalogValidationReport",
    "CheckResult",
    "build_reference_profile",
    "write_reference_profile",
    "load_grounding_profile",
]
