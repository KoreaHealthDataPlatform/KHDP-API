"""KHDP Connector — auth + MCP server for the Korea Health Data Platform.

Also ships the **SNUH SuperTable** client (see ``khdp.supertable``) for
read-only SQL access to FHIR + OMOP CDM clinical-research data.
"""

# __version__ is defined first so submodules can ``from khdp import
# __version__`` without a circular import.
__version__ = "0.2.0"

from khdp.config import Config, load_config
from khdp.oauth import AuthError, KhdpAuthClient, OAuthError, TokenSet
from khdp.token_store import TokenStore

__all__ = [
    "AuthError",
    "Config",
    "KhdpAuthClient",
    "OAuthError",
    "TokenSet",
    "TokenStore",
    "__version__",
    "load_config",
]
