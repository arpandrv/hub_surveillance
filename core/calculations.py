# core/calculations.py

# Import models if needed for more complex calculations later
# from .models import Pest, Region, etc.

def calculate_surveillance_effort(farm):
    """
    Placeholder function to calculate required surveillance effort.
    Replace with actual logic later.
    Accepts a Farm object.
    """
    total_plants_on_farm = farm.total_plants()
    if not total_plants_on_farm or total_plants_on_farm <= 0:
        return {
            'error': 'Cannot calculate effort: Farm size or stocking rate not set or invalid.'
        }

    # --- Placeholder Logic ---
    # Example: Survey 5% of plants, minimum 10, maximum 500
    required_plants_to_survey = max(10, min(500, int(total_plants_on_farm * 0.05)))

    # Example: Calculate frequency '1 in X'
    if required_plants_to_survey > 0:
        survey_frequency = round(total_plants_on_farm / required_plants_to_survey)
    else:
        survey_frequency = None
    # --- End Placeholder Logic ---

    return {
        'total_plants_on_farm': total_plants_on_farm,
        'required_plants_to_survey': required_plants_to_survey,
        'survey_frequency': survey_frequency, # e.g., survey 1 plant in every X plants
        'confidence_level': 95, # Placeholder confidence level
        'error': None
    } 