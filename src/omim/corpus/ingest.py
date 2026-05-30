"""Corpus ingestion: walk a directory of real DXF files and extract measurements.

``CorpusIngestor`` reuses the existing :class:`omim.parser.dxf_parser.DXFParser`
to parse each ``.dxf`` file, builds an MGG via :class:`omim.graph.builder.MGGBuilder`,
and extracts per-feature manufacturing measurements (hole diameters, edge
setbacks, pairwise spacings, panel dimensions, thickness when available).

Parse failures are logged and skipped — ingestion of a corpus never aborts on a
single bad file. The result is a :class:`CorpusStatistics` object that the
distribution extractor and the catalog validator consume.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from pathlib import Path

from omim.graph.builder import MGGBuilder
from omim.parser.dxf_parser import DXFParser
from omim.parser.models import RawGeometry

logger = logging.getLogger(__name__)

# A circle is treated as a drilled hole (not a tiny arc artefact) above this.
MIN_HOLE_DIAMETER_MM = 1.0
# Two holes are "paired" for spacing stats if their centers are within this
# distance — captures shelf-pin columns, confirmat pairs, hinge pairs.
MAX_PAIR_SPACING_MM = 200.0
# Holes count as collinear (same column / row) within this perpendicular band.
COLLINEAR_TOL_MM = 1.5


@dataclass
class HoleMeasurement:
    """A single drilled hole extracted from a corpus file."""

    source_file: str
    diameter_mm: float
    center: tuple[float, float]
    layer: str
    inferred_layer_type: str
    edge_setback_mm: float | None = None  # min distance from any panel edge


@dataclass
class PanelMeasurement:
    """Panel-level measurements for one corpus file."""

    source_file: str
    width_mm: float | None = None
    height_mm: float | None = None
    area_mm2: float | None = None
    thickness_mm: float | None = None
    boundary_inferred: bool = False
    hole_count: int = 0


@dataclass
class CorpusStatistics:
    """Aggregated raw measurements over an ingested DXF corpus.

    This is the intermediate, un-binned representation. The distribution
    extractor turns it into histograms / percentiles, and the validator
    compares it against the catalog ground truth.
    """

    holes: list[HoleMeasurement] = field(default_factory=list)
    panels: list[PanelMeasurement] = field(default_factory=list)
    pairwise_spacings_mm: list[float] = field(default_factory=list)

    files_total: int = 0
    files_parsed: int = 0
    files_failed: int = 0
    failures: list[tuple[str, str]] = field(default_factory=list)  # (file, reason)
    source_dir: str = ""

    # ---- convenience accessors -------------------------------------------

    @property
    def diameters_mm(self) -> list[float]:
        return [h.diameter_mm for h in self.holes]

    @property
    def edge_setbacks_mm(self) -> list[float]:
        return [h.edge_setback_mm for h in self.holes if h.edge_setback_mm is not None]

    @property
    def panel_widths_mm(self) -> list[float]:
        return [p.width_mm for p in self.panels if p.width_mm is not None]

    @property
    def panel_heights_mm(self) -> list[float]:
        return [p.height_mm for p in self.panels if p.height_mm is not None]

    @property
    def thicknesses_mm(self) -> list[float]:
        return [p.thickness_mm for p in self.panels if p.thickness_mm is not None]

    @property
    def hole_counts(self) -> list[int]:
        return [p.hole_count for p in self.panels]

    def summary(self) -> dict:
        return {
            "source_dir": self.source_dir,
            "files_total": self.files_total,
            "files_parsed": self.files_parsed,
            "files_failed": self.files_failed,
            "total_holes": len(self.holes),
            "total_panels": len(self.panels),
            "total_pairwise_spacings": len(self.pairwise_spacings_mm),
        }


def _point_to_segment_distance(
    px: float, py: float, ax: float, ay: float, bx: float, by: float
) -> float:
    """Distance from point (px,py) to segment (ax,ay)-(bx,by)."""
    dx, dy = bx - ax, by - ay
    seg_len_sq = dx * dx + dy * dy
    if seg_len_sq == 0.0:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / seg_len_sq
    t = max(0.0, min(1.0, t))
    cx, cy = ax + t * dx, ay + t * dy
    return math.hypot(px - cx, py - cy)


def _edge_setback(center: tuple[float, float], boundary_coords: list) -> float | None:
    """Minimum distance from a hole center to the panel boundary edges."""
    pts = [(float(p[0]), float(p[1])) for p in boundary_coords if len(p) >= 2]
    if len(pts) < 2:
        return None
    px, py = center
    best = float("inf")
    for i in range(len(pts)):
        ax, ay = pts[i]
        bx, by = pts[(i + 1) % len(pts)]
        best = min(best, _point_to_segment_distance(px, py, ax, ay, bx, by))
    return round(best, 4) if best != float("inf") else None


class CorpusIngestor:
    """Walk a directory of ``.dxf`` files and extract corpus statistics."""

    def __init__(
        self,
        parser: DXFParser | None = None,
        builder: MGGBuilder | None = None,
        min_hole_diameter_mm: float = MIN_HOLE_DIAMETER_MM,
        max_pair_spacing_mm: float = MAX_PAIR_SPACING_MM,
    ) -> None:
        self.parser = parser or DXFParser()
        self.builder = builder or MGGBuilder()
        self.min_hole_diameter_mm = min_hole_diameter_mm
        self.max_pair_spacing_mm = max_pair_spacing_mm

    # ------------------------------------------------------------------

    def ingest_directory(self, dxf_dir: str | Path) -> CorpusStatistics:
        """Parse every ``.dxf`` under *dxf_dir* (recursively) and aggregate stats."""
        dxf_dir = Path(dxf_dir)
        stats = CorpusStatistics(source_dir=str(dxf_dir))

        if not dxf_dir.exists():
            logger.warning("Corpus directory does not exist: %s", dxf_dir)
            return stats

        files = sorted(dxf_dir.rglob("*.dxf")) + sorted(dxf_dir.rglob("*.DXF"))
        # De-duplicate (case-insensitive filesystems would double-count).
        seen: set[str] = set()
        unique_files = []
        for f in files:
            key = str(f).lower()
            if key not in seen:
                seen.add(key)
                unique_files.append(f)

        for filepath in unique_files:
            stats.files_total += 1
            self._ingest_file(filepath, stats)

        logger.info(
            "Corpus ingest complete: %d/%d files parsed, %d holes, %d panels",
            stats.files_parsed,
            stats.files_total,
            len(stats.holes),
            len(stats.panels),
        )
        return stats

    # ------------------------------------------------------------------

    def _ingest_file(self, filepath: Path, stats: CorpusStatistics) -> None:
        """Parse a single file and append its measurements to *stats*."""
        try:
            result = self.parser.parse(filepath)
        except Exception as exc:  # defensive: parser should not raise, but be safe
            stats.files_failed += 1
            stats.failures.append((str(filepath), f"exception: {exc}"))
            logger.warning("Failed to parse %s: %s", filepath, exc)
            return

        if not result.success or result.geometry is None:
            stats.files_failed += 1
            reason = result.errors[0].error_code if result.errors else "unknown"
            stats.failures.append((str(filepath), reason))
            logger.warning("Skipping %s (parse failed: %s)", filepath, reason)
            return

        stats.files_parsed += 1
        # Build the MGG (exercises the canonical pipeline; also validates the
        # geometry round-trips). Failure here is non-fatal.
        try:
            self.builder.build(result.geometry)
        except Exception as exc:
            logger.debug("MGG build failed for %s (non-fatal): %s", filepath, exc)

        self._extract_measurements(result.geometry, stats)

    # ------------------------------------------------------------------

    def _extract_measurements(
        self, geometry: RawGeometry, stats: CorpusStatistics
    ) -> None:
        """Extract holes, panel dims, setbacks, and spacings from one file."""
        source = geometry.source_file

        # Panel boundary coords for setback computation.
        boundary_coords: list = []
        panel = PanelMeasurement(source_file=source)
        if geometry.panel_boundary is not None:
            pb = geometry.panel_boundary
            boundary_coords = pb.coordinates
            panel.boundary_inferred = pb.inferred
            panel.area_mm2 = pb.area_mm2
            if pb.bounding_box and len(pb.bounding_box) == 4:
                xmin, ymin, xmax, ymax = pb.bounding_box
                panel.width_mm = round(xmax - xmin, 4)
                panel.height_mm = round(ymax - ymin, 4)

        # Thickness: DXF 2D geometry rarely carries thickness; capture it if a
        # layer name or block records it. v0 corpora are 2D, so this stays None
        # unless a thickness annotation convention is present.
        panel.thickness_mm = self._infer_thickness(geometry)

        # Collect holes (CIRCLE entities above the min diameter).
        file_holes: list[HoleMeasurement] = []
        for ent in geometry.entities:
            if ent.entity_type != "CIRCLE" or ent.diameter_mm is None:
                continue
            if ent.diameter_mm < self.min_hole_diameter_mm:
                continue
            center = (
                (float(ent.centroid[0]), float(ent.centroid[1]))
                if ent.centroid
                else (float(ent.coordinates[0]), float(ent.coordinates[1]))
            )
            setback = (
                _edge_setback(center, boundary_coords) if boundary_coords else None
            )
            hole = HoleMeasurement(
                source_file=source,
                diameter_mm=round(float(ent.diameter_mm), 4),
                center=center,
                layer=ent.layer,
                inferred_layer_type=ent.inferred_layer_type,
                edge_setback_mm=setback,
            )
            file_holes.append(hole)

        panel.hole_count = len(file_holes)
        stats.holes.extend(file_holes)
        stats.panels.append(panel)

        # Pairwise spacings: cluster holes of the same diameter that are close
        # together (shelf-pin columns, confirmat / hinge pairs).
        stats.pairwise_spacings_mm.extend(self._pairwise_spacings(file_holes))

    # ------------------------------------------------------------------

    def _pairwise_spacings(self, holes: list[HoleMeasurement]) -> list[float]:
        """Nearest-neighbour spacing between same-diameter holes in one file.

        For each hole, find the nearest other hole of (approximately) the same
        diameter within ``max_pair_spacing_mm``. This recovers the 32mm System
        32 pitch and confirmat/hinge pair spacing without needing labels.
        """
        spacings: list[float] = []
        n = len(holes)
        for i in range(n):
            hi = holes[i]
            best = None
            for j in range(n):
                if i == j:
                    continue
                hj = holes[j]
                if abs(hi.diameter_mm - hj.diameter_mm) > 0.6:
                    continue
                d = math.hypot(
                    hi.center[0] - hj.center[0], hi.center[1] - hj.center[1]
                )
                if d <= self.max_pair_spacing_mm and (best is None or d < best):
                    best = d
            if best is not None and best > 0.1:
                spacings.append(round(best, 4))
        return spacings

    # ------------------------------------------------------------------

    @staticmethod
    def _infer_thickness(geometry: RawGeometry) -> float | None:
        """Attempt to recover panel thickness from layer-name annotations.

        Real corpus files sometimes encode thickness in a layer name like
        ``PANEL_18MM`` or ``THK18``. 2D DXF geometry has no Z, so this is the
        only available cue. Returns ``None`` when no convention is detected.
        """
        import re

        pattern = re.compile(r"(?:THK|PANEL|MAT|T)[_-]?(\d{1,2})(?:MM)?", re.IGNORECASE)
        for ent in geometry.entities:
            m = pattern.search(ent.layer or "")
            if m:
                try:
                    val = float(m.group(1))
                    if 3.0 <= val <= 50.0:
                        return val
                except ValueError:
                    continue
        return None
