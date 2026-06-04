"""External-dataset adapters (not bundled — each carries its own license).

Make a downloaded third-party dataset usable in OMIM terms by mapping its native
label vocabulary onto OMIM's taxonomy:

  * archcad — ArchCAD-400K (CC0): vector-CAD panoptic symbols; methodology
              precedent + permissive pretraining corpus (architectural, not panels)
  * mfcad   — MFCAD / MFCAD++ (MIT): machining-feature TAXONOMY reference
              (3D B-Rep; geometry not ingestible, labels are)

See ``data/datasets/README.md`` for how to acquire each dataset.
"""

from omim.datasets import archcad, mfcad
from omim.datasets.models import DatasetManifest, DatasetSample

__all__ = ["DatasetManifest", "DatasetSample", "archcad", "mfcad"]
