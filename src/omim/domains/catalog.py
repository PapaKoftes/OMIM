"""The catalog of OMIM domain specs (data, not code).

Every sheet/panel/cut-from-stock fabrication domain OMIM can apply to, with its
vocabulary, the real datasets + open-source tools to reuse, and an honest status.

Provenance of references:
  * Datasets/tools marked with a verified URL + license were confirmed via web
    research during development (2026). Where a license could not be verified it
    is recorded as UNKNOWN (treat as do-not-ship until checked).
  * status reflects ACTUAL code maturity, not ambition:
      PRODUCTION  - real validated code (panel_furniture, pid)
      EXPERIMENTAL- real code, heuristics uncalibrated on real data
      STUB        - vocabulary + datasets scoped, no inference yet
      PLANNED     - researched + specced, not started
"""

from __future__ import annotations

from omim.domains.registry import (
    DatasetRef,
    DomainRegistry,
    DomainSpec,
    DomainStatus,
    LicenseClass,
    ToolRef,
)

PERM = LicenseClass.PERMISSIVE
COPYLEFT = LicenseClass.COPYLEFT
WEAK = LicenseClass.WEAK_COPYLEFT
NC = LicenseClass.NONCOMMERCIAL
SA = LicenseClass.SHAREALIKE
UNK = LicenseClass.UNKNOWN

# Cross-domain infrastructure reused everywhere (recorded once, referenced often).
_EZDXF = ToolRef("ezdxf", "DXF read/write + entity model", PERM,
                 "https://github.com/mozman/ezdxf", "2D vector parsing")
_SHAPELY = ToolRef("Shapely", "2D geometry / inscribed circle / containment", PERM,
                   "https://github.com/shapely/shapely", "geometry + validation")
_RECTPACK = ToolRef("rectpack", "rectangle bin-packing", PERM,
                    "https://github.com/secnot/rectpack", "rectangular nesting")
_SVGNEST = ToolRef("SVGnest/Deepnest", "irregular polygon nesting", PERM,
                   "https://github.com/Jack000/SVGnest", "irregular nesting baseline")
_NETCAL = ToolRef("netcal", "temperature/isotonic calibration + ECE", PERM,
                  "https://github.com/EFS-OpenSource/calibration-framework",
                  "confidence calibration")


CATALOG: list[DomainSpec] = [
    # ----------------------------------------------------------------- PRODUCTION
    DomainSpec(
        key="panel_furniture",
        title="Panel / cabinet CNC (furniture)",
        status=DomainStatus.PRODUCTION,
        summary="Flat MDF/ply/melamine panels machined on a 3-axis CNC router; the "
                "original OMIM domain.",
        feature_vocabulary=(
            "SHELF_PIN_HOLE", "HINGE_CUP_HOLE", "CONFIRMAT_HOLE", "DOWEL_HOLE",
            "DOWEL_HOLE_LIGHT", "CAM_HOLE", "HARDWARE_HOLE", "THROUGH_HOLE",
            "POCKET", "GROOVE", "INTERNAL_CUTOUT", "PROFILE_CUT",
        ),
        part_types=("SIDE_PANEL", "TOP_PANEL", "BOTTOM_PANEL", "SHELF", "DOOR",
                    "DRAWER_FRONT", "BACK_PANEL", "DIVIDER"),
        join_types=("DOWEL", "CONFIRMAT", "CAM_AND_DOWEL", "EDGE_BUTT"),
        datasets=(
            DatasetRef("(none real)", "no public labeled panel-furniture dataset",
                       UNK, "", "synthetic generator + self-annotate is the path"),
            DatasetRef("ArchCAD-400K", "vector-CAD symbol method precedent (arch)",
                       PERM, "https://huggingface.co/datasets/jackluoluo/ArchCAD",
                       "CC0; pretraining/method, not panel ground truth"),
        ),
        tools=(_EZDXF, _SHAPELY, _RECTPACK, _NETCAL),
        fit="Native fit; the whole pipeline was built here.",
        maturity_note="Features + validation are production-grade and "
                      "catalog-grounded. Part/assembly IDENTIFICATION is "
                      "experimental: hand-set confidences, validated only on "
                      "synthetic geometry, gated behind human review. See "
                      "docs/STRATEGY.md.",
        module="omim.domains.panel",
    ),
    DomainSpec(
        key="pid",
        title="P&ID (piping & instrumentation diagrams)",
        status=DomainStatus.PRODUCTION,
        summary="ISA-5.1 instrument diagrams as graphs; proves the core is "
                "domain-agnostic and has a real-data, non-circular benchmark.",
        feature_vocabulary=("INSTRUMENT", "VALVE", "TRANSMITTER", "CONTROLLER",
                            "SENSOR", "FINAL_ELEMENT"),
        part_types=("LOOP",),
        join_types=("PROCESS_LINE", "SIGNAL_LINE", "CONNECTED_TO"),
        datasets=(
            DatasetRef("PID2Graph", "real human-annotated P&ID graphs", SA,
                       "https://zenodo.org/records/14803338",
                       "CC BY-SA; the de-circularization win — real labels exist"),
        ),
        tools=(ToolRef("networkx", "graph model + graphml IO", PERM,
                       "https://github.com/networkx/networkx", "graph IO"),),
        fit="Real labeled data exists; the one domain with a non-circular benchmark.",
        module="omim.domains.pid",
    ),
    # --------------------------------------------------------------- EXPERIMENTAL
    DomainSpec(
        key="digital_fabrication",
        title="Tab-and-slot digital fabrication (CNC ply / laser)",
        status=DomainStatus.STUB,
        summary="WikiHouse / OpenDesk / AtFAB-style CNC-cut plywood where joints "
                "live IN the 2D geometry (tabs/slots) — the easiest place to learn "
                "2D->3D assembly, and open CC data actually exists.",
        feature_vocabulary=("TAB", "SLOT", "FINGER_JOINT", "MORTISE", "TENON",
                            "T_SLOT", "LIVING_HINGE", "BOLT_HOLE", "CUTOUT"),
        part_types=("PANEL", "RIB", "SPACER", "CONNECTOR", "FRAME"),
        join_types=("TAB_SLOT", "FINGER_JOINT", "MORTISE_TENON", "T_SLOT_BOLT"),
        datasets=(
            DatasetRef("WikiHouse blocks", "openly-licensed CNC building blocks",
                       SA, "https://www.wikihouse.cc/", "CC; real cut files"),
            DatasetRef("OpenDesk / AtFAB", "CC-licensed CNC furniture cut files",
                       SA, "https://www.opendesk.cc/", "license varies; verify each"),
        ),
        tools=(
            ToolRef("Boxes.py", "parametric finger-joint/tab-slot box generator",
                    COPYLEFT, "https://github.com/florianfesti/boxes",
                    "synthetic joint geometry generator (GPL — reference only)"),
            _SVGNEST, _EZDXF, _SHAPELY,
        ),
        fit="STRONG: joints are in the geometry (easier 2D->3D than furniture) AND "
            "open CC data exists to validate the assembly inference.",
        blockers=("joint (tab/slot) detector not implemented",
                  "CC datasets need download + license-per-design check"),
    ),
    # ------------------------------------------------------------------- STUB
    DomainSpec(
        key="sheet_metal",
        title="Sheet-metal fabrication / DFM",
        status=DomainStatus.STUB,
        summary="Punched/laser-cut + bent sheet metal; flat-pattern features plus "
                "bend lines. A real DFM-dataset wave is happening here.",
        feature_vocabulary=("BEND_LINE", "FLANGE", "HEM", "LOUVER", "TAB",
                            "CUTOUT", "HOLE", "NOTCH", "DIMPLE"),
        part_types=("BRACKET", "ENCLOSURE_PANEL", "CHASSIS_PART"),
        join_types=("BEND", "WELD", "RIVET", "TAB_SLOT"),
        datasets=(
            DatasetRef("BenDFM", "~20k sheet-metal bending DFM parts; graph reps win",
                       UNK, "https://arxiv.org/abs/2603.13102",
                       "license unverified — confirm before use"),
        ),
        tools=(
            ToolRef("FreeCAD SheetMetal Workbench", "bend/flange/unfold features",
                    WEAK, "https://github.com/shaise/FreeCAD_SheetMetal",
                    "flat-pattern + bend feature reference (LGPL — dep only)"),
            _SHAPELY, _SVGNEST,
        ),
        fit="STRONG conceptually (flat pattern + bend lines is exactly 2.5D); but "
            "bend data is the 3rd dimension, partly outside pure-DXF reach.",
        blockers=("bend-line semantics need a layer/Z convention",
                  "BenDFM license unverified; it is 3D not DXF"),
    ),
    DomainSpec(
        key="packaging_dieline",
        title="Packaging dielines (corrugated / folding carton)",
        status=DomainStatus.STUB,
        summary="Flat dielines that fold into boxes; cut vs crease vs perf lines "
                "are the whole game, codified by FEFCO/ECMA standards.",
        feature_vocabulary=("CUT_LINE", "CREASE_LINE", "PERFORATION", "GLUE_TAB",
                            "BLEED", "FOLD_LINE"),
        part_types=("PANEL", "FLAP", "TAB", "LID"),
        join_types=("FOLD", "GLUE", "LOCK_TAB"),
        datasets=(
            DatasetRef("FEFCO/ECMA box codes", "standard box-style taxonomy",
                       UNK, "https://www.fefco.org/",
                       "standard codes (not a dataset); vocabulary anchor"),
        ),
        tools=(_EZDXF, _SHAPELY,
               ToolRef("svgpathtools", "SVG path parsing", PERM,
                       "https://github.com/mathandy/svgpathtools",
                       "dieline vector parsing")),
        fit="STRONG: dieline = flat part with typed lines (cut/crease/perf); a clean "
            "fit for line-type classification + fold-graph assembly.",
        blockers=("crease/cut/perf line classifier not implemented",
                  "no open labeled dieline dataset found"),
    ),
    DomainSpec(
        key="stone_glass",
        title="Stone / glass / solid-surface CNC (countertops, waterjet)",
        status=DomainStatus.STUB,
        summary="Flat slab with cutouts (sink, cooktop, faucet) + edge profiles; "
                "a near-direct analogue of the panel pipeline.",
        feature_vocabulary=("SINK_CUTOUT", "FAUCET_HOLE", "COOKTOP_CUTOUT",
                            "EDGE_PROFILE", "SEAM"),
        part_types=("COUNTERTOP", "SPLASHBACK", "ISLAND_TOP"),
        join_types=("SEAM", "MITER"),
        datasets=(DatasetRef("(none found)", "no open slab-layout dataset", UNK, ""),),
        tools=(_EZDXF, _SHAPELY, _SVGNEST),
        fit="STRONG: flat part + cutouts + edges maps almost 1:1 onto panel features.",
        blockers=("cutout-type (sink/faucet) classifier not implemented",
                  "no open dataset"),
    ),
    DomainSpec(
        key="pcb_fab",
        title="PCB fabrication (panelized boards)",
        status=DomainStatus.STUB,
        summary="Gerber/Excellon drill + route of board panels; mature open parsers "
                "make this low-effort to wire, though it's a vocabulary stretch.",
        feature_vocabulary=("DRILL_HOLE", "ROUTE_PATH", "FIDUCIAL", "MOUSE_BITE",
                            "V_SCORE", "COPPER_POUR"),
        part_types=("BOARD", "PANEL_RAIL"),
        join_types=("MOUSE_BITE", "V_SCORE", "TAB_ROUTE"),
        datasets=(DatasetRef("(none labeled)", "no open PCB-feature dataset", UNK, ""),),
        tools=(
            ToolRef("gerbonara", "Gerber/Excellon parser", PERM,
                    "https://github.com/jaseg/gerbonara", "PCB vector parsing"),
            ToolRef("KiKit", "PCB panelization (mouse-bites, tabs, V-scores)",
                    COPYLEFT, "https://github.com/yaqwsx/KiKit",
                    "panelization feature reference (GPL — reference only)"),
        ),
        fit="PARTIAL: format is different (Gerber not DXF) but the graph/feature/"
            "panelization model transfers; mature parsers exist.",
        blockers=("Gerber/Excellon ingest adapter not written",
                  "vocabulary is electronics, not cut-stock"),
    ),
    # ------------------------------------------------------------------- PLANNED
    DomainSpec(
        key="mass_timber",
        title="Mass timber building panels (CLT / SIP / NLT)",
        status=DomainStatus.PLANNED,
        summary="Wall/floor/roof panels for CNC timber processing; BTLx is an open "
                "interchange format worth parsing.",
        feature_vocabulary=("WINDOW_CUTOUT", "DOOR_CUTOUT", "SERVICE_HOLE",
                            "REBATE", "DADO", "CONNECTOR_PATTERN"),
        part_types=("WALL_PANEL", "FLOOR_PANEL", "ROOF_PANEL"),
        join_types=("SCREW_PATTERN", "SPLINE", "HALF_LAP"),
        datasets=(DatasetRef("BTLx examples", "open timber interchange format",
                             UNK, "https://www.design2machine.com/btlx/",
                             "format spec; sample files exist, license per-source"),),
        tools=(_EZDXF, _SHAPELY),
        fit="PARTIAL: building-scale panels, BTLx not DXF; vocabulary overlaps "
            "(cutouts/rebates) but joinery is structural.",
        blockers=("BTLx parser not written", "no open labeled dataset"),
    ),
    DomainSpec(
        key="apparel_textile",
        title="Apparel / textile cut markers",
        status=DomainStatus.PLANNED,
        summary="Garment pattern pieces nested on fabric (markers/lay plans); "
                "fundamentally a nesting + part-recognition problem.",
        feature_vocabulary=("NOTCH", "DRILL_HOLE", "GRAINLINE", "SEAM_ALLOWANCE"),
        part_types=("PATTERN_PIECE",),
        join_types=("SEAM",),
        datasets=(DatasetRef("(none open CAD)", "no open AAMA/ASTM marker dataset",
                            UNK, ""),),
        tools=(_SVGNEST, ToolRef("libnest2d", "irregular nesting (C++)", WEAK,
                                 "https://github.com/tamasmeszaros/libnest2d",
                                 "nesting (LGPL — dep only)")),
        fit="PARTIAL: pure nesting fits; but DXF-AAMA format + textile vocab are a "
            "domain unto themselves.",
        blockers=("DXF-AAMA/ASTM ingest not written", "no open dataset"),
    ),
    DomainSpec(
        key="signage",
        title="Signage / acrylic / engraving",
        status=DomainStatus.PLANNED,
        summary="CNC/laser-cut letters and acrylic panels; cut-vs-engrave layer "
                "convention is the main signal.",
        feature_vocabulary=("CUT_CONTOUR", "ENGRAVE_REGION", "SCORE_LINE",
                            "STANDOFF_HOLE", "WEED_LINE"),
        part_types=("LETTER", "PANEL", "BACKER"),
        join_types=("STANDOFF", "ADHESIVE"),
        datasets=(DatasetRef("(none)", "no open sign-cut dataset", UNK, ""),),
        tools=(_EZDXF, _SHAPELY),
        fit="PARTIAL: simple (cut vs engrave layers) but low structural complexity; "
            "good easy demo domain.",
        blockers=("no dataset", "low complexity — limited research value"),
    ),
    DomainSpec(
        key="boatbuilding",
        title="Stitch-and-glue plywood boatbuilding",
        status=DomainStatus.PLANNED,
        summary="CNC-cut plywood boat kits (hull panels, bulkheads, frames, stitch "
                "holes) — a niche but real panel-construction domain.",
        feature_vocabulary=("STITCH_HOLE", "SCARF_JOINT", "LIMBER_HOLE", "CUTOUT"),
        part_types=("HULL_PANEL", "BULKHEAD", "FRAME", "STATION"),
        join_types=("STITCH", "SCARF", "EPOXY_FILLET"),
        datasets=(DatasetRef("(scattered CC plans)", "some open boat plans exist",
                            UNK, "", "no labeled corpus"),),
        tools=(_EZDXF, _SHAPELY),
        fit="NICHE: real panel construction, but small community + scattered data.",
        blockers=("no labeled dataset", "developable-surface unfolding is bespoke"),
    ),
    DomainSpec(
        key="mechanical_mfr",
        title="Mechanical machined parts (taxonomy reference)",
        status=DomainStatus.PLANNED,
        summary="3D B-rep machining-feature recognition — OMIM is 2D so the GEOMETRY "
                "is out of scope, but the feature TAXONOMY is a reusable reference.",
        feature_vocabulary=("HOLE", "POCKET", "SLOT", "CHAMFER", "STEP", "BOSS"),
        part_types=(),
        join_types=(),
        datasets=(
            DatasetRef("MFCAD++", "59k labeled machining-feature B-rep models", PERM,
                       "https://gitlab.com/qub_femg/machine-learning/mfcad2-dataset",
                       "MIT; taxonomy reference (adapter exists: omim.datasets.mfcad)"),
            DatasetRef("Fusion360 Gallery", "real-design CAD segmentation", NC,
                       "https://github.com/AutodeskAILab/Fusion360GalleryDataset",
                       "non-commercial — eval only"),
        ),
        tools=(ToolRef("AAGNet", "B-rep attributed-adjacency-graph MFR GNN", PERM,
                       "https://github.com/whjdark/AAGNet",
                       "MIT; graph-formulation method reference"),),
        fit="STRETCH for geometry (3D B-rep != 2D DXF); STRONG as a taxonomy/method "
            "reference (already wired via omim.datasets.mfcad).",
        blockers=("3D geometry not ingestible by a 2D pipeline (by design)",),
    ),
    DomainSpec(
        key="scenery_flats",
        title="Scenery / exhibition / set flats",
        status=DomainStatus.PLANNED,
        summary="CNC-cut theatrical/trade-show panels (flats, stiffeners, cutouts).",
        feature_vocabulary=("MOUNTING_HOLE", "CUTOUT", "STIFFENER_SLOT"),
        part_types=("FLAT", "STIFFENER", "TOGGLE"),
        join_types=("BOLT", "CLEAT"),
        datasets=(DatasetRef("(none)", "no open dataset", UNK, ""),),
        tools=(_EZDXF, _SHAPELY),
        fit="NICHE/STUB: real but tiny; low priority, listed for completeness.",
        blockers=("no dataset", "very niche"),
    ),
]


def build_registry() -> DomainRegistry:
    """Construct the canonical OMIM domain registry."""
    return DomainRegistry(CATALOG)
