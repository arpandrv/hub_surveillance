from django.shortcuts import render, redirect, get_object_or_404
from django.http import Http404, JsonResponse, HttpResponse
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count, Q
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
    Farm, PlantType, PlantPart, Pest, SurveillanceRecord, 
    Grower, Region, SurveillanceCalculation, BoundaryMappingToken, Disease, SurveySession, Observation, ObservationImage, User
)

# Import services
from .services.user_service import create_user_with_profile
from .services.farm_service import (
    get_user_farms, get_farm_details, create_farm, 
    update_farm, delete_farm, get_farm_surveillance_records
)
from .services.calculation_service import (
    calculate_surveillance_effort, get_recommended_plant_parts,
    get_surveillance_frequency, save_calculation_to_database
)
from .services.surveillance_service import (
    create_surveillance_record, get_surveillance_recommendations, 
    get_surveillance_stats
)
from .services.geoscape_service import (
    fetch_cadastral_boundary, search_addresses
)
from .services.boundary_service import (
    create_mapping_token, get_mapping_url, validate_mapping_token,
    invalidate_token, save_boundary_to_farm
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
    """Display the user's farms (My Farms page)."""
    farms = get_user_farms(request.user)
    return render(request, 'core/home.html', {'farms': farms})


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
    surveillance_records = farm.surveillance_records.order_by('-date_performed')[:5] # Get latest 5 records
    
    context = {
        'farm': farm,
        'current_stage': current_stage, # Pass stage name
        'month_used_for_stage': month_used_for_stage, # Pass the month used for clarity
        'calculation_results': calculation_results, # Results based on current stage & default confidence
        'surveillance_records': surveillance_records,
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

    context = {
        'form': form,
        'selected_farm': selected_farm_instance,
        'calculation_results': calculation_results,
        'form_submitted': form_submitted,
        'current_stage': current_stage, # Pass stage name (or None)
        # Pass prevalence as percentage, handle None
        'current_prevalence_p': float(current_prevalence_p * 100) if current_prevalence_p is not None else None, 
        'month_used_for_calc': month_used_for_calc # Pass month used
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
    """Display all surveillance records for the user."""
    grower = request.user.grower_profile
    records = SurveillanceRecord.objects.filter(performed_by=grower).order_by('-date_performed')
    
    # Group by farm for summary stats
    farms = Farm.objects.filter(owner=grower).annotate(
        record_count=Count('surveillance_records'),
        pest_count=Count('surveillance_records__pests_found', distinct=True)
    )
    
    context = {
        'records': records,
        'farms': farms
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
    
    # Get current season information
    sample_farm = farms.first()
    current_season = sample_farm.current_season() if sample_farm else 'Wet'
    
    season_labels = {
        'Wet': 'November-April',
        'Dry': 'May-October',
        'Flowering': 'During Dry Season'
    }
    
    context = {
        'grower': grower,
        'surveillance_count': surveillance_count,
        'latest_record': latest_record,
        'total_plants': total_plants,
        'recent_records': recent_records,
        'due_farms': due_farms,
        'due_farms_count': due_farms_count,
        'current_season': current_season,
        'season_label': season_labels.get(current_season, '')
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
    Handles recording of individual observations (via AJAX/future enhancement).
    Redirects desktop users to a QR code page.
    Loads draft observation data if available.
    Passes recommended pests/diseases to template.
    """
    session = get_object_or_404(SurveySession, session_id=session_id, surveyor=request.user)
    farm = session.farm

    # --- Restored Desktop User Redirection Block --- #
    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    is_mobile = 'mobile' in user_agent or 'android' in user_agent or 'iphone' in user_agent
    # --- ADDED Check for force_desktop parameter --- #
    force_desktop_param = request.GET.get('force_desktop', 'false').lower()
    force_desktop = force_desktop_param == 'true'

    # --- MODIFIED Condition to include force_desktop --- #
    if not is_mobile and not force_desktop:
        # Generate QR code for the CURRENT active session URL
        session_url = request.build_absolute_uri(request.path) # Get current page URL
        qr_image_base64 = None
        try:
            qr_img = qrcode.make(session_url)
            buffer = io.BytesIO()
            qr_img.save(buffer, format='PNG')
            qr_image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            print(f"Generated QR code for session URL: {session_url}") # Debug
        except Exception as e:
            print(f"Error generating QR code for session {session_id}: {e}")
            messages.error(request, "Could not generate QR code for mobile access.")
            # Optionally handle error differently, maybe show link without QR?

        # Render the desktop redirect template
        return render(request, 'core/desktop_redirect_qr.html', {
            'farm_name': farm.name,
            'session_url': session_url, # Pass the session URL
            'qr_image_base64': qr_image_base64, # Pass the generated QR code image data
            'session_id': session_id, # ADDED: Pass session ID
            'message': "This survey session requires GPS and should be run on a mobile device. Please scan the QR code or use the link on your mobile."
        })

    # --- Get Seasonal Info for Recommendations --- #
    # Use the current month by default for recommendations within the active session
    stage_info = get_seasonal_stage_info()
    recommended_pests = stage_info.get('pests', []) # Get Pest objects
    recommended_diseases = stage_info.get('diseases', []) # Get Disease objects
    recommended_parts = stage_info.get('parts', []) # Get PlantPart objects
    current_stage_name = stage_info.get('stage_name', 'Unknown')

    # --- Load Existing Observations --- #
    observations = Observation.objects.filter(session=session, status='completed').order_by('-observation_time')
    # --- Load Latest Draft Observation --- #
    latest_draft = Observation.objects.filter(session=session, status='draft').order_by('-observation_time').first()
    draft_data_json = '{}' # Default to empty JSON object
    if latest_draft:
        # Serialize draft data to pass to the template/JS
        draft_data = {
            'id': latest_draft.id,
            'latitude': str(latest_draft.latitude) if latest_draft.latitude else None,
            'longitude': str(latest_draft.longitude) if latest_draft.longitude else None,
            'gps_accuracy': str(latest_draft.gps_accuracy) if latest_draft.gps_accuracy else None,
            'pests_observed': list(latest_draft.pests_observed.values_list('id', flat=True)),
            'diseases_observed': list(latest_draft.diseases_observed.values_list('id', flat=True)),
            'notes': latest_draft.notes or '',
            'plant_sequence_number': latest_draft.plant_sequence_number or '',
            # Note: We don't load images for the draft in the form, only display previously saved ones.
        }
        draft_data_json = json.dumps(draft_data)

    observation_count = observations.count()
    # Get target plants from the session itself
    target_plants = session.target_plants_surveyed
    progress_percent = int((observation_count / target_plants * 100)) if target_plants else 0

    # Initialize the form
    form = ObservationForm() # We don't use initial data here, JS will populate from draft_data_json

    context = {
        'session': session,
        'farm': farm,
        'observations': observations,
        'form': form,
        'observation_count': observation_count,
        'target_plants': target_plants,
        'progress_percent': progress_percent,
        'recommended_pests_ids': [p.id for p in recommended_pests],
        'recommended_diseases_ids': [d.id for d in recommended_diseases],
        'recommended_parts': recommended_parts, # Pass full objects if needed by template
        'current_stage_name': current_stage_name,
        'latest_draft_json': draft_data_json, # Pass draft data as JSON
    }
    return render(request, 'core/active_survey_session.html', context)


@csrf_exempt # Use proper auth later
@require_POST
@login_required
def auto_save_observation_api(request):
    """
    API endpoint to handle AJAX submission for auto-saving draft observations.
    Finds or creates a draft observation and updates its fields.
    Does NOT finalize the observation (status remains 'draft').
    """
    try:
        data = json.loads(request.body)
        session_id = data.get('session_id')
        draft_id = data.get('draft_id') # ID of existing draft, if known
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        gps_accuracy = data.get('gps_accuracy')
        pest_ids = data.get('pests_observed', [])
        disease_ids = data.get('diseases_observed', [])
        notes = data.get('notes', '')
        plant_seq_str = data.get('plant_sequence_number', '')

        session = get_object_or_404(SurveySession, session_id=session_id, surveyor=request.user)

        # Convert plant sequence number safely
        plant_sequence_number = None
        if plant_seq_str:
            try:
                plant_sequence_number = int(plant_seq_str)
            except (ValueError, TypeError):
                pass # Ignore invalid input for drafts

        # Find existing draft or create a new one
        observation = None
        if draft_id:
            try:
                # Try to fetch the existing draft
                observation = Observation.objects.get(id=draft_id, session=session, status='draft')
                print(f"Finalizing draft observation ID: {draft_id}")
                # Update fields from the form
                observation.pests_observed.set(Pest.objects.filter(id__in=pest_ids))
                observation.diseases_observed.set(Disease.objects.filter(id__in=disease_ids))
                observation.notes = notes
                observation.plant_sequence_number = plant_sequence_number # Can be None for drafts
                observation.observation_time = timezone.now() # Update timestamp on each save

                observation.save() # Save basic fields first to get an ID if new

                # Update M2M fields
                if pest_ids:
                    observation.pests_observed.set(Pest.objects.filter(id__in=pest_ids))
                else:
                    observation.pests_observed.clear()

                if disease_ids:
                    observation.diseases_observed.set(Disease.objects.filter(id__in=disease_ids))
                else:
                    observation.diseases_observed.clear()

                # Note: Images are NOT handled in auto-save to avoid partial uploads.
                # They are only processed during the final save (create_observation_api).

                return JsonResponse({'status': 'success', 'message': 'Draft saved.', 'draft_id': observation.id})

            except Observation.DoesNotExist:
                pass # If ID is invalid/mismatched, we'll create a new one

        if not observation:
            observation = Observation(session=session, status='draft')

        # Update fields
        observation.latitude = Decimal(latitude) if latitude else None
        observation.longitude = Decimal(longitude) if longitude else None
        observation.gps_accuracy = Decimal(gps_accuracy) if gps_accuracy else None
        observation.notes = notes
        observation.plant_sequence_number = plant_sequence_number # Can be None for drafts
        observation.observation_time = timezone.now() # Update timestamp on each save

        observation.save() # Save observation to get ID if new, or save updates

        # Set M2M fields only after saving for new observations
        if not draft_id:
             observation.pests_observed.set(Pest.objects.filter(id__in=pest_ids))
             observation.diseases_observed.set(Disease.objects.filter(id__in=disease_ids))

        # Note: Images are NOT handled in auto-save to avoid partial uploads.
        # They are only processed during the final save (create_observation_api).

        return JsonResponse({'status': 'success', 'message': 'Draft saved.', 'draft_id': observation.id})

    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON data.'}, status=400)
    except SurveySession.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Survey session not found.'}, status=404)
    except Exception as e:
        # Log the exception for debugging
        print(f"Error in auto_save_observation_api: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'status': 'error', 'message': f'An unexpected error occurred: {e}'}, status=500)


@csrf_exempt # TODO: Replace with proper token/session auth for AJAX
@require_POST
@login_required
def create_observation_api(request):
    """
    API endpoint to handle AJAX submission of a new observation OR finalize a draft.
    Expects POST data including session_id, lat, lon, accuracy, pests, diseases, notes, images.
    Also expects 'draft_id' if finalizing a draft.
    Sets status to 'completed'.
    Handles multiple image uploads.
    """
    session_id = request.POST.get('session_id')
    draft_id = request.POST.get('draft_id') # Get draft ID if finalizing
    session = get_object_or_404(SurveySession, session_id=session_id, surveyor=request.user)

    # Use ObservationForm for validation, but handle GPS/images separately
    form = ObservationForm(request.POST) # Pass POST data directly

    if form.is_valid():
        try:
            observation = None
            if draft_id:
                try:
                    # Try to fetch the existing draft
                    observation = Observation.objects.get(id=draft_id, session=session, status='draft')
                    print(f"Finalizing draft observation ID: {draft_id}")
                    # Update fields from the form
                    observation.pests_observed.set(form.cleaned_data['pests_observed'])
                    observation.diseases_observed.set(form.cleaned_data['diseases_observed'])
                    observation.notes = form.cleaned_data['notes']
                    observation.plant_sequence_number = form.cleaned_data['plant_sequence_number'] # Required now
                except Observation.DoesNotExist:
                    print(f"Draft ID {draft_id} not found or not a draft, creating new observation.")
                    # Fall through to create a new one if draft not found

            if not observation:
                print("Creating new observation.")
                # Create a new observation instance if not updating a draft
                observation = Observation(
                    session=session,
                    plant_sequence_number=form.cleaned_data['plant_sequence_number'],
                    notes=form.cleaned_data['notes'],
                )
                # M2M fields will be set after initial save

            # Common fields (GPS, status, time) for both new and draft updates
            observation.latitude = Decimal(request.POST.get('latitude')) if request.POST.get('latitude') else None
            observation.longitude = Decimal(request.POST.get('longitude')) if request.POST.get('longitude') else None
            observation.gps_accuracy = Decimal(request.POST.get('gps_accuracy')) if request.POST.get('gps_accuracy') else None
            observation.observation_time = timezone.now() # Set time on final save
            observation.status = 'completed' # Mark as completed

            observation.save() # Save observation to get ID if new, or save updates

            # Set M2M fields only after saving for new observations
            if not draft_id:
                 observation.pests_observed.set(form.cleaned_data['pests_observed'])
                 observation.diseases_observed.set(form.cleaned_data['diseases_observed'])

            # Handle Multiple Image Uploads
            images = request.FILES.getlist('images') # Use the name from ObservationForm
            print(f"Received {len(images)} files for observation {observation.id}.") # Debug
            for img_file in images:
                ObservationImage.objects.create(observation=observation, image=img_file)
                print(f"Saved image {img_file.name} for observation {observation.id}") # Debug

            # Prepare data for the success response (e.g., for updating the UI)
            # Convert Decimal fields to string for JSON serialization
            response_data = {
                'status': 'success',
                'observation': {
                    'id': observation.id,
                    'time': observation.observation_time.strftime('%H:%M:%S'),
                    'latitude': str(observation.latitude) if observation.latitude else None,
                    'longitude': str(observation.longitude) if observation.longitude else None,
                    'pests': list(observation.pests_observed.values_list('name', flat=True)),
                    'diseases': list(observation.diseases_observed.values_list('name', flat=True)),
                    'notes': observation.notes,
                    'plant_sequence_number': observation.plant_sequence_number,
                    # Include image URLs if needed by the template
                    'image_urls': [img.image.url for img in observation.images.all()]
                },
                 # Send back counts for progress update
                'observation_count': Observation.objects.filter(session=session, status='completed').count()
            }
            return JsonResponse(response_data)

        except Exception as e:
            # Log the error
            print(f"Error saving observation: {e}")
            import traceback
            traceback.print_exc()
            return JsonResponse({'status': 'error', 'message': f'Error saving observation: {e}'}, status=500)
    else:
        # Form validation failed
        print(f"Observation form errors: {form.errors.as_json()}")
        return JsonResponse({'status': 'error', 'message': 'Invalid data submitted.', 'errors': form.errors.as_json()}, status=400)


@csrf_exempt # TODO: Replace with proper auth
@require_POST
@login_required
def finish_survey_session_api(request, session_id):
    """
    API endpoint to mark a survey session as completed.
    """
    try:
        session = get_object_or_404(
            SurveySession, 
            session_id=session_id, 
            surveyor=request.user # Ensure user owns the session
        )

        # Check if the session is actually in progress
        if session.status != 'in_progress':
            return JsonResponse({'status': 'error', 'message': 'Session is not currently in progress.'}, status=400)

        # Optional: Check if minimum observations met (can also be enforced client-side)
        # target_plants = session.target_plants_surveyed or 0
        # completed_plants = session.observations.count()
        # if target_plants > 0 and completed_plants < target_plants:
        #     return JsonResponse({'status': 'error', 'message': 'Minimum observations not yet recorded.'}, status=400)

        # Update session status and end time
        session.status = 'completed'
        session.end_time = timezone.now()
        session.save(update_fields=['status', 'end_time'])
        
        print(f"API Finish Session: Marked session {session.session_id} as completed.")
        messages.success(request, f"Survey session for {session.farm.name} completed successfully!") 

        # Provide a URL to redirect to upon success (e.g., farm detail)
        redirect_url = reverse('core:farm_detail', kwargs={'farm_id': session.farm.id})

        return JsonResponse({
            'status': 'success',
            'message': 'Survey session completed.',
            'redirect_url': redirect_url
        })

    except Http404:
        return JsonResponse({'status': 'error', 'message': 'Survey session not found or access denied.'}, status=404)
    except Exception as e:
        print(f"API Finish Session: Error finishing session {session_id}: {e}")
        return JsonResponse({'status': 'error', 'message': f'An internal error occurred: {e}'}, status=500) 


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
def survey_session_detail_view(request, session_id):
    """
    Displays the details of a completed or abandoned survey session.
    """
    try:
        # Fetch the session, prefetching related data for efficiency
        session = get_object_or_404(
            SurveySession.objects.select_related('farm', 'surveyor'), 
            session_id=session_id
        )
        print(f"SessionDetail: Fetched session {session.session_id} for farm '{session.farm.name}'")
        
        # --- Permission Check --- 
        # Ensure the logged-in user is the surveyor (or potentially admin in future)
        if session.surveyor != request.user:
             messages.error(request, "You do not have permission to view this survey session.")
             print(f"SessionDetail: Permission denied for user {request.user.username} on session {session.session_id}")
             # Redirect to farm list or session list for that farm
             return redirect('core:survey_session_list', farm_id=session.farm.id) 
             
        # Optionally restrict view to only completed/abandoned?
        # if session.status not in ['completed', 'abandoned']:
        #     messages.warning(request, "This session is still in progress.")
        #     return redirect('core:active_survey_session', session_id=session.session_id)

    except Http404:
        messages.error(request, "Survey session not found.")
        print(f"SessionDetail: SurveySession with ID {session_id} not found (404).")
        # Redirect to dashboard or somewhere sensible if session ID is invalid
        return redirect('core:dashboard') 
    except Exception as e:
         messages.error(request, f"An error occurred accessing the survey session: {e}")
         print(f"SessionDetail: Error fetching session {session_id}: {e}")
         return redirect('core:dashboard')

    # --- Fetch Observations with related data --- 
    observations = Observation.objects.filter(session=session).prefetch_related(
        'pests_observed', 
        'diseases_observed', 
        'images' # Prefetch images
    ).order_by('observation_time') # Order by time recorded
    
    # --- Prepare Coordinates for Map --- #
    observation_coords = []
    for obs in observations:
        if obs.latitude and obs.longitude:
            observation_coords.append({
                'lat': float(obs.latitude), 
                'lon': float(obs.longitude),
                'time': obs.observation_time.strftime('%I:%M %p'),
                'pests': [p.name for p in obs.pests_observed.all()],
                'diseases': [d.name for d in obs.diseases_observed.all()],
                'has_image': obs.images.exists() # Check if image exists
            })
    observation_coords_json = json.dumps(observation_coords)

    # --- Calculate Stats --- #
    completed_count = observations.count()
    unique_pests = Pest.objects.filter(observations__session=session).distinct()
    unique_diseases = Disease.objects.filter(observations__session=session).distinct()

    context = {
        'session': session,
        'farm': session.farm,
        'observations': observations,
        'completed_count': completed_count,
        'unique_pests_count': unique_pests.count(),
        'unique_diseases_count': unique_diseases.count(),
        'unique_pests': unique_pests,
        'unique_diseases': unique_diseases,
        'observation_coords_json': observation_coords_json # Add coordinates JSON to context
    }

    # --- DEBUG: Print context before rendering ---
    print("\\n--- DEBUG: Context for survey_session_detail ---")
    print(f"Session ID: {session.session_id}")
    print(f"Observation Coords JSON: {observation_coords_json}") 
    print("--------------------------------------------\\n")

    return render(request, 'core/survey_session_detail.html', context) 


# --- PDF Generation View ---
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