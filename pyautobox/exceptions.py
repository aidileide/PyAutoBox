"""Domain exceptions shared by the CLI, core modules, and Web API."""


class PyAutoBoxError(Exception):
    """Base class for expected, user-facing errors."""


class InvalidFileError(PyAutoBoxError):
    """Raised when an input path is missing or invalid."""


class UnsupportedFormatError(PyAutoBoxError):
    """Raised when a file extension or encoding is unsupported."""


class FileConflictError(PyAutoBoxError):
    """Raised when an operation would overwrite or collide with a file."""


class ToolExecutionError(PyAutoBoxError):
    """Raised when an underlying library cannot complete a tool operation."""


class ConversionNotSupportedError(PyAutoBoxError):
    """Raised when no converter supports a source and target format pair."""


class FileTooLargeError(PyAutoBoxError):
    """Raised when an upload exceeds the configured limit."""


class ConversionFailedError(PyAutoBoxError):
    """Raised when an otherwise supported conversion fails."""
