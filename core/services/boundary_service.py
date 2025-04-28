# core/services/boundary_service.py
import logging
import uuid
from django.utils import timezone
from django.urls import reverse
from datetime import timedelta
from typing import Dict, Any, Optional, Tuple

from ..models import Farm, BoundaryMappingToken
from .geoscape_service import fetch_cadastral_boundary

logger = logging.getLogger(__name__)


def create_mapping_token(farm: Farm) -> BoundaryMappingToken:
    """
    Creates a new boundary mapping token for a farm.
    
    Args:
        farm: The Farm instance to create a token for
        
    Returns:
        A BoundaryMappingToken instance
    """
    # Create a token that expires in 24 hours
    token = BoundaryMappingToken(
        farm=farm,
        expires_at=timezone.now() + timedelta(hours=24)
    )
    token.save()
    return token


def get_mapping_url(request, token: BoundaryMappingToken) -> str:
    """
    Generates the full URL for a mapping token.
    
    Args:
        request: The HTTP request object for building absolute URI
        token: The BoundaryMappingToken instance
        
    Returns:
        The full URL string for the mapping page
    """
    mapping_path = reverse('core:map_boundary_via_token', kwargs={'token': str(token.token)})
    return request.build_absolute_uri(mapping_path)


def validate_mapping_token(token_uuid: uuid.UUID) -> Tuple[bool, Optional[Farm], Optional[str]]:
    """
    Validates a mapping token and returns the associated farm.
    
    Args:
        token_uuid: The UUID of the token to validate
        
    Returns:
        Tuple containing (is_valid, farm_instance, error_message)
    """
    try:
        token_instance = BoundaryMappingToken.objects.get(token=token_uuid)
        
        if not token_instance.is_valid():
            return False, None, "This mapping link has expired."
        
        return True, token_instance.farm, None
    
    except BoundaryMappingToken.DoesNotExist:
        return False, None, "Invalid mapping link."
    
    except Exception as e:
        logger.exception(f"Error validating mapping token: {e}")
        return False, None, f"An unexpected error occurred: {e}"


def invalidate_token(token_instance: BoundaryMappingToken) -> None:
    """
    Invalidates a mapping token by setting its expiry to now.
    
    Args:
        token_instance: The token to invalidate
    """
    token_instance.expires_at = timezone.now()
    token_instance.save()


def save_boundary_to_farm(farm: Farm, boundary_coords_str: str) -> Tuple[bool, Optional[str]]:
    """
    Validates and saves boundary coordinates to a farm.
    
    Args:
        farm: The Farm instance to update
        boundary_coords_str: The boundary coordinates as a GeoJSON string
        
    Returns:
        Tuple containing (success_flag, error_message)
    """
    import json
    
    if not boundary_coords_str:
        return False, "No boundary coordinates received."
    
    try:
        # Parse the JSON string
        geojson_boundary = json.loads(boundary_coords_str)
        
        # Basic validation of GeoJSON structure
        valid_structure = True
        if not isinstance(geojson_boundary, dict):
            valid_structure = False
        if valid_structure and geojson_boundary.get('type') != 'Polygon':
            valid_structure = False
        coords = geojson_boundary.get('coordinates')
        if valid_structure and not isinstance(coords, list):
            valid_structure = False
        if valid_structure and len(coords) == 0:
            valid_structure = False
        if valid_structure and len(coords[0]) < 4:  # Min 4 points for closed Polygon
            valid_structure = False
            
        if not valid_structure:
            return False, "Invalid GeoJSON Polygon structure received."
        
        # Save to farm
        farm.boundary = geojson_boundary
        farm.save(update_fields=['boundary'])
        
        return True, None
    
    except json.JSONDecodeError:
        return False, "Invalid boundary data format received."
    except (ValueError, TypeError, IndexError) as e:
        return False, f"Error processing boundary data: {e}"
    except Exception as e:
        logger.exception(f"Unexpected error saving boundary: {e}")
        return False, f"An unexpected error occurred: {e}"


def fetch_and_save_cadastral_boundary(farm: Farm) -> Tuple[bool, Optional[str]]:
    """
    Fetches a cadastral boundary from Geoscape and saves it to the farm.
    
    Args:
        farm: The Farm instance to update
        
    Returns:
        Tuple containing (success_flag, message)
    """
    if not farm.geoscape_address_id:
        return False, "No Geoscape address ID available for this farm."
    
    boundary_json = fetch_cadastral_boundary(farm.geoscape_address_id)
    if not boundary_json:
        return False, "Failed to fetch cadastral boundary from Geoscape."
    
    # Save the boundary to the farm
    farm.boundary = boundary_json
    farm.save(update_fields=['boundary'])
    
    return True, "Successfully fetched and saved cadastral boundary."