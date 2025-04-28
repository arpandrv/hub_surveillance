# core/services/farm_service.py
import logging
from typing import Dict, Any, Optional, List, Tuple

from django.contrib.auth.models import User
from ..models import Farm, Grower, PlantType, SurveillanceRecord
from .geoscape_service import fetch_cadastral_boundary
from .boundary_service import fetch_and_save_cadastral_boundary

logger = logging.getLogger(__name__)


def get_user_farms(user: User) -> List[Farm]:
    """
    Retrieves all farms for a user.
    
    Args:
        user: The User instance
        
    Returns:
        List of Farm instances owned by the user
    """
    try:
        grower = user.grower_profile
        return Farm.objects.filter(owner=grower)
    except Grower.DoesNotExist:
        logger.warning(f"No grower profile found for user {user.username}")
        return []
    except Exception as e:
        logger.exception(f"Error retrieving farms for user {user.username}: {e}")
        return []


def get_farm_details(farm_id: int, user: User) -> Tuple[Optional[Farm], Optional[str]]:
    """
    Retrieves a farm by ID with access control check.
    
    Args:
        farm_id: The ID of the farm to retrieve
        user: The User instance to check ownership
        
    Returns:
        Tuple containing (farm_instance, error_message)
    """
    try:
        grower = user.grower_profile
        farm = Farm.objects.get(id=farm_id, owner=grower)
        return farm, None
    except Farm.DoesNotExist:
        return None, "Farm not found or you don't have permission to access it."
    except Grower.DoesNotExist:
        return None, "User profile not found."
    except Exception as e:
        logger.exception(f"Error retrieving farm {farm_id} for user {user.username}: {e}")
        return None, f"An unexpected error occurred: {e}"


def create_farm(farm_data: Dict[str, Any], user: User) -> Tuple[Optional[Farm], Optional[str]]:
    """
    Creates a new farm for a user.
    
    Args:
        farm_data: Dictionary containing farm details
        user: The owner User instance
        
    Returns:
        Tuple containing (created_farm, error_message)
    """
    try:
        grower = user.grower_profile
        
        # Create farm instance but don't save yet
        farm = Farm(owner=grower)
        
        # Set fields from farm_data
        for field, value in farm_data.items():
            if hasattr(farm, field):
                setattr(farm, field, value)
        
        # Set default plant type to Mango if not specified
        if not farm.plant_type:
            try:
                mango_type = PlantType.objects.get(name='Mango')
                farm.plant_type = mango_type
            except PlantType.DoesNotExist:
                return None, "Default 'Mango' PlantType not found. Please add it via admin."
        
        # Save the farm
        farm.save()
        
        # If we have a Geoscape address ID, try to fetch the boundary
        if farm.geoscape_address_id:
            success, message = fetch_and_save_cadastral_boundary(farm)
            if not success:
                logger.warning(f"Could not fetch boundary for farm {farm.id}: {message}")
        
        return farm, None
    
    except Exception as e:
        logger.exception(f"Error creating farm for user {user.username}: {e}")
        return None, f"An unexpected error occurred: {e}"


def update_farm(farm_id: int, farm_data: Dict[str, Any], user: User) -> Tuple[Optional[Farm], Optional[str]]:
    """
    Updates an existing farm.
    
    Args:
        farm_id: The ID of the farm to update
        farm_data: Dictionary containing updated farm details
        user: The owner User instance
        
    Returns:
        Tuple containing (updated_farm, error_message)
    """
    # First get the farm with permission check
    farm, error = get_farm_details(farm_id, user)
    if error:
        return None, error
    
    try:
        # Update fields from farm_data
        for field, value in farm_data.items():
            if hasattr(farm, field):
                setattr(farm, field, value)
        
        # Save the farm
        farm.save()
        
        # If the address ID has changed, try to fetch new boundary
        if 'geoscape_address_id' in farm_data and farm.geoscape_address_id:
            success, message = fetch_and_save_cadastral_boundary(farm)
            if not success:
                logger.warning(f"Could not fetch boundary for farm {farm.id}: {message}")
        
        return farm, None
    
    except Exception as e:
        logger.exception(f"Error updating farm {farm_id} for user {user.username}: {e}")
        return None, f"An unexpected error occurred: {e}"


def delete_farm(farm_id: int, user: User) -> Tuple[bool, Optional[str]]:
    """
    Deletes a farm.
    
    Args:
        farm_id: The ID of the farm to delete
        user: The owner User instance
        
    Returns:
        Tuple containing (success_flag, error_message)
    """
    # First get the farm with permission check
    farm, error = get_farm_details(farm_id, user)
    if error:
        return False, error
    
    try:
        farm_name = farm.name
        farm.delete()
        return True, f"Farm '{farm_name}' deleted successfully."
    
    except Exception as e:
        logger.exception(f"Error deleting farm {farm_id} for user {user.username}: {e}")
        return False, f"An unexpected error occurred: {e}"


def get_farm_surveillance_records(farm_id: int, user: User, limit: int = None) -> Tuple[Optional[List[SurveillanceRecord]], Optional[str]]:
    """
    Retrieves surveillance records for a farm.
    
    Args:
        farm_id: The ID of the farm
        user: The User instance for permission check
        limit: Optional limit on number of records to return
        
    Returns:
        Tuple containing (records_list, error_message)
    """
    # First get the farm with permission check
    farm, error = get_farm_details(farm_id, user)
    if error:
        return None, error
    
    try:
        records = SurveillanceRecord.objects.filter(farm=farm).order_by('-date_performed')
        if limit:
            records = records[:limit]
        return list(records), None
    
    except Exception as e:
        logger.exception(f"Error retrieving surveillance records for farm {farm_id}: {e}")
        return None, f"An unexpected error occurred: {e}"