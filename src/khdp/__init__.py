"""KHDP Connector — auth + MCP server for the Korea Health Data Platform."""

# __version__ is defined first so submodules can ``from khdp import
# __version__`` without a circular import.
__version__ = "0.4.0"

from khdp.config import Config, load_config
from khdp.oauth import AuthError, KhdpAuthClient, OAuthError, TokenSet
from khdp.session import Session
from khdp.token_store import TokenStore

__all__ = [
    "AuthError",
    "Config",
    "KhdpAuthClient",
    "OAuthError",
    "Session",
    "TokenSet",
    "TokenStore",
    "__version__",
    "load_config",
]
