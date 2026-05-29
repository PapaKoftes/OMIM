# CI Validation Strategy

Version: v0.1.0  
Section: 10_IMPLEMENTATION  

See also: [[10_IMPLEMENTATION/Acceptance_Tests]], [[10_IMPLEMENTATION/Definition_of_Done]]

---

## Purpose

Defines which automated checks run as part of CI, when they run, and what constitutes a blocking failure. CI is the enforcement mechanism for the Definition of Done.

---

## CI Check Categories

### Category 1: Blocking (PR merge blocked)

These must pass on every commit:

```yaml
# ci/blocking_checks.yaml
checks:
  - name: unit_tests
    command: pytest tests/unit/ -v --tb=short
    
  - name: acceptance_tests
    command: pytest tests/acceptance/ -v --tb=short
    
  - name: schema_validation
    command: python -m omim.tools.check_schema
    
  - name: provenance_audit
    command: python -m omim.tools.audit_provenance --fixtures-dir tests/fixtures/
    
  - name: module_isolation
    command: python -m omim.tools.check_module_isolation
    
  - name: type_check
    command: mypy src/omim/ --strict
```

### Category 2: Warning (merge allowed but flagged)

```yaml
  - name: test_coverage
    command: pytest --cov=omim --cov-fail-under=70
    blocking: false   # Warning only in v0
    
  - name: benchmark_regression
    command: python -m omim.benchmark.regression_check
    blocking: false   # Warning until benchmark baselines established
```

---

## Module Isolation Check

The most critical automated check — enforces the architectural invariants:

```python
# omim/tools/check_module_isolation.py

def check_module_isolation():
    violations = []
    
    # Validation module must not import semantic
    validation_files = glob.glob("src/omim/validation/**/*.py", recursive=True)
    for path in validation_files:
        content = open(path).read()
        if "from omim.semantic" in content or "import omim.semantic" in content:
            violations.append(f"{path}: imports omim.semantic (FORBIDDEN)")
    
    # Parser must not import MGG builder
    parser_files = glob.glob("src/omim/parser/**/*.py", recursive=True)
    for path in parser_files:
        content = open(path).read()
        if "from omim.mgg" in content or "import omim.mgg" in content:
            violations.append(f"{path}: imports omim.mgg (FORBIDDEN)")
    
    # MGG builder must not import validation
    mgg_files = glob.glob("src/omim/mgg/**/*.py", recursive=True)
    for path in mgg_files:
        content = open(path).read()
        if "from omim.validation" in content:
            violations.append(f"{path}: imports omim.validation (FORBIDDEN)")
    
    if violations:
        for v in violations:
            print(f"ISOLATION VIOLATION: {v}")
        sys.exit(1)
    
    print("Module isolation check: PASSED")
```

---

## Schema Validation Check

```python
# omim/tools/check_schema.py

def check_schema():
    """Validate all test fixtures produce schema-valid output."""
    failures = []
    
    for fixture in glob.glob("tests/fixtures/*.dxf"):
        try:
            result = pipeline.process(fixture, output_dir=tempfile.mkdtemp())
            if result.success:
                errors = validate_sample_schema(result.export_result.sample_dir)
                if errors:
                    failures.append(f"{fixture}: schema errors: {errors}")
        except Exception as e:
            failures.append(f"{fixture}: exception: {e}")
    
    if failures:
        for f in failures:
            print(f"SCHEMA FAILURE: {f}")
        sys.exit(1)
    
    print(f"Schema validation: PASSED ({len(glob.glob('tests/fixtures/*.dxf'))} fixtures)")
```

---

## Consistency Check Functions

These run as part of the integration test suite:

```python
def check_graph_integrity(mgg: ManufacturingGeometryGraph) -> list[str]:
    """
    Verify internal MGG consistency.
    Returns list of violations (empty = clean).
    """
    violations = []
    
    # All edges reference valid node IDs
    node_ids = {n.node_id for n in mgg.query().get_all_nodes()}
    for edge in mgg.query().get_all_edges():
        if edge.source_id not in node_ids:
            violations.append(f"Edge {edge.edge_id}: source_id {edge.source_id} not in nodes")
        if edge.target_id not in node_ids:
            violations.append(f"Edge {edge.edge_id}: target_id {edge.target_id} not in nodes")
    
    # Every node has provenance
    for node in mgg.query().get_all_nodes():
        if node.provenance is None:
            violations.append(f"Node {node.node_id}: provenance is None")
    
    # Graph has exactly one panel boundary node
    boundary_nodes = list(mgg.query().get_by_role("panel_boundary"))
    if len(boundary_nodes) != 1:
        violations.append(f"Expected 1 panel boundary, found {len(boundary_nodes)}")
    
    return violations


def check_ontology_consistency() -> list[str]:
    """
    Verify ontology YAML is internally consistent.
    Returns list of violations.
    """
    violations = []
    ontology = OntologyLoader.load()
    
    # All feature types referenced in rules exist in feature taxonomy
    for rule_id, feature_class in ontology.get_rule_feature_references():
        if feature_class not in ontology.feature_classes:
            violations.append(f"Rule {rule_id} references unknown feature_class: {feature_class}")
    
    # All FEATURE_TO_OPERATIONS entries reference valid operations
    valid_ops = {"DRILLING", "CNC_ROUTING", "PROFILE_CUTTING", "NESTING"}
    for feature, ops in FEATURE_TO_OPERATIONS.items():
        for op in ops:
            if op not in valid_ops:
                violations.append(f"FEATURE_TO_OPERATIONS[{feature}] references unknown op: {op}")
    
    return violations


def check_dataset_consistency(dataset_dir: str) -> list[str]:
    """
    Verify all samples in a dataset directory are schema-valid and consistent.
    Returns list of violations.
    """
    violations = []
    manifest_path = os.path.join(dataset_dir, "manifest.json")
    
    if not os.path.exists(manifest_path):
        return [f"No manifest.json in {dataset_dir}"]
    
    manifest = DatasetManifest.model_validate_json(open(manifest_path).read())
    
    for sample_id in manifest.sample_ids:
        sample_dir = os.path.join(dataset_dir, sample_id)
        errors = validate_sample_schema(sample_dir)
        violations.extend([f"{sample_id}: {e}" for e in errors])
    
    return violations
```

---

## CI Pipeline (GitHub Actions Structure)

```yaml
# .github/workflows/ci.yml
name: OMIM CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: "3.11"
      
      - name: Install dependencies
        run: pip install -e ".[dev]"
      
      - name: Module isolation check
        run: python -m omim.tools.check_module_isolation
      
      - name: Ontology consistency check
        run: python -m omim.tools.check_ontology_consistency
      
      - name: Unit tests
        run: pytest tests/unit/ -v
      
      - name: Acceptance tests
        run: pytest tests/acceptance/ -v
      
      - name: Schema validation on fixtures
        run: python -m omim.tools.check_schema
      
      - name: Type checking
        run: mypy src/omim/ --strict
```

---

## When Checks Run

| Check | On commit | On PR | On release |
|-------|-----------|-------|-----------|
| Unit tests | Yes | Yes | Yes |
| Acceptance tests | Yes | Yes | Yes |
| Module isolation | Yes | Yes | Yes |
| Schema validation | Yes | Yes | Yes |
| Type check | Yes | Yes | Yes |
| Benchmark regression | No | Yes | Yes |
| Expert review | No | No | Yes (manual) |
| Dataset integrity | No | No | Yes |
