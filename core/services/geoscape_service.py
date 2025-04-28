# core/services/geoscape_service.py
import requests
import logging
from django.conf import settings
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

# API URLs
GEOSCAPE_CADASTRE_URL = "https://api.psma.com.au/v1/landParcels/cadastres/findByIdentifier"
GEOSCAPE_ADDRESS_SEARCH_URL = "https://api.psma.com.au/v1/predictive/address"


def get_api_key() -> Optional[str]:
    """
    Retrieves the Geoscape API key from settings.
    
    Returns:
        The API key as a string or None if not configured
    """
    api_key = getattr(settings, 'GEOSCAPE_API_KEY', None)
    if not api_key:
        logger.error("GEOSCAPE_API_KEY setting is not configured")
    return api_key


def fetch_cadastral_boundary(address_id: str) -> Optional[Dict[str, Any]]:
    """
    Fetches the cadastral boundary geometry JSON for a given Geoscape address ID.
    
    Args:
        address_id: The Geoscape address ID (e.g., GANT_xxxxxxxx).
        
    Returns:
        A dictionary representing the GeoJSON geometry part of the boundary,
        or None if an error occurs or the boundary is not found.
    """
    if not address_id:
        logger.warning("fetch_cadastral_boundary called with no address_id")
        return None
    
    api_key = get_api_key()
    if not api_key:
        return None
    
    headers = {
        "Accept": "application/json",
        "Authorization": api_key
    }
    params = {"addressId": address_id}
    
    try:
        logger.info(f"Fetching cadastral boundary for addressId: {address_id}")
        response = requests.get(
            GEOSCAPE_CADASTRE_URL, 
            headers=headers, 
            params=params, 
            timeout=15
        )
        response.raise_for_status()
        
        data = response.json()
        
        if not data.get('features'):
            logger.warning(f"No features found in Geoscape response for addressId: {address_id}")
            return None
            
        # Assuming the first feature contains the relevant geometry
        geometry_data = data['features'][0].get('geometry')
        if not geometry_data:
            logger.warning(f"No geometry found in the first feature for addressId: {address_id}")
            return None
        
        # Return the raw geometry dictionary
        logger.info(f"Successfully fetched geometry data for addressId: {address_id}")
        return geometry_data
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error fetching Geoscape cadastral data for {address_id}: {e}")
        return None
    except (KeyError, IndexError, ValueError) as e:
        logger.error(f"Error processing Geoscape cadastral response for {address_id}: {e}")
        return None
    except Exception as e:
        logger.exception(f"Unexpected error fetching Geoscape cadastral data for {address_id}: {e}")
        return None


def search_addresses(query: str, state_territory: str) -> List[Dict[str, Any]]:
    """
    Searches for addresses using the Geoscape predictive API.
    
    Args:
        query: The address search query
        state_territory: The state/territory abbreviation (e.g., NT, QLD)
        
    Returns:
        A list of address suggestions or empty list if an error occurs
    """
    if not query or len(query) < 3:
        logger.warning("Address search query too short")
        return []
    
    api_key = get_api_key()
    if not api_key:
        return []
    
    headers = {
        "Accept": "application/json",
        "Authorization": api_key
    }
    params = {
        "query": query,
        "stateTerritory": state_territory
    }
    
    try:
        logger.info(f"Searching addresses: '{query}' in {state_territory}")
        response = requests.get(
            GEOSCAPE_ADDRESS_SEARCH_URL, 
            headers=headers, 
            params=params, 
            timeout=10
        )
        response.raise_for_status()
        
        data = response.json()
        suggestions = data.get('suggest', [])
        logger.info(f"Address search returned {len(suggestions)} results")
        return suggestions
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error in address search: {e}")
        return []
    except Exception as e:
        logger.exception(f"Unexpected error in address search: {e}")
        return []