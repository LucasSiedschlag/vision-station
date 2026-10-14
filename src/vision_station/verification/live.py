"""Verification with the live camera, and the rule for activating a job (FR-JOB-9).

A job becomes active only after verification passes, or after the Maintainer explicitly overrides it
with a recorded reason. Loading, importing, restoring and reconnecting all end here.
"""

import time
from collections.abc import Callable
from typing import Literal

from vision_station.station import Acquisition, VerifyResult
from vision_station.store import JobBundle, JobRef, JobStore, StoreError
from vision_station.verification.verify import (
    Check,
    Inspector,
    Locator,
    VerificationReport,
    verify_job,
)


class VerificationFailed(StoreError):
    def __init__(self, report: VerificationReport):
        super().__init__(f"job not verified: {report.summary()}")
        self.report = report


class JobVerifier:
    """The station controller's verifier: settings, live view against the reference, reference set.

    Pass an instance as `verifier=` to `StationController`; `last_report` keeps the full report.
    """

    def __init__(
        self,
        inspect: Inspector,
        locate: Locator | None = None,
        parts: Literal["both", "camera", "decision"] = "both",
        require_reference_set: bool = False,
    ):
        self._inspect = inspect
        self._locate = locate
        self._parts = parts
        self._require = require_reference_set
        self.last_report: VerificationReport | None = None

    def __call__(self, bundle: JobBundle, acquisition: Acquisition) -> VerifyResult:
        report = verify_job(
            bundle,
            inspect=self._inspect,
            apply_report=acquisition.last_apply,
            frame=acquisition.latest(),
            parts=self._parts,
            locate=self._locate,
            require_reference_set=self._require,
        )
        self.last_report = report
        return VerifyResult(report.ok, "" if report.ok else report.summary(), tuple(report.warnings))


def verify_stored_job(store: JobStore, ref: JobRef, inspect: Inspector, require_reference_set: bool = False) -> VerificationReport:
    """The decision-logic part only, from the stored reference set, no camera needed. This is how a
    restored job is proved to give the same results as the original (NFR-REL-5)."""
    return verify_job(store.load(ref), inspect=inspect, parts="decision", require_reference_set=require_reference_set)


def verify_live(
    store: JobStore,
    ref: JobRef,
    acquisition: Acquisition,
    inspect: Inspector,
    *,
    locate: Locator | None = None,
    require_reference_set: bool = False,
    timeout_s: float = 15.0,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    drive_acquisition: bool = False,
) -> VerificationReport:
    """Apply the job's camera settings, wait for a frame, then run both parts.

    With `drive_acquisition=True` the loop calls `acquisition.step()` itself (no thread running).
    """
    bundle = store.load(ref)
    acquisition.configure(bundle.profile, None)
    deadline = clock() + timeout_s
    while clock() < deadline:
        if drive_acquisition:
            acquisition.step()
        if acquisition.applied_serial == acquisition.profile_serial and acquisition.latest() is not None:
            break
        sleep(0.05)
    else:
        return VerificationReport(camera_view=(Check("camera", False, f"câmera não respondeu em {timeout_s:g} s"),))
    return verify_job(
        bundle,
        inspect=inspect,
        apply_report=acquisition.last_apply,
        frame=acquisition.latest(),
        locate=locate,
        require_reference_set=require_reference_set,
    )


def activate(store: JobStore, ref: JobRef, report: VerificationReport, override_reason: str | None = None) -> None:
    """Make a job active if it was verified, or if the Maintainer overrides with a reason. Both are logged."""
    if report.ok:
        store.set_active(ref)
        store.audit("activate", job_id=ref.job_id, version=ref.version, verified=True, warnings=list(report.warnings))
        return
    reason = (override_reason or "").strip()
    if not reason:
        raise VerificationFailed(report)
    store.set_active(ref)
    store.audit(
        "activate_override",
        job_id=ref.job_id,
        version=ref.version,
        reason=reason,
        failures=[c.message for c in report.failures()],
    )
