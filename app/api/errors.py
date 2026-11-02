"""Map provider failures onto HTTP responses."""

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.services.errors import InvalidTranscriptError, ProviderConfigError, ProviderError


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ProviderConfigError)
    async def provider_config_error(_request, exc: ProviderConfigError) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.exception_handler(ProviderError)
    async def provider_error(_request, exc: ProviderError) -> JSONResponse:
        return JSONResponse(status_code=502, content={"detail": str(exc)})

    @app.exception_handler(InvalidTranscriptError)
    async def invalid_transcript(_request, exc: InvalidTranscriptError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})
