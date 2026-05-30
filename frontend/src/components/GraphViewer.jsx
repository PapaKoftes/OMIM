import React, { useRef, useEffect } from "react";
import cytoscape from "cytoscape";
import { AUTHORITY } from "../authority";

// Fill color encodes WHAT the node is (node_type).
const NODE_COLORS = {
  geometry: "#3b82f6",
  feature: "#a855f7",
  operation: "#06b6d4",
  constraint: "#ef4444",
};

// Border color encodes HOW MUCH to trust it (authority / inference_method).
// We expose inference_method onto each node's cytoscape data as `authority`
// in the transform step below so selectors can target it.
const EDGE_COLORS = {
  COMPOSES: "#6366f1",
  CONTAINS: "#14b8a6",
  ADJACENT_TO: "#6b7280",
  VIOLATES: "#ef4444",
  CONFLICTS_WITH: "#ef4444",
  SAME_GROUP: "#f59e0b",
  SAME_ROW: "#8b5cf6",
  SAME_COLUMN: "#ec4899",
  PRODUCES: "#06b6d4",
  PRODUCED_BY: "#06b6d4",
  ENABLES: "#22c55e",
  REQUIRES_TOOLING: "#22c55e",
  DEPENDS_ON: "#94a3b8",
  APPLIES_TO: "#f97316",
};

const baseStylesheet = [
  {
    selector: "node",
    style: {
      label: "data(label)",
      "font-size": "8px",
      color: "#e7e9ea",
      "text-outline-color": "#0f1419",
      "text-outline-width": 1,
      "text-valign": "bottom",
      "text-margin-y": 2,
      width: 20,
      height: 20,
      "border-width": 3,
      "border-color": "#6b7280",
      "background-color": "#3b82f6",
    },
  },
  { selector: "node[node_type='geometry']", style: { "background-color": NODE_COLORS.geometry } },
  {
    selector: "node[node_type='feature']",
    style: { "background-color": NODE_COLORS.feature, shape: "diamond", width: 24, height: 24 },
  },
  {
    selector: "node[node_type='operation']",
    style: { "background-color": NODE_COLORS.operation, shape: "round-rectangle", width: 26, height: 18 },
  },
  {
    selector: "node[node_type='constraint']",
    style: { "background-color": NODE_COLORS.constraint, shape: "triangle", width: 24, height: 24 },
  },
  {
    selector: "node[is_outer_boundary]",
    style: { shape: "rectangle", width: 32, height: 32, "background-opacity": 0.35 },
  },
  // Authority borders (inference_method projected onto data.authority).
  ...Object.entries(AUTHORITY).map(([method, a]) => ({
    selector: `node[authority='${method}']`,
    style: { "border-color": a.color },
  })),
  // Selection highlight.
  {
    selector: "node:selected",
    style: { "border-width": 5, "border-color": "#ffffff", "overlay-opacity": 0.1 },
  },
  {
    selector: "edge",
    style: {
      width: 1.5,
      "line-color": "#4b5563",
      "target-arrow-color": "#4b5563",
      "target-arrow-shape": "triangle",
      "curve-style": "bezier",
      "arrow-scale": 0.6,
    },
  },
  ...Object.entries(EDGE_COLORS).map(([type, color]) => ({
    selector: `edge[edge_type='${type}']`,
    style: { "line-color": color, "target-arrow-color": color },
  })),
  {
    selector: "edge[edge_type='VIOLATES'], edge[edge_type='ADJACENT_TO'], edge[edge_type='CONFLICTS_WITH']",
    style: { "line-style": "dashed" },
  },
];

const legendStyle = {
  position: "absolute",
  bottom: 12,
  left: 12,
  background: "rgba(18,23,29,0.92)",
  border: "1px solid #2f3336",
  borderRadius: "8px",
  padding: "8px 10px",
  fontSize: "10px",
  lineHeight: 1.6,
  pointerEvents: "none",
  maxWidth: 220,
};

function LegendRow({ color, shape, text }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <span
        style={{
          width: 10,
          height: 10,
          background: color,
          display: "inline-block",
          borderRadius: shape === "round" ? "50%" : shape === "diamond" ? 0 : 2,
          transform: shape === "diamond" ? "rotate(45deg)" : "none",
        }}
      />
      <span>{text}</span>
    </div>
  );
}

export default function GraphViewer({ elements, onSelect }) {
  const containerRef = useRef(null);
  const cyRef = useRef(null);

  useEffect(() => {
    if (!containerRef.current || !elements) return;

    const cyElements = elements.map((el) => {
      if (el.group === "nodes") {
        const d = el.data || {};
        const method = d.provenance?.inference_method;
        const data = {
          ...d,
          authority: method || "unknown",
          // Friendly label: feature class / geometry type / constraint id, else id.
          label: d.feature_class || d.geometry_type || d.constraint_type || d.operation_type || d.id,
        };
        const pos = el.position || { x: Math.random() * 800, y: Math.random() * 600 };
        return { data, position: pos };
      }
      return { data: el.data };
    });

    const hasPositions = elements.some((e) => e.position);

    const cy = cytoscape({
      container: containerRef.current,
      elements: cyElements,
      style: baseStylesheet,
      layout: hasPositions
        ? { name: "preset", fit: true, padding: 40 }
        : { name: "cose", animate: false, nodeRepulsion: 8000, idealEdgeLength: 80, padding: 40 },
    });

    cy.on("tap", "node", (evt) => {
      if (onSelect) onSelect(evt.target.data());
    });
    cy.on("tap", (evt) => {
      if (evt.target === cy && onSelect) onSelect(null);
    });

    cyRef.current = cy;
    return () => cy.destroy();
  }, [elements, onSelect]);

  return (
    <div style={{ width: "100%", height: "100%", position: "relative" }}>
      <div ref={containerRef} style={{ width: "100%", height: "100%", background: "#0f1419" }} />
      <div style={legendStyle}>
        <div style={{ fontWeight: 700, marginBottom: 4, opacity: 0.7 }}>Node type (fill)</div>
        <LegendRow color={NODE_COLORS.geometry} shape="round" text="Geometry" />
        <LegendRow color={NODE_COLORS.feature} shape="diamond" text="Feature" />
        <LegendRow color={NODE_COLORS.operation} shape="rect" text="Operation" />
        <LegendRow color={NODE_COLORS.constraint} shape="diamond" text="Constraint" />
        <div style={{ fontWeight: 700, margin: "6px 0 4px", opacity: 0.7 }}>Border = authority</div>
        <LegendRow color={AUTHORITY.deterministic.color} shape="round" text="Deterministic (fact)" />
        <LegendRow color={AUTHORITY.heuristic.color} shape="round" text="Heuristic (advisory)" />
        <LegendRow color={AUTHORITY.ml_llm.color} shape="round" text="ML / LLM (advisory)" />
      </div>
    </div>
  );
}
