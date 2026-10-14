"""Print the API's OpenAPI document as JSON, for the web interface's generated types (docs/frontend.md §9).

    uv run python scripts/export_openapi.py > frontend/src/api/openapi.json

Nothing is started: the document depends only on the routes and models, so the dependencies are left empty.
"""

import json
import sys

from vision_station.api import ApiDeps, create_app


def main() -> int:
    deps = ApiDeps(controller=None, acquisition=None, jobs=None, results=None, auth=None, inspect=None)  # type: ignore[arg-type]
    json.dump(create_app(deps).openapi(), sys.stdout, indent=2, sort_keys=True, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
