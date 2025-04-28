# core/services/surveillance_service.py
import logging
from typing import Dict, Any, Optional, List, Tuple
from django.utils import timezone
from django.contrib.auth.models import User

from ..models import Farm, SurveillanceRecord, PlantPart, Pest
from .calculation_service import get_recommended_plant_parts

logger = logging.getLogger(__name__)


def create_surveillance_record(
    farm: Farm, 
    user: User, 
    data: Dict[str, Any]
) -> Tuple[Optional[SurveillanceRecord], Optional[str]]:
    """
    Creates a new surveillance record.
    
    Args:
        farm: The Farm instance
        user: The User who performed the surveillance
        data: Dictionary containing surveillance details
        
    Returns:
        Tuple containing (record_instance, error_message)
    """
    try:
        grower = user.grower_profile
        
        # Create record instance
        record = SurveillanceRecord(
            farm=farm,
            performed_by=grower
        )
        
        # Set basic fields from data
        for field in ['date_performed', 'plants_surveyed', 'notes']:
            if field in data:
                setattr(record, field, data[field])
        
        # If no date provided, use now
        if not record.date_performed:
            record.date_performed = timezone.now()
        
        # Validate plants_surveyed
        total_plants = farm.total_plants()
        if total_plants and record.plants_surveyed > total_plants:
            return None, f"Number of plants surveyed ({record.plants_surveyed}) cannot exceed total plants ({total_plants})."
        
        # Save record first to allow M2M relationships
        record.save()
        
        # Set plant parts checked
        if 'plant_parts_checked' in data:
            if isinstance(data['plant_parts_checked'], list):
                # If we got a list of IDs
                record.plant_parts_checked.set(data['plant_parts_checked'])
            else:
                # If we got a queryset
                record.plant_parts_checked.set(data['plant_parts_checked'])
        
        # Set pests found
        if 'pests_found' in data:
            if isinstance(data['pests_found'], list):
                # If we got a list of IDs
                record.pests_found.set(data['pests_found'])
            else:
                # If we got a queryset
                record.pests_found.set(data['pests_found'])
        
        return record, None
    
    except Exception as e:
        logger.exception(f"Error creating surveillance record for farm {farm.id}: {e}")
        return None, f"An unexpected error occurred: {e}"


def get_surveillance_recommendations(farm: Farm) -> Dict[str, Any]:
    """
    Gets surveillance recommendations for a farm.
    
    Args:
        farm: The Farm instance
        
    Returns:
        Dictionary containing recommendations
    """
    # Get current season
    season = farm.current_season()
    
    # Get plant parts to check
    plant_parts = get_recommended_plant_parts(season, farm.plant_type)
    
    # Convert to model objects if they exist
    plant_part_objects = list(PlantPart.objects.filter(name__in=plant_parts))
    
    # Get priority pests to watch for
    priority_pests = Pest.get_priority_pests_for_season(season, farm.plant_type)
    
    # Get date of last surveillance
    last_date = farm.last_surveillance_date()
    
    # Calculate next due date
    next_due = farm.next_due_date()
    
    return {
        'season': season,
        'recommended_parts': plant_part_objects,
        'priority_pests': priority_pests,
        'last_surveillance_date': last_date,
        'next_due_date': next_due
    }


def get_surveillance_stats(farm: Farm) -> Dict[str, Any]:
    """
    Gets surveillance statistics for a farm.
    
    Args:
        farm: The Farm instance
        
    Returns:
        Dictionary containing statistics
    """
    # Get total number of surveillance records
    total_records = SurveillanceRecord.objects.filter(farm=farm).count()
    
    # Get total plants inspected
    total_inspected = SurveillanceRecord.objects.filter(farm=farm).values_list('plants_surveyed', flat=True)
    total_inspected_sum = sum(total_inspected) if total_inspected else 0
    
    # Get records from last 30 days
    thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
    recent_records = SurveillanceRecord.objects.filter(
        farm=farm,
        date_performed__gte=thirty_days_ago
    ).count()
    
    # Get most common pests found
    from django.db.models import Count
    common_pests = Pest.objects.filter(
        surveillance_records__farm=farm
    ).annotate(
        occurrence_count=Count('surveillance_records')
    ).order_by('-occurrence_count')[:5]
    
    return {
        'total_records': total_records,
        'total_inspected': total_inspected_sum,
        'recent_records': recent_records,
        'common_pests': common_pests
    }