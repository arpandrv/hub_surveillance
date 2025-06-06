from django.shortcuts import render, redirect, get_object_or_404
from .season_utils import get_seasonal_stage_info
from django.http import Http404, JsonResponse, HttpResponse
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import models
from django.db.models import Count, F, Q, Max
from django.utils import timezone
from django.urls import reverse
import json
from django.conf import settings
import requests
from decimal import Decimal
from datetime import date, datetime, timedelta
import pprint
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
# --- Add imports for PDF generation ---
# from django.template.loader import render_to_string
# from weasyprint import HTML, CSS
# from weasyprint.fonts import FontConfiguration # If needing custom fonts later
# --- End PDF imports ---
import os
import io
import base64
import qrcode

from .forms import (
    SignUpForm, FarmForm, 
    UserEditForm, GrowerProfileEditForm, CalculatorForm, ObservationForm
)
from .models import (
    Farm, PlantType, PlantPart, Pest, 
    Grower, Region, SurveillanceCalculation, BoundaryMappingToken, Disease, SurveySession, Observation, ObservationImage, User
)

# Import services
from .services.user_service import create_user_with_profile
from .services.farm_service import (
    get_user_farms, get_farm_details, create_farm,
    update_farm, delete_farm, get_farm_survey_sessions
)
from .services.calculation_service import (
    calculate_surveillance_effort, get_recommended_plant_parts,
    get_surveillance_frequency, save_calculation_to_database
)
from .services.surveillance_service import (
    create_observation, get_surveillance_recommendations,
    get_surveillance_stats
)
from .services.geoscape_service import (
    fetch_cadastral_boundary, search_addresses
)
from .services.boundary_service import (
    create_mapping_token, get_mapping_url, validate_mapping_token,
    invalidate_token, save_boundary_to_farm, fetch_and_save_cadastral_boundary
)

# Import new utils
from .season_utils import get_seasonal_stage_info
# Import updated calculation function (assuming it's in calculations.py)
from .calculations import calculate_surveillance_effort, get_surveillance_frequency, Z_SCORES, DEFAULT_CONFIDENCE

# Import SeasonalStage for querying in active_survey_session_view
from .models import SeasonalStage


def signup_view(request):
    """Handle user registration and Grower profile creation."""
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()  # This saves User and creates Grower profile
            login(request, user)
            messages.success(request, f"Welcome to Mango Surveillance Hub, {user.username}!")
            return redirect('core:dashboard')
    else:
        form = SignUpForm()
    return render(request, 'core/signup.html', {'form': form})


@login_required
def home_view(request):
    """Display the user's farms (My Farms page) with enhanced mobile-friendly UI."""
    farms = get_user_farms(request.user)
    # Sort farms by surveillance status - Due farms first, then farms with recent checks
    sorted_farms = sorted(farms, key=lambda farm: (
        farm.days_since_last_surveillance() is None, # Farms never checked come first
        -1 if farm.days_since_last_surveillance() is None else farm.days_since_last_surveillance(), # Then sort by days since last check (descending)
        farm.name # Finally sort alphabetically
    ))
    
    return render(request, 'core/home.html', {'farms': sorted_farms})


@login_required
def create_farm_view(request):
    """Handle farm creation."""
    if request.method == 'POST':
        form = FarmForm(request.POST)
        if form.is_valid():
            # Extract data from the form
            farm_data = {field: form.cleaned_data[field] for field in form.Meta.fields}
            
            # Use service to create farm
            farm, error = create_farm(farm_data, request.user)
            
            if error:
                messages.error(request, error)
                return render(request, 'core/create_farm.html', {'form': form})
            
            messages.success(request, f"Farm '{farm.name}' was created successfully!")
            return redirect('core:farm_detail', farm_id=farm.id)
    else:
        form = FarmForm()
    
    return render(request, 'core/create_farm.html', {'form': form})


@login_required
def farm_detail_view(request, farm_id):
    """Display detailed information about a specific farm, using dynamic recommendations."""
    print(f"--- Entering farm_detail_view for farm_id: {farm_id} ---")
    farm = get_object_or_404(Farm, id=farm_id, owner=request.user.grower_profile)
    
    # --- Handle Debug Month Override ---
    debug_month_override = None
    debug_month_str = request.GET.get('debug_month')
    if debug_month_str:
        print(f"  DEBUG: Raw debug_month_str = '{debug_month_str}' (Type: {type(debug_month_str)})")
        cleaned_month_str = debug_month_str.strip()
        print(f"  DEBUG: Cleaned debug_month_str = '{cleaned_month_str}' (Type: {type(cleaned_month_str)})")
        
        try:
            print(f"  DEBUG: Attempting int('{cleaned_month_str}')...")
            month_val = int(cleaned_month_str)
            print(f"  DEBUG: int() conversion successful: month_val = {month_val} (Type: {type(month_val)})")

            if 1 <= month_val <= 12:
                debug_month_override = month_val
                print(f"Farm Detail: Using debug_month override: {debug_month_override}")
                messages.info(request, f"Displaying farm details based on overridden month: {datetime.date(1900, debug_month_override, 1).strftime('%B')}.")
            else:
                 print(f"  DEBUG: month_val ({month_val}) is not between 1 and 12.")
                 messages.warning(request, f"Invalid debug month ({cleaned_month_str}) ignored. Using current system month.")
        except (ValueError, TypeError) as e:
             print(f"  DEBUG: ERROR during int() conversion: {e}")
             messages.warning(request, f"Could not parse debug month ('{cleaned_month_str}') ignored. Using current system month.")
        except Exception as e:
             print(f"  DEBUG: UNEXPECTED ERROR during debug month processing: {e}")
             messages.warning(f"An unexpected error occurred processing debug month ('{cleaned_month_str}') ignored. Using current system month.")

    # --- Determine Current Stage Info (using potential override) ---
    stage_info = get_seasonal_stage_info(override_month=debug_month_override)
    print(f"\nDEBUG (farm_detail_view): stage_info received from util = {stage_info}") 
    
    current_stage = stage_info['stage_name']
    current_prevalence_p = stage_info['prevalence_p']
    month_used_for_stage = stage_info['month_used']
    pest_names = stage_info['pest_names']
    disease_names = stage_info['disease_names']
    part_names = stage_info['part_names']

    print(f"DEBUG (farm_detail_view): Unpacked values: \n  stage='{current_stage}', \n  p={current_prevalence_p}, \n  month={month_used_for_stage}, \n  pests={pest_names}, \n  diseases={disease_names}, \n  parts={part_names}") 

    print(f"Farm {farm.id}: Stage based on Month {month_used_for_stage}='{current_stage}', Prevalence={current_prevalence_p}") # Debug
    
    # --- Get or Calculate Sample Size for Display ---
    calculation_results = None
    print(f"Farm {farm.id}: Attempting to fetch/calculate results...") # ADDED
    
    # Try to get the most recent saved calculation for this farm
    try:
        print(f"Farm {farm.id}: Inside TRY block, searching for SurveillanceCalculation...") # ADDED
        latest_calc = SurveillanceCalculation.objects.filter(farm=farm, is_current=True).latest('date_created')
        print(f"Farm {farm.id}: Found latest_calc: ID={latest_calc.id}, Confidence={latest_calc.confidence_level}, Plants={latest_calc.required_plants}") # ADDED
        
        # Map model fields to the dictionary structure expected by the template
        print(f"Farm {farm.id}: Mapping latest_calc to dictionary...") # ADDED
        calculation_results = {
            'N': latest_calc.population_size,
            'confidence_level_percent': latest_calc.confidence_level,
            'prevalence_p': float(latest_calc.prevalence_percent / Decimal(100)) if latest_calc.prevalence_percent is not None else None, # ADDED safety check
            'margin_of_error': float(latest_calc.margin_of_error / Decimal(100)) if latest_calc.margin_of_error is not None else None, # ADDED safety check
            'required_plants_to_survey': latest_calc.required_plants,
            'percentage_of_total': float(latest_calc.percentage_of_total) if latest_calc.percentage_of_total is not None else None, # ADDED safety check
            'survey_frequency': latest_calc.survey_frequency,
            'error': None
        }
        print(f"Farm {farm.id}: Using saved calculation (ID: {latest_calc.id})")
    except SurveillanceCalculation.DoesNotExist:
        print(f"Farm {farm.id}: No saved calculation found (DoesNotExist). Calculating with default confidence.") # MODIFIED
        # Fallback: Calculate using default confidence if no saved record exists
        display_confidence = DEFAULT_CONFIDENCE 
        # Ensure we have a valid prevalence_p for calculation
        if current_prevalence_p is not None:
            calculation_results = calculate_surveillance_effort(
                farm=farm,
                confidence_level_percent=display_confidence,
                prevalence_p=current_prevalence_p # Use prevalence from DB stage info
            )
            # ADDED check if fallback calculation resulted in error
            if calculation_results.get('error'):
                 print(f"Farm {farm.id}: Fallback calculation resulted in error: {calculation_results['error']}")
            else:
                 print(f"Farm {farm.id}: Fallback calculation successful.")
        else:
            # Handle case where prevalence couldn't be determined (no stage found)
            print(f"Farm {farm.id}: Cannot calculate fallback - prevalence_p is None (likely no stage found for month {month_used_for_stage})")
            calculation_results = {'error': f'Cannot calculate recommendations: No seasonal stage found for the current month ({month_used_for_stage}). Please define stages in admin.'}

    except Exception as e:
        # Handle other potential errors during fetch/mapping
        print(f"Farm {farm.id}: Error fetching or mapping saved calculation: {e}") # MODIFIED
        calculation_results = {'error': f'Error retrieving saved calculation: {e}'}
        print(f"Farm {farm.id}: Displaying error message: {calculation_results['error']}") # ADDED

    # Ensure calculation_results is not None if calculation failed
    if calculation_results is None:
        print(f"Farm {farm.id}: calculation_results was None after try/except block. Setting error.") # ADDED
        # Ensure error message reflects potential stage issue if prevalence was None
        error_msg = 'Could not determine surveillance recommendations.'
        if current_prevalence_p is None:
            error_msg = f'Cannot calculate recommendations: No seasonal stage found for the current month ({month_used_for_stage}). Please define stages in admin.'
        calculation_results = {'error': error_msg}
        
    print(f"Farm {farm.id}: Final Calculation Results for display={calculation_results}") # Debug

    # --- Get Active Threats and Parts for the Current Stage ---
    print(f"Farm {farm.id}: Active Pests={pest_names}, Diseases={disease_names}, Parts={part_names} for stage '{current_stage}'") # Debug

    # --- Fetch corresponding Model objects --- 
    print(f"DEBUG (farm_detail_view): Filtering Pest model with names: {pest_names}") 
    priority_pests = Pest.objects.filter(name__in=pest_names)
    print(f"DEBUG (farm_detail_view): Found priority_pests QuerySet: {priority_pests}") 

    print(f"DEBUG (farm_detail_view): Filtering Disease model with names: {disease_names}") 
    priority_diseases = Disease.objects.filter(name__in=disease_names)
    print(f"DEBUG (farm_detail_view): Found priority_diseases QuerySet: {priority_diseases}") 

    print(f"DEBUG (farm_detail_view): Filtering PlantPart model with names: {part_names}") 
    recommended_parts = PlantPart.objects.filter(name__in=part_names)
    print(f"DEBUG (farm_detail_view): Found recommended_parts QuerySet: {recommended_parts}") 

    # --- Other Info ---
    # TODO: Refactor frequency logic if needed, maybe based on stage?
    surveillance_frequency = get_surveillance_frequency(current_stage, farm) # Still uses stage name, might need update if frequency depends on DB stage
    last_surveillance_date = farm.last_surveillance_date()
    next_due_date = farm.next_due_date() # Uses simple 7-day logic for now

    # Get completed survey sessions for this farm
    completed_sessions = SurveySession.objects.filter(
        farm=farm,
        status='completed'
    ).order_by('-end_time')[:5]

    # Get latest in-progress session if exists
    latest_in_progress = SurveySession.objects.filter(
        farm=farm,
        status__in=['not_started', 'in_progress']
    ).order_by('-start_time').first()

    context = {
        'farm': farm,
        'current_stage': current_stage, # Pass stage name
        'month_used_for_stage': month_used_for_stage, # Pass the month used for clarity
        'calculation_results': calculation_results, # Results based on current stage & default confidence
        'completed_sessions': completed_sessions,
        'latest_in_progress': latest_in_progress,
        'priority_pests': priority_pests,
        'priority_diseases': priority_diseases,
        'recommended_parts': recommended_parts,
        'surveillance_frequency': surveillance_frequency,
        'last_surveillance_date': last_surveillance_date,
        'next_due_date': next_due_date,
        'farm_boundary_json': farm.boundary
    }
    print(f"\nDEBUG (farm_detail_view): Final context dictionary passed to template:")
    pprint.pprint(context)
    print("---")
    
    return render(request, 'core/farm_detail.html', context)


@login_required
def edit_farm_view(request, farm_id):
    """Handle farm editing."""
    # Get farm with permission check
    farm, error = get_farm_details(farm_id, request.user)
    if error:
        messages.error(request, error)
        return redirect('core:home')
    
    original_address_id = farm.geoscape_address_id  # Store before binding form
    
    if request.method == 'POST':
        form = FarmForm(request.POST, instance=farm)
        if form.is_valid():
            # Extract data from the form
            farm_data = {field: form.cleaned_data[field] for field in form.Meta.fields}
            
            # Use service to update farm
            updated_farm, error = update_farm(farm_id, farm_data, request.user)
            if error:
                messages.error(request, error)
                return render(request, 'core/create_farm.html', {'form': form, 'farm': farm, 'is_edit': True})
            
            messages.success(request, f"Farm '{updated_farm.name}' was updated successfully!")
            
            # Handle boundary update if address changed
            address_id_changed = (updated_farm.geoscape_address_id != original_address_id)
            boundary_is_missing = not updated_farm.boundary
            new_address_id_set = bool(updated_farm.geoscape_address_id)
            
            if new_address_id_set and (address_id_changed or boundary_is_missing):
                success, message = fetch_and_save_cadastral_boundary(updated_farm)
                if success:
                    messages.info(request, f"Cadastral boundary retrieved/updated and saved for '{updated_farm.name}'.")
                elif address_id_changed and updated_farm.boundary is not None:
                    # Clear potentially outdated boundary
                    updated_farm.boundary = None
                    updated_farm.save(update_fields=['boundary'])
                    messages.warning(request, f"Address changed, but could not retrieve new boundary for '{updated_farm.name}'. Old boundary cleared.")
                elif boundary_is_missing:
                    messages.warning(request, f"Could not automatically retrieve cadastral boundary for '{updated_farm.name}'.")
            
            return redirect('core:farm_detail', farm_id=updated_farm.id)
    else:
        form = FarmForm(instance=farm)
    
    context = {
        'form': form,
        'farm': farm,
        'is_edit': True  # Flag to indicate this is an edit operation
    }
    
    return render(request, 'core/create_farm.html', context)


@login_required
def delete_farm_view(request, farm_id):
    """Handle farm deletion."""
    # Get farm with permission check
    farm, error = get_farm_details(farm_id, request.user)
    if error:
        messages.error(request, error)
        return redirect('core:home')
    
    if request.method == 'POST':
        farm_name = farm.name
        success, error = delete_farm(farm_id, request.user)
        
        if success:
            messages.success(request, f"Farm '{farm_name}' was deleted successfully.")
            return redirect('core:myfarms')
        else:
            messages.error(request, error)
    
    context = {'farm': farm}
    return render(request, 'core/delete_farm_confirm.html', context)


@login_required
def calculator_view(request):
    """Calculate surveillance requirements based on user inputs (confidence only)."""
    grower = request.user.grower_profile
    calculation_results = None
    selected_farm_instance = None
    form_submitted = False
    debug_month_override = None # Initialize

    # --- Handle Debug Month Override --- 
    debug_month_str = request.GET.get('debug_month')
    if debug_month_str:
        cleaned_month_str = debug_month_str.strip()
        try:
            month_val = int(cleaned_month_str)
            if 1 <= month_val <= 12:
                debug_month_override = month_val
                print(f"Calculator View: Using debug_month override: {debug_month_override}")
            else:
                 messages.warning(request, f"Invalid debug month ({cleaned_month_str}) ignored. Using current system month.")
        except (ValueError, TypeError):
             messages.warning(request, f"Could not parse debug month ({cleaned_month_str}) ignored. Using current system month.")

    # Determine current stage info (potentially overridden)
    stage_info = get_seasonal_stage_info(override_month=debug_month_override)
    current_stage = stage_info['stage_name']
    current_prevalence_p = stage_info['prevalence_p']
    month_used_for_calc = stage_info['month_used']
    
    # Get initial farm_id from query params if available
    initial_farm_id = request.GET.get('farm')
    
    # Check if form is submitted (farm and confidence present)
    if request.GET and 'farm' in request.GET and 'confidence_level' in request.GET:
        form_submitted = True
        form = CalculatorForm(grower, request.GET) # Pass grower and GET data
        
        if form.is_valid():
            selected_farm_instance = form.cleaned_data['farm']
            confidence_str = form.cleaned_data['confidence_level'] # It's a string here
            
            # Convert confidence string to int for calculation
            try:
                confidence = int(confidence_str)
            except (ValueError, TypeError):
                 messages.error(request, "Invalid confidence level selected.")
                 # Set confidence to default or handle error appropriately
                 confidence = DEFAULT_CONFIDENCE 
                 # Potentially return here or set an error flag in calculation_results
                 calculation_results = {'error': 'Invalid confidence level.'} 
            
            # Only proceed if confidence was valid or handled
            if not (calculation_results and calculation_results.get('error')):
                # Ensure we have a valid prevalence_p for calculation
                if current_prevalence_p is not None:
                    # Calculate surveillance effort using stage/p (from DB stage info) and SELECTED confidence
                    calculation_results = calculate_surveillance_effort(
                        farm=selected_farm_instance,
                        confidence_level_percent=confidence, # Pass the integer confidence
                        prevalence_p=current_prevalence_p # Use stage-determined prevalence
                    )
                else:
                    # Handle case where prevalence couldn't be determined
                    print(f"Calculator View: Cannot calculate - prevalence_p is None (likely no stage found for month {month_used_for_calc})")
                    calculation_results = {'error': f'Calculation failed: No seasonal stage found for the current month ({month_used_for_calc}). Please define stages in admin.'}

                # Add the month used to the results dict for display (only if calc didn't fail)
                if calculation_results and not calculation_results.get('error'):
                     calculation_results['month_used'] = month_used_for_calc
                
                # Save calculation to database (if valid result)
                if not calculation_results.get('error') and selected_farm_instance:
                    SurveillanceCalculation.objects.filter(
                        farm=selected_farm_instance, 
                        is_current=True
                    ).update(is_current=False)
                    
                    surveillance_calc = SurveillanceCalculation(
                        farm=selected_farm_instance,
                        created_by=request.user,
                        season=current_stage if current_stage else "Unknown", # Store the auto-determined stage name (or fallback)
                        confidence_level=confidence,
                        population_size=calculation_results['N'],
                        # Use Decimal directly from prevalence_p if available
                        prevalence_percent=(current_prevalence_p * Decimal(100)) if current_prevalence_p is not None else Decimal('0.0'),
                        margin_of_error=Decimal(str(calculation_results.get('margin_of_error', 0.05))) * 100, # Use default if not returned
                        required_plants=calculation_results['required_plants_to_survey'],
                        percentage_of_total=Decimal(str(calculation_results.get('percentage_of_total', 0))),
                        survey_frequency=calculation_results.get('survey_frequency'),
                        is_current=True,
                        # notes=f"Calculation based on month: {month_used_for_calc}" # Optional notes
                    )
                    surveillance_calc.save()
                    messages.success(
                        request, 
                        f"Surveillance calculation saved for {selected_farm_instance.name} ({current_stage or 'Unknown Stage'} based on month {month_used_for_calc}): {calculation_results['required_plants_to_survey']} plants at {confidence}% confidence."
                    )
        else:
            # Show form errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{form.fields[field].label}: {error}")
    
    # Initialize form
    elif initial_farm_id and not form_submitted:
        try:
            initial_farm = Farm.objects.get(id=initial_farm_id, owner=grower)
            form = CalculatorForm(grower, initial={'farm': initial_farm, 'confidence_level': DEFAULT_CONFIDENCE})
        except Farm.DoesNotExist:
            form = CalculatorForm(grower) # Initialize empty if initial farm not found
    else:
        form = CalculatorForm(grower) # Initialize empty if no initial farm ID

    # Get all seasonal stages for our timeline display
    all_seasonal_stages = SeasonalStage.objects.all().order_by('id')
    
    # Create a mapping of month to stage for the timeline
    month_to_stage_map = {}
    for stage in all_seasonal_stages:
        months_list = [int(m.strip()) for m in stage.months.split(',') if m.strip().isdigit()]
        for month in months_list:
            month_to_stage_map[month] = {
                'name': stage.name,
                'prevalence_p': float(stage.prevalence_p * 100),
                'is_current': month == month_used_for_calc
            }
    
    # Get active pests and diseases for current stage if it exists
    current_pests = []
    current_diseases = []
    if current_stage:
        try:
            current_stage_obj = SeasonalStage.objects.get(name=current_stage)
            current_pests = list(current_stage_obj.active_pests.all().values('name', 'description'))
            current_diseases = list(current_stage_obj.active_diseases.all().values('name', 'description'))
        except SeasonalStage.DoesNotExist:
            pass
    
    context = {
        'form': form,
        'selected_farm': selected_farm_instance,
        'calculation_results': calculation_results,
        'form_submitted': form_submitted,
        'current_stage': current_stage, # Pass stage name (or None)
        # Pass prevalence as percentage, handle None
        'current_prevalence_p': float(current_prevalence_p * 100) if current_prevalence_p is not None else None, 
        'month_used_for_calc': month_used_for_calc, # Pass month used
        'all_stages': all_seasonal_stages,
        'month_to_stage_map': month_to_stage_map,
        'current_pests': current_pests,
        'current_diseases': current_diseases
    }
    
    return render(request, 'core/calculator.html', context)


@login_required
def record_surveillance_view(request, farm_id):
    """Record a new surveillance activity for a farm."""
    # Get farm with permission check
    farm, error = get_farm_details(farm_id, request.user)
    if error:
        messages.error(request, error)
        return redirect('core:home')
    
    # Get current seasonal recommendations for GET request display
    stage_info = get_seasonal_stage_info() # Use current month by default
    recommended_part_names = stage_info.get('part_names', [])
    recommended_pest_names = stage_info.get('pest_names', [])
    recommended_disease_names = stage_info.get('disease_names', [])
    current_stage_name = stage_info.get('stage_name', 'Unknown')
    current_prevalence_p = stage_info.get('prevalence_p') # Needed for fallback calculation
    
    # Fetch the actual model instances for recommendations to potentially highlight in template
    recommended_parts_qs = PlantPart.objects.filter(name__in=recommended_part_names)
    recommended_pests_qs = Pest.objects.filter(name__in=recommended_pest_names)
    recommended_diseases_qs = Disease.objects.filter(name__in=recommended_disease_names)

    if request.method == 'POST':
        form = SurveillanceRecordForm(request.POST, farm=farm)
        if form.is_valid():
            # Extract data from the form
            data = {
                'date_performed': form.cleaned_data['date_performed'],
                'plants_surveyed': form.cleaned_data['plants_surveyed'],
                'notes': form.cleaned_data['notes'],
                'plant_parts_checked': form.cleaned_data['plant_parts_checked'],
                'pests_found': form.cleaned_data['pests_found'],
                'diseases_found': form.cleaned_data.get('diseases_found') # Use .get() in case field isn't always present
            }
            
            # Use service to create record
            record, error = create_surveillance_record(farm, request.user, data)
            
            if error:
                messages.error(request, error)
                # Pass recommendations to context even on POST error
                context = {
                    'form': form, 
                    'farm': farm,
                    'recommended_parts': recommended_parts_qs,
                    'recommended_pests': recommended_pests_qs,
                    'recommended_diseases': recommended_diseases_qs,
                    'current_stage_name': current_stage_name
                }
                return render(request, 'core/record_surveillance.html', context)
            
            # Check if pests or diseases were found for appropriate messaging
            pests_found_count = record.pests_found.count()
            diseases_found_count = record.diseases_found.count()
            
            if pests_found_count > 0 or diseases_found_count > 0:
                msg = f"Surveillance recorded."
                if pests_found_count > 0:
                    msg += f" {pests_found_count} pest(s) found."
                if diseases_found_count > 0:
                     msg += f" {diseases_found_count} disease(s) found."
                msg += " Consider treatment options."
                messages.warning(request, msg)
            else:
                messages.success(request, "Surveillance recorded successfully. No pests or diseases found.")
                
            return redirect('core:farm_detail', farm_id=farm.id)
    else: # GET request
        # Check if we have a saved calculation to use for initial plants value
        initial_data = {}
        try:
            saved_calculation = SurveillanceCalculation.objects.filter(
                farm=farm,
                is_current=True
            ).latest('date_created') # Use latest()
            initial_data['plants_surveyed'] = saved_calculation.required_plants
            print(f"Record View: Using saved calculation plants: {saved_calculation.required_plants}")
        except SurveillanceCalculation.DoesNotExist:
            # No saved calculation found, calculate using default confidence and current stage prevalence
            print(f"Record View: No saved calculation. Calculating fallback...")
            if current_prevalence_p is not None and farm.total_plants() is not None:
                 try:
                    calculation = calculate_surveillance_effort(
                        farm=farm, 
                        confidence_level_percent=DEFAULT_CONFIDENCE, # Use default 95%
                        prevalence_p=current_prevalence_p
                    )
                    if not calculation.get('error'):
                        initial_data['plants_surveyed'] = calculation.get('required_plants_to_survey')
                        print(f"Record View: Calculated fallback plants: {initial_data['plants_surveyed']}")
                    else:
                        print(f"Record View: Fallback calculation error: {calculation.get('error')}")
                 except Exception as calc_err:
                      print(f"Record View: Error during fallback calculation: {calc_err}")      
            else:
                print(f"Record View: Cannot calculate fallback (prevalence={current_prevalence_p}, total_plants={farm.total_plants()})")
                    
        except Exception as e:
            # If anything else goes wrong, initialize without plants_surveyed
            print(f"Record View: Error fetching saved calculation or calculating fallback: {e}")
            initial_data = {}
            
        form = SurveillanceRecordForm(farm=farm, initial=initial_data)
    
    # Pass recommendations to the template context
    context = {
        'form': form,
        'farm': farm,
        'recommended_parts': recommended_parts_qs,
        'recommended_pests': recommended_pests_qs,
        'recommended_diseases': recommended_diseases_qs,
        'current_stage_name': current_stage_name
    }
    
    return render(request, 'core/record_surveillance.html', context)


@login_required
def profile_view(request):
    """Handle user profile editing."""
    user_form = UserEditForm(instance=request.user)
    grower_profile = get_object_or_404(Grower, user=request.user)
    profile_form = GrowerProfileEditForm(instance=grower_profile)

    if request.method == 'POST':
        user_form = UserEditForm(request.POST, instance=request.user)
        profile_form = GrowerProfileEditForm(request.POST, instance=grower_profile)
        
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, 'Your profile was successfully updated!')
            return redirect('core:profile')
        else:
            messages.error(request, 'Please correct the errors below.')

    context = {
        'user_form': user_form,
        'profile_form': profile_form
    }
    
    return render(request, 'core/profile.html', context)


@login_required
def record_list_view(request):
    """Display all completed survey sessions for the user, grouped by farm."""
    grower = request.user.grower_profile

    # Get all completed survey sessions
    completed_sessions = SurveySession.objects.filter(
        farm__owner=grower,
        status='completed'
    ).select_related('farm', 'surveyor').order_by('-end_time')

    # Group sessions by farm
    from itertools import groupby
    from django.db.models import Count, Q

    # Get farms with session counts
    farms = Farm.objects.filter(owner=grower).annotate(
        session_count=Count('survey_sessions', filter=Q(survey_sessions__status='completed')),
        pest_count=Count('survey_sessions__observations__pests_observed',
                        filter=Q(survey_sessions__status='completed'),
                        distinct=True)
    ).order_by('name')

    # Group sessions by farm
    sessions_by_farm = {}
    for farm in farms:
        if farm.session_count > 0:
            farm_sessions = completed_sessions.filter(farm=farm)
            sessions_by_farm[farm] = farm_sessions

    context = {
        'farms': farms,
        'sessions_by_farm': sessions_by_farm,
        'completed_sessions': completed_sessions
    }

    return render(request, 'core/record_list.html', context)


@login_required
def dashboard_view(request):
    """Display the user dashboard with summary information."""
    grower = request.user.grower_profile
    farms = get_user_farms(request.user)
    
    # Get counts and summary information
    surveillance_count = grower.surveillance_records.count()
    latest_record = grower.surveillance_records.order_by('-date_performed').first()
    total_plants = grower.total_plants_managed()
    
    # Get recent records
    recent_records = grower.surveillance_records.order_by('-date_performed')[:5]
    
    # Get farms due for surveillance (simple calculation - needs improvement)
    today = timezone.now().date()
    week_ago = today - timezone.timedelta(days=7)
    
    # Get farms that haven't been checked in the last 7 days
    due_farms = []
    for farm in farms:
        last_date = farm.last_surveillance_date()
        if not last_date or last_date.date() < week_ago:
            due_farms.append(farm)
    
    due_farms_count = len(due_farms)
    
    # Get current season information from the database
    seasonal_info = get_seasonal_stage_info()
    current_season = seasonal_info['stage_name'] if seasonal_info['stage_name'] else 'Unknown'
    
    # Get the month ranges for the current season
    month_used = seasonal_info['month_used']
    
    # Create a label based on the seasonal stage data
    month_names = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
    season_label = f"Current month: {month_names[month_used-1]}"
    
    context = {
        'grower': grower,
        'surveillance_count': surveillance_count,
        'latest_record': latest_record,
        'total_plants': total_plants,
        'recent_records': recent_records,
        'due_farms': due_farms,
        'due_farms_count': due_farms_count,
        'current_season': current_season,
        'season_label': season_label,
        'seasonal_info': seasonal_info  # Pass the full seasonal info to the template
    }
    
    return render(request, 'core/dashboard.html', context)


@login_required
def address_suggestion_view(request):
    """Handle address suggestion API requests."""
    # Check if debug mode is requested
    if 'debug' in request.GET:
        debug_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Address API Debug</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                pre { background: #f5f5f5; padding: 15px; border-radius: 5px; }
                .success { color: green; }
                .error { color: red; }
            </style>
        </head>
        <body>
            <h1>Address API Debug Page</h1>
            
            <h2>Test API directly:</h2>
            <div>
                <input type="text" id="query" value="darwin" style="padding: 5px; width: 200px;">
                <select id="region_id" style="padding: 5px;">
                    <option value="1">Northern Territory</option>
                    <option value="2">Queensland</option>
                    <option value="3">Western Australia</option>
                </select>
                <button onclick="testApi()" style="padding: 5px;">Test API</button>
            </div>
            
            <div id="result" style="margin-top: 20px;"></div>
            
            <script>
                function testApi() {
                    const resultDiv = document.getElementById('result');
                    const query = document.getElementById('query').value;
                    const regionId = document.getElementById('region_id').value;
                    
                    resultDiv.innerHTML = '<p>Testing API...</p>';
                    
                    const url = `?query=${encodeURIComponent(query)}&region_id=${encodeURIComponent(regionId)}`;
                    
                    fetch(url)
                        .then(response => response.json())
                        .then(data => {
                            let html = '<h3>API Response:</h3>';
                            html += `<pre>${JSON.stringify(data, null, 2)}</pre>`;
                            
                            if (data.error) {
                                html += `<p class="error">Error: ${data.error}</p>`;
                            } else if (data.suggestions && data.suggestions.length > 0) {
                                html += `<p class="success">Found ${data.suggestions.length} suggestions:</p>`;
                                html += '<ul>';
                                data.suggestions.forEach(item => {
                                    html += `<li>${item.address}</li>`;
                                });
                                html += '</ul>';
                            } else {
                                html += '<p>No suggestions found.</p>';
                            }
                            
                            resultDiv.innerHTML = html;
                        })
                        .catch(error => {
                            resultDiv.innerHTML = `<p class="error">Error: ${error.message}</p>`;
                        });
                }
            </script>
        </body>
        </html>
        """
        return HttpResponse(debug_html)
    
    # Regular API logic
    query = request.GET.get('query', '')
    region_id = request.GET.get('region_id', None)
    suggestions = []
    error_message = None
    state_territory_used = None

    if not region_id:
        error_message = "Region must be selected first."
    elif query and len(query) >= 3:
        try:
            # Look up the region to get the state abbreviation
            selected_region = Region.objects.get(id=region_id)
            state_territory_used = selected_region.state_abbreviation
            
            if not state_territory_used:
                error_message = f"State/Territory not configured for region: {selected_region.name}."
            else:
                # Use service to search addresses
                suggestions = search_addresses(query, state_territory_used)
                if not suggestions:
                    error_message = "No address suggestions found. Try a different search term."

        except Region.DoesNotExist:
            error_message = "Invalid region selected."
        except Exception as e:
            error_message = "An error occurred while processing the address search."

    # Prepare JSON response
    response_data = {'suggestions': suggestions}
    if error_message:
        response_data['error'] = error_message
    if state_territory_used:
        response_data['state_territory_used'] = state_territory_used
        
    return JsonResponse(response_data)


@login_required
def generate_mapping_link_view(request, farm_id):
    """Generates a unique link and displays it with a QR code for mobile mapping."""
    # Get farm with permission check
    farm, error = get_farm_details(farm_id, request.user)
    if error:
        messages.error(request, error)
        return redirect('core:home')

    # Create token
    token_instance = create_mapping_token(farm)
    
    # Generate URL
    mapping_url = get_mapping_url(request, token_instance)

    context = {
        'farm': farm,
        'mapping_url': mapping_url,
        'expires_at': token_instance.expires_at,
    }
    return render(request, 'core/mapping_link_page.html', context)


@login_required
def map_boundary_corners_view(request, farm_id):
    """DEPRECATED/OLD - Handles manual boundary mapping directly in session."""
    # This view is replaced by the token-based one below
    # You might want to remove it or leave it commented out
    farm, error = get_farm_details(farm_id, request.user)
    if error:
        messages.error(request, error)
        return redirect('core:home')

    messages.warning(request, "This mapping method is deprecated. Please generate a mapping link instead.")
    return redirect('core:farm_detail', farm_id=farm.id)


def map_boundary_via_token_view(request, token):
    """Handles mapping using a unique token, typically on mobile."""
    # Validate token and get farm
    is_valid, farm, error = validate_mapping_token(token)
    
    if not is_valid:
        return render(request, 'core/mapping_error.html', {'error': error})

    if request.method == 'POST':
        boundary_coords_str = request.POST.get('boundary_coordinates')
        if not boundary_coords_str:
            return render(request, 'core/map_boundary_corners.html', {
                'farm': farm,
                'token': token,
                'error_message': "No boundary coordinates received."
            })

        # Save boundary to farm
        success, error_message = save_boundary_to_farm(farm, boundary_coords_str)
        
        if success:
            # Invalidate the token after successful use
            invalidate_token(BoundaryMappingToken.objects.get(token=token))
            
            # Redirect to success page
            return render(request, 'core/mapping_success.html', {'farm_name': farm.name})
        else:
            # If errors occurred, render the mapping page again with an error
            return render(request, 'core/map_boundary_corners.html', {
                'farm': farm,
                'token': token,
                'error_message': error_message
            })

    # GET request: Render the mapping template
    context = {
        'farm': farm,
        'token': token,
    }
    return render(request, 'core/map_boundary_corners.html', context)


@login_required
def geoscape_test_view(request):
    """Renders the Geoscape API test page."""
    return render(request, 'core/geoscape_test.html')


@login_required
def start_survey_session_view(request, farm_id):
    """
    Initiates a new survey session for the given farm.
    Checks for existing incomplete sessions (future enhancement).
    Creates a new SurveySession object and redirects to the active session view.
    """
    # Get farm with permission check (using existing service)
    farm, error = get_farm_details(farm_id, request.user)
    if error:
        messages.error(request, error)
        # Redirect to farm list or dashboard if farm access fails
        return redirect('core:myfarms') 

    # TODO: Check for existing 'in_progress' sessions for this farm/user
    # existing_session = SurveySession.objects.filter(
    #     farm=farm, 
    #     surveyor=request.user, 
    #     status='in_progress' 
    # ).first()
    # if existing_session:
    #     messages.info(request, f"Resuming existing survey session for {farm.name}.")
    #     # Redirect to the active session view, passing the session ID
    #     return redirect('core:active_survey_session', session_id=existing_session.session_id)

    # Get recommended plant count (target) for this session
    target_plants = None
    try:
        latest_calc = SurveillanceCalculation.objects.filter(farm=farm, is_current=True).latest('date_created')
        target_plants = latest_calc.required_plants
        print(f"StartSession: Found target plants from calculation: {target_plants}")
    except SurveillanceCalculation.DoesNotExist:
        print(f"StartSession: No current calculation found for farm {farm.id}. Target plants will be None.")
        # Optionally, calculate on the fly here if needed
    except Exception as e:
        print(f"StartSession: Error fetching calculation for farm {farm.id}: {e}")

    # Create a new session
    try:
        new_session = SurveySession.objects.create(
            farm=farm,
            surveyor=request.user,
            status='in_progress', # Start immediately as in progress
            start_time=timezone.now(),
            target_plants_surveyed=target_plants
        )
        messages.success(request, f"New survey session started for {farm.name}.")
        print(f"StartSession: Created new session {new_session.session_id} for farm {farm.id}")
        
        # Redirect to the actual active session view using the created session_id
        return redirect('core:active_survey_session', session_id=new_session.session_id)
        # messages.info(request, "Redirecting to active session page (placeholder). Session ID: {}".format(new_session.session_id))
        # # TEMPORARY Redirect back to farm detail until active session page exists
        # return redirect('core:farm_detail', farm_id=farm.id) 

    except Exception as e:
        messages.error(request, f"Could not start a new survey session: {e}")
        print(f"StartSession: Error creating SurveySession for farm {farm.id}: {e}")
        return redirect('core:farm_detail', farm_id=farm.id)


@login_required
def active_survey_session_view(request, session_id):
    """
    Displays the main interface for an active survey session.
    
    Features:
    - Handles recording of individual observations via AJAX
    - Redirects desktop users to a QR code page for mobile use
    - Loads draft observation data if available
    - Provides seasonally-appropriate pest/disease recommendations
    
    Args:
        request: HTTP request object
        session_id: UUID of the survey session
        
    Returns:
        Rendered template response with session data and form
    """
    # Get session and verify ownership
    session = get_object_or_404(SurveySession, session_id=session_id, surveyor=request.user)
    farm = session.farm

    # Mobile device detection
    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    mobile_indicators = ['mobile', 'android', 'iphone', 'ipad', 'tablet']
    is_mobile = any(indicator in user_agent for indicator in mobile_indicators)
    force_desktop = request.GET.get('force_desktop', 'false').lower() == 'true'

    # Redirect desktop users to QR code page unless override is set
    if not is_mobile and not force_desktop:
        # Generate QR code for the session URL
        session_url = request.build_absolute_uri(request.path)
        qr_image_base64 = None
        
        # Generate QR code with error handling
        try:
            qr_img = qrcode.make(session_url)
            buffer = io.BytesIO()
            qr_img.save(buffer, format='PNG')
            qr_image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        except Exception as e:
            import logging
            logging.error(f"QR code generation failed: {e}")
            messages.error(request, "Could not generate QR code for mobile access. Please use the direct link instead.")

        # Render desktop redirect template with QR code
        return render(request, 'core/desktop_redirect_qr.html', {
            'farm_name': farm.name,
            'session_url': session_url,
            'qr_image_base64': qr_image_base64,
            'session_id': session_id,
            'message': "This survey session requires GPS and should be run on a mobile device. Please scan the QR code or use the link on your mobile."
        })

    # Get seasonal recommendations
    stage_info = get_seasonal_stage_info()
    
    # Retrieve recommended pests, diseases and plant parts for this season
    pest_names = stage_info.get('pest_names', [])
    disease_names = stage_info.get('disease_names', [])
    part_names = stage_info.get('part_names', [])
    current_stage_name = stage_info.get('stage_name', 'Unknown')
    
    # Fetch all required objects in batch queries
    recommended_pests = Pest.objects.filter(name__in=pest_names)
    recommended_diseases = Disease.objects.filter(name__in=disease_names)
    recommended_parts = PlantPart.objects.filter(name__in=part_names)

    # Load completed observations and draft data
    observations = Observation.objects.filter(
        session=session, 
        status='completed'
    ).select_related().order_by('-observation_time')
    
    latest_draft = Observation.objects.filter(
        session=session, 
        status='draft'
    ).order_by('-observation_time').first()
    
    # Prepare draft data for frontend if it exists
    draft_data_json = '{}'
    if latest_draft:
        draft_data = {
            'id': latest_draft.id,
            'latitude': str(latest_draft.latitude) if latest_draft.latitude else None,
            'longitude': str(latest_draft.longitude) if latest_draft.longitude else None,
            'gps_accuracy': str(latest_draft.gps_accuracy) if latest_draft.gps_accuracy else None,
            'pests_observed': list(latest_draft.pests_observed.values_list('id', flat=True)),
            'diseases_observed': list(latest_draft.diseases_observed.values_list('id', flat=True)),
            'notes': latest_draft.notes or '',
            'plant_sequence_number': latest_draft.plant_sequence_number or '',
        }
        draft_data_json = json.dumps(draft_data)

    # Calculate progress statistics
    observation_count = observations.count()
    target_plants = session.target_plants_surveyed or 0
    
    # Handle division by zero safely
    try:
        progress_percent = int((observation_count / target_plants) * 100) if target_plants > 0 else 0
        # Ensure percentage is within valid range
        progress_percent = min(max(progress_percent, 0), 100)
    except (ZeroDivisionError, TypeError):
        progress_percent = 0

    # Calculate unique pest and disease counts for this session
    unique_pests_count = Pest.objects.filter(observations__in=observations).distinct().count()
    unique_diseases_count = Disease.objects.filter(observations__in=observations).distinct().count()
    
    # Prepare view context
    context = {
        'session': session,
        'farm': farm,
        'observations': observations,
        'form': ObservationForm(),  # Empty form - will be populated by JavaScript
        'observation_count': observation_count,
        'completed_plants': observation_count,
        'target_plants': target_plants,
        'progress_percent': progress_percent,
        'unique_pests_count': unique_pests_count,
        'unique_diseases_count': unique_diseases_count,
        'recommended_pests_ids': [p.id for p in recommended_pests],
        'recommended_diseases_ids': [d.id for d in recommended_diseases],
        'recommended_pests': recommended_pests,
        'recommended_diseases': recommended_diseases,
        'recommended_parts': recommended_parts,
        'current_stage_name': current_stage_name,
        'latest_draft_json': draft_data_json,
    }
    
    return render(request, 'core/active_survey_session.html', context)


@csrf_exempt
@require_POST
@login_required
def auto_save_observation_api(request):
    """
    API endpoint to handle AJAX submission for auto-saving draft observations.
    
    This endpoint finds or creates a draft observation and updates its fields.
    It does NOT finalize the observation (status remains 'draft').
    
    Args:
        request: HTTP request with observation data in POST params
        
    Returns:
        JsonResponse with success/error status and observation info
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # Extract data from request
        session_id = request.POST.get('session_id')
        draft_id = request.POST.get('draft_id') 
        latitude = request.POST.get('latitude')
        longitude = request.POST.get('longitude')
        gps_accuracy = request.POST.get('gps_accuracy')
        pest_ids = request.POST.getlist('pests_observed')
        disease_ids = request.POST.getlist('diseases_observed')
        notes = request.POST.get('notes', '')
        plant_seq_str = request.POST.get('plant_sequence_number', '')

        # Validate required fields
        if not session_id:
            return JsonResponse({
                'status': 'error', 
                'message': 'Session ID is required.'
            }, status=400)

        # Get session and verify ownership
        try:
            session = SurveySession.objects.get(session_id=session_id, surveyor=request.user)
            if not session.is_active():
                return JsonResponse({
                    'status': 'error',
                    'message': 'This survey session is no longer active.'
                }, status=400)
        except SurveySession.DoesNotExist:
            logger.warning(f"User {request.user.username} attempted to access non-existent session {session_id}")
            return JsonResponse({
                'status': 'error', 
                'message': 'Survey session not found.'
            }, status=404)

        # Convert plant sequence number safely
        plant_sequence_number = None
        if plant_seq_str:
            try:
                plant_sequence_number = int(plant_seq_str)
            except (ValueError, TypeError):
                logger.debug(f"Invalid plant sequence number provided: {plant_seq_str}")
                # Ignore invalid input for drafts

        # Find existing draft or create a new one
        observation = None
        if draft_id:
            try:
                observation = Observation.objects.drafts().get(id=draft_id, session=session)
                logger.debug(f"Found existing draft observation {draft_id} for session {session_id}")
            except Observation.DoesNotExist:
                logger.info(
                    f"Draft observation {draft_id} not found for session {session_id}, will create new"
                )
                # If ID is invalid/mismatched, we'll create a new one

        # Create new observation if no valid draft found
        if not observation:
            observation = Observation(session=session, status='draft')
            logger.debug(f"Creating new draft observation for session {session_id}")

        # Update fields
        try:
            observation.latitude = Decimal(latitude) if latitude else None
            observation.longitude = Decimal(longitude) if longitude else None
            observation.gps_accuracy = Decimal(gps_accuracy) if gps_accuracy else None
            observation.notes = notes
            observation.plant_sequence_number = plant_sequence_number
            observation.observation_time = timezone.now()  # Update timestamp on each save

            # Save to generate ID if new
            observation.save()

            # Update many-to-many relationships
            observation.pests_observed.set(Pest.objects.filter(id__in=pest_ids) if pest_ids else [])
            observation.diseases_observed.set(Disease.objects.filter(id__in=disease_ids) if disease_ids else [])
            
            # Update session status if needed
            if session.status == 'not_started':
                session.status = 'in_progress'
                session.save(update_fields=['status'])

            return JsonResponse({
                'status': 'success', 
                'message': 'Draft saved successfully.', 
                'draft_id': observation.id,
                'has_coordinates': observation.has_coordinates(),
                'has_pests': observation.has_pests(),
                'has_diseases': observation.has_diseases()
            })
        except Exception as field_error:
            logger.error(f"Error saving observation fields: {field_error}", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': 'Error saving observation data.'
            }, status=500)

    except Exception as e:
        # Log the exception for debugging but don't expose details to client
        logger.error(f"Error in auto_save_observation_api: {e}", exc_info=True)
        return JsonResponse({
            'status': 'error', 
            'message': 'An unexpected error occurred.'
        }, status=500)


@csrf_exempt
@require_POST
@login_required
def create_observation_api(request):
    """
    API endpoint to handle AJAX submission of a new observation or finalize a draft.
    
    This endpoint creates a completed observation or finalizes an existing draft.
    It also handles image uploads and automatically updates session status as needed.
    
    Features:
    - Sets observation status to 'completed'
    - Handles multiple image uploads
    - Auto-assigns plant sequence numbers if not provided
    - Updates session status from 'not_started' to 'in_progress' if needed
    
    Args:
        request: HTTP request with observation data in POST params
        
    Returns:
        JsonResponse with success/error status and observation info
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # Extract data from request
        session_id = request.POST.get('session_id')
        draft_id = request.POST.get('draft_id')

        # Validate required fields
        if not session_id:
            return JsonResponse({
                'status': 'error', 
                'message': 'Session ID is required.'
            }, status=400)

        # Get session and verify ownership
        try:
            session = SurveySession.objects.get(session_id=session_id, surveyor=request.user)
            if not session.is_active():
                return JsonResponse({
                    'status': 'error',
                    'message': 'This survey session is no longer active.'
                }, status=400)
        except SurveySession.DoesNotExist:
            logger.warning(f"User {request.user.username} attempted to access non-existent session {session_id}")
            return JsonResponse({
                'status': 'error',
                'message': 'Survey session not found.'
            }, status=404)

        # Extract observation data
        pest_ids = request.POST.getlist('pests_observed')
        disease_ids = request.POST.getlist('diseases_observed')
        notes = request.POST.get('notes', '')
        plant_seq_str = request.POST.get('plant_sequence_number', '')
        latitude = request.POST.get('latitude')
        longitude = request.POST.get('longitude')
        gps_accuracy = request.POST.get('gps_accuracy')

        # Process plant sequence number
        plant_sequence_number = None
        if plant_seq_str:
            try:
                plant_sequence_number = int(plant_seq_str)
            except (ValueError, TypeError):
                logger.debug(f"Invalid plant sequence number provided: {plant_seq_str}")

        # Auto-assign sequence number if not provided
        if not plant_sequence_number:
            # Use the custom manager to get the highest sequence number
            latest_observations = Observation.objects.filter(session=session).order_by('-plant_sequence_number')
            max_sequence = latest_observations[0].plant_sequence_number if latest_observations.exists() else 0
            plant_sequence_number = max_sequence + 1
            logger.debug(f"Auto-assigned plant sequence number {plant_sequence_number} for session {session_id}")

        # Find draft observation or create new one
        try:
            if draft_id:
                observation = Observation.objects.drafts().get(id=draft_id, session=session)
                logger.debug(f"Found draft observation {draft_id} to finalize")
            else:
                observation = Observation(session=session)
                logger.debug(f"Creating new observation for session {session_id}")
                
            # Update observation fields
            observation.latitude = Decimal(latitude) if latitude else None
            observation.longitude = Decimal(longitude) if longitude else None
            observation.gps_accuracy = Decimal(gps_accuracy) if gps_accuracy else None
            observation.notes = notes
            observation.plant_sequence_number = plant_sequence_number
            observation.observation_time = timezone.now()
            
            # Use our custom finalize method
            observation.finalize(save=True)
            
            # Update many-to-many relationships
            observation.pests_observed.set(Pest.objects.filter(id__in=pest_ids) if pest_ids else [])
            observation.diseases_observed.set(Disease.objects.filter(id__in=disease_ids) if disease_ids else [])
            
            # Update session status if needed
            if session.status == 'not_started':
                session.status = 'in_progress'
                session.save(update_fields=['status'])
                logger.info(f"Updated session {session_id} status to 'in_progress'")
            
            # Process image uploads
            files = request.FILES.getlist('images')
            image_ids = []
            
            for img_file in files:
                try:
                    image = ObservationImage(observation=observation, image=img_file)
                    image.save()
                    image_ids.append(image.id)
                    logger.debug(f"Saved image for observation {observation.id}")
                except Exception as img_error:
                    logger.error(f"Error saving image: {img_error}", exc_info=True)
                    # Continue processing other images if one fails
            
            # Build response with observation data
            return JsonResponse({
                'status': 'success',
                'message': 'Observation saved successfully.',
                'observation_id': observation.id,
                'image_ids': image_ids,
                'plant_number': plant_sequence_number,
                'progress_percent': session.get_progress_percentage(),
                'observation_count': session.observation_count()
            })
            
        except Observation.DoesNotExist:
            logger.warning(f"Draft observation {draft_id} not found for session {session_id}")
            return JsonResponse({
                'status': 'error',
                'message': 'Draft observation not found.'
            }, status=404)
        except Exception as obs_error:
            logger.error(f"Error processing observation: {obs_error}", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': 'Error processing observation data.'
            }, status=500)
            
    except Exception as e:
        logger.error(f"Error in create_observation_api: {e}", exc_info=True)
        return JsonResponse({
            'status': 'error', 
            'message': 'An unexpected error occurred.'
        }, status=500)


@csrf_exempt
@require_POST
@login_required
def finish_survey_session_api(request, session_id):
    """
    API endpoint to mark a survey session as completed.
    
    This endpoint finalizes a survey session by marking it as completed,
    recording the end time, and cleaning up any draft observations.
    
    Features:
    - Validates that the session has at least one completed observation
    - Deletes any remaining draft observations
    - Updates session status and end time
    - Returns redirection URL to the session detail page
    
    Args:
        request: HTTP request
        session_id: UUID of the survey session to complete
        
    Returns:
        JsonResponse with success/error status and session info
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # Get the session and verify ownership
        try:
            session = SurveySession.objects.get(session_id=session_id, surveyor=request.user)
            logger.info(f"Processing completion request for session {session_id} by {request.user.username}")
        except SurveySession.DoesNotExist:
            logger.warning(f"User {request.user.username} attempted to complete non-existent session {session_id}")
            return JsonResponse({
                'status': 'error', 
                'message': 'Survey session not found.'
            }, status=404)
        
        # Check if the session can be completed (not already completed or abandoned)
        if not session.is_active():
            logger.warning(
                f"Cannot complete session {session_id} with status '{session.status}'"
            )
            return JsonResponse({
                'status': 'error', 
                'message': f'Session is already marked as {session.status}.'
            }, status=400)
            
        # Count completed observations using our custom manager
        completed_observations = Observation.objects.completed().filter(session=session).count()
        if completed_observations == 0:
            logger.warning(f"Attempted to complete session {session_id} with no observations")
            return JsonResponse({
                'status': 'error', 
                'message': 'Cannot complete session with no observations.'
            }, status=400)
            
        # Update the session status and end time
        session.status = 'completed'
        session.end_time = timezone.now()
        session.save(update_fields=['status', 'end_time'])
        logger.info(f"Marked session {session_id} as completed with {completed_observations} observations")
        
        # Delete any draft observations using our custom manager
        draft_observations = Observation.objects.drafts().filter(session=session)
        draft_count = draft_observations.count()
        if draft_count > 0:
            logger.info(f"Deleting {draft_count} draft observations from session {session_id}")
            draft_observations.delete()
        
        # Generate summary info
        unique_pests_count = session.get_unique_pests().count()
        unique_diseases_count = session.get_unique_diseases().count()
        
        # Calculate duration if available
        duration_minutes = session.duration()
        
        # Return success response with redirection URL and additional info
        redirect_url = reverse('core:survey_session_detail', kwargs={'session_id': session_id})
        return JsonResponse({
            'status': 'success',
            'message': 'Survey session completed successfully.',
            'redirect_url': redirect_url,
            'completed_observations': completed_observations,
            'unique_pests_count': unique_pests_count,
            'unique_diseases_count': unique_diseases_count,
            'duration_minutes': duration_minutes,
            'session_summary': session.summarize()
        })
        
    except Exception as e:
        logger.error(f"Error in finish_survey_session_api: {e}", exc_info=True)
        return JsonResponse({
            'status': 'error', 
            'message': 'An unexpected error occurred.'
        }, status=500)


@login_required
def survey_session_list_view(request, farm_id):
    """
    Displays a list of all survey sessions for a specific farm.
    """
    # Get farm with permission check (reuse existing service if applicable, or basic check)
    try:
        farm = get_object_or_404(Farm, id=farm_id, owner=request.user.grower_profile)
    except Http404:
        messages.error(request, "Farm not found or you do not have permission to view it.")
        return redirect('core:myfarms')

    # Fetch survey sessions for this farm, ordered by start time (newest first)
    # Add annotation for observation count
    sessions = SurveySession.objects.filter(farm=farm).annotate(
        observation_count=Count('observations')
    ).order_by('-start_time')

    context = {
        'farm': farm,
        'sessions': sessions,
    }
    return render(request, 'core/survey_session_list.html', context)


@login_required
def generate_test_observation_data(farm_id):
    """
    Generate test observation data for demonstration purposes.
    
    Args:
        farm_id: ID of the farm to generate test data for
        
    Returns:
        tuple: (observation_coords, all_pests, all_diseases, farm_boundary_json)
    """
    # Only generate test data for farm with ID 1 or if special debug flag exists
    all_pests = set()
    all_diseases = set()
    
    # Generate test farm boundary (simple rectangle for farm 1)
    farm_boundary_json = {
        "type": "Feature",
        "properties": {
            "name": "Test Farm Boundary"
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [130.83916495, -12.46017243],
                    [130.83941962, -12.46041745],
                    [130.83957579, -12.46026002],
                    [130.83932478, -12.46001226],
                    [130.83916495, -12.46017243]  # Close the polygon by repeating first point
                ]
            ]
        }
    }
    
    # Create a function to generate points within the farm boundary polygon
    def generate_point_within_polygon():
        # Define exact corner points of our farm polygon
        polygon_coords = [
            [-12.46017243, 130.83916495],
            [-12.46041745, 130.83941962],
            [-12.46026002, 130.83957579],
            [-12.46001226, 130.83932478],
            [-12.46017243, 130.83916495]
        ]
        
        # Extract min/max bounds
        lats = [pt[0] for pt in polygon_coords]
        lons = [pt[1] for pt in polygon_coords]
        min_lat = min(lats)
        max_lat = max(lats)
        min_lon = min(lons)
        max_lon = max(lons)
        
        # Generate a point with some random noise
        center_lat = (min_lat + max_lat) / 2
        center_lon = (min_lon + max_lon) / 2

        import random
        
        # Use a triangle distribution to bias points toward center
        def triangle_random():
            # Returns values biased toward 0.5 (triangle distribution)
            return (random.random() + random.random()) / 2
        
        # Generate random coordinates with bias toward center
        lat_range = (max_lat - min_lat) * 0.6  # Reduced range for clustering
        lon_range = (max_lon - min_lon) * 0.6
        
        # Generate point biased toward center
        lat = center_lat + (triangle_random() - 0.5) * lat_range
        lon = center_lon + (triangle_random() - 0.5) * lon_range
        
        return lat, lon
    
    # Generate test observation data
    observation_coords = []
    times = ["10:15 AM", "10:20 AM", "10:25 AM", "10:30 AM", "10:35 AM",
             "10:40 AM", "10:45 AM", "10:50 AM", "10:55 AM", "11:00 AM",
             "11:05 AM", "11:10 AM", "11:15 AM", "11:20 AM", "11:25 AM",
             "11:30 AM", "11:35 AM", "11:40 AM", "11:45 AM", "11:50 AM"]
    
    # Define pests and diseases for our observations - using mango-specific ones
    pest_options = ["Mango Leaf Hopper", "Mango Tip Borer", "Mango Fruit Fly", 
                  "Mango Scale Insect", "Mango Seed Weevil"]
    disease_options = ["Anthracnose", "Powdery Mildew", "Stem End Rot", 
                     "Mango Malformation", "Bacterial Black Spot"]
    
    # Create observations with proper coordinates
    import random
    for i, time in enumerate(times):
        # Generate point within polygon
        lat, lon = generate_point_within_polygon()
        
        # Randomly assign pests and diseases
        pest_count = random.randint(0, 2)  # 0-2 pests per observation
        disease_count = random.randint(0, 1)  # 0-1 diseases per observation
        
        pests = random.sample(pest_options, pest_count) if pest_count > 0 else []
        diseases = random.sample(disease_options, disease_count) if disease_count > 0 else []
        
        # Create the observation data
        observation_coords.append({
            "lat": lat,
            "lon": lon,
            "time": time,
            "pests": pests,
            "diseases": diseases,
            "has_image": random.choice([True, False])
        })
    
    # Extract unique pests and diseases
    for obs in observation_coords:
        for pest in obs['pests']:
            all_pests.add(pest)
        for disease in obs['diseases']:
            all_diseases.add(disease)
            
    return observation_coords, all_pests, all_diseases, farm_boundary_json


def survey_session_detail_view(request, session_id):
    """
    Displays the details of a completed or abandoned survey session.
    
    Features:
    - Shows all observations recorded during the session
    - Displays a map with observation locations
    - Shows statistics on pests and diseases found
    - Provides test data for demonstration purposes when needed
    
    Args:
        request: HTTP request object
        session_id: UUID of the survey session
        
    Returns:
        Rendered template with session details
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # Fetch the session, prefetching related data for efficiency
        session = get_object_or_404(
            SurveySession.objects.select_related('farm', 'surveyor'), 
            session_id=session_id
        )
        logger.info(f"Fetched session {session.session_id} for farm '{session.farm.name}'")
        
        # --- Permission Check --- 
        # Ensure the logged-in user is the surveyor (or potentially admin in future)
        if session.surveyor != request.user:
            messages.error(request, "You do not have permission to view this survey session.")
            logger.warning(
                f"Permission denied for user {request.user.username} on session {session.session_id}"
            )
            return redirect('core:survey_session_list', farm_id=session.farm.id) 
    except Http404:
        messages.error(request, "Survey session not found.")
        logger.warning(f"SurveySession with ID {session_id} not found")
        return redirect('core:dashboard') 
    except Exception as e:
        messages.error(request, f"An error occurred accessing the survey session: {e}")
        logger.error(f"Error fetching session {session_id}: {e}", exc_info=True)
        return redirect('core:dashboard')

    # --- Fetch Observations with related data --- 
    observations = Observation.objects.filter(session=session).prefetch_related(
        'pests_observed', 
        'diseases_observed', 
        'images'
    ).order_by('observation_time')
    
    # --- Determine if we need test data ---
    use_test_data = session.farm.id == 1 and not observations.exists()
    
    # --- Process observations or generate test data ---
    observation_coords = []
    all_pests = set()
    all_diseases = set()
    
    if use_test_data:
        # Generate test data for demo purposes
        try:
            farm_boundary_json, observation_coords = generate_test_observation_data(session.farm.id)
            
            # Extract unique pests and diseases for stats
            for obs in observation_coords:
                all_pests.update(obs['pests'])
                all_diseases.update(obs['diseases'])
        except Exception as e:
            logger.error(f"Error generating test data: {e}", exc_info=True)
            use_test_data = False
    else:
        # Process actual observation data
        observation_coords = []
        for obs in observations:
            if obs.has_coordinates():
                observation_coords.append({
                    'lat': float(obs.latitude), 
                    'lon': float(obs.longitude),
                    'time': obs.observation_time.strftime('%I:%M %p'),
                    'pests': [p.name for p in obs.pests_observed.all()],
                    'diseases': [d.name for d in obs.diseases_observed.all()],
                    'has_image': obs.has_images()
                })
    
    # Serialize observation coordinates for the map
    observation_coords_json = json.dumps(observation_coords)

    # --- Calculate stats and prepare context data ---
    if use_test_data:
        # For test data, create mock objects
        completed_count = len(observation_coords)
        observations, unique_pests, unique_diseases = create_mock_observations(
            observation_coords, all_pests, all_diseases
        )
    else:
        # For real data, use database queries
        completed_count = observations.count()
        unique_pests = Pest.objects.filter(observations__session=session).distinct()
        unique_diseases = Disease.objects.filter(observations__session=session).distinct()

    # --- Process farm boundary data ---
    farm_boundary_json = session.farm.boundary if session.farm.boundary else None
    
    if use_test_data and farm_boundary_json:
        # For test data, convert dict to JSON string
        farm_boundary_json_str = json.dumps(farm_boundary_json)
    else:
        # For real data, the boundary is already a JSON string
        farm_boundary_json_str = farm_boundary_json
    
    # --- Prepare context for template ---
    context = {
        'session': session,
        'farm': session.farm,
        'observations': observations,
        'completed_count': completed_count,
        'unique_pests_count': unique_pests.count(),
        'unique_diseases_count': unique_diseases.count(),
        'unique_pests': unique_pests,
        'unique_diseases': unique_diseases,
        'observation_coords_json': observation_coords_json,
        'farm_boundary_json': farm_boundary_json_str,
        'using_test_data': use_test_data
    }

    return render(request, 'core/survey_session_detail.html', context)


def generate_test_observation_data(farm_id):
    """
    Generate test observation data for demonstration purposes.
    
    Args:
        farm_id: ID of the farm to generate test data for
        
    Returns:
        tuple: (farm_boundary_json, observation_coords)
    """
    import random
    from datetime import datetime
    
    # Use hardcoded test data for farm boundary in proper GeoJSON format
    farm_boundary_json = {
        "type": "Feature",
        "properties": {},
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [130.83916495, -12.46017243],
                    [130.83941962, -12.46041745],
                    [130.83957579, -12.46026002],
                    [130.83932478, -12.46001226],
                    [130.83916495, -12.46017243]  # Close the polygon
                ]
            ]
        }
    }
    
    # Define polygon coordinates for point generation
    polygon_coords = [
        [-12.46017243, 130.83916495],
        [-12.46041745, 130.83941962],
        [-12.46026002, 130.83957579],
        [-12.46001226, 130.83932478],
        [-12.46017243, 130.83916495]
    ]
    
    # Extract min/max bounds
    lats = [pt[0] for pt in polygon_coords]
    lons = [pt[1] for pt in polygon_coords]
    min_lat = min(lats)
    max_lat = max(lats)
    min_lon = min(lons)
    max_lon = max(lons)
    center_lat = (min_lat + max_lat) / 2
    center_lon = (min_lon + max_lon) / 2
    
    # Sample observation times
    times = ["10:15 AM", "10:20 AM", "10:25 AM", "10:30 AM", "10:35 AM",
             "10:40 AM", "10:45 AM", "10:50 AM", "10:55 AM", "11:00 AM",
             "11:05 AM", "11:10 AM", "11:15 AM", "11:20 AM", "11:25 AM",
             "11:30 AM", "11:35 AM", "11:40 AM", "11:45 AM", "11:50 AM"]
    
    # Mango-specific pests and diseases
    pest_options = ["Mango Leaf Hopper", "Mango Tip Borer", "Mango Fruit Fly", 
                   "Mango Scale Insect", "Mango Seed Weevil"]
    disease_options = ["Anthracnose", "Powdery Mildew", "Stem End Rot", 
                      "Mango Malformation", "Bacterial Black Spot"]
    
    observation_coords = []
    
    # Generate test observations
    for time in times:
        # Generate point with bias toward center
        lat_range = (max_lat - min_lat) * 0.6  # Reduced range for tighter clustering
        lon_range = (max_lon - min_lon) * 0.6
        
        # Use triangle distribution for more realistic point clustering
        triangle_random = lambda: (random.random() + random.random()) / 2
        
        lat = center_lat + (triangle_random() - 0.5) * lat_range
        lon = center_lon + (triangle_random() - 0.5) * lon_range
        
        # Randomly assign pests and diseases
        pest_count = random.randint(0, 2)  # 0-2 pests per observation
        disease_count = random.randint(0, 1)  # 0-1 diseases per observation
        
        pests = random.sample(pest_options, pest_count) if pest_count > 0 else []
        diseases = random.sample(disease_options, disease_count) if disease_count > 0 else []
        
        # Create the observation data
        observation_coords.append({
            "lat": lat,
            "lon": lon,
            "time": time,
            "pests": pests,
            "diseases": diseases,
            "has_image": random.choice([True, False])
        })
    
    return farm_boundary_json, observation_coords


def create_mock_observations(observation_coords, all_pests, all_diseases):
    """
    Create mock observation objects for template rendering from test data.
    
    Args:
        observation_coords: List of test observation coordinate dictionaries
        all_pests: Set of all pest names
        all_diseases: Set of all disease names
        
    Returns:
        tuple: (mock_observations, mock_pests, mock_diseases)
    """
    from datetime import datetime
    
    # Create mock classes for test data rendering
    class MockPest:
        def __init__(self, name):
            self.name = name
            
    class MockDisease:
        def __init__(self, name):
            self.name = name
    
    class MockObservation:
        def __init__(self, data):
            self.id = f"mock-{id(data)}"  # Create a unique ID
            try:
                self.observation_time = datetime.strptime(data['time'], '%I:%M %p')
            except (ValueError, TypeError):
                self.observation_time = timezone.now()
            self.latitude = data['lat']
            self.longitude = data['lon']
            self.gps_accuracy = 5.0  # Mock accuracy value
            self.notes = f"Observation at {data['time']}"
            self._pests = data['pests']
            self._diseases = data['diseases']
            self._has_image = data['has_image']
            
        @property
        def pests_observed(self):
            class MockRelation:
                def __init__(self, names):
                    self.names = names
                def all(self):
                    return [MockPest(name) for name in self.names]
            return MockRelation(self._pests)
            
        @property
        def diseases_observed(self):
            class MockRelation:
                def __init__(self, names):
                    self.names = names
                def all(self):
                    return [MockDisease(name) for name in self.names]
            return MockRelation(self._diseases)
            
        @property
        def images(self):
            class MockImages:
                def __init__(self, has_image):
                    self.has_image = has_image
                def exists(self):
                    return self.has_image
                def first(self):
                    if not self.has_image:
                        return None
                    return type('MockImage', (), {'image': type('MockImageField', (), {'url': '/static/img/mock-image.jpg'})})
            return MockImages(self._has_image)
    
    # Create a mock QuerySet class
    class MockQuerySet:
        def __init__(self, items):
            self.items = items
        
        def count(self):
            return len(self.items)
            
        def __iter__(self):
            return iter(self.items)
    
    # Create the mock objects
    mock_observations = [MockObservation(data) for data in observation_coords]
    mock_pests = MockQuerySet([MockPest(name) for name in all_pests])
    mock_diseases = MockQuerySet([MockDisease(name) for name in all_diseases])
    
    return mock_observations, mock_pests, mock_diseases


# --- PDF Generation View Implementation to be added later ---
# @login_required
# def generate_survey_pdf_view(request, session_id):
#     """
#     Generates a PDF report for a specific survey session.
#     """
#     session = get_object_or_404(SurveySession.objects.select_related('farm', 'surveyor'), id=session_id)
#
#     # Basic authorization check
#     if session.farm.owner != request.user.grower_profile:
#         raise Http404("Session not found or you do not have permission.")
#
#     farm = session.farm
#     # Prefetch related data for efficiency
#     observations = session.observations.prefetch_related('pests_observed', 'diseases_observed', 'images').order_by('observation_time')
#     completed_count = observations.count()
#     
#     # Get unique pests/diseases
#     unique_pests = Pest.objects.filter(observation__session=session).distinct()
#     unique_diseases = Disease.objects.filter(observation__session=session).distinct()
#     unique_pests_count = unique_pests.count()
#     unique_diseases_count = unique_diseases.count()
#
#     # --- Helper function to build absolute URIs for images ---
#     # WeasyPrint needs absolute paths for local files/media
#     def build_absolute_uri(path):
#         return request.build_absolute_uri(path)
#
#     # Process observations to include absolute image URLs if needed
#     observations_for_pdf = []
#     for obs in observations:
#         first_image_url = None
#         first_image = obs.images.first()
#         if first_image and hasattr(first_image.image, 'url'):
#             # Construct absolute URL for the image
#             try:
#                 # Ensure media URL is handled correctly
#                  # Check if MEDIA_URL is already absolute
#                 if first_image.image.url.startswith(('http://', 'https://')):
#                     first_image_url = first_image.image.url
#                 else:
#                     # Build absolute URI based on request
#                     first_image_url = build_absolute_uri(first_image.image.url)
#                 print(f"PDF Gen: Image URL for obs {obs.id}: {first_image_url}") # Debug
#             except Exception as e:
#                  print(f"PDF Gen: Error building image URL for obs {obs.id}: {e}") # Debug
#         
#         observations_for_pdf.append({
#             'id': obs.id,
#             'observation_time': obs.observation_time,
#             'latitude': obs.latitude,
#             'longitude': obs.longitude,
#             'gps_accuracy': obs.gps_accuracy,
#             'pests_observed': list(obs.pests_observed.all()), # Pass full objects if needed in template
#             'diseases_observed': list(obs.diseases_observed.all()),
#             'notes': obs.notes,
#             'first_image_absolute_url': first_image_url # Pass absolute URL
#         })
#
#
#     # Prepare context for the PDF template
#     context = {
#         'session': session,
#         'farm': farm,
#         'observations': observations_for_pdf, # Use processed observations
#         'completed_count': completed_count,
#         'unique_pests': unique_pests,
#         'unique_diseases': unique_diseases,
#         'unique_pests_count': unique_pests_count,
#         'unique_diseases_count': unique_diseases_count,
#         # Pass the helper function if needed directly in template (less common)
#         # 'build_absolute_uri': build_absolute_uri 
#     }
#
#     try:
#         # Render the HTML template to a string
#         html_string = render_to_string('core/survey_session_pdf.html', context)
#
#         # --- Use WeasyPrint to generate PDF ---
#         # We need the base URL to resolve relative paths (like CSS if not inline)
#         # For media files, absolute paths are usually better.
#         base_url = request.build_absolute_uri('/') 
#         print(f"PDF Gen: Base URL for WeasyPrint: {base_url}") # Debug
#
#         # Create WeasyPrint HTML object
#         # Pass the base_url to help resolve relative URLs if any exist
#         html = HTML(string=html_string, base_url=base_url) 
#         
#         # Generate PDF bytes
#         pdf_bytes = html.write_pdf()
#         print(f"PDF Gen: PDF generated successfully ({len(pdf_bytes)} bytes)") # Debug
#
#         # Create HTTP response
#         response = HttpResponse(pdf_bytes, content_type='application/pdf')
#         
#         # Suggest a filename for the download
#         filename = f"survey_report_{session.farm.name.replace(' ', '_')}_{session.id}.pdf"
#         response['Content-Disposition'] = f'inline; filename="{filename}"' 
#         # Use 'attachment;' instead of 'inline;' to force download immediately
#
#         return response
#
#     except Exception as e:
#         # Log the error (replace with proper logging in production)
#         print(f"Error generating PDF for session {session.id}: {e}") 
#         messages.error(request, f"Could not generate PDF report. Error: {e}")
#         # Redirect back to the detail page or show an error page
#         return redirect('core:survey_session_detail', session_id=session.id)

# --- End PDF Generation View ---

@login_required
def delete_survey_session_view(request, session_id):
    """
    Deletes an incomplete survey session.

    Only allows deletion of sessions with status 'not_started' or 'in_progress'.
    Completed sessions cannot be deleted as they are part of the historical record.
    """
    # Get session and verify ownership
    session = get_object_or_404(SurveySession, session_id=session_id, surveyor=request.user)
    farm = session.farm

    # Only allow deletion of incomplete sessions
    if session.status not in ['not_started', 'in_progress']:
        messages.error(request, "Only incomplete sessions can be deleted.")
        return redirect('core:survey_session_list', farm_id=farm.id)

    if request.method == 'POST':
        # Keep session details for confirmation message
        start_time = session.start_time
        observation_count = session.observation_count()

        # Delete the session (this will cascade to related observations due to on_delete=models.CASCADE)
        session.delete()

        # Add confirmation message
        messages.success(
            request,
            f"Survey session from {start_time.strftime('%Y-%m-%d')} with {observation_count} observation(s) was deleted."
        )

        # Redirect back to the session list
        return redirect('core:survey_session_list', farm_id=farm.id)

    # If not POST, redirect to session list (shouldn't happen with our implementation)
    return redirect('core:survey_session_list', farm_id=farm.id)

@login_required
def test_heatmap_view(request):
    """A simple test view to demonstrate the heatmap functionality with static data."""
    # Get a random farm if the user has any
    farm = Farm.objects.filter(owner=request.user.grower_profile).first()
    
    if not farm:
        messages.warning(request, "You need at least one farm to test the heatmap.")
        return redirect('core:myfarms')
    
    # Create a mock session object with basic attributes for template rendering
    class MockSession:
        def __init__(self, farm, user):
            self.farm = farm
            self.surveyor = user
            self.session_id = 'test-session'
            self.start_time = timezone.now() - timedelta(hours=2)
            self.end_time = timezone.now() - timedelta(minutes=30)
            self.status = 'completed'
            self.target_plants_surveyed = 20
        
        def get_status_display(self):
            return "Completed"
            
        def get_status_badge_class(self):
            return "success"
            
        @property
        def duration(self):
            return "1 hour 30 minutes"
    
    # Create mock session
    mock_session = MockSession(farm, request.user)
    
    # Create mock pest and disease objects
    class MockItem:
        def __init__(self, name):
            self.name = name
    
    mock_pests = [MockItem(p) for p in ['Mango Leaf Hopper', 'Mango Tip Borer', 'Mango Fruit Fly', 'Mango Scale Insect', 'Mango Seed Weevil']]
    mock_diseases = [MockItem(d) for d in ['Anthracnose', 'Powdery Mildew', 'Stem End Rot', 'Mango Malformation', 'Bacterial Black Spot']]
    
    # Create mock observations
    class MockObservation:
        def __init__(self, time, lat, lon, pests, diseases, has_image=False, notes="Test observation"):
            self.observation_time = time
            self.latitude = lat
            self.longitude = lon
            self.gps_accuracy = 5.0
            self.notes = notes
            self._pests = pests
            self._diseases = diseases
            self.has_image = has_image
        
        class MockRelated:
            def __init__(self, items):
                self.items = items
            def all(self):
                return self.items
            def first(self):
                return None if not self.items else self.items[0]
            def exists(self):
                return bool(self.items)
        
        @property        
        def pests_observed(self):
            return self.MockRelated(self._pests)
            
        @property
        def diseases_observed(self):
            return self.MockRelated(self._diseases)
            
        @property
        def images(self):
            return self.MockRelated([])
    
    # Generate 20 mock observations
    mock_observations = []
    import random
    start_time = timezone.now() - timedelta(hours=2)
    
    for i in range(20):
        obs_time = start_time + timedelta(minutes=i*5)
        obs_pests = random.sample(mock_pests, random.randint(0, 2))
        obs_diseases = random.sample(mock_diseases, random.randint(0, 1))
        has_image = random.choice([True, False])
        
        mock_observations.append(
            MockObservation(
                time=obs_time,
                lat=0,  # These will be ignored since we're using client-side coordinates
                lon=0,  # These will be ignored since we're using client-side coordinates
                pests=obs_pests,
                diseases=obs_diseases,
                has_image=has_image,
                notes=f"Test observation #{i+1}"
            )
        )
    
    # Render the test template with minimal context
    context = {
        'session': mock_session,
        'farm': farm,
        'completed_count': 20,
        'unique_pests_count': len(mock_pests),
        'unique_diseases_count': len(mock_diseases),
        'unique_pests': mock_pests,
        'unique_diseases': mock_diseases,
        'observations': mock_observations
    }
    
    return render(request, 'core/survey_session_detail_test.html', context) 