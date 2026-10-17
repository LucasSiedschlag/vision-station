"""Image quality gates of the pipeline (architecture §7.1): brightness before the locator, sharpness after it."""

import numpy as np

from vision_station.algorithms import metrics
from vision_station.core.errors import ErrorCode
from vision_station.pipeline.stop import Stop
from vision_station.store.bundle import JobBundle
from vision_station.verification.reference import REFERENCE_META, parse_meta


def brightness_gate(bundle: JobBundle, image: np.ndarray) -> None:
    quality = bundle.job.quality
    level = metrics.brightness(image)
    if level < quality.brightness.min:
        raise Stop(ErrorCode.TOO_DARK)
    if level > quality.brightness.max:
        raise Stop(ErrorCode.TOO_BRIGHT)


def sharp_enough(bundle: JobBundle, image: np.ndarray) -> bool:
    raw = bundle.extra.get(REFERENCE_META)
    if raw is None:
        return True  # a job without a reference has nothing to compare sharpness with; verification asks for it
    reference = parse_meta(raw).sharpness
    return not (reference > 0 and metrics.sharpness(image) < bundle.job.quality.sharpness_min_ratio * reference)
