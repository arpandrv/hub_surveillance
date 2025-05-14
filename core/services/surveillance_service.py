# core/services/surveillance_service.py
import logging
from typing import Dict, Any, Optional, List, Tuple
from django.utils import timezone
from django.contrib.auth.models import User

from ..models import Farm, PlantPart, Pest, SurveySession, Observation
from .calculation_service import get_recommended_plant_parts

logger = logging.getLogger(__name__)


def create_observation(
    session: SurveySession,
    data: Dict[str, Any]
) -> Tuple[Optional[Observation], Optional[str]]:
    """
    Creates a new observation within a survey session.

    Args:
        session: The SurveySession instance
        data: Dictionary containing observation details

    Returns:
        Tuple containing (observation_instance, error_message)
    """
    try:
        # Create observation instance
        observation = Observation(
            session=session,
            observation_time=timezone.now()
        )

        # Set basic fields from data
        for field in ['latitude', 'longitude', 'gps_accuracy', 'notes', 'plant_sequence_number']:
            if field in data:
                setattr(observation, field, data[field])

        # Save record first to allow M2M relationships
        observation.save()

        # Set pests observed
        if 'pests_observed' in data:
            if isinstance(data['pests_observed'], list):
                # If we got a list of IDs
                observation.pests_observed.set(data['pests_observed'])
            else:
                # If we got a queryset
                observation.pests_observed.set(data['pests_observed'])

        # Set diseases observed
        if 'diseases_observed' in data:
            if isinstance(data['diseases_observed'], list):
                # If we got a list of IDs
                observation.diseases_observed.set(data['diseases_observed'])
            else:
                # If we got a queryset
                observation.diseases_observed.set(data['diseases_observed'])

        return observation, None

    except Exception as e:
        logger.exception(f"Error creating observation for session {session.session_id}: {e}")
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
    # Get total number of survey sessions
    total_sessions = SurveySession.objects.filter(farm=farm, status='completed').count()

    # Get total observations made
    total_observations = Observation.objects.filter(
        session__farm=farm,
        session__status='completed',
        status='completed'
    ).count()

    # Get sessions from last 30 days
    thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
    recent_sessions = SurveySession.objects.filter(
        farm=farm,
        status='completed',
        end_time__gte=thirty_days_ago
    ).count()

    # Get most common pests found
    from django.db.models import Count
    common_pests = Pest.objects.filter(
        observations__session__farm=farm,
        observations__status='completed'
    ).annotate(
        occurrence_count=Count('observations')
    ).order_by('-occurrence_count')[:5]

    return {
        'total_sessions': total_sessions,
        'total_observations': total_observations,
        'recent_sessions': recent_sessions,
        'common_pests': common_pests
    }