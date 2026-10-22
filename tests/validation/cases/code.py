import numpy as np
import zxingcpp

from validation.case import Case, Golden


def qr(text):
    image = np.array(zxingcpp.create_barcode(text, zxingcpp.BarcodeFormat.QRCode).to_image(scale=4))
    return np.pad(image, 20, constant_values=255)


_SIDE = np.hstack([qr("LOTE-1"), qr("LOTE-2")])

TOOLS = {1: Case(
    params={"expect": "LOTE-1"},
    bad_params=({"min_count": 3, "max_count": 1}, {"formats": ["NoSuchFormat"]}, {"pattern": "("}, {"min_count": 0}),
    passing=qr("LOTE-1"),
    failing=qr("LOTE-2"),
    goldens=(
        Golden("one code, the expected one", qr("LOTE-1"), passed=True, values={"found": 1, "matching": 1}, tolerance=0),
        Golden("two codes, one of them expected", _SIDE, {"max_count": 1}, passed=True, values={"found": 2, "matching": 1}, tolerance=0),
        Golden("no code", np.full((100, 100), 255, np.uint8), passed=False, values={"found": 0, "matching": 0}, tolerance=0),
    ),
)}
