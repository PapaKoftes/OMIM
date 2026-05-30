import React from "react";
import { AUTHORITY_ORDER, authorityFor } from "../authority";

// Small inline pill that names the authority level of a single fact.
export function AuthorityBadge({ method, title }) {
  const a = authorityFor(method);
  return (
    <span
      title={title || a.desc}
      style={{
        display: "inline-block",
        padding: "1px 6px",
        borderRadius: "4px",
        fontSize: "10px",
        fontWeight: 700,
        letterSpacing: "0.3px",
        background: a.color + "22",
        color: a.color,
        border: `1px solid ${a.color}`,
        whiteSpace: "nowrap",
      }}
    >
      {a.short}
    </span>
  );
}

// The headline differentiator: a ranked legend that teaches the trust model.
// Geometry (fact) > Validation (deterministic) > Semantic (heuristic) > ML/LLM (advisory).
export function AuthorityLegend({ compact = false }) {
  return (
    <div
      style={{
        background: "#12171d",
        border: "1px solid #2f3336",
        borderRadius: "8px",
        padding: "10px 12px",
        fontSize: "11px",
      }}
    >
      <div
        style={{
          fontWeight: 700,
          fontSize: "11px",
          textTransform: "uppercase",
          letterSpacing: "0.5px",
          opacity: 0.7,
          marginBottom: "8px",
        }}
      >
        Authority hierarchy
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "4px" }}>
        {AUTHORITY_ORDER.map((a, i) => (
          <React.Fragment key={a.label}>
            <span
              title={a.desc}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "5px",
                padding: "2px 7px",
                borderRadius: "5px",
                background: a.color + "22",
                border: `1px solid ${a.color}`,
                color: a.color,
                fontWeight: 600,
                whiteSpace: "nowrap",
              }}
            >
              <span
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  background: a.color,
                  display: "inline-block",
                }}
              />
              {a.tier}
            </span>
            {i < AUTHORITY_ORDER.length - 1 && (
              <span style={{ opacity: 0.4, fontWeight: 700 }}>&gt;</span>
            )}
          </React.Fragment>
        ))}
      </div>
      {!compact && (
        <div style={{ marginTop: "8px", opacity: 0.55, lineHeight: 1.4 }}>
          Higher authority overrides lower. Geometry is fact; validation is exact
          pass/fail; semantic and ML/LLM outputs are <strong>advisory</strong>.
        </div>
      )}
    </div>
  );
}

export default AuthorityBadge;
