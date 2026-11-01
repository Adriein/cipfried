class AnalysisError(Exception):
    """Base error for the packet analysis layer."""


class ParseError(AnalysisError):
    """Raised when a message cannot be decoded from a payload."""


class TruncatedMessage(ParseError):
    """Raised when a payload ends before a message is complete."""


__all__ = ["AnalysisError", "ParseError", "TruncatedMessage"]
