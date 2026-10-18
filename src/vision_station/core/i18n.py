"""Texts the server shows to people, in Portuguese and English (TD-30, UI-C3).

Portuguese is the source language, as in the interface: a text is written in the code in pt-BR and translated by
the PO catalog `locales/en/LC_MESSAGES/messages.po`, whose msgids are those Portuguese texts. Codes, never
texts, are the contract for programs (TD-22); the texts are for screens.

    tr("Localizador não pode rodar: {exc}", exc=exc)   # a Msg: reads as pt-BR, carries msgid and parameters

A `Msg` is a `str` that already holds the Portuguese text, so the core, the records and the comparisons of
a job's reference set (FR-JOB-*) keep working in one language, whatever the station speaks. Only the edge that
talks to a person (the API) calls `render`, with the language of that person: the station's, the request's
`Accept-Language`, or the `lang` of a WebSocket. A plain `str` is looked up as a msgid and left alone if the
catalog does not know it (job texts, technical tails such as a camera's own error).
"""

from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from babel.messages.pofile import read_po

Language = Literal["pt-BR", "en"]
LANGUAGES: tuple[Language, ...] = ("pt-BR", "en")
SOURCE: Language = "pt-BR"
CATALOG_FILE = Path(__file__).parent / "locales" / "en" / "LC_MESSAGES" / "messages.po"


class Msg(str):
    """A text with its msgid and parameters. As a `str` it is the Portuguese text."""

    msgid: str
    params: dict[str, Any]

    def __new__(cls, msgid: str, **params: Any) -> "Msg":
        text = super().__new__(cls, msgid.format(**params) if params else msgid)
        text.msgid = msgid
        text.params = params
        return text

    def __reduce__(self) -> tuple[Any, ...]:  # copy/pickle: rebuilt from the msgid, not from the formatted text
        return (_rebuild, (self.msgid, self.params))


def _rebuild(msgid: str, params: dict[str, Any]) -> Msg:
    return Msg(msgid, **params)


def tr(msgid: str, **params: Any) -> Msg:
    """Mark a Portuguese text for translation; the parameters fill its `{names}`."""
    return Msg(msgid, **params)


def join(items: Iterable[str], separator: str = "; ") -> Msg:
    """Texts one after the other, each rendered in the language asked for (no msgid of its own to translate)."""
    items = list(items)
    return Msg(separator.join(f"{{p{i}}}" for i in range(len(items))), **{f"p{i}": item for i, item in enumerate(items)})


@lru_cache(maxsize=1)
def english() -> dict[str, str]:
    """msgid -> English text; an untranslated entry is absent (the test of the catalog says which)."""
    with CATALOG_FILE.open("rb") as f:
        catalog = read_po(f)
    return {m.id: m.string for m in catalog if m.id and isinstance(m.id, str) and isinstance(m.string, str) and m.string}


@lru_cache(maxsize=1)
def _portuguese() -> dict[str, str]:
    return {text: msgid for msgid, text in english().items()}


def text_of(error: BaseException) -> str:
    """What an exception says, as a Msg when it was raised with one (`str(error)` would flatten it to Portuguese)."""
    return error.args[0] if len(error.args) == 1 and isinstance(error.args[0], Msg) else str(error)


def render(text: str, language: str | None = None) -> str:
    """The text in a language (default: the one of the current request, see `using`)."""
    language = language or current()
    if language == SOURCE:
        if isinstance(text, Msg):
            return str(text)
        return _portuguese().get(str(text), str(text))  # a standard text recorded in English, shown to a Portuguese reader
    if isinstance(text, Msg):
        template = english().get(text.msgid, text.msgid)  # untranslated: still renders its parameters
        params = {k: _param(v, language) for k, v in text.params.items()}
        return template.format(**params) if params else template
    return english().get(str(text), str(text))


def _param(value: Any, language: str) -> Any:
    if isinstance(value, BaseException):  # `exc=exc`: the text it was raised with, translated
        value = text_of(value)
    return render(value, language) if isinstance(value, Msg) else value


def render_schema(schema: Any, language: str | None = None) -> Any:
    """A JSON Schema with the titles, descriptions and choice labels of the parameter forms translated
    (`core/schema_labels.py`); the validation is untouched."""
    language = language or current()
    if language == SOURCE:
        return schema
    if isinstance(schema, list):
        return [render_schema(item, language) for item in schema]
    if not isinstance(schema, dict):
        return schema
    out: dict[str, Any] = {}
    for key, value in schema.items():
        if key in ("title", "description") and isinstance(value, str):
            out[key] = render(value, language)
        elif key == "x-enum-labels" and isinstance(value, dict):
            out[key] = {k: render(v, language) for k, v in value.items()}
        else:
            out[key] = render_schema(value, language)
    return out


_BY_LANGUAGE: dict[str, Language] = {"pt": "pt-BR", "en": "en"}


def negotiate(accept_language: str | None, default: Language = SOURCE) -> Language:
    """The language an `Accept-Language` header asks for, `default` when it names none of ours."""
    if not accept_language:
        return default
    ranked: list[tuple[float, int, str]] = []
    for position, part in enumerate(accept_language.split(",")):
        tag, *params = (piece.strip() for piece in part.split(";"))
        if not tag or tag == "*":
            continue
        quality = 1.0
        for param in params:
            if param.startswith("q="):
                try:
                    quality = float(param[2:])
                except ValueError:
                    quality = 0.0
        if quality > 0:
            ranked.append((-quality, position, tag))
    for _, _, tag in sorted(ranked):  # the best-liked tag we speak, by its language: `pt`, `pt-PT` and `pt_BR` are pt-BR
        spoken = _BY_LANGUAGE.get(tag.replace("_", "-").split("-")[0].lower())
        if spoken:
            return spoken
    return default


def choose(requested: str | None, default: Language = SOURCE) -> Language:
    """A language named directly (`?lang=` of the WebSocket): ours as written or by its first part, else `default`."""
    if not requested:
        return default
    return negotiate(requested, default)


_language: ContextVar[Language] = ContextVar("language", default=SOURCE)


def current() -> Language:
    return _language.get()


@contextmanager
def using(language: Language) -> Iterator[None]:
    """Everything rendered inside speaks `language` (one request, one WebSocket message)."""
    token = _language.set(language)
    try:
        yield
    finally:
        _language.reset(token)
