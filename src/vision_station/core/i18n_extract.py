"""Which Portuguese texts the server translates, found in the code (TD-30, UI-C3).

    uv run python -m vision_station.core.i18n_extract            # list what the English catalog lacks or has left over
    uv run python -m vision_station.core.i18n_extract --update   # add the new texts to the catalog (empty), drop the old

The texts are the first argument of `tr(...)` and `render(...)`, the message of `Problem(status, "...")`, and the
labels given to `labels(...)` for the parameter forms. The catalog check in the tests uses the same list, so a text
without an English translation fails CI, as in the interface (`npm run i18n:check`).
"""

import ast
import sys
from pathlib import Path

from babel.messages.catalog import Catalog
from babel.messages.pofile import read_po, write_po

from vision_station.core.i18n import CATALOG_FILE

PACKAGE = Path(__file__).resolve().parents[1]


def _strings(node: ast.AST) -> list[str]:
    """The texts an argument can be: a text, or either text of `a if cond else b` (not what the condition compares)."""
    if isinstance(node, ast.Constant):
        return [node.value] if isinstance(node.value, str) else []
    if isinstance(node, ast.IfExp):
        return _strings(node.body) + _strings(node.orelse)
    return []


def from_code() -> tuple[set[str], list[str]]:
    """The texts the code marks, and the places that mark something a catalog cannot hold (a formatted string)."""
    found: set[str] = set()
    problems: list[str] = []
    for path in sorted(PACKAGE.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            name = node.func.id
            if name in ("tr", "render") and node.args:
                target = node.args[0]
            elif name == "Problem" and len(node.args) > 1:
                target = node.args[1]
            else:
                continue
            if any(isinstance(n, ast.JoinedStr) for n in ast.walk(target)):
                problems.append(f"{path.relative_to(PACKAGE)}:{node.lineno}: an f-string cannot be translated, use tr(..., name=value)")
            elif name == "render" and not isinstance(target, ast.Constant):
                continue  # rendering a value that is a text already
            else:
                found.update(text for text in _strings(target) if text.strip())
    return found, problems


def from_schemas() -> set[str]:
    from vision_station.core import schema_labels
    from vision_station import locators, tools  # noqa: F401  (importing registers the labels)

    return set(schema_labels.USED)


def wanted() -> tuple[set[str], list[str]]:
    code, problems = from_code()
    return code | from_schemas(), problems


def update() -> None:
    texts, _ = wanted()
    with CATALOG_FILE.open("rb") as f:
        old = read_po(f)
    catalog = Catalog(
        locale="en", project="Vision Station", version="", charset="utf-8", fuzzy=False, msgid_bugs_address="",
        creation_date=old.creation_date, revision_date=old.creation_date, last_translator="", language_team="",  # no dates: the file changes only with its texts
    )
    catalog.header_comment = "# English texts of the server (TD-30). The msgid is the Portuguese text in the code."
    for text in sorted(texts):
        known = old.get(text)
        catalog.add(text, string=known.string if known else "")
    with CATALOG_FILE.open("wb") as f:
        write_po(f, catalog, width=0, omit_header=False, include_previous=False)
    text = CATALOG_FILE.read_text(encoding="utf-8")
    for noise, clean in (("VERSION", ""), ("EMAIL@ADDRESS", ""), ("FULL NAME <", "<"), ("<>", ""), ("en <LL@li.org>", "")):
        text = text.replace(noise, clean)
    CATALOG_FILE.write_text(text.replace("Vision Station \n", "Vision Station\n"), encoding="utf-8")


def main() -> int:
    texts, problems = wanted()
    with CATALOG_FILE.open("rb") as f:
        catalog = read_po(f)
    have = {m.id: m.string for m in catalog if m.id}
    missing = sorted(t for t in texts if not have.get(t))
    stale = sorted(set(have) - texts)
    if "--update" in sys.argv:
        update()
        print(f"{len(texts)} texts; {len(missing)} still need an English translation")
        return 0
    for line in problems:
        print(line)
    for t in missing:
        print("missing:", t)
    for t in stale:
        print("stale:  ", t)
    return 1 if problems or missing or stale else 0


if __name__ == "__main__":
    raise SystemExit(main())
