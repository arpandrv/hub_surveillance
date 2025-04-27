from django.shortcuts import render, redirect, get_object_or_404
from django.http import Http404
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count, Q

from .forms import SignUpForm, FarmForm, SurveillanceRecordForm, UserEditForm, GrowerProfileEditForm, CalculatorForm
from .models import Farm, PlantType, PlantPart, Pest, SurveillanceRecord, Grower, Region
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
    
    # Set default confidence and determine current season
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
    
    # Get recommended parts to check
    recommended_parts = get_recommended_plant_parts(
        season=default_season,
        plant_type=farm.plant_type
    )
    
    # Get recommended frequency and next due date
    surveillance_frequency = get_surveillance_frequency(default_season, farm)
    last_surveillance_date = farm.last_surveillance_date()
    next_due_date = farm.next_due_date()
    
    # Get surveillance records
    surveillance_records = farm.surveillance_records.order_by('-date_performed')
    
    context = {
        'farm': farm,
        'calculation_results': calculation_results,
        'surveillance_records': surveillance_records,
        'default_season_used': default_season,
        'default_confidence_used': default_confidence,
        'priority_pests': priority_pests,
        'recommended_parts': recommended_parts,
        'surveillance_frequency': surveillance_frequency,
        'last_surveillance_date': last_surveillance_date,
        'next_due_date': next_due_date
    }
    
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
    
    # Get initial farm_id from query params if available
    initial_farm_id = request.GET.get('farm')
    
    # Initialize form with GET data or initial farm
    if initial_farm_id:
        try:
            initial_farm = Farm.objects.get(id=initial_farm_id, owner=grower)
            form = CalculatorForm(grower, initial={'farm': initial_farm})
        except Farm.DoesNotExist:
            form = CalculatorForm(grower, request.GET or None)
    else:
        form = CalculatorForm(grower, request.GET or None)

    if form.is_valid():
        selected_farm_instance = form.cleaned_data['farm']
        confidence = form.cleaned_data['confidence_level']
        season = form.cleaned_data['season']
        
        calculation_results = calculate_surveillance_effort(
            farm=selected_farm_instance,
            confidence_level_percent=confidence,
            season=season
        )

    context = {
        'form': form,
        'selected_farm': selected_farm_instance,
        'calculation_results': calculation_results,
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
        # Pre-populate with recommended surveillance count
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
