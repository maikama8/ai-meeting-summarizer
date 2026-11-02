"""Errors raised by transcription and summarization providers."""


class ProviderConfigError(Exception):
    """The selected provider is missing a dependency or credential."""


class ProviderError(Exception):
    """The selected provider failed while handling a request."""


class InvalidTranscriptError(Exception):
    """The transcript cannot be summarized."""
