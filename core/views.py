from django.shortcuts import render, redirect, get_object_or_404
from django.http import Http404
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import SignUpForm, FarmForm, SurveillanceRecordForm, UserEditForm, GrowerProfileEditForm, CalculatorForm
from .models import Farm, PlantType, SurveillanceRecord, Grower
from .calculations import calculate_surveillance_effort # Import from calculations

# Create your views here.

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
    # This view now serves as the "My Farms" list
    grower = request.user.grower_profile
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
    calculation_results = None
    selected_farm_instance = None # Store the selected Farm object
    form = CalculatorForm(grower, request.GET or None) # Initialize with GET data if available

    if form.is_valid():
        selected_farm_instance = form.cleaned_data['farm']
        confidence = form.cleaned_data['confidence_level']
        season = form.cleaned_data['season']
        
        calculation_results = calculate_surveillance_effort(
            farm=selected_farm_instance, 
            confidence_level_percent=confidence, # Pass cleaned data
            season=season # Pass cleaned data
        )

    context = {
        'form': form,
        'selected_farm': selected_farm_instance, # Pass the Farm object
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

@login_required
def record_list_view(request):
    grower = request.user.grower_profile
    # Fetch all records performed by this grower, ordered by date descending
    records = SurveillanceRecord.objects.filter(performed_by=grower).order_by('-date_performed')
    
    context = {
        'records': records
    }
    return render(request, 'core/record_list.html', context)

@login_required
def dashboard_view(request):
    grower = request.user.grower_profile # Get grower for potential future use
    context = {
        'grower': grower
    }
    return render(request, 'core/dashboard.html', context)

# Login view is handled by Django's auth_views.LoginView in urls.py
# Logout view is handled by Django's auth_views.LogoutView in urls.py
