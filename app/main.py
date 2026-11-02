"""FastAPI application factory."""

from fastapi import FastAPI

from app import __version__
from app.api.errors import register_exception_handlers
from app.api.routes import router
from app.config import Settings, get_settings
from app.services.factory import build_summarization_provider, build_transcription_provider


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the API and the providers selected by `settings`."""
    resolved = settings or get_settings()
    app = FastAPI(
        title="AI Meeting Summarizer",
        version=__version__,
        summary="Turn meeting audio and voice notes into a transcript, summary, and action items.",
        description=(
            "Upload audio (or a text transcript) and receive a transcript, a short summary, "
            "and action items with owners and due dates when the text supports them. "
            "The default providers run offline. OpenAI and faster-whisper are selected with "
            "environment variables."
        ),
        contact={"name": "Abdulrasheed Oseni", "url": "https://github.com/maikama8"},
        license_info={"name": "MIT"},
    )
    app.state.settings = resolved
    app.state.transcription = build_transcription_provider(resolved)
    app.state.summarization = build_summarization_provider(resolved)
    register_exception_handlers(app)
    app.include_router(router)
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
