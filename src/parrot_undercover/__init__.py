from importlib.metadata import PackageNotFoundError, version

__all__ = ["__version__"]

try:
    __version__ = version("parrot-undercover")
except PackageNotFoundError:
    __version__ = "0.1.0-dev"
