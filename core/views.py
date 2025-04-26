from django.shortcuts import render, redirect, get_object_or_404
from django.http import Http404
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import SignUpForm, FarmForm, SurveillanceRecordForm, UserEditForm, GrowerProfileEditForm
from .models import Farm, PlantType, SurveillanceRecord, Grower

# Create your views here.

def calculate_surveillance_effort(farm):
    """
    Placeholder function to calculate required surveillance effort.
    Replace with actual logic later.
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

def signup_view(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save() # This now saves User and creates Grower profile
            login(request, user) # Log the user in immediately after signup
            # Redirect to the new home page after signup
            return redirect('core:home') 
    else:
        form = SignUpForm()
    return render(request, 'core/signup.html', {'form': form})

@login_required
def home_view(request):
    # Get the grower profile associated with the logged-in user
    grower = request.user.grower_profile
    # Fetch all farms owned by this grower
    farms = Farm.objects.filter(owner=grower)
    
    context = {
        'farms': farms
    }
    return render(request, 'core/home.html', context)

@login_required
def create_farm_view(request):
    if request.method == 'POST':
        form = FarmForm(request.POST)
        if form.is_valid():
            farm = form.save(commit=False)
            farm.owner = request.user.grower_profile
            try:
                mango_type = PlantType.objects.get(name='Mango')
            except PlantType.DoesNotExist:
                raise Http404("Default 'Mango' PlantType not found in database. Please add it via the admin interface.") 
            farm.plant_type = mango_type
            farm.save()
            return redirect('core:home')
    else:
        form = FarmForm()
    return render(request, 'core/create_farm.html', {'form': form})

@login_required
def farm_detail_view(request, farm_id):
    farm = get_object_or_404(Farm, id=farm_id, owner=request.user.grower_profile)
    calculation_results = calculate_surveillance_effort(farm)
    
    # Fetch related surveillance records, order by most recent first
    surveillance_records = farm.surveillance_records.order_by('-date_performed')
    
    context = {
        'farm': farm,
        'calculation_results': calculation_results,
        'surveillance_records': surveillance_records # Add records to context
    }
    return render(request, 'core/farm_detail.html', context)

@login_required
def edit_farm_view(request, farm_id):
    # Get the farm instance, ensuring it belongs to the current user
    farm_instance = get_object_or_404(Farm, id=farm_id, owner=request.user.grower_profile)
    
    if request.method == 'POST':
        # Pass the instance to the form so it knows we are editing
        form = FarmForm(request.POST, instance=farm_instance)
        if form.is_valid():
            form.save() # Save the changes to the existing instance
            # Redirect to the farm detail page after successful edit
            return redirect('core:farm_detail', farm_id=farm_instance.id) 
    else:
        # Pre-populate the form with the farm's current data
        form = FarmForm(instance=farm_instance)
        
    context = {
        'form': form,
        'farm': farm_instance # Pass farm to template for context (e.g., title)
    }
    # We can reuse the create_farm template for editing
    return render(request, 'core/create_farm.html', context)

@login_required
def delete_farm_view(request, farm_id):
    farm = get_object_or_404(Farm, id=farm_id, owner=request.user.grower_profile)
    if request.method == 'POST':
        farm.delete()
        # Add a success message (optional)
        # messages.success(request, f'Farm "{farm.name}" deleted successfully.')
        return redirect('core:home') # Redirect home after deletion
    
    # If GET, show confirmation page
    context = {'farm': farm}
    return render(request, 'core/delete_farm_confirm.html', context)

@login_required
def calculator_view(request):
    grower = request.user.grower_profile
    farms = Farm.objects.filter(owner=grower)
    selected_farm = None
    calculation_results = None

    if request.method == 'GET' and 'farm_id' in request.GET:
        farm_id = request.GET.get('farm_id')
        if farm_id:
            try:
                selected_farm = Farm.objects.get(id=farm_id, owner=grower)
                calculation_results = calculate_surveillance_effort(selected_farm)
            except Farm.DoesNotExist:
                pass 
            except ValueError:
                 pass

    context = {
        'farms': farms,
        'selected_farm': selected_farm,
        'calculation_results': calculation_results,
    }
    return render(request, 'core/calculator.html', context)

@login_required
def record_surveillance_view(request, farm_id):
    farm = get_object_or_404(Farm, id=farm_id, owner=request.user.grower_profile)
    
    if request.method == 'POST':
        # Pass farm to the form constructor
        form = SurveillanceRecordForm(request.POST, farm=farm) 
        if form.is_valid():
            record = form.save(commit=False)
            record.farm = farm
            record.performed_by = request.user.grower_profile
            record.save()
            form.save_m2m()
            return redirect('core:farm_detail', farm_id=farm.id)
    else:
        # Pass farm to the form constructor for GET requests too
        form = SurveillanceRecordForm(farm=farm) 
        
    context = {
        'form': form,
        'farm': farm
    }
    return render(request, 'core/record_surveillance.html', context)

@login_required
def profile_view(request):
    user_form = UserEditForm(instance=request.user)
    # Get the related Grower profile instance
    grower_profile = get_object_or_404(Grower, user=request.user)
    profile_form = GrowerProfileEditForm(instance=grower_profile)

    if request.method == 'POST':
        user_form = UserEditForm(request.POST, instance=request.user)
        profile_form = GrowerProfileEditForm(request.POST, instance=grower_profile)
        
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, 'Your profile was successfully updated!')
            return redirect('core:profile') # Redirect back to profile page
        else:
            messages.error(request, 'Please correct the error below.')

    context = {
        'user_form': user_form,
        'profile_form': profile_form
    }
    return render(request, 'core/profile.html', context)

# Login view is handled by Django's auth_views.LoginView in urls.py
# Logout view is handled by Django's auth_views.LogoutView in urls.py
