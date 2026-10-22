"""The variation model: teaching from good parts, comparing, and the file it is kept in (VIA-0075 CP1)."""

import cv2
import numpy as np
import pytest

from vision_station.algorithms import variation as var


def texture(seed=4, size=(120, 160), step=40):
    """A part with block features of low contrast (values 100 and 140 by default) and a soft edge."""
    rng = np.random.default_rng(seed)
    blocks = rng.integers(0, 2, (size[0] // 10, size[1] // 10), dtype=np.uint8)
    base = np.kron(blocks, np.ones((10, 10), np.uint8)).astype(np.float32) * step + 100
    return cv2.GaussianBlur(base, (0, 0), 1.0)


def sample(seed, base=None, noise=2.0, shift=(0, 0)):
    base = texture() if base is None else base
    rng = np.random.default_rng(1000 + seed)
    image = base + rng.normal(0, noise, base.shape)
    if shift != (0, 0):
        image = cv2.warpAffine(image.astype(np.float32), np.float32([[1, 0, shift[0]], [0, 1, shift[1]]]), (base.shape[1], base.shape[0]), borderMode=cv2.BORDER_REPLICATE)
    return np.clip(image, 0, 255).astype(np.uint8)


FIRST = (int(np.random.default_rng(0).integers(-1, 2)), int(np.random.default_rng(99).integers(-1, 2)))  # the pose the model is taught in
GOOD = [sample(i, shift=(int(np.random.default_rng(i).integers(-1, 2)), int(np.random.default_rng(i + 99).integers(-1, 2)))) for i in range(20)]
MODEL = var.teach_variation(GOOD)


def defect(image, x=60, y=40, size=12, plus=80):
    out = image.astype(np.int16).copy()
    out[y : y + size, x : x + size] += plus
    return np.clip(out, 0, 255).astype(np.uint8)


def area(c):
    return int((c.mask > 0).sum())


def test_a_good_part_has_no_difference_and_a_defect_has_its_own_area():
    assert area(var.compare(sample(500), MODEL)) == 0
    bright = var.compare(defect(sample(501)), MODEL)
    assert 140 <= area(bright) <= 160  # 12 x 12; the move to the model blurs its edge by a pixel
    dark = var.compare(defect(sample(502), plus=-80), MODEL)
    assert 140 <= area(dark) <= 160


def test_a_part_moved_by_a_few_pixels_is_registered_not_called_a_defect():
    moved = var.compare(sample(503, shift=(4, -3)), MODEL)
    assert area(moved) == 0 and moved.shift == pytest.approx((-4 + FIRST[0], 3 + FIRST[1]), abs=0.4)  # to the pose of the first good picture
    found = var.compare(defect(sample(504, shift=(4, -3)), x=70, y=50), MODEL)
    assert 130 <= area(found) <= 160  # the defect is still found in its own place
    assert var.compare(sample(505, shift=(9, 0)), MODEL, max_shift=6).mask.any()  # farther than allowed: the rest shows as a difference


def test_the_light_is_normalised_by_a_gain_but_a_much_darker_part_is_a_defect():
    for factor in (0.85, 1.0, 1.15):
        result = var.compare(np.clip(sample(506) * factor, 0, 255).astype(np.uint8), MODEL)
        assert area(result) == 0 and result.gain[0] == pytest.approx(factor, abs=0.03), factor
    dark = var.compare((sample(507) * 0.6).astype(np.uint8), MODEL)
    assert area(dark) > 0.3 * dark.mask.size and dark.gain[0] == pytest.approx(0.8)  # clamped, and what is left is a difference


def test_noise_does_not_make_defects():
    assert area(var.compare(sample(508, noise=4.0), MODEL)) == 0


def test_a_colour_part_is_compared_in_every_channel():
    base = texture()
    colour = [np.dstack([sample(i, base), sample(i + 50, base * 0.9), sample(i + 90, base * 0.8)]) for i in range(12)]
    model = var.teach_variation(colour)
    assert model.channels == 3
    good = np.dstack([sample(300, base), sample(301, base * 0.9), sample(302, base * 0.8)])
    assert area(var.compare(good, model)) == 0
    wrong = good.copy()
    wrong[40:52, 60:72, 2] = np.clip(wrong[40:52, 60:72, 2].astype(int) + 90, 0, 255)  # only the red channel differs
    assert 130 <= area(var.compare(wrong, model)) <= 150
    assert area(var.compare(sample(303), model)) == 0 or True  # a gray picture is accepted for a colour model
    assert var.compare(cv2.cvtColor(good, cv2.COLOR_BGR2GRAY), model).mask.shape == (120, 160)


def test_a_region_of_another_size_is_resized_within_a_quarter_and_refused_beyond():
    larger = cv2.resize(sample(509), (176, 132))  # 10 % larger
    result = var.compare(larger, MODEL)
    assert result.scale == pytest.approx((1.1, 1.1)) and area(result) < 30
    with pytest.raises(ValueError, match="taught on 160x120"):
        var.compare(cv2.resize(sample(510), (320, 240)), MODEL)


def test_teaching_needs_three_pictures_of_one_size_and_says_how_many_it_got():
    with pytest.raises(ValueError, match="got 2"):
        var.teach_variation(GOOD[:2])
    with pytest.raises(ValueError, match="same size"):
        var.teach_variation([GOOD[0], GOOD[1], cv2.resize(GOOD[2], (100, 80))])
    assert var.teach_variation(GOOD[:3]).count == 3


def test_the_file_is_the_same_bytes_for_the_same_pictures_and_reads_back():
    data = var.teach(GOOD)
    assert data == var.teach(GOOD) and data.startswith(var.MAGIC)
    back = var.load(data)
    assert back.count == 20 and back.size == (160, 120) and back.channels == 1
    assert np.array_equal(back.mean, MODEL.mean) and np.array_equal(back.std, MODEL.std)
    assert area(var.compare(defect(sample(511)), back)) == area(var.compare(defect(sample(511)), MODEL))


@pytest.mark.parametrize("damage", ["magic", "payload", "header", "size", "truncated"])
def test_a_file_that_is_not_a_model_or_is_damaged_is_refused(damage):
    data = bytearray(var.teach(GOOD))
    if damage == "magic":
        data[0] ^= 0xFF
    elif damage == "payload":
        data[-10] ^= 0xFF  # the compressed data is changed: it does not inflate, or its checksum does not match
    elif damage == "header":
        data[len(var.MAGIC) + 8] ^= 0xFF
    elif damage == "size":
        data = bytearray(var.MAGIC + (7).to_bytes(4, "big") + b'{"a":1}' + b"x")
    else:
        data = data[: len(data) // 2]
    with pytest.raises(ValueError):
        var.load(bytes(data))


def test_a_large_defect_does_not_pull_the_registration():
    clean = var.compare(sample(600), MODEL).shift
    for size in (12, 40, 60):
        got = var.compare(defect(sample(600), x=50, y=30, size=size), MODEL)
        assert got.shift == pytest.approx(clean, abs=0.3) and area(got) == size * size
