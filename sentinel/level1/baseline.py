"""SQLite-backed baseline for Level 1 anomaly detection.

Tracks per-tool statistics (call counts, error rates, parameter shapes)
and compares incoming requests against the established baseline.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import aiosqlite

from .fingerprint import RequestFingerprint


@dataclass
class AnomalyResult:
    """Result of an anomaly check against the baseline."""

    is_anomalous: bool
    score: float  # 0.0 = completely normal, 1.0 = very anomalous
    reasons: list[str] = field(default_factory=list)


class Baseline:
    """SQLite-backed baseline that learns what 'normal' looks like.

    The baseline is considered "established" after `threshold` observations.
    Before that, nothing is flagged — we're still learning.
    """

    def __init__(self, db_path: str | Path, threshold: int = 100):
        self.db_path = Path(db_path)
        self.threshold = threshold
        self._db: Optional[aiosqlite.Connection] = None
        self._total_observations: int = 0

    async def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(str(self.db_path))
        await self._create_tables()
        self._total_observations = await self._count_observations()

    async def _create_tables(self) -> None:
        await self._db.executescript("""
            CREATE TABLE IF NOT EXISTS tool_stats (
                tool_name   TEXT PRIMARY KEY,
                call_count  INTEGER DEFAULT 0,
                error_count INTEGER DEFAULT 0,
                first_seen  REAL,
                last_seen   REAL
            );

            CREATE TABLE IF NOT EXISTS param_shapes (
                tool_name       TEXT,
                shape_hash      TEXT,
                param_keys_json TEXT,
                count           INTEGER DEFAULT 0,
                first_seen      REAL,
                PRIMARY KEY (tool_name, shape_hash)
            );
        """)
        await self._db.commit()

    async def _count_observations(self) -> int:
        async with self._db.execute(
            "SELECT COALESCE(SUM(call_count), 0) FROM tool_stats"
        ) as cur:
            row = await cur.fetchone()
            return row[0]

    @property
    def is_established(self) -> bool:
        return self._total_observations >= self.threshold

    async def update(self, fp: RequestFingerprint) -> None:
        """Record a new observation into the baseline."""
        now = fp.timestamp

        await self._db.execute(
            """
            INSERT INTO tool_stats (tool_name, call_count, error_count, first_seen, last_seen)
            VALUES (?, 1, ?, ?, ?)
            ON CONFLICT(tool_name) DO UPDATE SET
                call_count  = call_count + 1,
                error_count = error_count + ?,
                last_seen   = ?
            """,
            (fp.tool_name, int(fp.is_error), now, now, int(fp.is_error), now),
        )

        param_keys_json = json.dumps(sorted(fp.param_keys))
        await self._db.execute(
            """
            INSERT INTO param_shapes (tool_name, shape_hash, param_keys_json, count, first_seen)
            VALUES (?, ?, ?, 1, ?)
            ON CONFLICT(tool_name, shape_hash) DO UPDATE SET
                count = count + 1
            """,
            (fp.tool_name, fp.shape_hash, param_keys_json, now),
        )

        await self._db.commit()
        self._total_observations += 1

    async def is_anomalous(
        self, fp: RequestFingerprint, sensitivity: float
    ) -> AnomalyResult:
        """Check whether a fingerprint deviates from the established baseline.

        Sensitivity scale (per spec):
            0.0 = flag everything (most sensitive)
            1.0 = almost never flag (least sensitive)

        An event is flagged when its anomaly score exceeds `sensitivity`.
        """
        if not self.is_established:
            return AnomalyResult(
                is_anomalous=False,
                score=0.0,
                reasons=["baseline not yet established"],
            )

        score = 0.0
        reasons: list[str] = []

        # --- Signal 1: unknown tool (strongest signal) ---
        async with self._db.execute(
            "SELECT call_count, error_count FROM tool_stats WHERE tool_name = ?",
            (fp.tool_name,),
        ) as cur:
            tool_row = await cur.fetchone()

        if tool_row is None:
            score = max(score, 1.0)
            reasons.append(f"unknown tool: {fp.tool_name}")
        else:
            call_count, error_count = tool_row

            # --- Signal 2: new parameter shape ---
            async with self._db.execute(
                "SELECT count FROM param_shapes WHERE tool_name = ? AND shape_hash = ?",
                (fp.tool_name, fp.shape_hash),
            ) as cur:
                shape_row = await cur.fetchone()

            if shape_row is None:
                score = max(score, 0.7)
                reasons.append(f"new parameter shape for tool {fp.tool_name}")

            # --- Signal 3: error on normally-reliable tool ---
            if fp.is_error and call_count > 0:
                error_rate = error_count / call_count
                if error_rate < 0.05:
                    score = max(score, 0.5)
                    reasons.append(
                        f"error on reliable tool {fp.tool_name} "
                        f"(historical error rate: {error_rate:.1%})"
                    )

        if not reasons:
            reasons.append("normal")

        return AnomalyResult(
            is_anomalous=score > sensitivity,
            score=score,
            reasons=reasons,
        )

    async def close(self) -> None:
        if self._db:
            await self._db.close()
            self._db = None
