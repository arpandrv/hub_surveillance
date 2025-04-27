# core/calculations.py
import math
import logging
from django.utils import timezone

# Setup logger
logger = logging.getLogger(__name__)

# Season prevalence mapping
SEASON_PREVALENCE = {
    'Wet': 0.10,      # 10% prevalence in wet season
    'Dry': 0.02,      # 2% prevalence in dry season
    'Flowering': 0.05 # 5% prevalence in flowering period
}

# Confidence level to z-score mapping
CONFIDENCE_Z_SCORES = {
    90: 1.645,  # 90% confidence
    95: 1.960,  # 95% confidence
    99: 2.575   # 99% confidence
}

# Standard margin of error
DEFAULT_MARGIN_OF_ERROR = 0.05  # 5%


def calculate_surveillance_effort(farm, confidence_level_percent, season):
    """
    Calculates required surveillance effort based on farm stats, confidence level, and season.
    
    Args:
        farm: Farm model instance
        confidence_level_percent: Integer (90, 95, or 99)
        season: String ('Wet', 'Dry', or 'Flowering')
        
    Returns:
        Dictionary containing calculation results and inputs
    """
    # Get total number of plants (population size)
    N = farm.total_plants()
    
    # Validate and convert confidence level to integer
    try:
        confidence_level_percent = int(confidence_level_percent)
    except (ValueError, TypeError):
        logger.error(f"Invalid confidence level format: {confidence_level_percent}")
        return {
            'N': N,
            'confidence_level_percent': confidence_level_percent,
            'season': season,
            'error': f'Invalid confidence level format: {confidence_level_percent}',
        }
    
    # Store calculation inputs for return
    calculation_inputs = {
        'N': N,
        'confidence_level_percent': confidence_level_percent,
        'season': season,
    }
    
    # Validate farm has valid plant count
    if not N or N <= 0:
        logger.warning(f"Cannot calculate for farm {farm.id}: Missing size or stocking rate")
        return {
            **calculation_inputs,
            'error': 'Cannot calculate effort: Farm size or stocking rate not set or invalid.',
        }

    # Get z-score for selected confidence level
    z = CONFIDENCE_Z_SCORES.get(confidence_level_percent)
    if z is None:
        logger.error(f"Invalid confidence level: {confidence_level_percent}")
        return {
            **calculation_inputs,
            'error': f'Invalid confidence level value: {confidence_level_percent}%',
        }
    
    # Get prevalence value for selected season
    p = SEASON_PREVALENCE.get(season)
    if p is None:
        logger.error(f"Invalid season: {season}")
        return {
            **calculation_inputs,
            'error': f'Invalid season selected: {season}',
        }
    
    # Calculate percentage for display
    p_percent = p * 100 
    
    # Set margin of error
    d = DEFAULT_MARGIN_OF_ERROR
    
    # Handle edge cases for prevalence
    if p <= 0:
        n_final = 0  # No samples needed if prevalence is zero
    elif p >= 1:
        n_final = N  # Must check all if prevalence is 100%
    else:
        # Calculate initial sample size for infinite population
        try:
            m = (z**2 * p * (1 - p)) / (d**2)
        except ZeroDivisionError:
            logger.error(f"Division by zero in calculation for farm {farm.id}")
            return {
                **calculation_inputs,
                'z': z, 'p': p, 'd': d,
                'error': 'Calculation error (division by zero, check parameters).',
            }
    
        # Apply finite population correction
        denominator = (1 + (m - 1) / N)
        if denominator <= 0:
            logger.error(f"Invalid denominator in calculation for farm {farm.id}")
            return {
                **calculation_inputs,
                'z': z, 'p': p, 'd': d, 'm': m,
                'error': 'Calculation error (invalid denominator in FPC).',
            }
            
        n_float = m / denominator
        
        # Round up to whole number and ensure within valid range
        n_final = math.ceil(n_float)
        n_final = min(n_final, N)  # Cap at population size
        n_final = max(n_final, 1)  # Ensure at least 1 sample if population exists
    
    # Calculate additional helpful metrics
    survey_frequency = round(N / n_final) if n_final > 0 else None
    percentage_of_total = (n_final / N * 100) if N > 0 else None
    
    # Return complete calculation results
    return {
        **calculation_inputs,
        'z': z,
        'p': p,
        'p_percent': p_percent,
        'd': d,
        'required_plants_to_survey': n_final,
        'survey_frequency': survey_frequency,
        'percentage_of_total': percentage_of_total,
        'calculation_date': timezone.now().date(),
        'error': None
    }


def get_recommended_plant_parts(season, plant_type=None):
    """
    Returns recommended plant parts to check based on season and plant type.
    
    In a real implementation, this would likely come from a database or more
    complex model.
    """
    # Basic implementation - in reality would be more sophisticated
    parts = {
        'Wet': ['Leaves', 'Fruit', 'Trunk'],
        'Dry': ['Trunk', 'Branches', 'Leaves'],
        'Flowering': ['Flowers', 'Leaves', 'Branches']
    }
    
    return parts.get(season, ['Leaves', 'Trunk', 'Branches'])


def get_surveillance_frequency(season, farm=None):
    """
    Returns recommended surveillance frequency in days.
    """
    # Basic implementation - could be more sophisticated
    frequency = {
        'Wet': 7,      # Weekly during wet season
        'Dry': 14,     # Bi-weekly during dry season
        'Flowering': 7  # Weekly during flowering
    }
    
    return frequency.get(season, 14)  # Default to 14 days