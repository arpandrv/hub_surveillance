import requests
from django.conf import settings
import logging
from typing import Dict, Any # Added for type hinting

logger = logging.getLogger(__name__)

GEOSCAPE_CADASTRE_URL = "https://api.psma.com.au/v1/landParcels/cadastres/findByIdentifier"

def fetch_cadastral_boundary(address_id: str) -> Dict[str, Any] | None:
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

    api_key = settings.GEOSCAPE_API_KEY
    if not api_key:
        logger.error("GEOSCAPE_API_KEY setting is not configured.")
        return None

    headers = {
        "Accept": "application/json",
        "Authorization": api_key 
    }
    params = {"addressId": address_id}

    try:
        logger.info(f"Fetching cadastral boundary for addressId: {address_id}")
        response = requests.get(GEOSCAPE_CADASTRE_URL, headers=headers, params=params, timeout=15) # Added timeout
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

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
    except (KeyError, IndexError, ValueError) as e: # Removed GEOSException
         logger.error(f"Error processing Geoscape cadastral response for {address_id}: {e}")
         return None
    except Exception as e: # Catch any other unexpected errors
        logger.exception(f"Unexpected error fetching Geoscape cadastral data for {address_id}: {e}") # Use logger.exception to include traceback
        return None 