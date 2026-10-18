"""Code tool: reads 1D bar codes and 2D codes (QR, Data Matrix...) in a region.

Decoder: zxing-cpp (Apache 2.0). A region passes when enough of the codes it reads
are the ones the job wants.

Fields for `reason_fail`: {found} codes read, {matching} of them accepted, {min_count},
{expected}, {texts} (the texts read, joined by ", ").
"""

import re
from typing import Annotated, Any

import numpy as np
import zxingcpp
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from vision_station.core.jobfiles import JobFiles
from vision_station.core.i18n import tr
from vision_station.core.schema_labels import labels, meta
from vision_station.tools.base import CriterionSpec, ToolResult, ToolType, count_at_most, judged, minimum, register


class CodeParams(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra=labels(
        "Lê códigos de barras (1D) e códigos 2D (QR, Data Matrix...) numa região.",
        meta={
            "formats": meta(1, "measure", widget="code-formats"),
            "expect": meta(1, "measure"),
            "pattern": meta(1, "measure", widget="regex"),
            "min_count": meta(1, "criteria", unit="count", tunable=True),
            "max_count": meta(1, "criteria", unit="count", tunable=True),
            "try_rotate": meta(3, "measure"),
            "try_downscale": meta(3, "measure"),
            "try_invert": meta(2, "measure"),
        },
        formats=("Formatos", "Ex.: QRCode, DataMatrix, Code128, EAN13. Vazio: todos os que forem lidos"),
        expect=("Texto esperado", "Um código só conta se tiver exatamente este texto"),
        pattern=("Padrão do texto", "Expressão regular; ex.: L\\d{6}"),
        min_count=("Mínimo de códigos", "Códigos aceitos para aprovar"),
        max_count=("Máximo de códigos", "Mais que isso reprova (ex.: etiqueta colada duas vezes)"),
        try_rotate=("Tentar girado", ""),
        try_downscale=("Tentar reduzido", ""),
        try_invert=("Tentar invertido", "Código claro sobre fundo escuro"),
    ))

    formats: list[str] | None = None  # e.g. ["QRCode", "Code128"]; None = every readable format
    expect: str | None = None  # a code is accepted if its text is exactly this
    pattern: str | None = None  # ...or fully matches this regular expression
    min_count: Annotated[int, Field(ge=1)] = 1  # accepted codes needed to pass
    max_count: Annotated[int, Field(ge=1)] | None = None  # more accepted codes than this fails
    try_rotate: bool = True
    try_downscale: bool = True
    try_invert: bool = True

    @field_validator("formats")
    @classmethod
    def _known_formats(cls, names: list[str] | None) -> list[str] | None:
        for name in names or []:
            try:
                zxingcpp.barcode_format_from_str(name)
            except ValueError as exc:
                raise ValueError(f"unknown code format '{name}'") from exc
        return names

    @field_validator("pattern")
    @classmethod
    def _valid_pattern(cls, pattern: str | None) -> str | None:
        if pattern is not None:
            try:
                re.compile(pattern)
            except re.error as exc:
                raise ValueError(f"invalid pattern: {exc}") from exc
        return pattern

    @model_validator(mode="after")
    def _counts_are_ordered(self) -> "CodeParams":
        if self.max_count is not None and self.max_count < self.min_count:
            raise ValueError("max_count must not be lower than min_count")
        return self


def _accepts(params: CodeParams, text: str) -> bool:
    if params.expect is None and params.pattern is None:
        return True
    if params.expect is not None and text == params.expect:
        return True
    return params.pattern is not None and re.fullmatch(params.pattern, text) is not None


def run(region: np.ndarray, params: CodeParams, files: JobFiles) -> ToolResult:
    read: list[Any] = []
    if region.size:
        kwargs: dict[str, Any] = dict(
            try_rotate=params.try_rotate,
            try_downscale=params.try_downscale,
            try_invert=params.try_invert,
        )
        if params.formats:
            kwargs["formats"] = [zxingcpp.barcode_format_from_str(n) for n in params.formats]
        read = zxingcpp.read_barcodes(np.ascontiguousarray(region), **kwargs)

    codes = [
        {
            "text": r.text,
            "format": r.format.name,
            "accepted": _accepts(params, r.text),
            "position": [(p.x, p.y) for p in (r.position.top_left, r.position.top_right, r.position.bottom_right, r.position.bottom_left)],
        }
        for r in read
        if r.valid
    ]
    matching = sum(c["accepted"] for c in codes)
    criteria = [minimum("min_count", "matching", matching, params.min_count)]
    if params.max_count is not None:
        criteria.append(count_at_most("max_count", "matching", matching, params.max_count))
    values = {
        "found": len(codes),
        "matching": matching,
        "min_count": params.min_count,
        "expected": params.expect if params.expect is not None else params.pattern,
        "texts": ", ".join(c["text"] for c in codes),
    }
    return judged(criteria, values=values, details={"codes": codes}, units={"found": "count", "matching": "count"})


CODE = register(ToolType(
    name="code", version=1, params=CodeParams, run=run,
    criteria=(CriterionSpec("matching", tr("Códigos aceitos"), "count", "min_count", "max_count"),),
))
