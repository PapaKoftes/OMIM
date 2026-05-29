# Feature Taxonomy

Version: v0.1.0  
Section: 04_ONTOLOGY  

See also: [[04_ONTOLOGY/Manufacturing_Ontology]], [[06_REAL_WORLD_GROUNDING/Hardware_System_References]]

---

## Class: HOLE_FEATURES

### THROUGH_HOLE
- **Definition**: Circular cutout passing completely through the panel
- **Detection**: Circle entity, cutting layer, diameter within range
- **Diameter range**: 2mm – 60mm (general; specific subtypes below)
- **Confidence**: 0.6–0.9
- **Source**: ANSI/ASME Y14.5

### BLIND_HOLE
- **Definition**: Circular hole that does not pass completely through
- **Detection**: Requires depth metadata; often inferred from context
- **Confidence**: 0.5–0.8 (layer convention + context)

### COUNTERSINK
- **Definition**: Conical enlargement at top of hole for flush fastener seating (flat-head screw recesses)
- **Detection**: Concentric geometry — small pilot circle + larger conical outline, or layer named "V_SINK"; ratio outer_diameter / inner_diameter ≈ 2.0 for standard 90° countersink
- **Confidence**: 0.75–0.90
- **Source**: ISO 10642:2004 (hexagon socket countersunk head screws)

### COUNTERBORE
- **Definition**: Cylindrical (flat-bottomed) enlargement at top of hole for socket-head screws
- **Detection**: Concentric circles where outer/inner diameter ratio matches standard counterbore specs; outer circle substantially larger with flat shoulder implied; distinct from COUNTERSINK by lack of V-taper
- **Confidence**: 0.70–0.85
- **Source**: ISO 6194

### SHELF_PIN_HOLE ← Primary panel feature
- **Definition**: 5mm hole for adjustable shelf support pins; follows 32mm grid
- **Diameter**: 5.0mm ± 0.2mm (standard)
- **Detection**: 5mm circles, collinear, spaced 32mm ± 1mm apart, minimum 3 in a row
- **Pattern**: European Rasterbohrsystem (32mm modular system)
- **Confidence**: single_hole=0.75 / confirmed_pattern=0.92
- **Source**: Hettich shelf pin systems; Blum catalog; DIN 68xxx furniture hardware

### HINGE_CUP_HOLE ← Primary panel feature
- **Definition**: Large circular recess for concealed hinge cup (Blum/Grass style)
- **Diameter**: 35.0mm ± 0.5mm (standard), 26mm for mini hinges
- **Edge distance**: 22.5mm from panel edge (Blum CLIP top standard)
- **Detection**: Circle diameter 34–36mm, positioned near panel edge
- **Confidence**: 0.88–0.96
- **Source**: Blum CLIP top BLUMOTION spec; DIN 68xxx furniture hardware

### CONFIRMAT_HOLE ← Primary panel feature
- **Definition**: Stepped hole for Confirmat (Euro) screw fastener
- **Diameter**: Body=7.0mm; Head=10mm (stepped)
- **Detection**: 7mm circle or stepped geometry on joining faces
- **Confidence**: 0.80–0.92
- **Source**: HÄFELE Confirmat screw specifications

### DOWEL_HOLE
- **Definition**: Cylindrical hole for wooden dowel alignment/joining
- **Diameter**: 8mm (standard), 10mm (heavy duty), 6mm (light duty)
- **Detection**: 8mm or 10mm circles in pairs/groups near panel edges
- **Confidence**: 0.70–0.85
- **Source**: ISO 10140 — Dowel pins; DIN 7 — Dowel pins

### HARDWARE_HOLE
- **Definition**: Generic hole for hardware mounting (handles, locks, etc.)
- **Diameter**: 20–50mm range
- **Detection**: Large circles not matching other known patterns
- **Confidence**: 0.50–0.70

---

## Class: MILLED_FEATURES

### POCKET
- **Definition**: Bounded, closed milled recess that does not pass through
- **Minimum dimensions**: Width ≥ tool_diameter × 1.2, depth < panel_thickness
- **Confidence**: 0.75–0.90
- **Source**: CNC routing fundamentals; Machinery's Handbook §pocket milling

### THROUGH_POCKET
- **Definition**: Milled recess passing completely through (internal cutout)
- **Detection**: Closed contour fully inside panel boundary on cut layer
- **Confidence**: 0.85–0.95

### GROOVE ← Common joinery feature
- **Definition**: Long, narrow linear or curved milled slot for joinery or panel insertion
- **Typical**: Width 4–15mm, depth 6–12mm, length >> width (aspect ratio > 5)
- **Confidence**: 0.75–0.90
- **Source**: Woodworking joinery; DIN 68752 (tongue and groove boards)

### DADO
- **Definition**: Groove cut perpendicular to panel's primary dimension
- **Detection**: GROOVE perpendicular to panel's long axis
- **Confidence**: 0.65–0.85

### RABBET (REBATE)
- **Definition**: L-shaped notch along panel edge or end
- **Detection**: Open-sided rectangular recess along panel edge
- **Typical**: Depth × width 9×12mm, 12×12mm (matches panel thickness)
- **Confidence**: 0.75–0.88

### OPEN_SLOT
- **Definition**: Open-ended slot milled from panel edge inward
- **Detection**: U-shaped or elongated open contour opening at panel boundary
- **Confidence**: 0.78–0.90

---

## Class: PROFILE_FEATURES

### PROFILE_CUT (OUTER_CONTOUR)
- **Definition**: Outer boundary cut producing final panel shape
- **Detection**: Outermost closed contour on cut layer
- **Note**: Every panel has exactly one profile cut
- **Confidence**: 0.95+

### INTERNAL_CUTOUT
- **Definition**: Closed internal profile cut (creates window/opening in panel)
- **Detection**: Closed contour fully inside panel boundary, on cut layer
- **Confidence**: 0.88–0.96

### CHAMFER
- **Definition**: Angled cut removing a corner (45° standard)
- **Detection**: Diagonal line segment at corner intersection
- **Confidence**: 0.70–0.85
- **Source**: ISO 286

### FILLET
- **Definition**: Rounded corner (concave arc at internal corner)
- **Detection**: Arc entity at internal corner with radius matching tool radius
- **Confidence**: 0.75–0.88
- **Source**: ISO 2768

---

## Special Values

### UNKNOWN_FEATURE
- **Assigned when**: No hypothesis exceeds confidence threshold of 0.30
- **Handling**: Included in benchmark as valid classification target; flags for human review
- **NOTE**: This is a legitimate label, not an error condition

---

## Out-of-Scope Features (v0.1.0)

These feature types are explicitly excluded from the v0.1.0 ontology:

### EDGE_BANDING
- **Definition**: Thin strip of material applied to exposed panel edges
- **Why excluded**: Edge banding is applied after CNC machining; it is a post-processing operation, not a geometric feature present in the DXF. Edge banding cannot be detected from 2D cutting geometry. Detecting it from DXF would require inferring which edges are "exposed" from the assembly context — which requires multi-panel reasoning not in scope for v0.1.
- **v0.2 consideration**: Could be inferred from panel type + edge accessibility in an assembly graph

### ENGRAVING / MARKING
- **Why excluded**: Laser engraving, V-carving, and surface marking are non-structural operations. They appear in DXF on dedicated layers (ENGRAVE, MARK) but do not affect manufacturability in the scope of OMIM v0.1.
- **Impact**: Entities on engraving layers are parsed as `inferred_layer_type="engrave"` but not classified as features.

### ASSEMBLY HARDWARE (GENERAL)
- **Why excluded**: Cam-lock fittings, barrel nuts, handles, drawer slides, and other hardware beyond the core set (hinge cups, confirmat, shelf pins, dowels) are deferred. The core set covers ~85% of cabinet joinery hardware.
- **Later expansion**: Each new hardware type requires a validated reference in a manufacturer catalog before being added to the ontology.

---

## Confidence Summary Table

| Feature | Min Conf | Max Conf | Primary Evidence |
|---------|----------|----------|-----------------|
| SHELF_PIN_HOLE | 0.75 | 0.95 | Diameter + 32mm pattern |
| HINGE_CUP_HOLE | 0.88 | 0.96 | Diameter + edge proximity |
| CONFIRMAT_HOLE | 0.80 | 0.92 | Diameter match |
| DOWEL_HOLE | 0.70 | 0.85 | Diameter + position |
| PROFILE_CUT | 0.95 | 0.99 | Outermost contour |
| GROOVE | 0.75 | 0.90 | Aspect ratio + orientation |
| RABBET | 0.75 | 0.88 | Open contour at edge |
| POCKET | 0.75 | 0.90 | Closed contour + layer |
| THROUGH_HOLE | 0.60 | 0.90 | Diameter range exclusion |
