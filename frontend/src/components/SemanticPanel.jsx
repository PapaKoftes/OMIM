import React from "react";
import { confidenceColor, authorityFor } from "../authority";
import { AuthorityBadge } from "./AuthorityBadge";

const styles = {
  authorityNote: {
    fontSize: "11px",
    color: "#f59e0b",
    background: "#f59e0b18",
    border: "1px solid #f59e0b55",
    borderRadius: "6px",
    padding: "6px 8px",
    marginBottom: "10px",
    lineHeight: 1.4,
  },
  item: {
    padding: "9px",
    background: "#1a1f25",
    borderRadius: "6px",
    marginBottom: "8px",
    fontSize: "12px",
    cursor: "pointer",
    border: "1px solid transparent",
  },
  itemSelected: { border: "1px solid #ffffff55" },
  featureClass: { fontWeight: 700 },
  barTrack: {
    height: 6,
    background: "#0f1419",
    borderRadius: 3,
    overflow: "hidden",
    margin: "6px 0",
  },
  nodeId: { fontSize: "10px", opacity: 0.55, fontFamily: "monospace" },
  altWrap: {
    marginTop: 6,
    paddingTop: 6,
    borderTop: "1px dashed #2f3336",
    fontSize: "11px",
  },
  altRow: { display: "flex", justifyContent: "space-between", opacity: 0.8, padding: "1px 0" },
};

function ConfidenceBar({ value }) {
  const pct = Math.round((value || 0) * 100);
  return (
    <div style={styles.barTrack} title={`confidence ${pct}%`}>
      <div style={{ width: `${pct}%`, height: "100%", background: confidenceColor(value) }} />
    </div>
  );
}

export default function SemanticPanel({ annotations, selectedId, onSelect }) {
  // Accept the full SemanticAnnotations object from /analyze.
  const features = annotations?.feature_annotations || [];
  const coverage = annotations?.coverage_ratio;

  if (features.length === 0) {
    return (
      <div>
        <div style={styles.authorityNote}>
          Semantic classifications are <strong>heuristic / advisory</strong> — never
          treated as fact.
        </div>
        <div style={{ opacity: 0.6, fontSize: 12 }}>No features classified.</div>
      </div>
    );
  }

  return (
    <div>
      <div style={styles.authorityNote}>
        Heuristic / advisory layer. Confidence reflects the inference method's
        ceiling; alternatives shown when confidence &lt; 0.75.
      </div>
      <div style={{ fontSize: 12, opacity: 0.7, marginBottom: 8 }}>
        {features.length} feature{features.length === 1 ? "" : "s"} classified
        {coverage != null && ` · coverage ${(coverage * 100).toFixed(0)}%`}
      </div>

      {features.map((f) => {
        const method = f.provenance?.inference_method || authorityFor().label;
        const pct = Math.round((f.confidence || 0) * 100);
        const showAlts = (f.confidence ?? 1) < 0.75 && (f.alternative_classes?.length || 0) > 0;
        const selected = selectedId && selectedId === f.node_id;
        return (
          <div
            key={f.node_id}
            style={{ ...styles.item, ...(selected ? styles.itemSelected : {}) }}
            onClick={() => onSelect && onSelect(f.node_id)}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 6 }}>
              <span style={styles.featureClass}>{f.feature_class}</span>
              <span style={{ display: "flex", gap: 6, alignItems: "center" }}>
                <AuthorityBadge method={f.provenance?.inference_method} />
                <span style={{ color: confidenceColor(f.confidence), fontWeight: 700, fontSize: 11 }}>
                  {pct}%
                </span>
              </span>
            </div>
            <ConfidenceBar value={f.confidence} />
            <div style={styles.nodeId}>
              {f.node_id} · {method}
            </div>
            {showAlts && (
              <div style={styles.altWrap}>
                <div style={{ opacity: 0.6, marginBottom: 2 }}>Alternative hypotheses</div>
                {f.alternative_classes.map((alt, i) => (
                  <div key={i} style={styles.altRow}>
                    <span>{alt.feature_class}</span>
                    <span style={{ color: confidenceColor(alt.confidence) }}>
                      {Math.round((alt.confidence || 0) * 100)}%
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
