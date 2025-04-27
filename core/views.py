from django.shortcuts import render, redirect, get_object_or_404
from django.http import Http404, JsonResponse, HttpResponse
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count, Q
from django.conf import settings
import requests

from .forms import SignUpForm, FarmForm, SurveillanceRecordForm, UserEditForm, GrowerProfileEditForm, CalculatorForm
from .models import Farm, PlantType, PlantPart, Pest, SurveillanceRecord, Grower, Region, SurveillanceCalculation
from .calculations import (
    calculate_surveillance_effort, 
    get_recommended_plant_parts,
    get_surveillance_frequency
)

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
    grower = request.user.grower_profile
    farms = Farm.objects.filter(owner=grower)
    context = {
        'farms': farms
    }
    return render(request, 'core/home.html', context)

@login_required
def create_farm_view(request):
    """Handle farm creation."""
    if request.method == 'POST':
        form = FarmForm(request.POST)
        if form.is_valid():
            farm = form.save(commit=False)
            farm.owner = request.user.grower_profile
            
            # Set default plant type to Mango
            try:
                mango_type = PlantType.objects.get(name='Mango')
            except PlantType.DoesNotExist:
                raise Http404("Default 'Mango' PlantType not found in database. Please add it via the admin interface.")
            
            farm.plant_type = mango_type
            farm.save()
            messages.success(request, f"Farm '{farm.name}' was created successfully!")
            return redirect('core:farm_detail', farm_id=farm.id)
    else:
        form = FarmForm()
    
    return render(request, 'core/create_farm.html', {'form': form})

@login_required
def farm_detail_view(request, farm_id):
    """Display detailed information about a specific farm."""
    farm = get_object_or_404(Farm, id=farm_id, owner=request.user.grower_profile)
    
    # Check for a saved calculation in the database
    try:
        # Get the most recent current calculation
        saved_calculation = SurveillanceCalculation.objects.filter(
            farm=farm,
            is_current=True
        ).first()
        
        if saved_calculation:
            # Use the saved calculation data
            default_confidence = saved_calculation.confidence_level
            default_season = saved_calculation.season
            
            # Convert from database model to calculation result format
            calculation_results = {
                'N': saved_calculation.population_size,
                'confidence_level_percent': saved_calculation.confidence_level,
                'season': saved_calculation.season,
                'p_percent': float(saved_calculation.prevalence_percent),
                'd': float(saved_calculation.margin_of_error) / 100,  # Convert percentage back to decimal
                'required_plants_to_survey': saved_calculation.required_plants,
                'survey_frequency': saved_calculation.survey_frequency,
                'percentage_of_total': float(saved_calculation.percentage_of_total),
                'calculation_date': saved_calculation.date_created.date(),
                'error': None
            }
            
            # For debug
            print(f"Using saved calculation from {saved_calculation.date_created}")
        else:
            # No saved calculation found, calculate with defaults
            default_confidence = 95
            default_season = farm.current_season()
            calculation_results = calculate_surveillance_effort(
                farm=farm,
                confidence_level_percent=default_confidence,
                season=default_season
            )
    except Exception as e:
        # If anything goes wrong, fall back to a fresh calculation
        print(f"Error retrieving saved calculation: {e}")
        default_confidence = 95
        default_season = farm.current_season()
        calculation_results = calculate_surveillance_effort(
            farm=farm,
            confidence_level_percent=default_confidence,
            season=default_season
        )
    else:
        # No saved calculation, calculate with defaults
        default_confidence = 95
        default_season = farm.current_season()
        
        # Calculate surveillance effort
        calculation_results = calculate_surveillance_effort(
            farm=farm,
            confidence_level_percent=default_confidence,
            season=default_season
        )
    
    # Get priority pests for this season and plant type
    priority_pests = Pest.get_priority_pests_for_season(
        season=default_season,
        plant_type=farm.plant_type
    )
    
    # Get recommended parts to check (based on the season used in calculation)
    calculation_season = calculation_results.get('season', default_season)
    recommended_parts = get_recommended_plant_parts(
        season=calculation_season,
        plant_type=farm.plant_type
    )
    
    # Get recommended frequency and next due date
    surveillance_frequency = get_surveillance_frequency(calculation_season, farm)
    last_surveillance_date = farm.last_surveillance_date()
    next_due_date = farm.next_due_date()
    
    # Get surveillance records
    surveillance_records = farm.surveillance_records.order_by('-date_performed')
    
    # Print debug info about calculation results
    print(f"Calculation Results for farm {farm.id}:")
    print(f"- Required plants: {calculation_results.get('required_plants_to_survey')}")
    print(f"- Using: {calculation_results.get('confidence_level_percent')}% confidence")
    print(f"- Season: {calculation_results.get('season')}")
    print(f"- Date: {calculation_results.get('calculation_date')}")
    
    context = {
        'farm': farm,
        'calculation_results': calculation_results,
        'surveillance_records': surveillance_records,
        'default_season_used': calculation_season,
        'default_confidence_used': calculation_results.get('confidence_level_percent', default_confidence),
        'priority_pests': priority_pests,
        'recommended_parts': recommended_parts,
        'surveillance_frequency': surveillance_frequency,
        'last_surveillance_date': last_surveillance_date,
        'next_due_date': next_due_date
    }
    
    # Add debug message
    messages.info(request, f"Using calculation with {calculation_results.get('required_plants_to_survey')} plants to survey.")
    
    return render(request, 'core/farm_detail.html', context)

@login_required
def edit_farm_view(request, farm_id):
    """Handle farm editing."""
    farm_instance = get_object_or_404(Farm, id=farm_id, owner=request.user.grower_profile)
    
    if request.method == 'POST':
        form = FarmForm(request.POST, instance=farm_instance)
        if form.is_valid():
            form.save()
            messages.success(request, f"Farm '{farm_instance.name}' was updated successfully!")
            return redirect('core:farm_detail', farm_id=farm_instance.id)
    else:
        form = FarmForm(instance=farm_instance)
    
    context = {
        'form': form,
        'farm': farm_instance,
        'is_edit': True  # Flag to indicate this is an edit operation
    }
    
    return render(request, 'core/create_farm.html', context)

@login_required
def delete_farm_view(request, farm_id):
    """Handle farm deletion."""
    farm = get_object_or_404(Farm, id=farm_id, owner=request.user.grower_profile)
    
    if request.method == 'POST':
        farm_name = farm.name
        farm.delete()
        messages.success(request, f"Farm '{farm_name}' was deleted successfully.")
        return redirect('core:myfarms')
    
    context = {'farm': farm}
    return render(request, 'core/delete_farm_confirm.html', context)

@login_required
def calculator_view(request):
    """Calculate surveillance requirements based on user inputs."""
    grower = request.user.grower_profile
    calculation_results = None
    selected_farm_instance = None
    form_submitted = False
    
    # Get initial farm_id from query params if available
    initial_farm_id = request.GET.get('farm')
    
    # Check if there's actual form submission (all parameters present)
    if request.GET and 'farm' in request.GET and 'confidence_level' in request.GET and 'season' in request.GET:
        form_submitted = True
        form = CalculatorForm(grower, request.GET)
        
        if form.is_valid():
            selected_farm_instance = form.cleaned_data['farm']
            confidence = form.cleaned_data['confidence_level']
            season = form.cleaned_data['season']
            
            # Calculate surveillance effort
            calculation_results = calculate_surveillance_effort(
                farm=selected_farm_instance,
                confidence_level_percent=confidence,
                season=season
            )
            
            # Save calculation to database for historical record
            if not calculation_results.get('error') and selected_farm_instance:
                # First, mark all previous calculations for this farm as not current
                SurveillanceCalculation.objects.filter(
                    farm=selected_farm_instance, 
                    is_current=True
                ).update(is_current=False)
                
                # Create a new calculation record
                surveillance_calc = SurveillanceCalculation(
                    farm=selected_farm_instance,
                    created_by=request.user,
                    season=season,
                    confidence_level=confidence,
                    population_size=calculation_results['N'],
                    prevalence_percent=calculation_results['p_percent'],
                    margin_of_error=calculation_results['d'] * 100,  # Convert from decimal to percentage
                    required_plants=calculation_results['required_plants_to_survey'],
                    percentage_of_total=calculation_results.get('percentage_of_total', 0),
                    survey_frequency=calculation_results.get('survey_frequency'),
                    is_current=True  # This is the current calculation
                )
                surveillance_calc.save()
                
                # Add success message
                messages.success(
                    request, 
                    f"Surveillance calculation for {selected_farm_instance.name} saved: {calculation_results['required_plants_to_survey']} plants."
                )
        else:
            # If form is invalid after submission, show errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{form.fields[field].label}: {error}")
    
    # Initialize form with default farm if NOT submitting and farm ID is in URL
    elif initial_farm_id and not form_submitted:
        try:
            initial_farm = Farm.objects.get(id=initial_farm_id, owner=grower)
            # For new form, use defaults from the farm
            default_season = initial_farm.current_season()
            form = CalculatorForm(
                grower, 
                initial={
                    'farm': initial_farm,
                    'confidence_level': 95,
                    'season': default_season
                }
            )
        except Farm.DoesNotExist:
            form = CalculatorForm(grower)
    else:
        # Empty form with no defaults
        form = CalculatorForm(grower)

    context = {
        'form': form,
        'selected_farm': selected_farm_instance,
        'calculation_results': calculation_results,
        'form_submitted': form_submitted,
    }
    
    return render(request, 'core/calculator.html', context)

@login_required
def record_surveillance_view(request, farm_id):
    """Record a new surveillance activity for a farm."""
    farm = get_object_or_404(Farm, id=farm_id, owner=request.user.grower_profile)
    
    if request.method == 'POST':
        form = SurveillanceRecordForm(request.POST, farm=farm)
        if form.is_valid():
            record = form.save(commit=False)
            record.farm = farm
            record.performed_by = request.user.grower_profile
            record.save()
            form.save_m2m()
            
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
        # Check if we have a saved calculation in the database
        try:
            saved_calculation = SurveillanceCalculation.objects.filter(
                farm=farm,
                is_current=True
            ).first()
            
            initial_data = {}
            if saved_calculation:
                # Use the saved calculation data
                initial_data['plants_surveyed'] = saved_calculation.required_plants
                print(f"Using saved calculation: {initial_data['plants_surveyed']} plants")
            else:
                # No saved calculation found, use default
                default_season = farm.current_season()
                calculation = calculate_surveillance_effort(farm, 95, default_season)
                
                if not calculation.get('error'):
                    initial_data['plants_surveyed'] = calculation.get('required_plants_to_survey')
                    print(f"Using default calculation: {initial_data['plants_surveyed']} plants")
        except Exception as e:
            # If anything goes wrong, fall back to a default calculation
            print(f"Error retrieving saved calculation: {e}")
            default_season = farm.current_season()
            calculation = calculate_surveillance_effort(farm, 95, default_season)
            
            initial_data = {}
            if not calculation.get('error'):
                initial_data['plants_surveyed'] = calculation.get('required_plants_to_survey')
            
        form = SurveillanceRecordForm(farm=farm, initial=initial_data)
    
    # Get recommended plant parts to check for this season
    recommended_parts = get_recommended_plant_parts(farm.current_season(), farm.plant_type)
    
    context = {
        'form': form,
        'farm': farm,
        'recommended_parts': recommended_parts
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
    for farm in grower.farms.all():
        last_date = farm.last_surveillance_date()
        if not last_date or last_date.date() < week_ago:
            due_farms.append(farm)
    
    due_farms_count = len(due_farms)
    
    # Get current season information
    sample_farm = grower.farms.first()
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
    region_id = request.GET.get('region_id', None) # Expect region_id from frontend
    suggestions = []
    error_message = None
    state_territory_used = None

    print(f"Address suggestion API called with query: {query}, region_id: {region_id}")
    
    if not region_id:
        error_message = "Region must be selected first."
    elif query and len(query) >= 3:
        api_key = getattr(settings, 'GEOSCAPE_API_KEY', None)
        print(f"API key found: {'Yes' if api_key else 'No'}")
        
        if not api_key:
            error_message = "API key not configured."
        else:
            try:
                # Look up the region to get the state abbreviation
                selected_region = Region.objects.get(id=region_id)
                state_territory_used = selected_region.state_abbreviation
                print(f"Region {selected_region.name} has state_abbreviation: {state_territory_used}")
                
                if not state_territory_used:
                     error_message = f"State/Territory not configured for region: {selected_region.name}."
                else:
                    geoscape_url = "https://api.psma.com.au/v1/predictive/address"
                    headers = {
                        "Accept": "application/json",
                        "Authorization": api_key  # Using API key directly without Bearer prefix
                    }
                    params = {
                        "query": query,
                        "stateTerritory": state_territory_used # Use state from selected region
                    }
                    # Debug info
                    print(f"Using API Key starting with: {api_key[:5]}... (hidden)")
                    print(f"Request URL: {geoscape_url}")
                    print(f"Headers: {headers}")
                    print(f"Params: {params}")
                    
                    # Try the request
                    print("Making API request...")
                    response = requests.get(geoscape_url, headers=headers, params=params, timeout=10)
                    print(f"API Response status: {response.status_code}")
                    
                    # Add more error details if needed
                    if response.status_code != 200:
                        print(f"Error response body: {response.text}")
                        
                    response.raise_for_status()
                    data = response.json()
                    print(f"API Response structure: {list(data.keys())}")
                    suggestions = data.get('suggest', [])
                    print(f"Found {len(suggestions)} suggestions")

            except Region.DoesNotExist:
                error_message = "Invalid region selected."
            except requests.exceptions.RequestException as e:
                print(f"Error calling Geoscape API: {e}") 
                error_message = "Could not retrieve address suggestions."
            except Exception as e:
                print(f"Unexpected error processing Geoscape response: {e}")
                error_message = "An error occurred while processing suggestions."

    # Prepare JSON response
    response_data = {'suggestions': suggestions}
    if error_message:
        response_data['error'] = error_message
    if state_territory_used:
        response_data['state_territory_used'] = state_territory_used # Optionally return state used
        
    return JsonResponse(response_data)
