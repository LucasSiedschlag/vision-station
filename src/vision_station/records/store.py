"""Results and the training dataset (architecture §8).

    <root>/results/results.db                         one row per inspection (SQLite, WAL)
    <root>/results/images/YYYY/MM/DD/<id>.jpg         the inspection frame; <id>.overlay.jpg is the drawn-on copy
    <root>/dataset/<job-id>/<id>.jpg                  frames collected or corrected, for labeling and training

The raw frame is kept apart from the overlay so it stays usable for training. Nothing under
`dataset/` or the job store is ever deleted automatically (housekeeping only touches `results/`).
By default every image is kept; the sampling, retention and disk limits are settings, because how
long to keep them was not defined yet (FR-LOG-2/3).
"""

import csv
import hashlib
import io
import json
import os
import shutil
import sqlite3
import threading
import uuid
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from vision_station.core.results import InspectionResult, Outcome

SCHEMA_VERSION = 1
_SCHEMA = """
CREATE TABLE IF NOT EXISTS inspections (
    id TEXT PRIMARY KEY,
    at TEXT NOT NULL,
    at_epoch REAL NOT NULL,
    job_id TEXT NOT NULL,
    job_name TEXT NOT NULL,
    job_version INTEGER NOT NULL,
    outcome TEXT NOT NULL,
    reason TEXT NOT NULL,
    scores TEXT NOT NULL,
    timings TEXT NOT NULL,
    duration_ms REAL NOT NULL,
    image_path TEXT,
    overlay_path TEXT,
    sampled INTEGER NOT NULL DEFAULT 1,
    correct_outcome TEXT,
    corrected_at TEXT,
    corrected_by TEXT
);
CREATE INDEX IF NOT EXISTS ix_inspections_at ON inspections(at_epoch);
CREATE INDEX IF NOT EXISTS ix_inspections_job ON inspections(job_id, at_epoch);
CREATE INDEX IF NOT EXISTS ix_inspections_outcome ON inspections(outcome, at_epoch);
CREATE TABLE IF NOT EXISTS dataset (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    job_name TEXT NOT NULL,
    job_version INTEGER NOT NULL,
    file TEXT NOT NULL,
    result TEXT,
    label TEXT,
    source TEXT NOT NULL,
    added_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS collection (job_id TEXT PRIMARY KEY, enabled INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value INTEGER NOT NULL);
"""
_COLUMNS = (
    "id, at, job_id, job_name, job_version, outcome, reason, scores, timings, duration_ms, "
    "image_path, overlay_path, sampled, correct_outcome, corrected_at, corrected_by"
)


class ResultsError(Exception):
    pass


@dataclass(frozen=True)
class RecordingConfig:
    pass_sample_every: int = 1  # keep the image of 1 PASS in N (1 = all). FAIL and ERROR images are always kept.
    unsampled_pass_hours: float | None = None  # delete the image of a PASS not sampled after this long (None = never)
    retention_days: float | None = None  # delete records older than this (None = keep everything)
    min_free_bytes: int | None = None  # below this, delete the oldest PASS images, then FAIL ones
    jpeg_quality: int = 92


@dataclass(frozen=True)
class InspectionRecord:
    id: str
    at: str
    job_id: str
    job_name: str
    job_version: int
    outcome: str
    reason: str
    scores: Mapping[str, float]
    timings: Mapping[str, float]  # seconds per step (quality, locate, tools, total)
    tool_timings: Mapping[str, float]  # seconds per tool id
    duration_ms: float
    image_path: str | None
    overlay_path: str | None
    sampled: bool
    correct_outcome: str | None
    corrected_at: str | None
    corrected_by: str | None


@dataclass(frozen=True)
class Query:
    since: datetime | None = None
    until: datetime | None = None
    job_id: str | None = None
    outcome: str | None = None
    incorrect_only: bool = False  # results an operator marked as wrong


@dataclass(frozen=True)
class DatasetExport:
    path: Path
    dataset_id: str
    count: int


def _split_timings(raw: Any) -> tuple[dict[str, float], dict[str, float]]:
    """The pipeline keeps the time of each tool under `per_tool` (VIA-0046); the steps and the tools are
    returned apart, numbers only, so records saved before this read the same way."""
    if not isinstance(raw, Mapping):
        return {}, {}
    steps = {k: float(v) for k, v in raw.items() if isinstance(v, (int, float)) and not isinstance(v, bool)}
    per_tool = raw.get("per_tool")
    tools = {k: float(v) for k, v in per_tool.items() if isinstance(v, (int, float))} if isinstance(per_tool, Mapping) else {}
    return steps, tools


def _row(r: sqlite3.Row | tuple) -> InspectionRecord:
    timings, tool_timings = _split_timings(json.loads(r[8]))
    return InspectionRecord(
        id=r[0], at=r[1], job_id=r[2], job_name=r[3], job_version=r[4], outcome=r[5], reason=r[6],
        scores=json.loads(r[7]), timings=timings, tool_timings=tool_timings, duration_ms=r[9], image_path=r[10],
        overlay_path=r[11], sampled=bool(r[12]), correct_outcome=r[13], corrected_at=r[14], corrected_by=r[15],
    )


def _encode(image: np.ndarray, quality: int) -> bytes:
    ok, data = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise ResultsError("cannot encode the image")
    return data.tobytes()


def _write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.part")
    try:
        tmp.write_bytes(data)
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


class ResultStore:
    def __init__(
        self,
        root: Path | str,
        config: RecordingConfig = RecordingConfig(),
        clock: Callable[[], datetime] = lambda: datetime.now().astimezone(),
        disk_free: Callable[[Path], int] = lambda p: shutil.disk_usage(p).free,
    ):
        self.root = Path(root)
        self.config = config
        self._clock = clock
        self._disk_free = disk_free
        self.results_dir = self.root / "results"
        self.dataset_dir = self.root / "dataset"
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.dataset_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(self.results_dir / "results.db", check_same_thread=False, isolation_level=None)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=NORMAL")
        self._db.executescript(_SCHEMA)
        self._db.execute(f"PRAGMA user_version={SCHEMA_VERSION}")

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def __enter__(self) -> "ResultStore":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # --- recording -------------------------------------------------------------

    def record(
        self,
        result: InspectionResult,
        frame: np.ndarray | None,
        *,
        job_id: str,
        job_name: str,
        job_version: int,
        overlay: np.ndarray | None = None,
    ) -> InspectionRecord:
        """Write one inspection: the frame first, then the row, so a row never points at a missing image."""
        now = self._clock()
        rid = f"{now:%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:6]}"
        with self._lock:
            written: list[Path] = []
            self._db.execute("BEGIN IMMEDIATE")
            try:
                sampled = True
                if result.outcome is Outcome.PASS:
                    n = self._bump("pass_counter")
                    sampled = self.config.pass_sample_every <= 1 or n % self.config.pass_sample_every == 0
                encoded = _encode(frame, self.config.jpeg_quality) if frame is not None else None
                image_rel = overlay_rel = None
                if encoded is not None:
                    folder = Path("results") / "images" / f"{now:%Y}" / f"{now:%m}" / f"{now:%d}"
                    image_rel = (folder / f"{rid}.jpg").as_posix()
                    _write_atomic(self.root / image_rel, encoded)
                    written.append(self.root / image_rel)
                    if overlay is not None:
                        overlay_rel = (folder / f"{rid}.overlay.jpg").as_posix()
                        _write_atomic(self.root / overlay_rel, _encode(overlay, self.config.jpeg_quality))
                        written.append(self.root / overlay_rel)
                raw_timings = result.details.get("timings", {})
                timings = dict(raw_timings) if isinstance(raw_timings, Mapping) else {}
                self._db.execute(
                    f"INSERT INTO inspections ({_COLUMNS}, at_epoch) VALUES ({','.join('?' * 17)})",
                    (
                        rid, now.isoformat(timespec="milliseconds"), job_id, job_name, job_version, str(result.outcome), result.reason,
                        json.dumps(dict(result.scores), sort_keys=True), json.dumps(timings, sort_keys=True),
                        (result.duration_s or 0.0) * 1000, image_rel, overlay_rel, int(sampled), None, None, None,
                        now.timestamp(),
                    ),
                )
                if encoded is not None and self._collecting(job_id):
                    written.append(self._add_dataset(rid, job_id, job_name, job_version, encoded, result=str(result.outcome), label=None, source="collected", now=now))
                self._db.execute("COMMIT")
            except BaseException:
                self._db.execute("ROLLBACK")
                for path in written:
                    path.unlink(missing_ok=True)
                raise
            return self.get(rid)  # type: ignore[return-value]

    def _bump(self, key: str) -> int:
        self._db.execute("INSERT INTO meta(key, value) VALUES(?, 1) ON CONFLICT(key) DO UPDATE SET value = value + 1", (key,))
        return self._db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()[0]

    # --- reading ---------------------------------------------------------------

    def get(self, rid: str) -> InspectionRecord | None:
        with self._lock:
            r = self._db.execute(f"SELECT {_COLUMNS} FROM inspections WHERE id=?", (rid,)).fetchone()
        return _row(r) if r else None

    @staticmethod
    def _where(q: Query) -> tuple[str, list[Any]]:
        clauses, args = [], []
        if q.since is not None:
            clauses.append("at_epoch >= ?")
            args.append(q.since.timestamp())
        if q.until is not None:
            clauses.append("at_epoch < ?")
            args.append(q.until.timestamp())
        if q.job_id:
            clauses.append("job_id = ?")
            args.append(q.job_id)
        if q.outcome:
            clauses.append("outcome = ?")
            args.append(q.outcome)
        if q.incorrect_only:
            clauses.append("correct_outcome IS NOT NULL")
        return (" WHERE " + " AND ".join(clauses)) if clauses else "", args

    def find(self, query: Query = Query(), limit: int = 100, offset: int = 0) -> list[InspectionRecord]:
        """Newest first."""
        where, args = self._where(query)
        with self._lock:
            rows = self._db.execute(f"SELECT {_COLUMNS} FROM inspections{where} ORDER BY at_epoch DESC, rowid DESC LIMIT ? OFFSET ?", (*args, limit, offset)).fetchall()
        return [_row(r) for r in rows]

    def count(self, query: Query = Query()) -> int:
        where, args = self._where(query)
        with self._lock:
            return self._db.execute(f"SELECT COUNT(*) FROM inspections{where}", args).fetchone()[0]

    def counts(self, since: datetime, job_id: str | None = None) -> dict[str, int]:
        """Totals for a shift (FR-UI-4): total, PASS, FAIL, ERROR since a moment."""
        where, args = self._where(Query(since=since, job_id=job_id))
        with self._lock:
            rows = self._db.execute(f"SELECT outcome, COUNT(*) FROM inspections{where} GROUP BY outcome", args).fetchall()
        out = {"PASS": 0, "FAIL": 0, "ERROR": 0}
        out.update({k: v for k, v in rows})
        out["total"] = sum(out.values())
        return out

    def image_path(self, record: InspectionRecord) -> Path | None:
        return self.root / record.image_path if record.image_path else None

    def export_csv(self, dest: Path | str | io.TextIOBase, query: Query = Query(), delimiter: str = ";") -> int:
        """Write the filtered results as CSV (UTF-8 with BOM, ';' separator, as Excel in Portuguese expects). Returns the row count."""
        header = ["id", "data_hora", "job", "versao", "resultado", "motivo", "notas", "duracao_ms", "imagem", "correcao", "corrigido_em", "corrigido_por"]

        def write(f: Any) -> int:
            w = csv.writer(f, delimiter=delimiter, lineterminator="\n")
            w.writerow(header)
            n = 0
            for offset in range(0, 10**9, 1000):
                page = self.find(query, limit=1000, offset=offset)
                if not page:
                    break
                for r in page:
                    w.writerow([r.id, r.at, r.job_name, r.job_version, r.outcome, r.reason, json.dumps(dict(r.scores), sort_keys=True), f"{r.duration_ms:.0f}", r.image_path or "", r.correct_outcome or "", r.corrected_at or "", r.corrected_by or ""])
                    n += 1
            return n

        if isinstance(dest, (str, Path)):
            with open(dest, "w", encoding="utf-8-sig", newline="") as f:
                return write(f)
        return write(dest)

    # --- collection mode and corrections (FR-MDL-1/2) ------------------------------

    def set_collection(self, job_id: str, enabled: bool) -> None:
        """While on for a job, every inspection frame is also saved to the training dataset."""
        with self._lock:
            self._db.execute("INSERT INTO collection(job_id, enabled) VALUES(?, ?) ON CONFLICT(job_id) DO UPDATE SET enabled=excluded.enabled", (job_id, int(enabled)))

    def _collecting(self, job_id: str) -> bool:
        r = self._db.execute("SELECT enabled FROM collection WHERE job_id=?", (job_id,)).fetchone()
        return bool(r and r[0])

    def collecting(self, job_id: str) -> bool:
        with self._lock:
            return self._collecting(job_id)

    def _add_dataset(self, rid: str, job_id: str, job_name: str, job_version: int, jpeg: bytes, *, result: str | None, label: str | None, source: str, now: datetime) -> Path:
        rel = (Path("dataset") / job_id / f"{rid}.jpg").as_posix()
        _write_atomic(self.root / rel, jpeg)
        self._db.execute(
            "INSERT INTO dataset(id, job_id, job_name, job_version, file, result, label, source, added_at) VALUES(?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET label=excluded.label, source=excluded.source, added_at=excluded.added_at",
            (rid, job_id, job_name, job_version, rel, result, label, source, now.isoformat(timespec="seconds")),
        )
        return self.root / rel

    def mark_incorrect(self, rid: str, correct_outcome: str, by: str = "") -> InspectionRecord:
        """The operator says this result was wrong. The frame goes to the dataset with the right label.

        Needs the stored frame: an unsampled PASS whose image was already deleted cannot be corrected.
        """
        if correct_outcome not in ("PASS", "FAIL"):
            raise ResultsError("the correct result must be PASS or FAIL")
        with self._lock:
            record = self.get(rid)
            if record is None:
                raise ResultsError(f"no such result: {rid}")
            if record.image_path is None or not (self.root / record.image_path).is_file():
                raise ResultsError("the image of this result was not kept, so it cannot go to the dataset")
            now = self._clock()
            self._db.execute("UPDATE inspections SET correct_outcome=?, corrected_at=?, corrected_by=?, sampled=1 WHERE id=?", (correct_outcome, now.isoformat(timespec="seconds"), by, rid))
            self._add_dataset(rid, record.job_id, record.job_name, record.job_version, (self.root / record.image_path).read_bytes(), result=record.outcome, label=correct_outcome, source="corrected", now=now)
            return self.get(rid)  # type: ignore[return-value]

    def dataset_count(self, job_id: str | None = None) -> int:
        with self._lock:
            if job_id:
                return self._db.execute("SELECT COUNT(*) FROM dataset WHERE job_id=?", (job_id,)).fetchone()[0]
            return self._db.execute("SELECT COUNT(*) FROM dataset").fetchone()[0]

    def export_dataset(self, dest_dir: Path | str, job_id: str | None = None) -> DatasetExport:
        """Copy the dataset to a folder: images/, labels.csv and a manifest with the SHA-256 of every file.
        The dataset id comes from the content, so a model card can point at exactly these images (TD-10)."""
        with self._lock:
            where, args = (" WHERE job_id=?", [job_id]) if job_id else ("", [])
            rows = self._db.execute(f"SELECT id, job_id, job_name, job_version, file, result, label, source, added_at FROM dataset{where} ORDER BY added_at, id", args).fetchall()
        if not rows:
            raise ResultsError("the dataset is empty")
        files: dict[str, bytes] = {}
        labels = io.StringIO()
        w = csv.writer(labels, lineterminator="\n")
        w.writerow(["file", "id", "job", "job_version", "result", "label", "source", "added_at"])
        for rid, jid, jname, jver, rel, result, label, source, added in rows:
            name = f"images/{jid}/{rid}.jpg"
            files[name] = (self.root / rel).read_bytes()
            w.writerow([name, rid, jname, jver, result or "", label or "", source, added])
        files["labels.csv"] = labels.getvalue().encode("utf-8")
        sums = {n: hashlib.sha256(d).hexdigest() for n, d in sorted(files.items())}
        dataset_id = hashlib.sha256("".join(f"{n}:{h}" for n, h in sums.items()).encode()).hexdigest()[:16]
        manifest = {"dataset_id": dataset_id, "created_at": self._clock().isoformat(timespec="seconds"), "count": len(rows), "files": sums}
        final = Path(dest_dir) / f"dataset_{dataset_id}"
        if final.exists():
            return DatasetExport(final, dataset_id, len(rows))  # the same content was exported before
        tmp = final.with_name(f".{final.name}.{uuid.uuid4().hex}.part")
        try:
            for name, data in {**files, "manifest.json": json.dumps(manifest, indent=2, sort_keys=True).encode()}.items():
                path = tmp / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            os.replace(tmp, final)
        except BaseException:
            shutil.rmtree(tmp, ignore_errors=True)
            raise
        return DatasetExport(final, dataset_id, len(rows))

    # --- housekeeping (FR-LOG-3) ---------------------------------------------------

    def housekeeping(self) -> dict[str, int]:
        """Apply the retention and disk limits to `results/`. Never touches `dataset/` or the job store.

        Order: records past retention; unsampled PASS images past their hours; then, if the disk is
        below the free-space limit, the oldest PASS images first and the oldest FAIL/ERROR images after.
        """
        cfg, now = self.config, self._clock()
        out = {"records": 0, "images": 0}
        with self._lock:
            if cfg.retention_days is not None:
                cutoff = (now - timedelta(days=cfg.retention_days)).timestamp()
                for rid, image, overlay in self._db.execute("SELECT id, image_path, overlay_path FROM inspections WHERE at_epoch < ?", (cutoff,)).fetchall():
                    out["images"] += self._delete_files(image, overlay)
                out["records"] = self._db.execute("DELETE FROM inspections WHERE at_epoch < ?", (cutoff,)).rowcount
            if cfg.unsampled_pass_hours is not None:
                cutoff = (now - timedelta(hours=cfg.unsampled_pass_hours)).timestamp()
                rows = self._db.execute("SELECT id, image_path, overlay_path FROM inspections WHERE outcome='PASS' AND sampled=0 AND image_path IS NOT NULL AND at_epoch < ?", (cutoff,)).fetchall()
                out["images"] += self._drop_images(rows)
            if cfg.min_free_bytes is not None:
                for outcome in ("PASS", "FAIL", "ERROR"):
                    while self._disk_free(self.root) < cfg.min_free_bytes:
                        rows = self._db.execute("SELECT id, image_path, overlay_path FROM inspections WHERE outcome=? AND image_path IS NOT NULL AND correct_outcome IS NULL ORDER BY at_epoch LIMIT 1", (outcome,)).fetchall()
                        if not rows:
                            break
                        out["images"] += self._drop_images(rows)  # one at a time: stop as soon as there is room
        return out

    def _drop_images(self, rows: list[tuple[str, str | None, str | None]]) -> int:
        n = 0
        for rid, image, overlay in rows:
            n += self._delete_files(image, overlay)
            self._db.execute("UPDATE inspections SET image_path=NULL, overlay_path=NULL WHERE id=?", (rid,))
        return n

    def _delete_files(self, *rels: str | None) -> int:
        n = 0
        for rel in rels:
            if rel and (self.root / rel).is_file():
                (self.root / rel).unlink()
                n += 1
        return n
