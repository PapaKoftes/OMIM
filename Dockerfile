# OMIM backend — FastAPI service.
#
# Single-stage build: installs the `omim` package (hatchling backend) and runs
# the API via uvicorn. The frontend lives in a separate image (Dockerfile.frontend).
FROM python:3.11-slim

WORKDIR /app

# System deps kept minimal; shapely/ezdxf ship manylinux wheels so no build
# toolchain is required for the pinned dependency set.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# The package layout is src/omim with a hatchling build backend, so the build
# needs pyproject.toml, the README it references, and the source tree present
# before `pip install .`.
COPY pyproject.toml README.md ./
COPY src/ src/
COPY data/ data/

RUN pip install --no-cache-dir .

EXPOSE 8000

# Entry point matches src/omim/api/main.py:app
CMD ["uvicorn", "omim.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
