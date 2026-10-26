"""The editor's check of a template crop: its size, flatness and shape model (VIA-0076)."""

import base64

import cv2
import numpy as np

from test_color_range import b64, env, mnt, png  # noqa: F401 (fixtures and helpers)
from vision_station.algorithms.shapematch import MIN_SIDE


def _crop(kind: str) -> np.ndarray:
    image = np.full((60, 90, 3), 40, np.uint8)
    if kind == "edges":
        cv2.rectangle(image, (10, 10), (70, 45), (230, 230, 230), 3)
        cv2.circle(image, (45, 28), 8, (200, 60, 60), -1)
    elif kind == "tiny":
        image = np.full((8, 8, 3), 40, np.uint8)
        image[2:6, 2:6] = 220
    return image


def test_a_crop_with_edges_gives_a_model(env, mnt):  # noqa: F811
    out = env.client.post("/api/editor/inspect/model", headers=mnt, json={"image": b64(png(_crop("edges")))})
    assert out.status_code == 200
    out = out.json()
    assert out["ok"] and (out["width"], out["height"]) == (90, 60)
    assert out["flat"] is False and out["points"] >= 30 and out["reason"] is None


def test_a_flat_crop_has_no_model(env, mnt):  # noqa: F811
    out = env.client.post("/api/editor/inspect/model", headers=mnt, json={"image": b64(png(_crop("flat")))}).json()
    assert out["ok"] and out["flat"] is True and out["points"] is None and out["reason"]


def test_a_tiny_crop_has_no_model_and_says_why(env, mnt):  # noqa: F811
    out = env.client.post("/api/editor/inspect/model", headers=mnt, json={"image": b64(png(_crop("tiny")))}).json()
    assert out["ok"] and out["points"] is None and out["reason"]
    assert out["reason"] != env.client.post("/api/editor/inspect/model", headers=mnt, json={"image": b64(png(_crop("flat")))}).json()["reason"]


def test_bad_input_and_permission(env, mnt):  # noqa: F811
    body = {"image": b64(png(_crop("edges")))}
    assert env.client.post("/api/editor/inspect/model", json=body).status_code == 401
    bad = env.client.post("/api/editor/inspect/model", headers=mnt, json={"image": "not base64!"}).json()
    assert bad["ok"] is False and bad["message"]
    not_image = env.client.post("/api/editor/inspect/model", headers=mnt, json={"image": base64.b64encode(b"abc").decode()}).json()
    assert not_image["ok"] is False


def test_reasons_and_bad_input_follow_the_requested_language(env, mnt):  # noqa: F811
    headers = {**mnt, "Accept-Language": "en"}
    for kind, expected in (
        ("tiny", f"The crop has a side smaller than {MIN_SIDE} pixels"),
        ("flat", "The crop is flat or has too few edges for shape matching"),
    ):
        out = env.client.post("/api/editor/inspect/model", headers=headers, json={"image": b64(png(_crop(kind)))}).json()
        assert out["reason"] == expected
    for image, expected in (
        ("not base64!", "the image is not base64"),
        (base64.b64encode(b"abc").decode(), "the file is not an image"),
    ):
        out = env.client.post("/api/editor/inspect/model", headers=headers, json={"image": image}).json()
        assert out["ok"] is False and out["message"] == expected
