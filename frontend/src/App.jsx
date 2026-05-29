import React, { useState, useCallback } from "react";
import GraphViewer from "./components/GraphViewer";
import ValidationPanel from "./components/ValidationPanel";
import SemanticPanel from "./components/SemanticPanel";

const styles = {
  container: {
    display: "flex",
    flexDirection: "column",
    height: "100vh",
    background: "#0f1419",
    color: "#e7e9ea",
  },
  header: {
    padding: "12px 24px",
    borderBottom: "1px solid #2f3336",
    display: "flex",
    alignItems: "center",
    gap: "16px",
  },
  title: { fontSize: "18px", fontWeight: 700 },
  subtitle: { fontSize: "12px", opacity: 0.6 },
  main: { display: "flex", flex: 1, overflow: "hidden" },
  graphPanel: { flex: 1, position: "relative" },
  sidebar: {
    width: "360px",
    borderLeft: "1px solid #2f3336",
    overflow: "auto",
    padding: "16px",
  },
  upload: {
    padding: "8px 16px",
    background: "#1d9bf0",
    border: "none",
    borderRadius: "6px",
    color: "#fff",
    cursor: "pointer",
    fontSize: "14px",
  },
  dropZone: {
    border: "2px dashed #2f3336",
    borderRadius: "8px",
    padding: "40px",
    textAlign: "center",
    margin: "20px",
  },
  summary: {
    padding: "12px",
    background: "#1a1f25",
    borderRadius: "8px",
    marginBottom: "12px",
    fontSize: "13px",
  },
};

export default function App() {
  const [analysisResult, setAnalysisResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleUpload = useCallback(async (file) => {
    setLoading(true);
    setError(null);
    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch("/api/v1/analyze", {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Analysis failed");
      setAnalysisResult(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleFileInput = (e) => {
    const file = e.target.files?.[0];
    if (file) handleUpload(file);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    const file = e.dataTransfer.files?.[0];
    if (file) handleUpload(file);
  };

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
        <label htmlFor="file-upload" style={styles.upload}>
          {loading ? "Analyzing..." : "Upload DXF"}
        </label>
        {error && <span style={{ color: "#f4212e", fontSize: "13px" }}>{error}</span>}
      </header>

      <div style={styles.main}>
        <div style={styles.graphPanel} onDrop={handleDrop} onDragOver={(e) => e.preventDefault()}>
          {analysisResult?.graph ? (
            <GraphViewer elements={analysisResult.graph.elements} />
          ) : (
            <div style={styles.dropZone}>
              <p style={{ fontSize: "16px", marginBottom: "8px" }}>
                Drop a DXF file here or click Upload
              </p>
              <p style={{ opacity: 0.5, fontSize: "13px" }}>
                Supports: CIRCLE, LWPOLYLINE, LINE, ARC entities
              </p>
            </div>
          )}
        </div>

        {analysisResult && (
          <aside style={styles.sidebar}>
            <div style={styles.summary}>
              <strong>Summary</strong>
              <div>Geometry: {analysisResult.summary?.geometry_nodes || 0} nodes</div>
              <div>Features: {analysisResult.summary?.feature_nodes || 0} classified</div>
              <div>Edges: {analysisResult.summary?.edges || 0}</div>
              <div>
                Panel: {analysisResult.summary?.panel_width_mm?.toFixed(0) || "?"} ×{" "}
                {analysisResult.summary?.panel_height_mm?.toFixed(0) || "?"} mm
              </div>
            </div>
            <ValidationPanel validation={analysisResult.validation} />
            <SemanticPanel classifications={analysisResult.classifications} />
          </aside>
        )}
      </div>
    </div>
  );
}
