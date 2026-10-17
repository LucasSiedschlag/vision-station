"""Image quality gates of the pipeline (architecture §7.1): brightness before the locator, sharpness after it."""

import numpy as np

from vision_station.algorithms import metrics
from vision_station.pipeline.stop import Stop
from vision_station.store.bundle import JobBundle
from vision_station.verification.reference import REFERENCE_META, parse_meta

OUT_OF_FOCUS = "Imagem fora de foco, verificar a lente e a câmera"


def brightness_gate(bundle: JobBundle, image: np.ndarray) -> None:
    quality = bundle.job.quality
    level = metrics.brightness(image)
    if level < quality.brightness.min:
        raise Stop("Imagem escura demais, verificar a iluminação")
    if level > quality.brightness.max:
        raise Stop("Imagem clara demais, verificar a iluminação")


def sharp_enough(bundle: JobBundle, image: np.ndarray) -> bool:
    raw = bundle.extra.get(REFERENCE_META)
    if raw is None:
        return True  # a job without a reference has nothing to compare sharpness with; verification asks for it
    reference = parse_meta(raw).sharpness
    return not (reference > 0 and metrics.sharpness(image) < bundle.job.quality.sharpness_min_ratio * reference)
