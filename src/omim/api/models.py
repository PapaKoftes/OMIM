"""Request/response schemas for the OMIM API.

These are thin Pydantic models for the endpoints that accept JSON bodies
(/annotate, /generate). File-upload endpoints use multipart and do not need a
body model. Response payloads are returned as plain dicts so they can carry the
existing ``model_dump()`` shapes from the core pipeline without re-modelling.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    """Body for ``POST /generate``.

    ``num_samples`` is capped server-side (see routes) so a single API call can
    never spin up a runaway generation job.
    """

    num_samples: int = Field(default=5, ge=1, le=50)
    seed: int = Field(default=42, ge=0)
    invalid_ratio: float = Field(default=0.30, ge=0.0, le=1.0)
    density: str = Field(default="medium", pattern="^(sparse|medium|dense)$")


class AnnotateRequest(BaseModel):
    """Body for ``POST /annotate`` when an MGG is supplied directly as JSON.

    Provide ``mgg`` (a serialized ManufacturingGeometryGraph dict, the shape
    produced by ``mgg.to_dict()``). If omitted, the endpoint expects a DXF
    upload instead (multipart) — the two modes are mutually exclusive.
    """

    mgg: dict[str, Any] | None = None
    max_features: int = Field(default=20, ge=1, le=50)
