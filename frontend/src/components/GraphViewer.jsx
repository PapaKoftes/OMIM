import React, { useRef, useEffect } from "react";
import cytoscape from "cytoscape";

const NODE_COLORS = {
  geometry: "#3b82f6",
  feature: "#10b981",
  constraint: "#ef4444",
};

const EDGE_COLORS = {
  COMPOSES: "#6366f1",
  ADJACENT_TO: "#6b7280",
  VIOLATES: "#ef4444",
  SAME_GROUP: "#f59e0b",
  SAME_ROW: "#8b5cf6",
  SAME_COLUMN: "#ec4899",
  CONTAINS: "#14b8a6",
};

const stylesheet = [
  {
    selector: "node",
    style: {
      label: "data(id)",
      "font-size": "8px",
      color: "#e7e9ea",
      "text-outline-color": "#0f1419",
      "text-outline-width": 1,
      width: 20,
      height: 20,
    },
  },
  {
    selector: "node[node_type='geometry']",
    style: { "background-color": NODE_COLORS.geometry },
  },
  {
    selector: "node[node_type='feature']",
    style: { "background-color": NODE_COLORS.feature, shape: "diamond", width: 24, height: 24 },
  },
  {
    selector: "node[node_type='constraint']",
    style: { "background-color": NODE_COLORS.constraint, shape: "triangle", width: 24, height: 24 },
  },
  {
    selector: "node[is_outer_boundary]",
    style: { "background-color": "#64748b", width: 30, height: 30, shape: "rectangle" },
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
  {
    selector: "edge[edge_type='VIOLATES']",
    style: { "line-color": EDGE_COLORS.VIOLATES, "target-arrow-color": EDGE_COLORS.VIOLATES, "line-style": "dashed" },
  },
  {
    selector: "edge[edge_type='COMPOSES']",
    style: { "line-color": EDGE_COLORS.COMPOSES, "target-arrow-color": EDGE_COLORS.COMPOSES },
  },
  {
    selector: "edge[edge_type='ADJACENT_TO']",
    style: { "line-color": EDGE_COLORS.ADJACENT_TO, "target-arrow-shape": "none", "line-style": "dotted" },
  },
];

export default function GraphViewer({ elements }) {
  const containerRef = useRef(null);
  const cyRef = useRef(null);

  useEffect(() => {
    if (!containerRef.current || !elements) return;

    // Transform elements for Cytoscape
    const cyElements = elements.map((el) => {
      if (el.group === "nodes") {
        const pos = el.position || { x: Math.random() * 800, y: Math.random() * 600 };
        return { data: el.data, position: pos };
      }
      return { data: el.data };
    });

    const cy = cytoscape({
      container: containerRef.current,
      elements: cyElements,
      style: stylesheet,
      layout: {
        name: elements.some((e) => e.position) ? "preset" : "cose",
        animate: false,
        nodeRepulsion: 8000,
        idealEdgeLength: 80,
      },
    });

    cyRef.current = cy;

    return () => cy.destroy();
  }, [elements]);

  return (
    <div
      ref={containerRef}
      style={{ width: "100%", height: "100%", background: "#0f1419" }}
    />
  );
}
