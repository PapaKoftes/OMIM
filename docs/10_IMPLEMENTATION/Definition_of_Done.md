# Definition of Done

Version: v0.1.0  
Section: 10_IMPLEMENTATION  

See also: [[10_IMPLEMENTATION/Acceptance_Tests]], [[10_IMPLEMENTATION/CI_Validation_Strategy]]

---

## Purpose

Unambiguous criteria for declaring OMIM v0.1.0 complete. "Done" means these conditions are met — not "mostly done" or "passes happy path."

---

## System-Level Done Criteria

### Parser

- [ ] Extracts CIRCLE, LWPOLYLINE, LINE, ARC from real DXF files
- [ ] Normalizes all coordinates to mm
- [ ] Returns structured `ParseResult` for all failure cases (no unhandled exceptions)
- [ ] All 5 Parser acceptance tests pass (see [[10_IMPLEMENTATION/Acceptance_Tests]])
- [ ] `test_parser_handles_malformed_dxf` passes without stack trace to user

### MGG Builder

- [ ] Creates GeometryNode for every RawEntity
- [ ] Computes CONTAINS edges via Shapely
- [ ] Computes ADJACENT_TO, SAME_ROW, SAME_COLUMN edges
- [ ] Every node has non-null provenance
- [ ] `mgg.to_json()` / `from_json()` roundtrip identical
- [ ] All 5 MGG acceptance tests pass

### Validation Engine

- [ ] All 6 Layer 1 rules implemented and tested
- [ ] All 10 Layer 2 rules implemented and tested
- [ ] `ValidationReport.model_dump_json()` produces valid JSON
- [ ] Same MGG always produces identical ValidationReport (determinism test)
- [ ] No validation failure is silent — every failed rule produces a RuleResult
- [ ] All 6 Validation acceptance tests pass

### Semantic Layer

- [ ] HINGE_CUP_HOLE, SHELF_PIN_HOLE classified correctly on test fixtures
- [ ] No MGG mutation (node count identical before and after classify())
- [ ] All nodes get at least UNKNOWN_FEATURE if not classified
- [ ] All 6 Semantic acceptance tests pass

### Dataset Exporter

- [ ] All 5 sample files written for every export request
- [ ] `validate_sample_schema()` passes on all exported samples
- [ ] Atomic write (no partial samples on disk)
- [ ] All 6 Export acceptance tests pass

### Synthetic Generator

- [ ] Generates 1000 samples in under 10 minutes
- [ ] Same seed → identical output (byte-level for DXF files)
- [ ] 30% of samples are invalid (±5%)
- [ ] All generated valid samples pass OMIM validation
- [ ] All generated invalid samples fail OMIM validation at the expected rule
- [ ] Feature distribution matches target distribution within 10% per class
- [ ] All 5 Generator acceptance tests pass

### Benchmark Evaluation

- [ ] BENCH-001 through BENCH-004 evaluation scripts implemented
- [ ] OMIM rule-based baseline computed and published for all tasks
- [ ] BENCH-002 FNR ≤ 0.10 for rule-based baseline
- [ ] Test set is frozen, hash-verified, separate from train/val

---

## Pipeline-Level Done Criteria

- [ ] `test_vertical_slice` passes: one DXF → 5 schema-valid files
- [ ] `check_graph_integrity(mgg)` returns no violations on all generated samples
- [ ] `check_ontology_consistency()` returns no violations
- [ ] `check_dataset_consistency(dataset_dir)` returns no violations
- [ ] `audit_provenance(mgg)` returns no violations on all generated samples

---

## Code Quality Done Criteria

- [ ] All Pydantic models use model_validators where specified
- [ ] No `# FORBIDDEN` patterns present anywhere in codebase
- [ ] `from omim.semantic` not imported in validation module
- [ ] `from omim.validation` not imported in parser module
- [ ] All public interfaces match the Interface Contract documents

---

## What "Done" Does NOT Require

- Performance optimization (profile only if pipeline is unusably slow)
- ML model training (out of scope for OMIM infrastructure)
- Multi-panel / nesting optimization (v0.2)
- Edge banding features (v0.2)
- 5-axis or turning operations (out of scope permanently)
- 100% test coverage (acceptance tests + happy path is sufficient for v0)
- Documentation beyond this vault (README is sufficient for v0)
