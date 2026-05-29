# Hackathon Execution Order

Version: v0.1.0  
Section: 10_IMPLEMENTATION  

See also: [[10_IMPLEMENTATION/Vertical_Slice_Execution]], [[10_IMPLEMENTATION/Definition_of_Done]]

---

## ⚠ ARCHITECTURE COMPLETE — BUILD NOW

> The architecture is done. The specs are done. The schemas are frozen. The ontology is defined.
> **The only remaining high-value move is to write running code.**

Reading more docs does not move the project forward. Refining the ontology does not move the project forward. Adding more edge cases to the MGG spec does not move the project forward.

**The minimum success condition for this hackathon is:**

```
One DXF file
  → python -m omim.cli input.dxf --output out/
    → out/mgg.json           (exists, valid JSON, has nodes)
    → out/validation.json    (exists, overall_valid field present)
    → out/labels.json        (exists, features list present)
    → out/provenance.json    (exists, pipeline_stages present)
```

If that runs and produces output, the core thesis is proven. Everything else — ML, benchmarks, 1000+ samples, demo UI — is additive value on top of a working foundation.

**Architecture gravity is the most common way infrastructure projects die.** The vault has enough. Stop reading. Start building. The specs exist to guide the implementation, not to replace it.

---

## Overview

48-hour battle plan for producing a working OMIM v0.1.0 with passing benchmarks. Phases are sequential. Each phase has a go/no-go checkpoint before proceeding.

---

## H0–H4: Environment + Slice Foundation

**Goal**: Working dev environment + first data flowing through the system.

```
H0: Environment setup
    [ ] Python 3.11+ venv
    [ ] pip install ezdxf shapely networkx pydantic pyyaml numpy
    [ ] Project structure created (src/omim/, data/, tests/, fixtures/)
    [ ] pytest configured + one trivial test passes

H1–H2: Parser implementation
    [ ] DXFParser.parse() extracts CIRCLE entities from test DXF
    [ ] RawGeometry schema validates with Pydantic
    [ ] Unit test: test_parser_circle_extraction passes
    [ ] Layer classification working

H2–H4: MGG Builder
    [ ] ManufacturingGeometryGraph wrapping NetworkX
    [ ] GeometryNode Pydantic schema
    [ ] MGGBuilder.build() creates nodes from RawGeometry
    [ ] CONTAINS edges via Shapely containment
    [ ] mgg.to_json() / from_json() roundtrip passes
```

**H4 Checkpoint**: `test_mgg_builds_from_geometry` and `test_mgg_roundtrip` pass.  
**Abort condition**: If parser or MGG builder not working at H4, skip semantic layer — focus on validation only.

---

## H4–H8: Validation Engine

**Goal**: ValidationReport produced for any MGG.

```
H4–H6: Rule Engine + Layer 1
    [ ] RuleEngine loads YAML, raises RuleLoadError if missing
    [ ] GEO-001 (open contour) implemented and tested
    [ ] GEO-002 to GEO-006 implemented
    [ ] test_open_contour_detected passes
    [ ] test_valid_panel_passes_all_rules passes (layer 1 only)

H6–H8: Layer 2 rules
    [ ] MFG-001 (edge clearance) implemented
    [ ] MFG-002 (feature spacing) implemented
    [ ] MFG-003 to MFG-010 implemented
    [ ] ValidationReport.model_dump_json() produces valid JSON
    [ ] test_validation_determinism passes
```

**H8 Checkpoint**: Full validation pipeline working. `validate_mgg()` produces complete `ValidationReport`.

---

## H8–H16: Export + Vertical Slice

**Goal**: End-to-end pipeline writing 5-file samples.

```
H8–H12: Dataset Exporter
    [ ] DatasetExporter.export() writes all 5 files
    [ ] validate_sample_schema() implemented
    [ ] test_export_writes_five_files passes
    [ ] test_export_validates_schema passes
    [ ] Atomic write (temp dir → final) implemented

H12–H16: Full Vertical Slice Test
    [ ] Pipeline orchestrator: parse → build → validate → export
    [ ] test_vertical_slice passes end-to-end
    [ ] simple_panel.dxf → 5 valid files
    [ ] panel_with_violations.dxf → 5 valid files (with is_valid=False)
```

**H16 Checkpoint**: `test_vertical_slice` passes for all 3 required fixtures.  
**This is the most important checkpoint in the hackathon.**

---

## H16–H24: Synthetic Generator

**Goal**: 1000 synthetic samples generated and exported.

```
H16–H20: PanelGenerator
    [ ] PanelGeneratorConfig Pydantic model
    [ ] generate_sample() produces valid PanelSpec + FeatureSpec list
    [ ] DXFWriter produces valid ezdxf DXF
    [ ] test_generator_deterministic passes

H20–H24: Full Dataset Generation
    [ ] generate_dataset() produces 1000 samples
    [ ] 30% invalid samples with correct violations
    [ ] All samples pass validate_sample_schema()
    [ ] manifest.json written
    [ ] test_generator_invalid_ratio passes
```

**H24 Checkpoint**: 1000-sample dataset on disk. All samples schema-valid.

---

## H24–H32: Semantic Layer

**Goal**: Feature classification working with provenance.

```
H24–H28: SemanticInferenceEngine
    [ ] classify() returns SemanticAnnotations
    [ ] HINGE_CUP_HOLE rule working
    [ ] SHELF_PIN_HOLE rule working
    [ ] test_hinge_cup_classified_correctly passes
    [ ] test_shelf_pin_grid_detected passes

H28–H32: Integration
    [ ] Labels.json updated with semantic annotations for real DXF samples
    [ ] test_semantic_layer_does_not_mutate_mgg passes
    [ ] Provenance records on all annotations
    [ ] audit_provenance() returns zero violations
```

**H32 Checkpoint**: Semantic layer working, provenance clean.

---

## H32–H40: Benchmark Evaluation

**Goal**: All 4 benchmarks producing scores.

```
H32–H36: Evaluation Script
    [ ] evaluate_bench001() implemented
    [ ] evaluate_bench002() implemented
    [ ] evaluate_bench003() implemented
    [ ] evaluate_bench004() implemented
    [ ] OMIM rule-based baseline computed for all 4 tasks

H36–H40: Results and Verification
    [ ] All benchmarks scored on test set
    [ ] BENCH-002 FNR ≤ 0.10 for rule-based baseline (should be ~0)
    [ ] CI runs all automated checks
    [ ] README with quickstart example
```

**H40 Final Checkpoint**: OMIM v0.1.0 complete.

---

## Contingency Plans

### If H16 checkpoint missed (vertical slice not working)

- Drop semantic layer entirely for v0
- Focus: parser + MGG + validation + export + synthetic generator
- Still generates a valid dataset; semantic tasks become v0.2 work

### If H24 checkpoint missed (generator not producing 1000 samples)

- Reduce dataset to 100 samples for hackathon
- Document 1000-sample as target; 100-sample as hackathon delivery

### If benchmark evaluation cannot be completed

- Report OMIM pipeline metrics only (parse success rate, validation coverage)
- Defer benchmark scores to post-hackathon submission

---

## HPC / High-Performance Computing Strategy

If a GPU cluster is available:
- Use it ONLY for post-H32 (ML baseline experiments for BENCH-001, BENCH-004)
- All OMIM infrastructure runs on CPU; no GPU dependency in core pipeline
- Dataset generation target: 10,000 samples if time permits post-H24
