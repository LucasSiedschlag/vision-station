"""The variation model: what a good part looks like, pixel by pixel, and where a part differs (TD-25, architecture §15.4).

A model is taught from pictures of good parts that the fixture has already aligned (the upright cut of the region): the mean and
the standard deviation of each pixel and channel. A part is compared by finding the pixels that differ from the mean by more than
what the good parts allowed. Four things keep that from being a source of false alarms and of false passes:

- **registration**: the part never lands exactly where it was taught (a pixel or a few), so the picture is moved to the model by
  phase correlation (`cv2.phaseCorrelate`, at most 256 pixels a side, at most `max_shift` pixels) before it is compared, and the
  band the move uncovered is left out. Teaching does the same with each good picture, to the first one, so what is taught and what
  is compared are measured the same way;
- **light**: the picture is divided by one gain per channel, fitted by a robust least squares of the picture on the mean through the
  origin (no offset: an offset would absorb a darker material) and clamped to 0.8 to 1.25. A part darker than that stays darker, and
  is a defect;
- **edges**: where the mean changes between neighbours, a pixel of misregistration changes the value, so the tolerance there
  grows by `edge_px` times the largest change to a neighbour;
- **few pictures**: the deviation is the sample one (n - 1); a model needs at least 3 pictures, and below about 15 the floors
  (`abs_threshold` and the edge term) are what holds the tolerance.

The tolerance of a pixel is `max(abs_threshold, k * sigma + edge_px * range)`. The taught data is a file of the job
(`models/<name>.var`): a header (JSON) and the mean and deviation as float16, compressed, with the SHA-256 of the data; it holds data,
never code (FR-PLT-12), and it is written the same bytes for the same pictures.
"""

import hashlib
import json
import math
import struct
import zlib
from collections.abc import Sequence
from dataclasses import dataclass, field
from functools import lru_cache

import cv2
import numpy as np

MAGIC = b"VSVAR1\n"
FORMAT = 1
MIN_IMAGES = 3
GAIN_RANGE = (0.8, 1.25)
REGISTER_SIDE = 256  # registration and the gain work on pictures reduced to this side
REGISTER_RESPONSE = 0.05  # a phase correlation weaker than this is no structure to register on: the picture is not moved
GAIN_ROUNDS = 2  # the gain is fitted, the pixels far from the fit dropped, and it is fitted again this many times
NO_MOVE = 0.02  # a move under this many pixels is no move


@dataclass(frozen=True)
class VariationModel:
    mean: np.ndarray  # H x W x C, float32
    std: np.ndarray  # H x W x C, float32 (sample deviation)
    count: int  # the pictures it was taught from
    range: np.ndarray  # H x W x C: the largest change from a pixel to one of its 4 neighbours in the mean, float32
    mean8: np.ndarray  # the mean rounded to 8 bits, the comparison is made on bytes
    small_mean: np.ndarray  # the mean reduced to at most 256 a side, float32
    gain_mean: np.ndarray  # n x C: the reduced mean on every 4th pixel of every 4th row, the pixels the gain is fitted on
    gain_weight: np.ndarray  # n x C: 1 for those whose deviation in teaching was at most the median, 0 for the rest, float64
    gray: np.ndarray  # the reduced mean in gray, float32: what registration meets
    tolerances: dict = field(default_factory=dict, compare=False, repr=False)  # (abs_threshold, k, edge_px) -> the tolerance of every pixel, 8 bits

    @property
    def size(self) -> tuple[int, int]:
        """Width and height."""
        return self.mean.shape[1], self.mean.shape[0]

    @property
    def channels(self) -> int:
        return self.mean.shape[2]


def _channels(image: np.ndarray) -> np.ndarray:
    image = image if image.ndim == 3 else image[:, :, None]
    return image.astype(np.float32)


def _u8(image: np.ndarray) -> np.ndarray:
    image = image if image.ndim == 3 else image[:, :, None]
    return image if image.dtype == np.uint8 else np.clip(np.rint(image), 0, 255).astype(np.uint8)


def _local_range(mean: np.ndarray) -> np.ndarray:
    """The largest difference from each pixel to one of its 4 neighbours (a cross of 3 x 3), per channel."""
    cross = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
    out = np.empty_like(mean)
    for c in range(mean.shape[2]):
        plane = np.ascontiguousarray(mean[:, :, c])
        out[:, :, c] = np.maximum(cv2.dilate(plane, cross) - plane, plane - cv2.erode(plane, cross))
    return out


def _small_size(width: int, height: int) -> tuple[int, int]:
    factor = min(1.0, REGISTER_SIDE / max(width, height))
    return max(1, round(width * factor)), max(1, round(height * factor))


def _reduce(image: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    """The picture (H x W x C) reduced to `size` = (width, height) by averaging areas, still H x W x C."""
    if (image.shape[1], image.shape[0]) == size:
        return image
    out = cv2.resize(image, size, interpolation=cv2.INTER_AREA)
    return out if out.ndim == 3 else out[:, :, None]


def _gray(image: np.ndarray) -> np.ndarray:
    """Gray, float32, of a picture of 1 or 3 channels."""
    if image.shape[2] == 3:
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY).astype(np.float32, copy=False)
    return image[:, :, 0].astype(np.float32, copy=False)


def _model(mean: np.ndarray, std: np.ndarray, count: int) -> VariationModel:
    size = _small_size(mean.shape[1], mean.shape[0])
    small_mean = _reduce(mean, size)
    small_std = _reduce(std, size)
    stable = small_std <= np.median(small_std.reshape(-1, small_std.shape[2]), axis=0)[None, None, :]
    channels = mean.shape[2]
    gain_mean = np.ascontiguousarray(small_mean[::4, ::4]).reshape(-1, channels).astype(np.float64)
    gain_weight = np.ascontiguousarray(stable[::4, ::4]).reshape(-1, channels).astype(np.float64)
    return VariationModel(mean, std, count, _local_range(mean), _u8(mean), small_mean, gain_mean, gain_weight, _gray(small_mean))


def tolerance(model: VariationModel, abs_threshold: float, k: float, edge_px: float) -> np.ndarray:
    """What a pixel may differ from the mean by, in gray levels rounded up and kept in 8 bits: `max(abs_threshold, k * sigma + edge_px *
    range)`. Kept in the model for the next picture."""
    key = (abs_threshold, k, edge_px)
    if key not in model.tolerances:
        if len(model.tolerances) >= 4:
            model.tolerances.clear()
        wanted = np.maximum(np.float32(abs_threshold), np.float32(k) * model.std + np.float32(edge_px) * model.range)
        model.tolerances[key] = np.minimum(np.ceil(wanted), 255).astype(np.uint8)
    return model.tolerances[key]


def _phase(reference: np.ndarray, gray: np.ndarray) -> tuple[float, float, float]:
    """The move in pixels (dx, dy) that takes `gray` onto `reference` (both float32, the same size, reduced) and how sure the correlation is."""
    window = cv2.createHanningWindow((reference.shape[1], reference.shape[0]), cv2.CV_32F)
    # phaseCorrelate multiplies its inputs by the window in place: it gets copies, never the picture or the model's own reference
    (dx, dy), response = cv2.phaseCorrelate(gray.copy(), reference.copy(), window)
    return dx, dy, response


def register_shift(reference_small: np.ndarray, gray: np.ndarray) -> tuple[float, float]:
    """How many pixels (dx, dy) `gray` (a picture in gray, any size) must be moved to lie on `reference_small` (the reference, already
    reduced to at most 256 a side): (0, 0) without enough structure to tell."""
    height, width = gray.shape[:2]
    small = _reduce(np.ascontiguousarray(gray, dtype=np.float32)[:, :, None], (reference_small.shape[1], reference_small.shape[0]))[:, :, 0]
    return _movement(reference_small, small, reference_small.shape[1] / width, reference_small.shape[0] / height)


def _movement(reference: np.ndarray, small: np.ndarray, fx: float, fy: float) -> tuple[float, float]:
    if min(reference.shape[:2]) < 16 or float(reference.std()) < 1.0 or float(small.std()) < 1.0:
        return 0.0, 0.0
    dx, dy, response = _phase(reference, small)
    if response < REGISTER_RESPONSE or not (math.isfinite(dx) and math.isfinite(dy)):
        return 0.0, 0.0
    return dx / fx, dy / fy


def _moved(image: np.ndarray, dx: float, dy: float) -> np.ndarray:
    """The picture moved by (dx, dy) pixels, the uncovered edge repeating its border."""
    if abs(dx) < NO_MOVE and abs(dy) < NO_MOVE:
        return image
    moved = cv2.warpAffine(image, np.float32([[1, 0, dx], [0, 1, dy]]), (image.shape[1], image.shape[0]), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    return moved if moved.ndim == 3 else moved[:, :, None]


def teach_variation(images: Sequence[np.ndarray], max_shift: float = 6.0) -> VariationModel:
    """The model of a set of good pictures of the same size and channels (at least 3). Each is registered to the first. Raises `ValueError`."""
    if len(images) < MIN_IMAGES:
        raise ValueError(f"teaching needs at least {MIN_IMAGES} pictures of good parts, got {len(images)}")
    first = _channels(images[0])
    if min(first.shape[:2]) < 8:
        raise ValueError("the pictures are smaller than 8 pixels")
    stack = [first]
    size = _small_size(first.shape[1], first.shape[0])
    reference = _reduce(first.mean(axis=2, keepdims=True), size)[:, :, 0]
    for image in images[1:]:
        picture = _channels(image)
        if picture.shape != first.shape:
            raise ValueError(f"the pictures must have the same size and channels: {picture.shape} is not {first.shape}")
        small = _reduce(picture.mean(axis=2, keepdims=True), size)[:, :, 0]
        dx, dy = _movement(reference, small, size[0] / picture.shape[1], size[1] / picture.shape[0])
        stack.append(_moved(picture, float(np.clip(dx, -max_shift, max_shift)), float(np.clip(dy, -max_shift, max_shift))))
    data = np.stack(stack)
    mean = data.mean(axis=0, dtype=np.float64).astype(np.float16).astype(np.float32)  # as it will be read back
    std = data.std(axis=0, ddof=1, dtype=np.float64).astype(np.float16).astype(np.float32)
    return _model(mean, std, len(images))


def to_bytes(model: VariationModel) -> bytes:
    """The file of the model: the same bytes for the same model."""
    payload = model.mean.astype(np.float16).tobytes() + model.std.astype(np.float16).tobytes()
    width, height = model.size
    header = json.dumps(
        {"format": FORMAT, "width": width, "height": height, "channels": model.channels, "count": model.count, "sha256": hashlib.sha256(payload).hexdigest()},
        sort_keys=True,
    ).encode()
    return MAGIC + struct.pack(">I", len(header)) + header + zlib.compress(payload, 6)


def teach(images: Sequence[np.ndarray], max_shift: float = 6.0) -> bytes:
    """The file of the model taught from `images` (see `teach_variation`)."""
    return to_bytes(teach_variation(images, max_shift))


@lru_cache(maxsize=4)
def load(data: bytes) -> VariationModel:
    """The model of a file, cached by its bytes (decoding a model of a megapixel is tens of megabytes). Raises `ValueError` for a file
    that is not a model, of another format, damaged (the SHA-256 of its data does not match) or whose size is not what its header says."""
    if not data.startswith(MAGIC) or len(data) < len(MAGIC) + 4:
        raise ValueError("not a variation model")
    (size,) = struct.unpack(">I", data[len(MAGIC) : len(MAGIC) + 4])
    start = len(MAGIC) + 4
    try:
        header = json.loads(data[start : start + size])
        payload = zlib.decompress(data[start + size :])
        width, height, channels, count = (int(header[k]) for k in ("width", "height", "channels", "count"))
        wanted = str(header["sha256"])
    except (ValueError, KeyError, zlib.error, TypeError) as exc:
        raise ValueError("the variation model is damaged") from exc
    if header.get("format") != FORMAT:
        raise ValueError(f"the variation model is of format {header.get('format')}, this software reads {FORMAT}")
    if hashlib.sha256(payload).hexdigest() != wanted:
        raise ValueError("the variation model is damaged: its checksum does not match")
    n = width * height * channels
    if width < 1 or height < 1 or channels not in (1, 3) or len(payload) != 4 * n:
        raise ValueError("the variation model is damaged: its size is not the one of its header")
    mean = np.frombuffer(payload[: 2 * n], np.float16).reshape(height, width, channels).astype(np.float32)
    std = np.frombuffer(payload[2 * n :], np.float16).reshape(height, width, channels).astype(np.float32)
    return _model(mean, std, count)


def fit_gain(small: np.ndarray, model: VariationModel) -> np.ndarray:
    """One gain per channel such that `small` (the picture reduced like `model.small_mean`) is about `gain * mean`, through the origin: a
    weighted least squares on every 4th pixel of every 4th row, on the pixels whose deviation in teaching was at most the median,
    fitted again `GAIN_ROUNDS` times without the pixels farther than 3 median absolute deviations from the fit. Clamped to `GAIN_RANGE`.
    The edge band a move uncovers is a few pixels of hundreds and the robust fit absorbs it."""
    px = np.ascontiguousarray(small[::4, ::4]).reshape(-1, model.channels).astype(np.float64)
    mu = model.gain_mean
    gains = np.ones(model.channels, np.float64)
    for c in range(model.channels):
        weight = model.gain_weight[:, c].copy()
        x, y = mu[:, c], px[:, c]
        gain = 1.0
        for _ in range(GAIN_ROUNDS + 1):
            denominator = float((weight * x) @ x)
            if weight.sum() < 16 or denominator < 1e-6:
                break
            gain = float((weight * x) @ y / denominator)
            residual = y - gain * x
            kept = weight > 0
            centre = np.median(residual[kept])
            spread = 1.4826 * float(np.median(np.abs(residual[kept] - centre)))
            weight = weight * (np.abs(residual) <= max(3 * spread, 2.0))
        gains[c] = gain
    return np.clip(gains, *GAIN_RANGE)


@dataclass(frozen=True)
class Comparison:
    mask: np.ndarray  # H x W, uint8 (255 where the part differs), in the size of the model
    gain: tuple[float, ...]
    shift: tuple[float, float]  # the pixels the picture was moved to meet the model
    scale: tuple[float, float]  # region pixels per model pixel, x and y (1 unless the region was resized to the model)


def _band(shift: float, size: int) -> tuple[int, int]:
    """The first and the last-plus-one index of a side that the move of `shift` pixels left covered; one more pixel for the interpolation."""
    if shift > NO_MOVE:
        return min(math.ceil(shift) + 1, size), size
    if shift < -NO_MOVE:
        return 0, max(size - math.ceil(-shift) - 1, 0)
    return 0, size


def compare(
    image: np.ndarray, model: VariationModel, *, abs_threshold: float = 15.0, k: float = 3.0, edge_px: float = 1.0, max_shift: float = 6.0,
    normalize: bool = True, resize_limit: float = 0.25,
) -> Comparison:
    """Where `image` (the upright cut of the region, 8 bits) differs from the model. A picture of another size than the model is resized
    to it if it is within `resize_limit` in both sides (the scale of a fixture), else `ValueError`. A picture with another number of channels
    is made gray or colour. The comparison is made on bytes."""
    width, height = model.size
    h, w = image.shape[:2]
    if abs(w / width - 1) > resize_limit or abs(h / height - 1) > resize_limit:
        raise ValueError(f"the region is {w}x{h} pixels and the model was taught on {width}x{height}")
    picture = _u8(image)
    if (w, h) != (width, height):
        picture = _u8(cv2.resize(picture, (width, height), interpolation=cv2.INTER_LINEAR if w < width else cv2.INTER_AREA))
    if picture.shape[2] != model.channels:
        picture = cv2.cvtColor(picture, cv2.COLOR_BGR2GRAY)[:, :, None] if model.channels == 1 else np.repeat(picture, 3, axis=2)
    small_size = (model.small_mean.shape[1], model.small_mean.shape[0])
    small = _reduce(picture, small_size).astype(np.float32)
    fx, fy = small_size[0] / width, small_size[1] / height
    dx, dy = _movement(model.gray, _gray(small), fx, fy)
    dx, dy = float(np.clip(dx, -max_shift, max_shift)), float(np.clip(dy, -max_shift, max_shift))
    left, right = _band(dx, width)
    top, bottom = _band(dy, height)
    valid = (slice(top, bottom), slice(left, right))
    gains = fit_gain(_moved(small, dx * fx, dy * fy), model) if normalize and bottom > top and right > left else np.ones(model.channels)
    picture = _moved(picture, dx, dy)
    if float(np.abs(gains - 1.0).max()) > 0.004:  # |picture / gain - mean| > tolerance, on bytes
        picture = cv2.transform(picture, np.diag(1.0 / gains).astype(np.float32)) if model.channels == 3 else cv2.convertScaleAbs(picture, alpha=1.0 / float(gains[0]))[:, :, None]
    over = cv2.compare(cv2.absdiff(picture, model.mean8), tolerance(model, abs_threshold, k, edge_px), cv2.CMP_GT)
    differs = over if over.ndim == 2 else cv2.max(cv2.max(over[:, :, 0], over[:, :, 1]), over[:, :, 2])
    mask = np.zeros((height, width), np.uint8)
    mask[valid] = differs[valid]
    return Comparison(mask, tuple(float(g) for g in gains), (dx, dy), (w / width, h / height))
