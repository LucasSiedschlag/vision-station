"""Make a printable sheet of test codes in several sizes, to find the smallest code a camera reads.

    uv run python scripts/make_test_codes.py            # writes test_codes.html and test_codes.png
    open test_codes.html                                 # print at 100% / actual size, A4

Every code carries its size (module or bar width in mm) written under it. Stick the sheet at the
station's working distance and run scripts/read_codes.py to see which sizes the camera reads.
"""

import base64
import sys

import cv2
import numpy as np
import zxingcpp

DPI = 600
MM_PER_PX = 25.4 / DPI
PAGE_W, PAGE_H = round(210 / MM_PER_PX), round(297 / MM_PER_PX)
MARGIN = round(12 / MM_PER_PX)
GAP = round(8 / MM_PER_PX)

# (format, text, pixels per module / bar at 600 dpi)
ROWS = [
    ("QR", zxingcpp.BarcodeFormat.QRCode, "LOTE-2026-10", [8, 12, 16, 24, 36]),
    ("Data Matrix", zxingcpp.BarcodeFormat.DataMatrix, "DM-4711", [8, 12, 16, 24, 36]),
    ("Code 128", zxingcpp.BarcodeFormat.Code128, "A-1", [8, 12, 18]),
    ("Code 128", zxingcpp.BarcodeFormat.Code128, "A-1", [24, 36]),
]


def code_image(fmt, text, px: int) -> np.ndarray:
    gray = np.array(zxingcpp.create_barcode(text, fmt).to_image(scale=px))
    if fmt == zxingcpp.BarcodeFormat.Code128:
        gray = gray[: max(gray.shape[0], 1)]
        gray = cv2.resize(gray, (gray.shape[1], 8 * px * 4), interpolation=cv2.INTER_NEAREST)  # tall enough to scan
    return gray


def build() -> np.ndarray:
    page = np.full((PAGE_H, PAGE_W), 255, np.uint8)
    y = MARGIN
    cv2.putText(page, "Vision Station - test codes (print at 100%)", (MARGIN, y + 40), cv2.FONT_HERSHEY_SIMPLEX, 1.6, 0, 3)
    y += 120
    for name, fmt, text, sizes in ROWS:
        x = MARGIN
        row_h = 0
        for px in sizes:
            img = code_image(fmt, text, px)
            if x + img.shape[1] > PAGE_W - MARGIN:
                break
            page[y : y + img.shape[0], x : x + img.shape[1]] = img
            label = f"{name} {px * MM_PER_PX:.2f} mm"
            cv2.putText(page, label, (x, y + img.shape[0] + 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, 0, 2)
            x += img.shape[1] + GAP
            row_h = max(row_h, img.shape[0])
        y += row_h + 120
    return page


def main() -> int:
    page = build()
    cv2.imwrite("test_codes.png", page)
    ok, png = cv2.imencode(".png", page)
    html = (
        "<!doctype html><meta charset=utf-8><title>Test codes</title>"
        "<style>@page{size:A4;margin:0}body{margin:0}img{width:210mm;height:297mm;display:block}</style>"
        f'<img src="data:image/png;base64,{base64.b64encode(png).decode()}">'
    )
    with open("test_codes.html", "w", encoding="utf-8") as f:
        f.write(html)
    read = zxingcpp.read_barcodes(page)
    print(f"test_codes.png ({PAGE_W}x{PAGE_H} px, {DPI} dpi) and test_codes.html written; the sheet itself decodes {len(read)} codes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
