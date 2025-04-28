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

from .forms import (
    SignUpForm, FarmForm, SurveillanceRecordForm, 
    UserEditForm, GrowerProfileEditForm, CalculatorForm
)
from .models import (
    Farm, PlantType, PlantPart, Pest, SurveillanceRecord, 
    Grower, Region, SurveillanceCalculation, BoundaryMappingToken, Disease
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
from .season_utils import determine_stage_and_p, get_active_threats_and_parts 
# Import updated calculation function (assuming it's in calculations.py)
from .calculations import calculate_surveillance_effort, get_surveillance_frequency, Z_SCORES, DEFAULT_CONFIDENCE


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
    
    # --- Determine Current Stage and Prevalence --- 
    current_stage, current_prevalence_p, _ = determine_stage_and_p()
    print(f"Farm {farm.id}: Current Stage='{current_stage}', Prevalence={current_prevalence_p}") # Debug
    
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
        calculation_results = calculate_surveillance_effort(
            farm=farm,
            confidence_level_percent=display_confidence,
            prevalence_p=current_prevalence_p
        )
        # ADDED check if fallback calculation resulted in error
        if calculation_results.get('error'):
             print(f"Farm {farm.id}: Fallback calculation resulted in error: {calculation_results['error']}")
        else:
             print(f"Farm {farm.id}: Fallback calculation successful.")
            
    except Exception as e:
        # Handle other potential errors during fetch/mapping
        print(f"Farm {farm.id}: Error fetching or mapping saved calculation: {e}") # MODIFIED
        calculation_results = {'error': f'Error retrieving saved calculation: {e}'} 

    # Ensure calculation_results is not None if calculation failed
    if calculation_results is None:
        print(f"Farm {farm.id}: calculation_results was None after try/except block. Setting error.") # ADDED
        calculation_results = {'error': 'Could not determine surveillance recommendations.'}
        
    print(f"Farm {farm.id}: Final Calculation Results for display={calculation_results}") # Debug

    # --- Get Active Threats and Parts for the Current Stage ---
    threats_and_parts = get_active_threats_and_parts(current_stage)
    pest_names = threats_and_parts['pest_names']
    disease_names = threats_and_parts['disease_names']
    part_names = threats_and_parts['part_names']
    print(f"Farm {farm.id}: Active Pests={pest_names}, Diseases={disease_names}, Parts={part_names}") # Debug

    # --- Fetch corresponding Model objects --- 
    priority_pests = Pest.objects.filter(name__in=pest_names)
    priority_diseases = Disease.objects.filter(name__in=disease_names)
    recommended_parts = PlantPart.objects.filter(name__in=part_names)

    # --- Other Info ---
    # TODO: Refactor frequency logic if needed, maybe based on stage?
    surveillance_frequency = get_surveillance_frequency(current_stage, farm) 
    last_surveillance_date = farm.last_surveillance_date()
    next_due_date = farm.next_due_date() # Uses simple 7-day logic for now
    surveillance_records = farm.surveillance_records.order_by('-date_performed')[:5] # Get latest 5 records
    
    context = {
        'farm': farm,
        'current_stage': current_stage, # Pass stage name
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
    current_stage = None
    current_prevalence_p = None
    month_used_for_calc = None
    debug_month_override = None # Initialize

    # --- Handle Debug Month Override --- 
    debug_month_str = request.GET.get('debug_month')
    if debug_month_str:
        try:
            month_val = int(debug_month_str)
            if 1 <= month_val <= 12:
                debug_month_override = month_val
                print(f"Calculator View: Using debug_month override: {debug_month_override}")
            else:
                 messages.warning(request, f"Invalid debug month ({debug_month_str}) ignored. Using current system month.")
        except (ValueError, TypeError):
             messages.warning(request, f"Could not parse debug month ({debug_month_str}) ignored. Using current system month.")

    # Determine current stage, prevalence, and the month used (potentially overridden)
    current_stage, current_prevalence_p, month_used_for_calc = determine_stage_and_p(override_month=debug_month_override)
    
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
                # Calculate surveillance effort using stage/p (potentially from override) and SELECTED confidence
                calculation_results = calculate_surveillance_effort(
                    farm=selected_farm_instance,
                    confidence_level_percent=confidence, # Pass the integer confidence
                    prevalence_p=current_prevalence_p # Use stage-determined prevalence
                )
                
                # Add the month used to the results dict for display
                if calculation_results:
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
                        season=current_stage, # Store the auto-determined stage
                        confidence_level=confidence,
                        population_size=calculation_results['N'],
                        prevalence_percent=Decimal(str(calculation_results['prevalence_p'])) * 100,
                        margin_of_error=Decimal(str(calculation_results['margin_of_error'])) * 100,
                        required_plants=calculation_results['required_plants_to_survey'],
                        percentage_of_total=Decimal(str(calculation_results.get('percentage_of_total', 0))),
                        survey_frequency=calculation_results.get('survey_frequency'),
                        is_current=True,
                        # Add notes field if you want to record the month used for debug?
                        # notes=f"Calculation based on month: {month_used_for_calc}"
                    )
                    surveillance_calc.save()
                    messages.success(
                        request, 
                        f"Surveillance calculation saved for {selected_farm_instance.name} ({current_stage} stage based on month {month_used_for_calc}): {calculation_results['required_plants_to_survey']} plants at {confidence}% confidence."
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
        'current_stage': current_stage, # Pass stage to template
        'current_prevalence_p': current_prevalence_p * 100 if current_prevalence_p is not None else None, # Pass prevalence as percentage
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
    
    if request.method == 'POST':
        form = SurveillanceRecordForm(request.POST, farm=farm)
        if form.is_valid():
            # Extract data from the form
            data = {
                'date_performed': form.cleaned_data['date_performed'],
                'plants_surveyed': form.cleaned_data['plants_surveyed'],
                'notes': form.cleaned_data['notes'],
                'plant_parts_checked': form.cleaned_data['plant_parts_checked'],
                'pests_found': form.cleaned_data['pests_found']
            }
            
            # Use service to create record
            record, error = create_surveillance_record(farm, request.user, data)
            
            if error:
                messages.error(request, error)
                return render(request, 'core/record_surveillance.html', {'form': form, 'farm': farm})
            
            # Check if pests were found for appropriate messaging
            if record.pests_found.exists():
                messages.warning(
                    request, 
                    f"Surveillance recorded with {record.pests_found.count()} pest(s) found. Consider treatment options."
                )
            else:
                messages.success(request, "Surveillance recorded successfully. No pests found.")
                
            return redirect('core:farm_detail', farm_id=farm.id)
    else:
        # Check if we have a saved calculation to use for initial plants value
        try:
            saved_calculation = SurveillanceCalculation.objects.filter(
                farm=farm,
                is_current=True
            ).first()
            
            initial_data = {}
            if saved_calculation:
                initial_data['plants_surveyed'] = saved_calculation.required_plants
            else:
                # No saved calculation found, use default
                default_season = farm.current_season()
                calculation = calculate_surveillance_effort(farm, 95, default_season)
                
                if not calculation.get('error'):
                    initial_data['plants_surveyed'] = calculation.get('required_plants_to_survey')
                    
        except Exception as e:
            # If anything goes wrong, initialize without plants_surveyed
            initial_data = {}
            
        form = SurveillanceRecordForm(farm=farm, initial=initial_data)
    
    # Get recommended plant parts to check for this season
    recommendations = get_surveillance_recommendations(farm)
    
    context = {
        'form': form,
        'farm': farm,
        'recommended_parts': recommendations['recommended_parts']
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