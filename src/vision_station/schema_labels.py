"""Portuguese labels for the parameter forms (FR-PLT-2: the editor draws a tool's form from its JSON Schema).

    model_config = ConfigDict(extra="forbid", json_schema_extra=labels(
        min_fraction=("Fração mínima da área", "0 a 1"),
        axis=("Medir ao longo de", "", {"none": "área toda", "x": "horizontal", "y": "vertical"}),
    ))

Each entry is a title, or (title, description) or (title, description, labels of the choices). `about` is what
the tool or locator does, shown above its form (the code's docstrings stay in English). The labels only change
the schema the screen reads, never validation.
"""

from collections.abc import Callable
from typing import Any

Label = str | tuple[str, str] | tuple[str, str, dict[str, str]]


def labels(about: str = "", **fields: Label) -> Callable[[dict[str, Any]], None]:
    def extra(schema: dict[str, Any]) -> None:
        if about:
            schema["description"] = about
        properties = schema.get("properties", {})
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
