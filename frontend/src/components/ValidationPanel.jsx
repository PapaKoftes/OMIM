import React from "react";
import { severityStyle, VALIDATION_AUTHORITY } from "../authority";

const styles = {
  section: { marginBottom: "8px" },
  authorityNote: {
    fontSize: "11px",
    color: VALIDATION_AUTHORITY.color,
    background: VALIDATION_AUTHORITY.color + "18",
    border: `1px solid ${VALIDATION_AUTHORITY.color}55`,
    borderRadius: "6px",
    padding: "6px 8px",
    marginBottom: "10px",
    lineHeight: 1.4,
  },
  layerHeader: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    fontSize: "12px",
    fontWeight: 600,
    margin: "10px 0 6px",
  },
  item: {
    padding: "8px",
    background: "#1a1f25",
    borderRadius: "6px",
    marginBottom: "6px",
    fontSize: "12px",
    lineHeight: 1.45,
  },
  meta: { display: "flex", flexWrap: "wrap", gap: "10px", marginTop: "5px", opacity: 0.85 },
  metaItem: { fontSize: "11px" },
};

function severityBadge(sev) {
  const s = severityStyle(sev);
  return {
    display: "inline-block",
    padding: "1px 6px",
    borderRadius: "4px",
    fontSize: "11px",
    fontWeight: 700,
    marginRight: "6px",
    background: s.bg,
    color: s.fg,
  };
}

function passPill(passed) {
  return {
    fontSize: "11px",
    fontWeight: 700,
    padding: "1px 8px",
    borderRadius: "10px",
    background: passed ? "#064e3b" : "#7f1d1d",
    color: passed ? "#6ee7b7" : "#fca5a5",
  };
}

function num(v) {
  if (v == null) return "—";
  return Number.isInteger(v) ? String(v) : v.toFixed(2);
}

function RuleResult({ r }) {
  const failed = !r.passed;
  return (
    <div
      style={{
        ...styles.item,
        borderLeft: `3px solid ${severityStyle(failed ? r.severity : "PASS").color}`,
      }}
    >
      <div>
        <span style={severityBadge(failed ? r.severity : "PASS")}>
          {failed ? r.severity : "PASS"}
        </span>
        <strong>{r.rule_id}</strong>
        {r.rule_name ? <span style={{ opacity: 0.6 }}> — {r.rule_name}</span> : null}
      </div>
      <div style={{ marginTop: 4 }}>{r.message}</div>
      <div style={styles.meta}>
        {r.measured_value != null && (
          <span style={styles.metaItem}>
            measured <strong>{num(r.measured_value)}</strong>
          </span>
        )}
        {r.threshold_value != null && (
          <span style={styles.metaItem}>
            threshold <strong>{num(r.threshold_value)}</strong>
          </span>
        )}
        <span style={styles.metaItem} title="Rule confidence ceiling — caps advisory weight of this result">
          conf ceiling <strong>{num(r.confidence)}</strong>
        </span>
        {Array.isArray(r.affected_node_ids) && r.affected_node_ids.length > 0 && (
          <span style={styles.metaItem}>nodes: {r.affected_node_ids.join(", ")}</span>
        )}
      </div>
    </div>
  );
}

function Layer({ title, passed, results }) {
  const list = results || [];
  const failures = list.filter((r) => !r.passed);
  const shown = failures.length > 0 ? failures : list;
  return (
    <div style={styles.section}>
      <div style={styles.layerHeader}>
        <span>{title}</span>
        <span style={passPill(passed)}>{passed ? "PASS" : "FAIL"}</span>
      </div>
      {list.length === 0 ? (
        <div style={{ ...styles.item, opacity: 0.6 }}>No rules evaluated.</div>
      ) : failures.length === 0 ? (
        <div style={{ ...styles.item, color: "#6ee7b7" }}>
          All {list.length} rule{list.length === 1 ? "" : "s"} passed.
        </div>
      ) : (
        shown.map((r, i) => <RuleResult key={r.rule_id + i} r={r} />)
      )}
    </div>
  );
}

export default function ValidationPanel({ validation }) {
  if (!validation) return null;

  const {
    overall_valid,
    layer1_passed,
    layer2_passed,
    layer1_results = [],
    layer2_results = [],
    severity_summary = {},
  } = validation;

  return (
    <div>
      <div style={styles.authorityNote}>
        Deterministic rule engine — pass/fail is exact. Each rule carries a{" "}
        <strong>confidence ceiling</strong> that caps how much advisory weight a
        result implies.
      </div>

      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 4, fontSize: 13 }}>
        <span style={passPill(overall_valid)}>
          {overall_valid ? "OVERALL VALID" : "INVALID"}
        </span>
        <span style={{ color: severityStyle("ERROR").color }}>
          {severity_summary.ERROR || 0} errors
        </span>
        <span style={{ color: severityStyle("WARNING").color }}>
          {severity_summary.WARNING || 0} warnings
        </span>
        {severity_summary.INFO ? (
          <span style={{ color: severityStyle("INFO").color }}>{severity_summary.INFO} info</span>
        ) : null}
      </div>

      <Layer title="Layer 1 — Geometric" passed={layer1_passed} results={layer1_results} />
      <Layer title="Layer 2 — Manufacturability" passed={layer2_passed} results={layer2_results} />
    </div>
  );
}
