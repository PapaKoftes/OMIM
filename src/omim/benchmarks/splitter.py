"""Deterministic train/val/test splitting for OMIM benchmarks.

Mirrors docs/09_BENCHMARKS/Train_Test_Policy.md:

  * Split membership is reproducible from the sample index alone.
  * The test split is frozen — given the same dataset it never changes.
  * Splits are guaranteed disjoint.

Two sources of truth, in priority order:

  1. ``splits/{train,val,test}.jsonl`` on disk (written by the synthetic
     generator). If present these are authoritative and simply loaded.
  2. Otherwise, a deterministic re-derivation from the integer index embedded
     in each ``sample_id`` (``sample_000007`` -> 7) using the ``% 100`` banding
     from the Train-Test Policy.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

__all__ = ["DatasetSplits", "BenchmarkSplitter"]

_INDEX_RE = re.compile(r"(\d+)")


@dataclass
class DatasetSplits:
    """Disjoint sample-id sets for the three canonical splits."""

    train: list[str] = field(default_factory=list)
    val: list[str] = field(default_factory=list)
    test: list[str] = field(default_factory=list)

    def get(self, split: str) -> list[str]:
        split = split.lower()
        if split == "train":
            return self.train
        if split == "val":
            return self.val
        if split == "test":
            return self.test
        raise ValueError(f"Unknown split {split!r}; expected train|val|test")

    def is_disjoint(self) -> bool:
        s_train, s_val, s_test = set(self.train), set(self.val), set(self.test)
        return (
            not (s_train & s_val)
            and not (s_train & s_test)
            and not (s_val & s_test)
        )

    def counts(self) -> dict[str, int]:
        return {
            "train": len(self.train),
            "val": len(self.val),
            "test": len(self.test),
        }


def _sample_index(sample_id: str) -> int:
    """Extract the trailing integer index from a sample id (deterministic)."""
    matches = _INDEX_RE.findall(sample_id)
    if not matches:
        # Stable hash fallback so unusual ids still split deterministically.
        return abs(hash(sample_id)) % 100
    return int(matches[-1])


class BenchmarkSplitter:
    """Produce deterministic, disjoint dataset splits by sample id."""

    def __init__(
        self,
        train_ratio: float = 0.70,
        val_ratio: float = 0.15,
        test_ratio: float = 0.15,
    ) -> None:
        total = train_ratio + val_ratio + test_ratio
        if abs(total - 1.0) > 1e-6:
            raise ValueError(
                f"Split ratios must sum to 1.0 (got {total:.4f})"
            )
        self.train_ratio = train_ratio
        self.val_ratio = val_ratio
        self.test_ratio = test_ratio

    # ------------------------------------------------------------------
    # Disk-backed splits (authoritative when present)
    # ------------------------------------------------------------------

    @staticmethod
    def _load_jsonl_ids(path: Path) -> list[str]:
        if not path.exists():
            return []
        ids: list[str] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                ids.append(line)
                continue
            if isinstance(obj, str):
                ids.append(obj)
            elif isinstance(obj, dict):
                sid = obj.get("sample_id") or obj.get("id")
                if sid is not None:
                    ids.append(str(sid))
        return ids

    def load_splits(self, dataset_dir: str | Path) -> DatasetSplits | None:
        """Load ``splits/*.jsonl`` if present; return ``None`` if absent."""
        splits_dir = Path(dataset_dir) / "splits"
        train_p = splits_dir / "train.jsonl"
        val_p = splits_dir / "val.jsonl"
        test_p = splits_dir / "test.jsonl"
        if not (train_p.exists() or val_p.exists() or test_p.exists()):
            return None
        return DatasetSplits(
            train=self._load_jsonl_ids(train_p),
            val=self._load_jsonl_ids(val_p),
            test=self._load_jsonl_ids(test_p),
        )

    # ------------------------------------------------------------------
    # Deterministic derivation from sample ids
    # ------------------------------------------------------------------

    def assign(self, sample_id: str) -> str:
        """Return the split name for one sample id via ``% 100`` banding."""
        band = _sample_index(sample_id) % 100
        train_cut = self.train_ratio * 100
        val_cut = (self.train_ratio + self.val_ratio) * 100
        if band < train_cut:
            return "train"
        if band < val_cut:
            return "val"
        return "test"

    def create_splits(self, sample_ids: list[str]) -> DatasetSplits:
        """Derive disjoint splits from a list of sample ids (deterministic).

        Each id is assigned to exactly one split, so disjointness is guaranteed
        by construction. Order within a split follows the sorted sample ids.
        """
        splits = DatasetSplits()
        for sid in sorted(set(sample_ids), key=lambda s: (_sample_index(s), s)):
            getattr(splits, self.assign(sid)).append(sid)
        return splits

    # ------------------------------------------------------------------
    # Unified entry point
    # ------------------------------------------------------------------

    def resolve(
        self,
        dataset_dir: str | Path,
        sample_ids: list[str] | None = None,
    ) -> DatasetSplits:
        """Prefer on-disk splits; fall back to deterministic derivation.

        Always returns disjoint splits. If on-disk splits somehow overlap, they
        are repaired deterministically (a sample is kept only in its first
        appearance in train, then val, then test).
        """
        disk = self.load_splits(dataset_dir)
        if disk is not None:
            return self._dedupe(disk)
        if sample_ids is None:
            # Discover sample ids from the samples directory.
            samples_dir = Path(dataset_dir) / "samples"
            sample_ids = (
                [p.name for p in samples_dir.iterdir() if p.is_dir()]
                if samples_dir.exists()
                else []
            )
        return self.create_splits(sample_ids)

    @staticmethod
    def _dedupe(splits: DatasetSplits) -> DatasetSplits:
        """Guarantee disjointness: train wins over val wins over test."""
        seen: set[str] = set()
        out = DatasetSplits()
        for name in ("train", "val", "test"):
            for sid in splits.get(name):
                if sid in seen:
                    continue
                seen.add(sid)
                getattr(out, name).append(sid)
        return out
