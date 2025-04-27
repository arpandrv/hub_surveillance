# core/calculations.py
import math # Import math for ceiling function

# Import models if needed for more complex calculations later
# from .models import Pest, Region, etc.

def calculate_surveillance_effort(farm, confidence_level_percent, season):
    """
    Calculates required surveillance effort based on farm stats,
    confidence level, and season.
    """
    N = farm.total_plants()
    # Ensure confidence level is an integer for dictionary lookup
    try:
        confidence_level_percent = int(confidence_level_percent)
    except (ValueError, TypeError):
         return {
            'N': N,
            'confidence_level_percent': confidence_level_percent,
            'season': season,
            'error': f'Invalid confidence level format: {confidence_level_percent}',
        }
        
    calculation_inputs = {
        'N': N,
        'confidence_level_percent': confidence_level_percent,
        'season': season,
    }
    
    if not N or N <= 0:
        return {
            **calculation_inputs,
            'error': 'Cannot calculate effort: Farm size or stocking rate not set or invalid.',
        }

    # 1. Map confidence to z-score
    z_map = {90: 1.645, 95: 1.960, 99: 2.575}
    z = z_map.get(confidence_level_percent)
    if z is None:
         return {
            **calculation_inputs,
            'error': f'Invalid confidence level value: {confidence_level_percent}%',
        }
    
    # 2. Map season to prevalence p
    p_map = {'Wet': 0.10, 'Dry': 0.02, 'Flowering': 0.05}
    p = p_map.get(season)
    if p is None:
        return {
            **calculation_inputs,
            'error': f'Invalid season selected: {season}',
        }
    
    # Calculate p_percent for display
    p_percent = p * 100 

    # 3. Set margin of error
    d = 0.05
    
    # Check if p is 0 or 1, which breaks the formula or needs special handling
    if p <= 0:
         n_final = 0 # If no prevalence expected, no samples needed for estimation
    elif p >= 1:
         n_final = N # If 100% prevalence, must check all 
    else:
        # 4. Calculate m (initial sample size for infinite population)
        try:
            m = (z**2 * p * (1 - p)) / (d**2)
        except ZeroDivisionError: # Should not happen if d=0.05
             return {
                **calculation_inputs,
                'z': z, 'p': p, 'd': d,
                'error': 'Calculation error (division by zero, check parameters).',
            }
    
        # 5. Finite population correction
        denominator = (1 + (m - 1) / N)
        if denominator <= 0:
             return {
                **calculation_inputs,
                'z': z, 'p': p, 'd': d, 'm': m,
                'error': 'Calculation error (invalid denominator in FPC).',
            }
        else:
             n_float = m / denominator
        
        # 6. Round up and cap at N
        n_final = math.ceil(n_float)
        if n_final > N:
            n_final = N
        if N > 0 and n_final < 1: # Ensure at least 1 sample if N > 0
            n_final = 1 
            
    # Calculate frequency (optional output)
    survey_frequency = round(N / n_final) if n_final > 0 else None

    return {
        **calculation_inputs, # Include inputs used
        'z': z,
        'p': p,
        'p_percent': p_percent,
        'd': d,
        'required_plants_to_survey': n_final,
        'survey_frequency': survey_frequency,
        'error': None
    } 