import io
import json
import os
import stat
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

from vision_station.jobs import CameraProfile, Job
from vision_station.store import (
    FormatError,
    IntegrityError,
    JobBundle,
    JobRef,
    JobStore,
    StoreError,
    bundle_from_files,
)
from vision_station.store import archive as arc
from vision_station.store import job_store as js

FIXTURES = Path(__file__).parent / "fixtures"
JOB_ID = "3f1c9a2e-5b7d-4c1e-9a0f-2d6b8e4f7a10"
OTHER_ID = "9b2d4c60-1a3e-4f5b-8c7d-0e1f2a3b4c5d"


class Clock:
    """A clock that moves one minute on every call, so backup names differ."""

    def __init__(self):
        self.t = datetime(2026, 10, 14, 10, 0, tzinfo=timezone(timedelta(hours=-3)))

    def __call__(self):
        self.t += timedelta(minutes=1)
        return self.t


def make_bundle(version=1, job_id=JOB_ID, name="Etiqueta de lote", extra=None, params=None) -> JobBundle:
    data = yaml.safe_load((FIXTURES / "job.yaml").read_text(encoding="utf-8"))
    data["job"].update(id=job_id, name=name, version=version, parent_version=version - 1 if version > 1 else None)
    data["geometry"] = {"rois": {"label": {"relative_to": "frame", "rect": [0.2, 0.2, 0.8, 0.5]}}}
    data["tools"] = [
        {"id": "lote", "type": "code", "version": 1, "roi": "label", "params": params or {"formats": ["QRCode"]}, "reason_fail": "Código não lido"}
    ]
    profile = CameraProfile.model_validate(yaml.safe_load((FIXTURES / "profile.yaml").read_text()))
    return JobBundle(
        job=Job.model_validate(data),
        profile=profile,
        extra=extra if extra is not None else {"reference/reference.png": b"\x89PNG-fake", "tests/expected.yaml": b"images: []\n"},
    )


@pytest.fixture
def store(tmp_path):
    return JobStore(tmp_path / "data", clock=Clock())


def rezip(data: bytes, change) -> bytes:
    """Rebuild an archive after `change(entries: dict[name, bytes])`, keeping the manifest as it was."""
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        entries = {n: zf.read(n) for n in zf.namelist()}
    change(entries)
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as zf:
        for n, d in entries.items():
            zf.writestr(n, d)
    return out.getvalue()


# --- archive ---------------------------------------------------------------


def test_pack_and_unpack_round_trip_and_are_deterministic():
    files = {"job.yaml": b"a: 1\n", "camera/profile.yaml": b"b: 2\n", "reference/x.png": bytes(range(256))}
    data = arc.pack("job", files, {"job_id": "j", "version": 1})
    assert data == arc.pack("job", dict(reversed(files.items())), {"job_id": "j", "version": 1})
    out = arc.unpack(data, "job")
    assert out.files == files
    assert out.manifest["format"] == 1 and out.manifest["kind"] == "job"
    assert out.manifest["files"]["job.yaml"]["sha256"] == arc.sha256(b"a: 1\n")


@pytest.mark.parametrize(
    "tamper, error",
    [
        (lambda e: e.update({"job.yaml": b"a: 999\n"}), IntegrityError),  # content changed, manifest not
        (lambda e: e.pop("camera/profile.yaml"), IntegrityError),  # file missing
        (lambda e: e.update({"extra.txt": b"x"}), IntegrityError),  # file the manifest does not list
        (lambda e: e.pop("manifest.json"), FormatError),
        (lambda e: e.update({"manifest.json": b"{not json"}), FormatError),
        (lambda e: e.update({"manifest.json": json.dumps({"format": 2, "kind": "job", "files": {}}).encode()}), FormatError),
        (lambda e: e.update({"manifest.json": json.dumps({"format": 1, "kind": "backup", "files": {}}).encode()}), FormatError),
    ],
)
def test_damaged_or_wrong_files_are_refused(tamper, error):
    data = arc.pack("job", {"job.yaml": b"a: 1\n", "camera/profile.yaml": b"b: 2\n"}, {})
    with pytest.raises(error):
        arc.unpack(rezip(data, tamper), "job")


def test_newer_format_has_a_clear_message_and_garbage_is_refused():
    data = arc.pack("job", {"job.yaml": b"a: 1\n"}, {})
    newer = rezip(data, lambda e: e.update({"manifest.json": json.dumps({"format": 2, "kind": "job", "files": {}}).encode()}))
    with pytest.raises(FormatError, match="newer than this software"):
        arc.unpack(newer, "job")
    with pytest.raises(FormatError, match="not a valid"):
        arc.unpack(b"this is not a zip", "job")


@pytest.mark.parametrize("name", ["../evil.txt", "/abs.txt", "a/../../b.txt", "a\\b.txt", "C:/x.txt", "a//b.txt", ""])
def test_unsafe_paths_are_refused_on_pack_and_on_read(name):
    with pytest.raises(FormatError):
        arc.pack("job", {name: b"x"}, {})
    data = arc.pack("job", {"ok.txt": b"x"}, {})
    with pytest.raises(FormatError):
        arc.unpack(rezip(data, lambda e: e.update({name: b"x"})), "job")


def test_secrets_are_refused():
    arc.refuse_secrets({"job.yaml": b"tools: [{params: {mode: fast}}]\n"})
    with pytest.raises(StoreError, match="secrets"):
        arc.refuse_secrets({"job.yaml": b"camera:\n  password: hunter2\n"})
    with pytest.raises(StoreError, match="secrets"):
        arc.refuse_secrets({"system.yaml": b"- api_token: abc\n"})


# --- store -----------------------------------------------------------------


def test_save_and_load_versions(store):
    ref1 = store.save(make_bundle(1))
    ref2 = store.save(make_bundle(2))
    assert ref1 == JobRef(JOB_ID, 1) and ref2 == JobRef(JOB_ID, 2)
    assert store.job_ids() == [JOB_ID] and store.versions(JOB_ID) == [1, 2] and store.latest(JOB_ID) == 2
    loaded = store.load(ref2)
    assert loaded.job.job.version == 2 and loaded.job.job.parent_version == 1
    assert loaded.profile.resolution == (1920, 1080)
    assert loaded.extra["reference/reference.png"] == b"\x89PNG-fake"
    assert store.latest("nope") is None and store.versions("nope") == []


@pytest.mark.parametrize(
    "bundle_args",
    [
        {"version": 2},  # a new job must start at 1
        {"version": 1, "job_id": JOB_ID},  # saved twice (checked after the first save below)
    ],
)
def test_version_rules(store, bundle_args):
    if bundle_args["version"] == 1:
        store.save(make_bundle(1))
    with pytest.raises(StoreError):
        store.save(make_bundle(**bundle_args))


def test_versions_must_follow_each_other(store):
    store.save(make_bundle(1))
    with pytest.raises(StoreError, match="next version"):
        store.save(make_bundle(3))
    assert store.versions(JOB_ID) == [1]


def test_saved_files_are_read_only_and_a_version_is_never_overwritten(store):
    ref = store.save(make_bundle(1))
    path = store._folder(ref) / "job.yaml"
    assert not os.access(path, os.W_OK) or not (path.stat().st_mode & stat.S_IWUSR)
    with pytest.raises(StoreError, match="never changed"):
        store._store(ref, make_bundle(1).files())


def test_a_crash_while_saving_leaves_nothing_behind(store, monkeypatch):
    def boom(*a, **k):
        raise OSError("disk unplugged")

    monkeypatch.setattr(js.os, "rename", boom)
    with pytest.raises(OSError):
        store.save(make_bundle(1))
    assert store.versions(JOB_ID) == []
    assert list((store.jobs_dir / JOB_ID).iterdir()) == []  # no .tmp folder either


def test_damage_on_disk_is_detected_on_read(store):
    ref = store.save(make_bundle(1))
    victim = store._folder(ref) / "reference" / "reference.png"
    os.chmod(victim, stat.S_IREAD | stat.S_IWRITE)
    victim.write_bytes(b"changed")
    with pytest.raises(IntegrityError, match="damaged"):
        store.read_files(ref)


def test_jobs_with_secrets_or_unknown_tools_are_not_saved(store):
    with pytest.raises(StoreError, match="secrets"):
        store.save(make_bundle(1, extra={"camera/raw/dump.yaml": b"admin:\n  password: x\n"}))
    data = make_bundle(1).job.model_dump(mode="json")
    data["tools"][0]["type"] = "not_a_tool"
    bad = JobBundle(job=Job.model_validate(data), profile=make_bundle(1).profile)
    with pytest.raises(FormatError, match="cannot run on this software"):
        store.save(bad)
    assert store.job_ids() == []


def test_active_job(store):
    assert store.get_active() is None
    ref = store.save(make_bundle(1))
    store.set_active(ref)
    assert store.get_active() == ref
    store.set_active(store.save(make_bundle(2)))
    assert store.get_active() == JobRef(JOB_ID, 2)
    with pytest.raises(StoreError, match="no such job version"):
        store.set_active(JobRef(JOB_ID, 9))
    assert store.get_active() == JobRef(JOB_ID, 2)  # a refused change leaves the old one


# --- export and import -----------------------------------------------------


def test_export_import_round_trip_gives_the_same_files(store, tmp_path):
    ref = store.save(make_bundle(1))
    path = store.write_vjob(ref, tmp_path / "usb")
    assert path.name == f"{JOB_ID}_v1.vjob" and not list((tmp_path / "usb").glob(".*"))
    other = JobStore(tmp_path / "other")
    result = other.import_vjob(path.read_bytes())
    assert result.status == "added" and result.ref == ref
    assert other.read_files(ref).files == store.read_files(ref).files
    assert other.export_vjob(ref) == store.export_vjob(ref)  # same bytes: the export is a packed copy of the folder


def test_importing_the_same_file_twice_changes_nothing(store):
    data = (lambda r: store.export_vjob(r))(store.save(make_bundle(1)))
    again = store.import_vjob(data)
    assert again.status == "already_present" and store.versions(JOB_ID) == [1]


def test_same_version_with_different_content_becomes_the_next_version(store, tmp_path):
    store.save(make_bundle(1))
    other = JobStore(tmp_path / "other")
    other.save(make_bundle(1, name="Etiqueta (outra instalação)"))
    result = store.import_vjob(other.export_vjob(JobRef(JOB_ID, 1)))
    assert result.status == "renumbered" and result.original == JobRef(JOB_ID, 1) and result.ref == JobRef(JOB_ID, 2)
    assert store.versions(JOB_ID) == [1, 2]
    assert store.load(JobRef(JOB_ID, 1)).job.job.name == "Etiqueta de lote"  # the old one is untouched
    renumbered = store.load(JobRef(JOB_ID, 2)).job.job
    assert renumbered.name == "Etiqueta (outra instalação)" and renumbered.version == 2 and renumbered.parent_version == 1


def test_refused_imports_change_nothing(store):
    store.save(make_bundle(1))
    good = store.export_vjob(JobRef(JOB_ID, 1))
    for bad in (b"junk", rezip(good, lambda e: e.update({"job.yaml": b"format: 1\n"}))):
        with pytest.raises(StoreError):
            store.import_vjob(bad)
    no_profile = arc.pack("job", {k: v for k, v in make_bundle(1, job_id=OTHER_ID).files().items() if k != "camera/profile.yaml"}, {})
    with pytest.raises(FormatError, match="camera profile"):
        store.import_vjob(no_profile)
    assert store.job_ids() == [JOB_ID] and store.versions(JOB_ID) == [1]


def test_a_bad_copy_is_not_reported_as_written(store, tmp_path, monkeypatch):
    ref = store.save(make_bundle(1))
    monkeypatch.setattr(js, "unpack", lambda d, k: (_ for _ in ()).throw(IntegrityError("read back differs")))
    with pytest.raises(IntegrityError):
        store.write_vjob(ref, tmp_path / "usb")
    assert list((tmp_path / "usb").iterdir()) == []


# --- backup ----------------------------------------------------------------


def populate(store):
    store.save(make_bundle(1))
    store.save(make_bundle(2))
    store.save(make_bundle(1, job_id=OTHER_ID, name="Outro produto"))
    store.set_active(JobRef(JOB_ID, 2))


def test_backup_and_restore_on_a_fresh_installation(store, tmp_path):
    populate(store)
    path = store.make_backup(tmp_path / "bk", system_yaml="station: A1\ncamera:\n  driver: uvc\n")
    assert path.name.startswith("backup_2026-10-14_") and path.suffix == ".vbak"
    fresh = JobStore(tmp_path / "new-pc")
    report = fresh.restore_backup(path.read_bytes())
    assert sorted(r.ref for r in report.imported) == [JobRef(JOB_ID, 1), JobRef(JOB_ID, 2), JobRef(OTHER_ID, 1)]
    assert all(r.status == "added" for r in report.imported)
    assert report.active == JobRef(JOB_ID, 2) and fresh.get_active() is None  # to be verified before it is activated
    assert "driver: uvc" in report.system_yaml
    for ref in (JobRef(JOB_ID, 1), JobRef(JOB_ID, 2), JobRef(OTHER_ID, 1)):
        assert fresh.read_files(ref).files == store.read_files(ref).files


def test_backup_latest_only_and_restoring_twice(store, tmp_path):
    populate(store)
    data = store.make_backup(tmp_path / "bk", include="latest").read_bytes()
    fresh = JobStore(tmp_path / "new-pc")
    assert sorted(r.ref for r in fresh.restore_backup(data).imported) == [JobRef(JOB_ID, 2), JobRef(OTHER_ID, 1)]
    again = fresh.restore_backup(data)
    assert all(r.status == "already_present" for r in again.imported)


def test_backup_rotation_keeps_the_newest_after_the_copy_is_checked(store, tmp_path):
    populate(store)
    dest = tmp_path / "bk"
    made = [store.make_backup(dest, keep=3) for _ in range(5)]
    left = sorted(p.name for p in dest.glob("backup_*.vbak"))
    assert left == sorted(p.name for p in made[-3:])


def test_backup_names_do_not_collide_within_a_minute(tmp_path):
    fixed = datetime(2026, 10, 14, 18, 0, tzinfo=timezone.utc)
    s = JobStore(tmp_path / "d", clock=lambda: fixed)
    s.save(make_bundle(1))
    a, b = s.make_backup(tmp_path / "bk"), s.make_backup(tmp_path / "bk")
    assert a.name == "backup_2026-10-14_1800.vbak" and b.name == "backup_2026-10-14_1800-1.vbak"


def test_damaged_backup_restores_nothing(store, tmp_path):
    populate(store)
    data = store.make_backup(tmp_path / "bk").read_bytes()
    fresh = JobStore(tmp_path / "new-pc")

    def corrupt_inner(e):
        inner = next(n for n in e if n.endswith("v2.vbak") or n.endswith("v2.vjob"))
        e[inner] = rezip(e[inner], lambda x: x.update({"job.yaml": b"x: 1\n"}))

    with pytest.raises(StoreError):
        fresh.restore_backup(rezip(data, corrupt_inner))
    assert fresh.job_ids() == []
    with pytest.raises(StoreError):
        fresh.restore_backup(b"junk")
    with pytest.raises(FormatError, match="not a 'backup' file"):
        fresh.restore_backup(store.export_vjob(JobRef(JOB_ID, 1)))


def test_backup_refuses_secrets_in_the_system_config(store, tmp_path):
    store.save(make_bundle(1))
    with pytest.raises(StoreError, match="secrets"):
        store.make_backup(tmp_path / "bk", system_yaml="camera:\n  password: x\n")
    assert not list((tmp_path / "bk").glob("*.vbak"))


def test_bundle_from_files_reports_each_missing_piece():
    files = make_bundle(1).files()
    assert bundle_from_files(files).job.job.version == 1
    with pytest.raises(FormatError, match="job.yaml is missing"):
        bundle_from_files({})
    with pytest.raises(FormatError, match="camera profile"):
        bundle_from_files({k: v for k, v in files.items() if k != "camera/profile.yaml"})
    with pytest.raises(FormatError, match="profile.yaml is not valid"):
        bundle_from_files({**files, "camera/profile.yaml": b"resolution: [0, 0]\n"})
