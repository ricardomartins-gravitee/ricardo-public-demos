"""Shared Services API — read-only catalog HTTP server."""

import json
import os
from pathlib import Path

import uvicorn
from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from catalog import (
    get_notice,
    get_service,
    get_service_v2,
    list_notices_envelope,
    list_services_envelope,
    list_services_v2_envelope,
)

_APP_DIR = Path(__file__).resolve().parent
with (_APP_DIR / "openapi.json").open(encoding="utf-8") as openapi_file:
    OPENAPI_DOCUMENT = json.load(openapi_file)

# Longer prefixes first, so /shared-services-v2 is not read as /shared-services.
_CONTEXT_PREFIXES = ("/shared-services-v2", "/platform-notices", "/shared-services")


class NormalizeSharedServicesPrefix(BaseHTTPMiddleware):
    """Map a gateway context path onto the same handlers as the path without it."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        for prefix in _CONTEXT_PREFIXES:
            if path == prefix or path.startswith(f"{prefix}/"):
                stripped = path[len(prefix) :] or "/"
                request.scope["path"] = stripped
                request.scope["raw_path"] = stripped.encode("utf-8")
                break
        return await call_next(request)


async def health(_request: Request):
    return JSONResponse({"status": "ok"})


async def serve_openapi(_request: Request):
    return JSONResponse(OPENAPI_DOCUMENT)


async def list_services(_request: Request):
    return JSONResponse(list_services_envelope())


async def list_services_v2(_request: Request):
    return JSONResponse(list_services_v2_envelope())


async def get_service_v2_by_id(request: Request):
    service_id = request.path_params["id"]
    service = get_service_v2(service_id)
    if service is None:
        return JSONResponse(
            {
                "error": "not_found",
                "message": f"No service has the id {service_id}.",
            },
            status_code=404,
        )
    return JSONResponse(service)


async def list_notices(_request: Request):
    return JSONResponse(list_notices_envelope())


async def get_notice_by_id(request: Request):
    notice_id = request.path_params["id"]
    notice = get_notice(notice_id)
    if notice is None:
        return JSONResponse(
            {
                "error": "not_found",
                "message": f"No notice has the id {notice_id}.",
            },
            status_code=404,
        )
    return JSONResponse(notice)


async def get_service_by_id(request: Request):
    service_id = request.path_params["id"]
    service = get_service(service_id)
    if service is None:
        return JSONResponse(
            {
                "error": "not_found",
                "message": f"No service has the id {service_id}.",
            },
            status_code=404,
        )
    return JSONResponse(service)


routes = [
    Route("/health", health, methods=["GET"]),
    Route("/openapi.json", serve_openapi, methods=["GET"]),
    Route("/v1/health", health, methods=["GET"]),
    Route("/v1/services", list_services, methods=["GET"]),
    Route("/v1/services/{id}", get_service_by_id, methods=["GET"]),
    Route("/v2/health", health, methods=["GET"]),
    Route("/v2/services", list_services_v2, methods=["GET"]),
    Route("/v2/services/{id}", get_service_v2_by_id, methods=["GET"]),
    Route("/v1/notices", list_notices, methods=["GET"]),
    Route("/v1/notices/{id}", get_notice_by_id, methods=["GET"]),
]

app = Starlette(routes=routes)
app.add_middleware(NormalizeSharedServicesPrefix)


def main():
    port = int(os.environ.get("HTTP_PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port, access_log=True, log_level="info")


if __name__ == "__main__":
    main()
