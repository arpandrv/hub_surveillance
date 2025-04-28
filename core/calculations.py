# core/calculations.py
from .services.calculation_service import (
    calculate_surveillance_effort,
    get_recommended_plant_parts,
    get_surveillance_frequency,
    SEASON_PREVALENCE,
    CONFIDENCE_Z_SCORES,
    DEFAULT_MARGIN_OF_ERROR
)

import math
from decimal import Decimal

# Assumed z-scores based on approach.md
Z_SCORES = {
    90: 1.645,
    95: 1.960,
    99: 2.575,
}
DEFAULT_CONFIDENCE = 95
MARGIN_OF_ERROR = Decimal('0.05') # Fixed margin of error d=5%

def calculate_surveillance_effort(farm, confidence_level_percent, prevalence_p):
    """
    Calculates the required sample size based on farm population (N),
    confidence level (z), expected prevalence (p), and margin of error (d).
    Uses the formula for finite populations from approach.md.

    Args:
        farm (Farm): The Farm model instance.
        confidence_level_percent (int): The desired confidence level (e.g., 90, 95, 99).
        prevalence_p (float or Decimal): The expected prevalence for the current stage.

    Returns:
        dict: Containing calculation results including 'required_plants_to_survey',
              'percentage_of_total', 'survey_frequency', and input params, or an 'error'.
    """
    N = farm.total_plants()
    if N is None or N <= 0:
        return {'error': 'Total number of plants (N) must be calculated and positive.', 
                'required_plants_to_survey': None, 'percentage_of_total': None, 'survey_frequency': None}

    # Convert string confidence level from form to int for lookup
    try:
        confidence_level_int = int(confidence_level_percent)
    except (ValueError, TypeError):
        confidence_level_int = DEFAULT_CONFIDENCE # Fallback if conversion fails

    z = Decimal(str(Z_SCORES.get(confidence_level_int, Z_SCORES[DEFAULT_CONFIDENCE])))
    p = Decimal(str(prevalence_p)) # Convert float to Decimal
    d = MARGIN_OF_ERROR

    if not (0 < p < 1):
         return {'error': 'Prevalence (p) must be between 0 and 1.', 
                 'required_plants_to_survey': None, 'percentage_of_total': None, 'survey_frequency': None}

    try:
        # Calculate m = (z^2 * p * (1-p)) / d^2
        m_numerator = (z**2) * p * (Decimal(1) - p)
        m_denominator = d**2
        if m_denominator == 0:
             raise ValueError("Margin of error cannot be zero.")
        m = m_numerator / m_denominator

        # Calculate n = m / (1 + ((m - 1) / N))
        n_denominator = Decimal(1) + ((m - Decimal(1)) / Decimal(N))
        if n_denominator == 0:
             raise ValueError("Calculation resulted in division by zero for sample size.")
        n_float = m / n_denominator

        # Final sample size (rounded up, cannot exceed N)
        required_plants = min(N, int(math.ceil(n_float)))
        
        # Calculate percentage and frequency
        percentage_of_total = round((Decimal(required_plants) / Decimal(N)) * 100, 1) if N > 0 else 0
        survey_frequency = int(round(Decimal(N) / Decimal(required_plants))) if required_plants > 0 else None

        return {
            'N': N,
            'confidence_level_percent': confidence_level_percent,
            'prevalence_p': float(p), # Return as float for consistency?
            'margin_of_error': float(d),
            'required_plants_to_survey': required_plants,
            'percentage_of_total': float(percentage_of_total),
            'survey_frequency': survey_frequency,
            'error': None
        }

    except Exception as e:
        print(f"Error in sample size calculation: {e}")
        return {'error': f'Calculation error: {e}', 
                'required_plants_to_survey': None, 'percentage_of_total': None, 'survey_frequency': None}

# --- Placeholder functions below - replace or remove if not used elsewhere ---

def get_recommended_plant_parts(season, plant_type):
    """Placeholder: Returns hardcoded list of parts."""
    # This logic should now be handled by get_active_threats_and_parts
    # based on the stage derived from the season/month.
    # We will replace the call to this in the view.
    print("Warning: Deprecated get_recommended_plant_parts called.")
    if season == 'Flowering':
        return ["Flowers", "Leaves", "Branches"]
    else:
        return ["Leaves", "Fruit", "Stems", "Branches"]

def get_surveillance_frequency(season, farm):
    """Placeholder: Returns hardcoded frequency."""
    # This could also be made dynamic based on risk/stage later
    return 7 # Example: Every 7 days

# Re-export from service module for backward compatibility
__all__ = [
    'calculate_surveillance_effort',
    'get_recommended_plant_parts',
    'get_surveillance_frequency',
    'SEASON_PREVALENCE',
    'CONFIDENCE_Z_SCORES',
    'DEFAULT_MARGIN_OF_ERROR'
]