"""Runs the API with uvicorn, on this machine only unless the configuration says otherwise (NFR-SEC-3)."""

import uvicorn

from vision_station.api.app import ApiDeps, create_app


def serve(deps: ApiDeps, host: str = "127.0.0.1", port: int = 8765) -> None:
    uvicorn.run(create_app(deps), host=host, port=port, log_level="info")
