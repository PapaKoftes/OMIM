# Versioning Policy

Version: v0.1.0  
Section: 02_SCHEMA  

See also: [[02_SCHEMA/Canonical_Sample_Schema]], [[10_IMPLEMENTATION/Definition_of_Done]]

---

## Scope

Everything in OMIM is versioned. This is not overhead — it is what makes the provenance system work and what allows datasets and models to be reproducibly referenced.

---

## Version Registry (v0.1.0)

| Artifact | Version | Format | Where Stored |
|----------|---------|--------|-------------|
| Ontology | v0.1.0 | SemVer | `data/ontology/VERSION` |
| MGG Schema | v0.1.0 | SemVer | `$schema` field in mgg.json |
| Rule Set | v0.1.0 | SemVer | `data/rules/panel_cnc_rules.yaml` header |
| Labels Schema | v0.1.0 | SemVer | `$schema` field in labels.json |
| Provenance Schema | v0.1.0 | SemVer | `$schema` field in provenance.json |
| Validation Schema | v0.1.0 | SemVer | `$schema` field in validation.json |
| Synthetic Dataset | omim-synthetic-v0.1.0 | named+SemVer | `dataset_metadata.json` |
| OMIM Codebase | v0.1.0 | SemVer + git tag | `pyproject.toml`, git tags |

---

## Semantic Versioning Rules

```
v{major}.{minor}.{patch}

major: Breaking change — schema field removed/renamed, rule ID changed, ontology term removed
minor: Additive change — new field added, new rule, new ontology term
patch: Fix/clarification — description change, source citation added, bug fix that doesn't change output
```

### What Triggers Each Version Level

| What Changed | Version Impact | Example |
|-------------|--------------|---------|
| Feature class ID renamed | ontology: major | v0.1.0 → v0.2.0 |
| New feature class added | ontology: minor | v0.1.0 → v0.1.1 |
| Rule threshold changed | ruleset: minor | v0.1.0 → v0.1.1 |
| New rule added | ruleset: minor | v0.1.0 → v0.1.1 |
| labels.json field renamed | labels schema: major | v0.1.0 → v0.2.0 |
| New optional labels.json field | labels schema: minor | v0.1.0 → v0.1.1 |
| Bug fix with no output change | Any: patch | v0.1.0 → v0.1.0 |

---

## Version Compatibility

Components are compatible iff they share the same **major** version:
- `omim-labels-v0.1.0` is compatible with `omim-labels-v0.1.7` (same major = 0)
- `omim-labels-v0.1.0` is NOT compatible with `omim-labels-v0.2.0`

Every output artifact MUST store the version of every component used:
```python
OMIM_VERSION = "v0.1.0"
ONTOLOGY_VERSION = "v0.1.0"      # loaded from data/ontology/VERSION
RULESET_VERSION = "v0.1.0"       # loaded from data/rules/panel_cnc_rules.yaml
LABELS_SCHEMA_VERSION = "v0.1.0" # hardcoded in canonical schema
```

---

## Hackathon Freeze Rule

**All versions are frozen at `v0.1.0` for the 48-hour hackathon.**

No version increments during the implementation window. Post-hackathon work starts from `v0.2.0-dev`.

The freeze prevents:
- Mid-hackathon ontology drift invalidating half the test fixtures
- Rule changes making validation results incomparable
- Schema changes breaking the pipeline midway

---

## Provenance Version References

Every ProvenanceRecord stores the component versions active at generation time:

```json
{
  "generator_version": "v0.1.0",
  "ontology_version": "v0.1.0",
  "ruleset_version": "v0.1.0"
}
```

This allows future tooling to re-validate a historical sample against the rules that were in effect when it was generated.

---

## Migration Policy

When breaking changes require a major version bump:

1. Write migration script: `tools/migrate_dataset_v{old}_to_v{new}.py`
2. Update `validate_sample_schema()` to accept both old and new version
3. Document all field changes in `CHANGELOG.md`
4. Never silently change field semantics within a version
5. Maintain deprecated rules with `status: deprecated` — never delete
