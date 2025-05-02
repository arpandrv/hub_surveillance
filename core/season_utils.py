import datetime
from decimal import Decimal # Import Decimal
from django.db.models import Q # Import Q for query
from .models import SeasonalStage, Pest, Disease, PlantPart # Import necessary models

def get_seasonal_stage_info(override_month=None):
    """
    Determines the farming stage and associated data (prevalence, pests, diseases)
    by querying the SeasonalStage model based on the current or overridden month.
    Dynamically determines the recommended plant parts based on the parts affected 
    by the active pests and diseases for the found stage.

    Args:
        override_month (int, optional): A month number (1-12) to use 
                                        instead of the current system month. 
                                        Defaults to None.

    Returns:
        dict: {
            'stage_name': str or None, 
            'prevalence_p': Decimal or None,
            'pest_names': list[str], 
            'disease_names': list[str], 
            'part_names': list[str], # Dynamically generated
            'month_used': int
        }
        Returns None for stage_name and prevalence_p, and empty lists for names
        if no matching stage is found in the database.
    """
    month_to_use = None
    if override_month is not None:
        try:
            month_val = int(override_month)
            if 1 <= month_val <= 12:
                month_to_use = month_val
                print(f"DEBUG (get_seasonal_stage_info): Using overridden month: {month_to_use}")
            else:
                print(f"Warning (get_seasonal_stage_info): Invalid override_month ({override_month}). Using current month.")
        except (ValueError, TypeError):
            print(f"Warning (get_seasonal_stage_info): Could not parse override_month ({override_month}). Using current month.")

    # If override wasn't valid or provided, use current system month
    if month_to_use is None:
        month_to_use = datetime.datetime.now().month
        # print(f"DEBUG (get_seasonal_stage_info): Using current system month: {month_to_use}")

    current_stage = None
    try:
        # Find stages where the current month number is in the comma-separated 'months' string.
        stages = SeasonalStage.objects.filter(
            Q(months__startswith=f"{month_to_use},") | # Starts with month,
            Q(months__endswith=f",{month_to_use}") |   # Ends with ,month
            Q(months__contains=f",{month_to_use},") | # Contains ,month,
            Q(months=str(month_to_use))              # Is exactly month (for single-month stages)
        ).prefetch_related('active_pests__affects_plant_parts', 'active_diseases__affects_plant_parts') # Prefetch related data
        
        if stages.exists():
            # In case a month is accidentally assigned to multiple stages, pick the first one found.
            current_stage = stages.first()
            print(f"DEBUG (get_seasonal_stage_info): Found stage '{current_stage.name}' for month {month_to_use}")
        else:
             print(f"Warning (get_seasonal_stage_info): No SeasonalStage found in database for month {month_to_use}.")

    except Exception as e:
        # Catch potential database errors
        print(f"Error (get_seasonal_stage_info): Database query failed - {e}")
        current_stage = None

    # Prepare the result dictionary
    result = {
        'stage_name': None,
        'prevalence_p': None,
        'pest_names': [],
        'disease_names': [],
        'part_names': [], # Will be populated dynamically
        'month_used': month_to_use
    }

    if current_stage:
        result['stage_name'] = current_stage.name
        result['prevalence_p'] = current_stage.prevalence_p
        
        # Get pest and disease names
        active_pests = current_stage.active_pests.all()
        active_diseases = current_stage.active_diseases.all()
        result['pest_names'] = list(active_pests.values_list('name', flat=True))
        result['disease_names'] = list(active_diseases.values_list('name', flat=True))

        # --- Dynamically determine recommended parts --- # MODIFIED SECTION
        recommended_parts_set = set()
        
        # Collect parts affected by active pests
        for pest in active_pests:
            for part in pest.affects_plant_parts.all():
                recommended_parts_set.add(part.name)
                
        # Collect parts affected by active diseases
        for disease in active_diseases:
            for part in disease.affects_plant_parts.all():
                recommended_parts_set.add(part.name)
                
        result['part_names'] = sorted(list(recommended_parts_set)) # Convert set to sorted list
        # --- End Dynamic Part Determination ---

    return result 