import React, { useState, useCallback, useMemo } from "react";
import GraphViewer from "./components/GraphViewer";
import ValidationPanel from "./components/ValidationPanel";
import SemanticPanel from "./components/SemanticPanel";
import ProvenancePanel from "./components/ProvenancePanel";
import LLMAdvisoryPanel from "./components/LLMAdvisoryPanel";
import { AuthorityLegend } from "./components/AuthorityBadge";

const C = {
  bg: "#0f1419",
  panel: "#12171d",
  card: "#1a1f25",
  border: "#2f3336",
  text: "#e7e9ea",
  accent: "#1d9bf0",
};

const styles = {
  container: {
    display: "flex",
    flexDirection: "column",
    height: "100vh",
    background: C.bg,
    color: C.text,
    overflow: "hidden",
  },
  header: {
    padding: "12px 20px",
    borderBottom: `1px solid ${C.border}`,
    display: "flex",
    alignItems: "center",
    gap: "16px",
    flexShrink: 0,
  },
  title: { fontSize: "18px", fontWeight: 800, letterSpacing: "0.5px" },
  subtitle: { fontSize: "11px", opacity: 0.55 },
  upload: {
    padding: "8px 16px",
    background: C.accent,
    border: "none",
    borderRadius: "6px",
    color: "#fff",
    cursor: "pointer",
    fontSize: "14px",
    fontWeight: 600,
  },
  legendWrap: { marginLeft: "auto" },
  main: { display: "flex", flex: 1, overflow: "hidden" },
  graphPanel: { flex: 1, position: "relative", minWidth: 0 },
  sidebar: {
    width: "380px",
    borderLeft: `1px solid ${C.border}`,
    display: "flex",
    flexDirection: "column",
    flexShrink: 0,
  },
  tabs: { display: "flex", borderBottom: `1px solid ${C.border}`, flexShrink: 0 },
  tab: (active) => ({
    flex: 1,
    padding: "10px 4px",
    textAlign: "center",
    fontSize: "12px",
    fontWeight: 600,
    cursor: "pointer",
    color: active ? C.text : "#71767b",
    borderBottom: active ? `2px solid ${C.accent}` : "2px solid transparent",
    background: active ? C.panel : "transparent",
  }),
  tabBody: { padding: "14px", overflow: "auto", flex: 1 },
  dropOverlay: {
    position: "absolute",
    inset: 0,
    background: "rgba(29,155,240,0.12)",
    border: `2px dashed ${C.accent}`,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: "18px",
    fontWeight: 700,
    zIndex: 10,
    pointerEvents: "none",
  },
  empty: {
    height: "100%",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    textAlign: "center",
    padding: 40,
    gap: 8,
  },
  summaryGrid: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gap: 8,
  },
  stat: {
    background: C.card,
    borderRadius: 8,
    padding: "10px 12px",
  },
  statNum: { fontSize: 20, fontWeight: 800 },
  statLabel: { fontSize: 11, opacity: 0.6 },
};

const TABS = ["Summary", "Validation", "Features", "Provenance", "LLM"];

function Stat({ num, label, color }) {
  return (
    <div style={styles.stat}>
      <div style={{ ...styles.statNum, color: color || C.text }}>{num}</div>
      <div style={styles.statLabel}>{label}</div>
    </div>
  );
}

export default function App() {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const [tab, setTab] = useState("Summary");
  const [selectedNode, setSelectedNode] = useState(null); // raw cytoscape node data
  const [selectedId, setSelectedId] = useState(null);

  const handleUpload = useCallback(async (file) => {
    setLoading(true);
    setError(null);
    setSelectedNode(null);
    setSelectedId(null);
    const formData = new FormData();
    formData.append("file", file);
    try {
      const res = await fetch("/api/v1/analyze", { method: "POST", body: formData });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Analysis failed");
      if (data.success === false) {
        const msgs = (data.errors || []).map((e) => e.message || JSON.stringify(e)).join("; ");
        throw new Error(msgs || "Parse failed");
      }
      setResult(data);
      setTab("Summary");
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleFileInput = (e) => {
    const file = e.target.files?.[0];
    if (file) handleUpload(file);
    e.target.value = "";
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) handleUpload(file);
  };

  // Index graph nodes by id so a selection (from graph or feature list) resolves
  // to the full node data (which carries the provenance record).
  const nodeIndex = useMemo(() => {
    const map = new Map();
    const els = result?.graph?.elements || [];
    for (const el of els) {
      if (el.group === "nodes" && el.data?.id) map.set(el.data.id, el.data);
    }
    return map;
  }, [result]);

  const onGraphSelect = useCallback((nodeData) => {
    setSelectedNode(nodeData);
    setSelectedId(nodeData?.id || null);
    if (nodeData) setTab("Provenance");
  }, []);

  // Selecting a feature in the Features tab also drives provenance.
  const onFeatureSelect = useCallback(
    (nodeId) => {
      setSelectedId(nodeId);
      const data = nodeIndex.get(nodeId);
      if (data) {
        setSelectedNode(data);
      } else {
        // Fall back to the annotation record itself if no graph node exists.
        const ann = (result?.annotations?.feature_annotations || []).find(
          (f) => f.node_id === nodeId
        );
        if (ann) {
          setSelectedNode({
            id: ann.node_id,
            node_type: "feature",
            feature_class: ann.feature_class,
            provenance: ann.provenance,
          });
        }
      }
      setTab("Provenance");
    },
    [nodeIndex, result]
  );

  const summary = result?.summary || {};
  const llm = result?.llm_annotations || null; // optional, "when available"

  return (
    <div style={styles.container}>
      <header style={styles.header}>
        <div>
          <div style={styles.title}>OMIM</div>
          <div style={styles.subtitle}>Manufacturing Geometry Graph Viewer</div>
        </div>
        <input
          type="file"
          accept=".dxf"
          onChange={handleFileInput}
          id="file-upload"
          style={{ display: "none" }}
        />
        <label htmlFor="file-upload" style={{ ...styles.upload, opacity: loading ? 0.6 : 1 }}>
          {loading ? "Analyzing…" : "Upload DXF"}
        </label>
        {error && (
          <span style={{ color: "#f4212e", fontSize: "13px", maxWidth: 360 }}>{error}</span>
        )}
        <div style={styles.legendWrap}>
          <AuthorityLegend compact />
        </div>
      </header>

      <div style={styles.main}>
        <div
          style={styles.graphPanel}
          onDrop={handleDrop}
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
        >
          {dragOver && <div style={styles.dropOverlay}>Drop DXF to analyze</div>}
          {result?.graph ? (
            <GraphViewer elements={result.graph.elements} onSelect={onGraphSelect} />
          ) : (
            <div style={styles.empty}>
              <div style={{ fontSize: 16, fontWeight: 600 }}>
                Drop a DXF file here, or click “Upload DXF”
              </div>
              <div style={{ opacity: 0.5, fontSize: 13 }}>
                Parses CIRCLE, LWPOLYLINE, LINE, ARC → builds the graph, classifies
                features, and runs validation.
              </div>
            </div>
          )}
        </div>

        {result && (
          <aside style={styles.sidebar}>
            <div style={styles.tabs}>
              {TABS.map((t) => (
                <div key={t} style={styles.tab(tab === t)} onClick={() => setTab(t)}>
                  {t}
                </div>
              ))}
            </div>
            <div style={styles.tabBody}>
              {tab === "Summary" && (
                <div>
                  <div style={styles.summaryGrid}>
                    <Stat num={summary.geometry_nodes ?? 0} label="Geometry nodes" color="#3b82f6" />
                    <Stat num={summary.feature_nodes ?? 0} label="Features" color="#a855f7" />
                    <Stat num={summary.constraint_nodes ?? 0} label="Constraints" color="#ef4444" />
                    <Stat num={summary.edges ?? 0} label="Edges" />
                    <Stat
                      num={summary.validation_errors ?? 0}
                      label="Validation errors"
                      color={summary.validation_errors ? "#ef4444" : "#10b981"}
                    />
                    <Stat
                      num={summary.validation_warnings ?? 0}
                      label="Warnings"
                      color={summary.validation_warnings ? "#f59e0b" : "#10b981"}
                    />
                  </div>
                  <div style={{ ...styles.stat, marginTop: 8 }}>
                    <div style={styles.statLabel}>Panel size</div>
                    <div style={{ fontWeight: 700 }}>
                      {summary.panel_width_mm != null
                        ? `${summary.panel_width_mm.toFixed(0)} × ${(summary.panel_height_mm ?? 0).toFixed(0)} mm`
                        : "unknown"}
                    </div>
                  </div>
                  {Array.isArray(result.parse_warnings) && result.parse_warnings.length > 0 && (
                    <div style={{ ...styles.stat, marginTop: 8 }}>
                      <div style={{ ...styles.statLabel, color: "#f59e0b" }}>
                        {result.parse_warnings.length} parse warning(s)
                      </div>
                      {result.parse_warnings.slice(0, 5).map((w, i) => (
                        <div key={i} style={{ fontSize: 11, opacity: 0.75, marginTop: 3 }}>
                          {w.message || JSON.stringify(w)}
                        </div>
                      ))}
                    </div>
                  )}
                  <div style={{ marginTop: 12 }}>
                    <AuthorityLegend />
                  </div>
                </div>
              )}
              {tab === "Validation" && <ValidationPanel validation={result.validation} />}
              {tab === "Features" && (
                <SemanticPanel
                  annotations={result.annotations}
                  selectedId={selectedId}
                  onSelect={onFeatureSelect}
                />
              )}
              {tab === "Provenance" && <ProvenancePanel node={selectedNode} />}
              {tab === "LLM" && <LLMAdvisoryPanel annotations={llm} />}
            </div>
          </aside>
        )}
      </div>
    </div>
  );
}
