import React from "react";

const styles = {
  section: { marginBottom: "16px" },
  heading: { fontSize: "14px", fontWeight: 600, marginBottom: "8px" },
  badge: (severity) => ({
    display: "inline-block",
    padding: "2px 6px",
    borderRadius: "4px",
    fontSize: "11px",
    fontWeight: 600,
    marginRight: "6px",
    background: severity === "ERROR" ? "#7f1d1d" : "#78350f",
    color: severity === "ERROR" ? "#fca5a5" : "#fde68a",
  }),
  item: {
    padding: "8px",
    background: "#1a1f25",
    borderRadius: "6px",
    marginBottom: "6px",
    fontSize: "12px",
    lineHeight: "1.4",
  },
  summary: {
    display: "flex",
    gap: "12px",
    marginBottom: "10px",
    fontSize: "13px",
  },
};

export default function ValidationPanel({ validation }) {
  if (!validation) return null;

  const { results = [], passed = 0, failed = 0, warnings = 0 } = validation;
  const failures = results.filter((r) => !r.passed);

  return (
    <div style={styles.section}>
      <div style={styles.heading}>Validation</div>
      <div style={styles.summary}>
        <span style={{ color: "#10b981" }}>✓ {passed} passed</span>
        {failed > 0 && <span style={{ color: "#ef4444" }}>✗ {failed} errors</span>}
        {warnings > 0 && <span style={{ color: "#f59e0b" }}>⚠ {warnings} warnings</span>}
      </div>
      {failures.map((r, i) => (
        <div key={i} style={styles.item}>
          <span style={styles.badge(r.severity)}>{r.severity}</span>
          <strong>{r.rule_id}</strong>: {r.message}
        </div>
      ))}
      {failures.length === 0 && (
        <div style={{ ...styles.item, color: "#10b981" }}>
          All validation rules passed ✓
        </div>
      )}
    </div>
  );
}
