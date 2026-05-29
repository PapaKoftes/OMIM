import React from "react";

const styles = {
  section: { marginBottom: "16px" },
  heading: { fontSize: "14px", fontWeight: 600, marginBottom: "8px" },
  item: {
    padding: "8px",
    background: "#1a1f25",
    borderRadius: "6px",
    marginBottom: "6px",
    fontSize: "12px",
  },
  featureClass: {
    fontWeight: 600,
    color: "#10b981",
  },
  confidence: (val) => ({
    display: "inline-block",
    padding: "1px 5px",
    borderRadius: "3px",
    fontSize: "10px",
    marginLeft: "6px",
    background: val > 0.8 ? "#064e3b" : val > 0.5 ? "#78350f" : "#7f1d1d",
    color: val > 0.8 ? "#6ee7b7" : val > 0.5 ? "#fde68a" : "#fca5a5",
  }),
  method: {
    fontSize: "10px",
    opacity: 0.6,
    marginTop: "2px",
  },
};

export default function SemanticPanel({ classifications }) {
  if (!classifications || classifications.length === 0) return null;

  const classified = classifications.filter((c) => c.best_hypothesis);

  return (
    <div style={styles.section}>
      <div style={styles.heading}>
        Feature Classification ({classified.length}/{classifications.length})
      </div>
      {classified.map((c, i) => (
        <div key={i} style={styles.item}>
          <span style={styles.featureClass}>{c.best_hypothesis.feature_class}</span>
          <span style={styles.confidence(c.best_hypothesis.confidence)}>
            {(c.best_hypothesis.confidence * 100).toFixed(0)}%
          </span>
          <div style={styles.method}>
            {c.geometry_node_id} — {c.best_hypothesis.method}
          </div>
        </div>
      ))}
    </div>
  );
}
