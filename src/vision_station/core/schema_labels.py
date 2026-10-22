"""Portuguese labels for the parameter forms (FR-PLT-2: the editor draws a tool's form from its JSON Schema).

    model_config = ConfigDict(extra="forbid", json_schema_extra=labels(
        min_fraction=("Fração mínima da área", "0 a 1"),
        axis=("Medir ao longo de", "", {"none": "área toda", "x": "horizontal", "y": "vertical"}),
    ))

Each entry is a title, or (title, description) or (title, description, labels of the choices). `about` is what
the tool or locator does, shown above its form (the code's docstrings stay in English). `meta` says how the screen
draws each parameter (frontend.md §9.3, §17): see `meta()`. The labels only change the schema the screen reads,
never validation. They are Portuguese texts translated by the server catalog when the schema is served
(`core/i18n.py`, TD-30); `USED` lists them for the catalog check.
"""

from collections.abc import Callable
from typing import Any

Label = str | tuple[str, str] | tuple[str, str, dict[str, str]]

USED: set[str] = set()  # every text given to `labels`, once the tools and locators are imported


Meta = dict[str, Any]

GROUPS = ("measure", "criteria")  # what a parameter is for: how the part is measured, or the limits it is judged by
LEVELS = (1, 2, 3)  # Essencial, Avançado, Especialista (frontend.md §17)


def meta(level: int, group: str, *, widget: str | None = None, unit: str | None = None, tunable: bool = False) -> Meta:
    """How the screen draws a parameter, written as `x-level`, `x-group`, `x-widget`, `x-unit` and `x-tunable` on it.

    `unit` is what the number is: `fraction` (0 to 1, shown as %), `count`, `score`, or a physical unit (`px`, ...).
    `tunable` is for a limit the supervisor may fine-tune (frontend.md §7.12); never for anything that changes what
    is measured."""
    if level not in LEVELS or group not in GROUPS:
        raise ValueError(f"level {level}, group {group!r}: levels are {LEVELS}, groups {GROUPS}")
    out: Meta = {"x-level": level, "x-group": group}
    if widget:
        out["x-widget"] = widget
    if unit:
        out["x-unit"] = unit
    if tunable:
        out["x-tunable"] = True
    return out


def labels(about: str = "", *, meta: dict[str, Meta] | None = None, **fields: Label) -> Callable[[dict[str, Any]], None]:
    USED.update(text for text in _texts(about, fields) if text)

    def extra(schema: dict[str, Any]) -> None:
        if about:
            schema["description"] = about
        else:
            schema.pop("description", None)  # pydantic takes the class docstring, which is English and not translated
        properties = schema.get("properties", {})
        for name, tags in (meta or {}).items():
            if name in properties:
                properties[name].update(tags)
        for name, label in fields.items():
            prop = properties.get(name)
            if prop is None:
                continue
            title, description, choices = (label, "", None) if isinstance(label, str) else (*label, None)[:3]  # type: ignore[misc]
            prop["title"] = title
            if description:
                prop["description"] = description
            if choices:
                prop["x-enum-labels"] = choices

    return extra


def _texts(about: str, fields: dict[str, Label]) -> list[str]:
    found = [about]
    for label in fields.values():
        for part in (label,) if isinstance(label, str) else label:
            found.extend(part.values() if isinstance(part, dict) else [part])
    return found


COLOR_RANGE: dict[str, Label] = {
    "mode": ("Modo", "Faixa de matiz, saturação e valor, ou distância a uma cor de referência", {"range": "faixa (HSV)", "reference": "cor de referência"}),
    "hue": ("Matiz (de, até)", "0 a 179 (graus ÷ 2). Se 'de' for maior que 'até', a faixa passa pelo vermelho, ex. 170 a 10"),
    "s_min": ("Saturação mínima", "0 a 255. Use uns 60 ou mais com uma faixa de matiz: cinza e branco têm matiz 0"),
    "s_max": ("Saturação máxima", "0 a 255"),
    "v_min": ("Brilho mínimo", "0 a 255"),
    "v_max": ("Brilho máximo", "0 a 255"),
    "rgb": ("Cor de referência (R, G, B)", "0 a 255 cada"),
    "max_distance": ("Distância máxima (ΔE)", "Quanto a cor pode diferir da referência; 10 a 30 é comum"),
}


# how a color range is drawn, for the `color` tool (it extends ColorRange) and the `blob` locator (which holds one)
COLOR_META: dict[str, Meta] = {
    "mode": meta(1, "measure"),
    "hue": meta(1, "measure", widget="hsv-range"),  # the picker also takes over s_min, s_max, v_min, v_max
    "s_min": meta(1, "measure"),
    "s_max": meta(2, "measure"),
    "v_min": meta(1, "measure"),
    "v_max": meta(2, "measure"),
    "rgb": meta(1, "measure", widget="reference-color"),
    "max_distance": meta(1, "measure", unit="ΔE"),
}
