import React from "react";
import { authorityFor, confidenceColor } from "../authority";
import { AuthorityBadge } from "./AuthorityBadge";

// OMIM's differentiator: every node carries a full ProvenanceRecord. This panel
// makes the "why should I trust this?" answer first-class.

const styles = {
  empty: { opacity: 0.55, fontSize: 12, lineHeight: 1.5 },
  card: {
    background: "#1a1f25",
    borderRadius: 8,
    padding: 12,
    fontSize: 12,
  },
  banner: (color) => ({
    display: "flex",
    alignItems: "center",
    gap: 8,
    padding: "8px 10px",
    borderRadius: 6,
    background: color + "1f",
    border: `1px solid ${color}`,
    marginBottom: 10,
  }),
  row: { display: "flex", justifyContent: "space-between", gap: 8, padding: "3px 0" },
  key: { opacity: 0.6 },
  val: { textAlign: "right", wordBreak: "break-word" },
  sectionTitle: {
    fontSize: 11,
    textTransform: "uppercase",
    letterSpacing: "0.5px",
    opacity: 0.6,
    margin: "12px 0 6px",
    fontWeight: 700,
  },
  evidence: {
    background: "#0f1419",
    borderRadius: 6,
    padding: "6px 8px",
    marginBottom: 6,
    lineHeight: 1.4,
  },
  evTop: { display: "flex", justifyContent: "space-between", gap: 6, alignItems: "center" },
  chip: (ok) => ({
    fontSize: 10,
    fontWeight: 700,
    padding: "0 6px",
    borderRadius: 8,
    background: ok ? "#064e3b" : "#7f1d1d",
    color: ok ? "#6ee7b7" : "#fca5a5",
  }),
  mono: { fontFamily: "monospace", fontSize: 11 },
};

function Row({ k, v }) {
  if (v == null || v === "") return null;
  return (
    <div style={styles.row}>
      <span style={styles.key}>{k}</span>
      <span style={styles.val}>{v}</span>
    </div>
  );
}

function EvidenceItem({ e }) {
  return (
    <div style={styles.evidence}>
      <div style={styles.evTop}>
        <strong>{e.evidence_type}</strong>
        <span style={styles.chip(e.satisfied !== false)}>
          {e.satisfied === false ? "UNMET" : "OK"}
        </span>
      </div>
      {e.description && <div style={{ opacity: 0.85, marginTop: 2 }}>{e.description}</div>}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 10, marginTop: 3, opacity: 0.75 }}>
        {e.value != null && (
          <span>
            value <strong>{String(e.value)}</strong>
            {e.unit ? ` ${e.unit}` : ""}
          </span>
        )}
        {e.expected != null && (
          <span>
            expected <strong>{String(e.expected)}</strong>
            {e.unit ? ` ${e.unit}` : ""}
          </span>
        )}
        {e.rule_id && <span style={styles.mono}>{e.rule_id}</span>}
      </div>
    </div>
  );
}

export default function ProvenancePanel({ node }) {
  if (!node) {
    return (
      <div style={styles.empty}>
        Select a node in the graph to inspect its provenance record — the
        inference method, confidence, supporting evidence, and source entities
        that produced it.
      </div>
    );
  }

  const prov = node.provenance;
  const a = authorityFor(prov?.inference_method);

  // Node identity (works for any node type).
  const typeLabel =
    node.feature_class ||
    node.geometry_type ||
    node.constraint_type ||
    node.operation_type ||
    node.node_type;

  return (
    <div style={styles.card}>
      <div style={styles.banner(a.color)}>
        <AuthorityBadge method={prov?.inference_method} />
        <div>
          <div style={{ fontWeight: 700, color: a.color }}>{a.tier}</div>
          <div style={{ fontSize: 10, opacity: 0.7 }}>{a.desc}</div>
        </div>
      </div>

      <div style={styles.sectionTitle}>Node</div>
      <Row k="id" v={<span style={styles.mono}>{node.id}</span>} />
      <Row k="type" v={node.node_type} />
      <Row k="class" v={typeLabel} />
      {node.layer && <Row k="layer" v={node.layer} />}
      {node.diameter_mm != null && <Row k="diameter" v={`${node.diameter_mm} mm`} />}
      {node.area_mm2 != null && <Row k="area" v={`${node.area_mm2} mm²`} />}

      {!prov ? (
        <div style={{ ...styles.empty, marginTop: 10 }}>
          No provenance record attached to this node.
        </div>
      ) : (
        <>
          <div style={styles.sectionTitle}>Provenance</div>
          <Row k="inference method" v={prov.inference_method} />
          <Row
            k="confidence"
            v={
              <span style={{ color: confidenceColor(prov.confidence), fontWeight: 700 }}>
                {prov.confidence != null ? `${(prov.confidence * 100).toFixed(0)}%` : "—"}
              </span>
            }
          />
          <Row k="confidence method" v={prov.confidence_method} />
          <Row k="pipeline stage" v={prov.pipeline_stage} />
          <Row k="module" v={prov.module ? <span style={styles.mono}>{prov.module}</span> : null} />
          <Row k="generator" v={prov.generator_version ? `${prov.generator} ${prov.generator_version}` : prov.generator} />
          <Row k="review status" v={prov.review_status} />

          {Array.isArray(prov.source_entity_ids) && prov.source_entity_ids.length > 0 && (
            <Row k="source entities" v={<span style={styles.mono}>{prov.source_entity_ids.join(", ")}</span>} />
          )}
          {Array.isArray(prov.parent_record_ids) && prov.parent_record_ids.length > 0 && (
            <Row k="parent records" v={prov.parent_record_ids.length} />
          )}

          <div style={styles.sectionTitle}>
            Evidence ({prov.evidence?.length || 0})
          </div>
          {prov.evidence?.length ? (
            prov.evidence.map((e, i) => <EvidenceItem key={i} e={e} />)
          ) : (
            <div style={styles.empty}>No evidence items recorded.</div>
          )}
        </>
      )}
    </div>
  );
}
