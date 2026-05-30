// Authority hierarchy shared across the UI.
//
// OMIM's core idea: every fact in the graph carries a provenance record with an
// `inference_method`. Methods map to authority levels (lower number = higher
// authority). The UI uses this single source of truth to color-code and badge
// everything so a user can always tell *how much to trust* a given statement.
//
// Mirrors src/omim/provenance/models.py :: AUTHORITY_LEVELS

// inference_method -> presentation metadata
export const AUTHORITY = {
  deterministic: {
    level: 1,
    tier: "Geometry / Fact",
    label: "Deterministic",
    short: "FACT",
    color: "#3b82f6", // blue
    desc: "Computed directly from geometry. Confidence is always 1.0.",
  },
  synthetic: {
    level: 1,
    tier: "Geometry / Fact",
    label: "Synthetic",
    short: "FACT",
    color: "#3b82f6",
    desc: "Generated ground-truth (synthetic dataset). Confidence 1.0.",
  },
  human_annotated: {
    level: 3,
    tier: "Human",
    label: "Human-reviewed",
    short: "HUMAN",
    color: "#22c55e", // green
    desc: "Confirmed by a human reviewer.",
  },
  heuristic: {
    level: 4,
    tier: "Semantic (Heuristic)",
    label: "Heuristic",
    short: "HEUR",
    color: "#f59e0b", // amber
    desc: "Rule/pattern heuristic. Advisory — confidence strictly below 1.0.",
  },
  semantic: {
    level: 5,
    tier: "Semantic",
    label: "Semantic",
    short: "SEM",
    color: "#a855f7", // purple
    desc: "Semantic inference. Advisory.",
  },
  ml_gnn: {
    level: 6,
    tier: "ML / Advisory",
    label: "ML (GNN)",
    short: "ML",
    color: "#ec4899", // pink
    desc: "Machine-learning prediction. Advisory only.",
  },
  ml_llm: {
    level: 6,
    tier: "LLM / Advisory",
    label: "LLM",
    short: "LLM",
    color: "#ec4899",
    desc: "LLM-generated explanation. Advisory only — never authoritative.",
  },
};

const UNKNOWN = {
  level: 99,
  tier: "Unknown",
  label: "Unknown",
  short: "?",
  color: "#6b7280",
  desc: "No provenance / inference method recorded.",
};

// Validation results are deterministic rules but carry their own authority story
// (a rule's confidence_ceiling caps how much trust its result implies).
export const VALIDATION_AUTHORITY = {
  level: 2,
  tier: "Validation (Deterministic Rules)",
  label: "Validation",
  short: "RULE",
  color: "#06b6d4", // cyan
  desc: "Deterministic rule engine. Pass/fail is exact; rule confidence ceiling caps advisory weight.",
};

export function authorityFor(method) {
  if (!method) return UNKNOWN;
  return AUTHORITY[method] || UNKNOWN;
}

// Ordered list (highest authority first) for legends.
export const AUTHORITY_ORDER = [
  AUTHORITY.deterministic,
  VALIDATION_AUTHORITY,
  AUTHORITY.heuristic,
  AUTHORITY.ml_llm,
];

// Severity presentation for validation.
export const SEVERITY = {
  ERROR: { color: "#ef4444", bg: "#7f1d1d", fg: "#fca5a5" },
  WARNING: { color: "#f59e0b", bg: "#78350f", fg: "#fde68a" },
  INFO: { color: "#3b82f6", bg: "#1e3a5f", fg: "#93c5fd" },
  PASS: { color: "#10b981", bg: "#064e3b", fg: "#6ee7b7" },
  SYSTEM_ERROR: { color: "#a855f7", bg: "#4c1d95", fg: "#d8b4fe" },
};

export function severityStyle(sev) {
  return SEVERITY[sev] || SEVERITY.INFO;
}

// Confidence -> color band (used by bars and chips).
export function confidenceColor(val) {
  if (val == null) return "#6b7280";
  if (val >= 0.8) return "#10b981";
  if (val >= 0.5) return "#f59e0b";
  return "#ef4444";
}
