# Domain Expansion Roadmap

OMIM's core (parse → graph → features → validation → nesting → label → dataset)
is domain-agnostic. A new domain is mostly **data**: a feature/part vocabulary, a
ruleset, the datasets to ground it, and the open-source tools to reuse. This
roadmap maps every domain OMIM can apply to, ordered by leverage. The live,
queryable version is the registry:

```bash
omim domains                       # all domains + status + has-real-data
omim domains --key digital_fabrication   # full detail for one
```
```python
from omim.domains import build_registry, DomainStatus
reg = build_registry()
reg.by_status(DomainStatus.STUB)   # shovel-ready next domains
reg.with_real_data()               # where usable datasets already exist
```

## Status legend (honest, not aspirational)

| Status | Meaning |
|---|---|
| **production** | Real, validated, well-tested code path |
| **experimental** | Real code; heuristics not yet calibrated on real data |
| **stub** | Vocabulary + datasets scoped; **no inference yet** |
| **planned** | Researched + specced; not started |

## The 13 domains

| Domain | Status | Real data? | Why it fits |
|---|---|---|---|
| Panel / cabinet CNC | production | synthetic only | The original domain; whole pipeline built here |
| P&ID (ISA-5.1) | production | **yes** (PID2Graph) | Proves core is domain-agnostic; non-circular benchmark |
| Tab-and-slot digital fab | stub | **yes** (WikiHouse/OpenDesk) | Joints are *in the geometry*; open CC data exists |
| Sheet-metal DFM | stub | unverified (BenDFM) | Flat pattern + bend lines = 2.5D; DFM wave is hot |
| Packaging dielines | stub | no | Cut/crease/perf line typing + fold graph; clean fit |
| Stone / glass / countertop | stub | no | Flat slab + cutouts + edges ≈ panels 1:1 |
| PCB fabrication | stub | no | Mature Gerber parsers; panelization model transfers |
| Mass timber (CLT/SIP) | planned | unverified (BTLx) | Building-scale panels; BTLx not DXF |
| Apparel / textile markers | planned | no | Pure nesting fits; AAMA format is its own world |
| Signage / acrylic | planned | no | Cut-vs-engrave layers; easy demo, low complexity |
| Boatbuilding (stitch-glue) | planned | no | Real panel construction; niche, scattered data |
| Mechanical MFR (taxonomy) | planned | **yes** (MFCAD++) | 3D geometry out of scope; taxonomy reusable |
| Scenery / set flats | planned | no | Real but tiny; listed for completeness |

## Recommended order (by leverage, not breadth)

### 1. Tab-and-slot digital fabrication — **do this next**
The single best second domain. Unlike furniture (where assembly is implied by
invisible dowel positions), the joints are **drawn in the 2D geometry** as
tabs/slots — so "2D parts → 3D assembly" (the hardest, most valuable inference)
is *easier* here, not harder. And open CC-licensed cut files exist
(WikiHouse, OpenDesk, AtFAB), so the assembly heuristics can finally be validated
against real data — closing the gap that hangs over every other domain.

- **Reuse:** `Boxes.py` (GPL — reference only, for synthetic joint geometry),
  SVGnest/Deepnest (nesting), ezdxf + Shapely (already deps).
- **New work:** a tab/slot detector (matching slot↔tab by geometry), a joint
  vocabulary, a CC-data ingest + license-per-design check.

### 2. Packaging dielines &nbsp;/&nbsp; 3. Stone-glass countertops
Both are clean fits with low conceptual risk:
- **Dielines** = a flat part whose lines are typed (cut / crease / perforation),
  folding into a box — a line-type classifier + a fold graph. Vocabulary anchored
  by FEFCO/ECMA box codes.
- **Countertops** = a flat slab with cutouts (sink/faucet/cooktop) + edge
  profiles — maps almost 1:1 onto the existing panel feature model.
Both lack open datasets, so they'd run on synthetic + self-annotate (the panel
playbook).

### 4. Sheet-metal DFM
Conceptually strong (flat pattern + bend lines is exactly the 2.5D model), and
the DFM-dataset wave (BenDFM) validates the direction. Blocked on: bend semantics
need a layer/Z convention, and BenDFM is 3D with an unverified license — confirm
before relying on it.

### 5. PCB fabrication
Low-effort to wire because mature open parsers exist (`gerbonara` MIT for
Gerber/Excellon; KiKit GPL for panelization reference). It's a vocabulary stretch
(electronics, not cut-stock) but the graph/feature/panelization model transfers.

### Later / opportunistic
Mass timber (BTLx parser), apparel (DXF-AAMA), signage (easy demo), boatbuilding
(niche). Mechanical MFR stays a **taxonomy reference only** — already wired via
`omim.datasets.mfcad` — because 3D B-rep geometry is out of a 2D pipeline's scope
by design.

## Cross-domain infrastructure to reuse (don't reinvent)

| Need | Reuse | License |
|---|---|---|
| DXF parsing | ezdxf | permissive |
| 2D geometry / inscribed circle | Shapely ≥ 2.1 | permissive |
| Rectangular nesting | rectpack | permissive |
| Irregular nesting | SVGnest / Deepnest | permissive |
| Confidence calibration | netcal (or sklearn.isotonic) | permissive |
| Gerber/Excellon (PCB) | gerbonara | permissive |
| Machining-feature taxonomy/method | MFCAD++, AAGNet | permissive |

GPL/LGPL tools (Boxes.py, KiKit, FreeCAD SheetMetal, libnest2d) are **reference or
unmodified-dependency only** — never vendored into Apache-2.0 source.

## The cross-cutting gate (unchanged)

Every domain's *identification* quality is gated on real labeled data. P&ID and
(soon) digital fabrication are the only domains where real data exists today —
which is exactly why they're the highest-leverage places to prove OMIM's thesis.
The strategic position is not "the rule engine" but **the open labeled
dataset/benchmark for sheet-and-panel fabrication AI** — the asset nobody else has
and that even drawing-reading VLMs will need.
