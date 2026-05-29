# Operation Taxonomy

Version: v0.1.0  
Section: 04_ONTOLOGY  

See also: [[04_ONTOLOGY/Feature_Taxonomy]], [[06_REAL_WORLD_GROUNDING/Cabinet_Standards]]

---

## Purpose

Defines the 4 manufacturing operation types used in OMIM v0.1.0. Operations are inferred from feature types — they are NOT parsed from DXF.

---

## DRILLING

- **Definition**: Vertical hole-making operation using rotating drill bit
- **Produces features**: THROUGH_HOLE, BLIND_HOLE, COUNTERSINK, COUNTERBORE, SHELF_PIN_HOLE, HINGE_CUP_HOLE, CONFIRMAT_HOLE, DOWEL_HOLE
- **Parameters**: diameter, depth, RPM, feed rate, tooling type
- **Machine type**: Vertical CNC drill, multi-spindle drill, Drill+Router combo
- **Source**: Machining handbooks; ISO 15487 — Twist drills
- **Inference rule**: Any circle entity → likely requires DRILLING

---

## CNC_ROUTING

- **Definition**: 2.5D CNC milling/routing operation following a defined path
- **Produces features**: POCKET, GROOVE, DADO, RABBET, OPEN_SLOT, THROUGH_POCKET
- **Parameters**: path, depth, tool_diameter, RPM, feed rate, passes
- **Machine type**: CNC router (3-axis)
- **Source**: CNC routing fundamentals
- **Inference rule**: Any non-circular closed/open milled contour → likely CNC_ROUTING

---

## PROFILE_CUTTING

- **Definition**: Following outer or inner profile contour to cut out the panel shape
- **Produces features**: PROFILE_CUT, INTERNAL_CUTOUT
- **Parameters**: contour, depth (through), tool_diameter, tabs/bridges
- **Machine type**: CNC router (3-axis)
- **Note**: Includes tab/bridge placement to prevent part movement during cut
- **Inference rule**: Outermost contour or closed internal cutout → PROFILE_CUTTING

---

## NESTING

- **Definition**: Placement optimization of multiple panel profiles onto a sheet
- **Note**: This is NOT a machining operation — it is a pre-processing step
- **Applies to**: Entire panel set (batch context, not single panel)
- **Source**: Nesting theory; OpenNest; SVGnest; DeepNest
- **v0 status**: Recognized as concept; not fully modeled until NestingNode added in v0.2
- **Inference rule**: Any panel with a PROFILE_CUT requires NESTING consideration

---

## Feature-to-Operation Deterministic Mapping

```python
FEATURE_TO_OPERATIONS = {
    "THROUGH_HOLE": ["DRILLING"],
    "BLIND_HOLE": ["DRILLING"],
    "COUNTERSINK": ["DRILLING"],
    "COUNTERBORE": ["DRILLING"],
    "SHELF_PIN_HOLE": ["DRILLING"],
    "HINGE_CUP_HOLE": ["DRILLING"],  # technically boring, modeled as drilling in v0
    "CONFIRMAT_HOLE": ["DRILLING"],
    "DOWEL_HOLE": ["DRILLING"],
    "GROOVE": ["CNC_ROUTING"],
    "DADO": ["CNC_ROUTING"],
    "POCKET": ["CNC_ROUTING"],
    "RABBET": ["CNC_ROUTING"],
    "OPEN_SLOT": ["CNC_ROUTING"],
    "THROUGH_POCKET": ["CNC_ROUTING"],
    "PROFILE_CUT": ["PROFILE_CUTTING"],
    "INTERNAL_CUTOUT": ["PROFILE_CUTTING"],
}
# Every panel with any feature requires "NESTING" (for multi-panel sheets)
```

This mapping is used by BENCH-003 (Operation Inference) as ground truth.

---

## Out of Scope (v0)

### EDGE_BANDING
- Post-routing operation; not representable in DXF geometry
- Deferred to v0.2 if DXF metadata allows depth annotations

### 5-AXIS_MILLING
- Out of domain scope for v0

### TURNING / GRINDING
- Out of domain scope — OMIM is 3-axis panel CNC only
