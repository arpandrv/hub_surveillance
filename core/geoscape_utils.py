# core/geoscape_utils.py
from .services.geoscape_service import (
    fetch_cadastral_boundary,
    search_addresses,
    get_api_key
)

# Re-export from service module for backward compatibility
__all__ = [
    'fetch_cadastral_boundary',
    'search_addresses',
    'get_api_key'
]