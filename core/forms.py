from django import forms
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError
from .models import Grower, Farm, PlantPart, Pest, SurveillanceRecord, Region

class SignUpForm(forms.ModelForm):
    # Fields for the User model
    password = forms.CharField(widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput)
    email = forms.EmailField(required=True)

    # Field for the Grower model
    farm_name = forms.CharField(max_length=100, required=True)
    contact_number = forms.CharField(max_length=20, required=False)

    class Meta:
        model = User
        fields = ['username', 'email', 'password'] # Fields from User model to include directly

    def clean_confirm_password(self):
        password = self.cleaned_data.get('password')
        confirm_password = self.cleaned_data.get('confirm_password')
        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError("Passwords don't match")
        return confirm_password

    def save(self, commit=True):
        # Save the User instance
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
            # Create and save the Grower profile
            Grower.objects.create(
                user=user,
                farm_name=self.cleaned_data.get('farm_name'),
                contact_number=self.cleaned_data.get('contact_number')
            )
        return user 

class FarmForm(forms.ModelForm):
    # Add Region field with limited queryset as per image
    # Note: This assumes 'Northern Territory' and potential others exist in the DB
    region = forms.ModelChoiceField(
        queryset=Region.objects.filter(name__in=['Northern Territory']), # Limit choices
        empty_label=None, # No empty choice needed if required
        required=True
    )
    # Add checkbox for address - this doesn't map directly to a model field
    # It will control display logic in the template via JavaScript (to be added)
    has_exact_address = forms.BooleanField(required=False, label="Do you have an exact street address for this farm?", initial=False)

    class Meta:
        model = Farm
        fields = [
            'name', 
            'region',
            # has_exact_address - not a model field 
            'location_description',
            'size_hectares', 
            'stocking_rate', 
            'distribution_pattern'
        ]
        widgets = {
            'location_description': forms.Textarea(attrs={'rows': 3, 'placeholder': 'e.g., "Near Katherine River", "Smith Property via XYZ Road"'}),
        }
        labels = {
            'location_description': 'General Location (Optional)',
            'stocking_rate': 'Stocking Rate (plants per hectare)'
        }

class SurveillanceRecordForm(forms.ModelForm):
    plant_parts_checked = forms.ModelMultipleChoiceField(
        queryset=PlantPart.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )
    pests_found = forms.ModelMultipleChoiceField(
        queryset=Pest.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )

    # Accept farm in constructor
    def __init__(self, *args, **kwargs):
        self.farm = kwargs.pop('farm', None) # Get farm from kwargs
        super().__init__(*args, **kwargs)
        if not self.farm:
            # This should ideally not happen if view is correct,
            # but good practice to handle it.
            raise ValueError("Farm instance must be provided to SurveillanceRecordForm")

    class Meta:
        model = SurveillanceRecord
        fields = [
            'date_performed',
            'plants_surveyed',
            'plant_parts_checked',
            'pests_found',
            'notes'
        ]
        widgets = {
            'date_performed': forms.DateTimeInput(attrs={'type': 'datetime-local', 'value': timezone.now().strftime('%Y-%m-%dT%H:%M')}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def clean_plants_surveyed(self):
        """Validate that plants_surveyed is not more than total plants on farm."""
        plants_surveyed = self.cleaned_data.get('plants_surveyed')
        total_plants = self.farm.total_plants()

        if plants_surveyed is None: # Handle case where field is empty
            raise ValidationError("This field is required.") 
        
        if total_plants is None:
             # If total plants can't be calculated, we can't validate this.
             # Depending on requirements, could allow save or raise error.
             # For now, let's allow it but maybe add a warning later.
             pass 
        elif plants_surveyed > total_plants:
            raise ValidationError(
                f"Number of plants surveyed ({plants_surveyed}) cannot exceed "
                f"the total plants calculated for this farm ({total_plants})."
            )
        elif plants_surveyed < 0:
             raise ValidationError("Number of plants surveyed cannot be negative.")
             
        return plants_surveyed 

class UserEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'email'] # Allow editing username and email

class GrowerProfileEditForm(forms.ModelForm):
    class Meta:
        model = Grower
        fields = ['farm_name', 'contact_number'] # Fields from Grower model 

SEASON_CHOICES = [
    ('Wet', 'Wet Season (Approx. Nov-Apr)'),
    ('Dry', 'Dry Season (Approx. May-Oct)'),
    ('Flowering', 'Flowering Period (Within Dry Season)'),
]

CONFIDENCE_CHOICES = [
    (90, '90%'),
    (95, '95% - Standard'),
    (99, '99% - High Confidence'),
]

class CalculatorForm(forms.Form):
    farm = forms.ModelChoiceField(
        queryset=Farm.objects.none(),  # Queryset set dynamically in the view
        label="Select Your Farm",
        empty_label="--------- Select a Farm ---------"
    )
    confidence_level = forms.ChoiceField(
        choices=CONFIDENCE_CHOICES, 
        initial=95, 
        label="Desired Confidence Level"
    )
    season = forms.ChoiceField(
        choices=SEASON_CHOICES, 
        initial='Wet',  # Default to higher risk
        label="Select Current Season/Period"
    )

    def __init__(self, grower, *args, **kwargs):
        # Get the initial data, if any
        initial = kwargs.get('initial', {})
        
        # If a farm is selected, update other defaults
        if 'farm' in initial and initial['farm']:
            farm = initial['farm']
            # Set confidence level default to 95% if not specified
            if 'confidence_level' not in initial:
                initial['confidence_level'] = 95
            # Set season default to current season if not specified
            if 'season' not in initial:
                try:
                    # Use the farm's current_season method if available
                    initial['season'] = farm.current_season()
                except AttributeError:
                    # Fall back to 'Wet' if method doesn't exist
                    initial['season'] = 'Wet'
            
            # Update the kwargs with our modified initial data
            kwargs['initial'] = initial
        
        super().__init__(*args, **kwargs)
        
        # Populate farm choices based on the logged-in grower
        self.fields['farm'].queryset = Farm.objects.filter(owner=grower)
        
        # Additional setup for better user experience
        self.fields['farm'].widget.attrs.update({'class': 'form-select form-select-lg'})
        self.fields['confidence_level'].widget.attrs.update({'class': 'form-select'})
        self.fields['season'].widget.attrs.update({'class': 'form-select'}) 