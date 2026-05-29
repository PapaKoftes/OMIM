# Manufacturing Conventions

Version: v0.1.0  
Section: 06_REAL_WORLD_GROUNDING  

See also: [[06_REAL_WORLD_GROUNDING/Cabinet_Standards]], [[03_INTERFACES/Parser_Interface]], [[04_ONTOLOGY/Feature_Taxonomy]]

---

## Purpose

Documents real-world manufacturing conventions that inform DXF interpretation, layer classification, and semantic inference. These are not formal standards — they are established practices in the CNC panel processing industry.

---

## DXF Layer Naming Conventions

DXF files from cabinet CAD/CAM software use layer names to indicate machining intent. These are not standardized across all software but represent dominant conventions.

### Common Layer Name Conventions

```yaml
# Parser layer_conventions (default_layer_map)
# Case-insensitive, prefix-matched

CUT:
  - "CUT"        # Generic cut operation
  - "CUT_"       # Cut with suffix (e.g., CUT_PROFILE)
  - "PROFILE"    # Outer profile cut
  - "OUTLINE"    # Panel outline
  - "OUTER"      # Outer contour
  - "CONTOUR"    # General contour

DRILL:
  - "DRILL"      # Drilling operations
  - "HOLE"       # Hole operations
  - "BORE"       # Boring (large holes)
  - "PUNCH"      # Punching operations

POCKET:
  - "POCKET"     # Pocket milling
  - "GROOVE"     # Linear groove
  - "SLOT"       # Slot milling
  - "DADO"       # Dado cut (North American term for groove)
  - "RABBET"     # Rabbet/rebate cut

BORDER:
  - "BORDER"     # Sheet border/stock boundary
  - "SHEET"      # Sheet boundary
  - "STOCK"      # Material stock outline
  - "MATERIAL"   # Material boundary

ENGRAVE:
  - "ENGRAVE"    # Engraving
  - "ETCH"       # Etching/scoring
  - "SCORE"      # Score line
```

**Note**: Layer names vary by CAD software. eCabinet Systems, Cabinet Vision, Mozaik, KCD Software all have different defaults. OMIM uses prefix matching rather than exact matching.

---

## CAD/CAM Software Layer Conventions

### Cabinet Vision (Planit Solutions)

```
Layers used:
  PANEL_OUTLINE    → BORDER
  DRILL_THRU       → DRILL (through holes)
  DRILL_BLIND      → DRILL (blind holes)
  ROUT_THRU        → CUT (through routing)
  ROUT_POCKET      → POCKET
  HINGE_CUP        → DRILL (explicitly named)
```

### eCabinet Systems

```
Layers used:
  CUT_THROUGH      → CUT
  DRILLING         → DRILL
  POCKET_ROUTE     → POCKET
  BORDER           → BORDER
```

### Mozaik Software

```
Layers used:
  PROFIL           → CUT (German/French software)
  BOHREN           → DRILL (German: drilling)
  FRAESEN          → POCKET (German: milling)
  PANEL            → BORDER
```

---

## DXF Origin Conventions

Cabinet DXF files use one of two origin conventions:

### Convention 1: Bottom-Left Origin (Most Common)

Panel placed with lower-left corner at (0, 0). Positive X = rightward, positive Y = upward. This is the standard for most European CAM software.

```
(0,0) ──────── (width, 0)
  |                  |
  |                  |
(0,height) ─ (width, height)
```

### Convention 2: Center Origin

Panel centered at (0, 0). Less common; used by some robotics/automation workflows.

**OMIM handling**: If origin is detected as center (negative coordinates in all quadrants), issue `warning: "non_standard_origin"` but continue processing. Coordinates remain as-is in RawGeometry.

---

## Machining Order Conventions

CNC programs typically machine in this order:
1. Drilling operations (fastest, no tool changes needed on multi-spindle)
2. Pocketing/grooving (routing passes)
3. Profile cutting last (prevents part movement during earlier operations)

**OMIM implication**: Profile cut contours are typically the outermost closed contour in a DXF. This is used as a classification hint in the semantic layer.

---

## Panel Orientation Convention

Panels are designed and measured in "face up" orientation — the visible face (A-face) is the top surface in 2D DXF representation. Hardware holes are measured from this reference.

**Edge distance convention**: All measurements reference the closest edge, not a fixed edge.

---

## Hinge Placement Rules (Shop Practice)

Standard cabinet hinge placement (not a formal standard — industry convention):

```
For doors up to 1000mm tall: 2 hinges
For doors 1000–1500mm:       3 hinges
For doors > 1500mm:          4 hinges
Top hinge from top edge:     typically 80–100mm (center of cup)
Bottom hinge from bottom:    typically 80–100mm (center of cup)
```

**OMIM v0 status**: Hinge count rules not validated in v0.1.0. Only per-hole geometry is checked (MFG-006).

---

## Shelf Pin Placement Rules (Shop Practice)

```
First row from panel top/bottom:  37mm or 57mm (row offset)
Subsequent rows:                  32mm increments
Column spacing:                   96mm or 64mm
Column setback from panel edge:   37mm (standard System 32)
```

**OMIM validation**: MFG-005 checks 32mm spacing within a detected collinear group. Row offsets are not checked in v0.1.0.

---

## Common DXF Authoring Errors

Based on patterns observed in real cabinet DXF files — these inform GEO-001 to GEO-005:

| Error | Frequency | OMIM Rule |
|-------|----------|---------|
| Open contour (LWPOLYLINE not closed) | Common | GEO-001 |
| Duplicate circles (copied without deleting original) | Common | GEO-005 |
| Zero-length lines (snap-to artifacts) | Occasional | GEO-003 |
| Off-origin geometry (everything at -10000mm) | Rare | GEO-004 |
| Self-intersecting profile from manual editing | Rare | GEO-002 |
| Holes outside panel boundary (coordinate error) | Occasional | MFG-001 |

---

## Material-Specific Machining Notes

### MDF (Medium Density Fibreboard)

- Abrasive to tooling — faster tool wear than solid wood
- Excellent surface for routing (no grain direction effects)
- Dust: very fine; extraction required
- Min edge clearance: 8mm (MFG-001 default) calibrated for MDF

### Particleboard / Chipboard

- More brittle at edges than MDF; higher tear-out risk
- Standard edge clearance: 8–10mm
- Max drill diameter near edges: reduced compared to MDF

### Melamine-Faced Panels

- Melamine surface is brittle — compression spiral bits required
- Geometry rules identical to base material (MDF or particleboard substrate)
- OMIM treats melamine and uncoated panels identically at geometry level

### Plywood

- Grain direction affects routing direction — not captured in 2D DXF
- Stronger than MDF/particleboard for the same thickness
- Edge clearance can be reduced to 6mm for birch plywood (not in v0.1.0 — uses 8mm default)
