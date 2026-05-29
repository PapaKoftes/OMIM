"""LLM-based semantic annotation via Featherless AI.

This is the LOWEST authority layer in OMIM. LLM output is advisory only.
It explains features in natural language — it NEVER overrides geometry or validation.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from omim.config import get_settings
from omim.graph.mgg import ManufacturingGeometryGraph
from omim.semantic.models import SemanticAnnotation

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a manufacturing domain expert analyzing CNC panel machining geometry.
You will be given a JSON description of a manufacturing feature detected in a DXF file.
Provide a brief, factual explanation of what this feature likely is and its manufacturing purpose.
Be specific to cabinetry and panel CNC machining (MDF, plywood, melamine).
Always note that your explanation is advisory and the geometric data is authoritative.
Respond with JSON: {"explanation": "...", "manufacturing_context": "..."}
"""


class LLMAnnotator:
    """Generate natural-language explanations for classified features."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        settings = get_settings()
        self.api_key = api_key or settings.featherless_api_key
        self.base_url = base_url or settings.featherless_base_url
        self.model = model or settings.featherless_model

    async def annotate_feature(
        self,
        feature_data: dict[str, Any],
        geometry_data: dict[str, Any] | None = None,
    ) -> SemanticAnnotation:
        """Call Featherless AI to explain a single feature."""
        user_content = json.dumps({
            "feature": feature_data,
            "geometry": geometry_data or {},
        }, default=str)

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_content},
                    ],
                    "temperature": 0.2,
                    "max_tokens": 300,
                },
            )
            response.raise_for_status()
            data = response.json()

        content = data["choices"][0]["message"]["content"]
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            parsed = {"explanation": content, "manufacturing_context": ""}

        return SemanticAnnotation(
            feature_node_id=feature_data.get("node_id", "unknown"),
            natural_language=parsed.get("explanation", content),
            manufacturing_context=parsed.get("manufacturing_context", ""),
            model_id=self.model,
        )

    async def annotate_mgg(
        self,
        mgg: ManufacturingGeometryGraph,
        *,
        max_features: int = 50,
    ) -> list[SemanticAnnotation]:
        """Annotate top features in an MGG. Returns annotations without
        modifying the graph (LLM output is advisory only)."""
        annotations = []
        count = 0

        for nid, data in mgg.feature_nodes():
            if count >= max_features:
                break

            # Get linked geometry data
            geom_ids = data.get("geometry_node_ids", [])
            geom_data = None
            if geom_ids:
                geom_data = mgg.get_node(geom_ids[0])

            try:
                annotation = await self.annotate_feature(data, geom_data)
                annotations.append(annotation)
            except Exception:
                logger.exception("LLM annotation failed for %s", nid)

            count += 1

        return annotations
