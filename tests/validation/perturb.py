"""The disturbances of V4 (architecture §15.3): light, sensor noise, a move and a turn."""

import cv2
import numpy as np

BRIGHTNESS = (0.85, 1.15)
NOISE_SIGMA = 2.0  # gray levels
SHIFT_PX = (4, -3)
TURN_DEGREES = 10.0


def brightness(image: np.ndarray, factor: float) -> np.ndarray:
    return np.clip(image.astype(np.float32) * factor, 0, 255).astype(np.uint8)


def noise(image: np.ndarray, sigma: float = NOISE_SIGMA, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return np.clip(image.astype(np.float32) + rng.normal(0, sigma, image.shape), 0, 255).round().astype(np.uint8)


def shift(image: np.ndarray, dx: int, dy: int) -> np.ndarray:
    matrix = np.float32([[1, 0, dx], [0, 1, dy]])
    return cv2.warpAffine(image, matrix, (image.shape[1], image.shape[0]), borderMode=cv2.BORDER_REPLICATE)


def turn(image: np.ndarray, degrees: float) -> np.ndarray:
    """Turned counter-clockwise on the screen about the centre of the picture."""
    h, w = image.shape[:2]
    matrix = cv2.getRotationMatrix2D((w / 2, h / 2), degrees, 1.0)
    return cv2.warpAffine(image, matrix, (w, h), borderMode=cv2.BORDER_REPLICATE)
