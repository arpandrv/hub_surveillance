from django import forms
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError
from decimal import Decimal
from django.forms.widgets import FileInput

class MultipleFileInput(FileInput):
    """
    Custom file input widget that supports multiple file upload.
    """
    def __init__(self, attrs=None):
        super().__init__(attrs)
        self.attrs['multiple'] = 'multiple'
        
    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context['widget']['attrs']['multiple'] = 'multiple'
        return context

from .models import (
    Grower, Farm, PlantPart, Pest, SurveillanceRecord, Region,
    SEASON_CHOICES, CONFIDENCE_CHOICES, Disease, Observation, ObservationImage
)


class SignUpForm(forms.ModelForm):
    """Form for user registration and Grower profile creation."""
    # Fields for the User model
    password = forms.CharField(widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput)
    email = forms.EmailField(required=True)

    # Field for the Grower model
    farm_name = forms.CharField(max_length=100, required=True)
    contact_number = forms.CharField(max_length=20, required=False)

    class Meta:
        model = User
        fields = ['username', 'email', 'password']  # Fields from User model to include directly

    def clean_confirm_password(self):
        """Ensure passwords match."""
        password = self.cleaned_data.get('password')
        confirm_password = self.cleaned_data.get('confirm_password')
        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError("Passwords don't match")
        return confirm_password

    def save(self, commit=True):
        """
        Save the User instance and create the Grower profile.
        
        Args:
            commit: Whether to save to database
            
        Returns:
            User instance with associated Grower profile
        """
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
    """Form for creating and editing Farm instances."""
    # Region field (already exists)
    region = forms.ModelChoiceField(
        queryset=Region.objects.all(),
        empty_label=None,
        required=True
    )

    class Meta:
        model = Farm
        fields = [
            'name',
            'region',
            'has_exact_address',      # Added model field
            'geoscape_address_id',    # Added model field
            'formatted_address',      # Added model field
            'location_description',   # Existing field
            'size_hectares',
            'stocking_rate',
            'distribution_pattern'
        ]
        widgets = {
            'location_description': forms.Textarea(attrs={
                'rows': 2,
                'placeholder': 'e.g., "Near Katherine River", "Smith Property via XYZ Road"'
            }),
            # Use hidden inputs for API data
            'geoscape_address_id': forms.HiddenInput(),
            'formatted_address': forms.HiddenInput(),
            # Explicitly use CheckboxInput for clarity
            'has_exact_address': forms.CheckboxInput(),
        }
        labels = {
            'stocking_rate': 'Stocking Rate (plants per hectare)',
            'has_exact_address': 'Do you have an exact street address for this farm?'  # Add label for the checkbox
        }
        # Set fields as not required initially
        required = {
            'geoscape_address_id': False,
            'formatted_address': False,
            'has_exact_address': False,
            'location_description': False,  # Only required if no exact address
            'size_hectares': False,
            'stocking_rate': False,
        }

    def clean(self):
        """
        Validate form data for address fields.
        
        Returns:
            Cleaned data dictionary
        """
        cleaned_data = super().clean()
        has_exact = cleaned_data.get('has_exact_address')
        geoscape_id = cleaned_data.get('geoscape_address_id')
        formatted_addr = cleaned_data.get('formatted_address')
        location_desc = cleaned_data.get('location_description')

        if has_exact:
            # If checkbox is checked, require the hidden fields to have been populated by JS
            if not geoscape_id or not formatted_addr:
                # This error might be hard for users to see as fields are hidden.
                # Consider adding a non-field error or JS validation.
                raise ValidationError(
                    "An exact address was indicated, but address details were not selected. "
                    "Please use the address search."
                )
            # Clear location description if exact address is given
            cleaned_data['location_description'] = ''
        else:
            # Clear exact address fields if general location is used
            cleaned_data['geoscape_address_id'] = None
            cleaned_data['formatted_address'] = ''

        return cleaned_data


class UserEditForm(forms.ModelForm):
    """Form for editing user account details."""
    class Meta:
        model = User
        fields = ['username', 'email']  # Allow editing username and email


class GrowerProfileEditForm(forms.ModelForm):
    """Form for editing grower profile details."""
    class Meta:
        model = Grower
        fields = ['farm_name', 'contact_number']  # Fields from Grower model


class CalculatorForm(forms.Form):
    """Form for surveillance effort calculator."""
    farm = forms.ModelChoiceField(
        queryset=Farm.objects.none(),
        label="Select Your Farm",
        empty_label="-- Please Select a Farm --",
        required=False,  # Don't show required validation until form submission
    )
    confidence_level = forms.ChoiceField(
        choices=CONFIDENCE_CHOICES,  # Use choices from models.py
        required=False,  # Don't show required validation until form submission
        label="Desired Confidence Level"
    )

    def __init__(self, grower, *args, **kwargs):
        """
        Initialize form with a grower instance.
        
        Args:
            grower: Grower instance to filter farms
        """
        # Get the initial data, if any
        initial = kwargs.get('initial', {})

        # If a farm is selected in initial data, we can set defaults
        if 'farm' in initial and initial['farm']:
            farm = initial['farm']

            # Only set these defaults if explicitly coming from a link
            # Don't override any user selections from the form
            if kwargs.get('data') is None:
                # Set confidence level default to 95% if not specified
                if 'confidence_level' not in initial:
                    initial['confidence_level'] = 95

                # Update the kwargs with our modified initial data
                kwargs['initial'] = initial

        super().__init__(*args, **kwargs)

        # Populate farm choices based on the logged-in grower
        self.fields['farm'].queryset = Farm.objects.filter(owner=grower)

        # Additional setup for better user experience
        self.fields['farm'].widget.attrs.update({'class': 'form-select form-select-lg'})
        self.fields['confidence_level'].widget.attrs.update({'class': 'form-select'})

    def clean(self):
        """
        Validate form fields when submitted.
        
        Returns:
            Cleaned data dictionary
        """
        cleaned_data = super().clean()

        # Only validate when the form is actually submitted
        if self.is_bound and self.data:
            # Now enforce required fields
            if not cleaned_data.get('farm'):
                self.add_error('farm', 'Please select a farm.')
            if not cleaned_data.get('confidence_level'):
                self.add_error('confidence_level', 'Please select a confidence level.')

        return cleaned_data


class ObservationForm(forms.ModelForm):
    """Form for recording a single observation point within a survey session."""
    pests_observed = forms.ModelMultipleChoiceField(
        queryset=Pest.objects.all().order_by('name'),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Pests Observed at this Location"
    )
    diseases_observed = forms.ModelMultipleChoiceField(
        queryset=Disease.objects.all().order_by('name'),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Diseases Observed at this Location"
    )
    notes = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}),
        required=False
    )
    images = forms.FileField(
        widget=MultipleFileInput(attrs={'accept': 'image/*'}), 
        required=False,
        label="Upload Images (Optional)",
        help_text="Select one or more images related to this observation."
    )
    plant_sequence_number = forms.IntegerField(
        required=True, 
        min_value=1,
        label="Plant Sequence Number",
        help_text="Enter the number of the plant you just checked (e.g., 1, 5, 10...).",
        widget=forms.NumberInput(attrs={'min': '1'})
    )

    class Meta:
        model = Observation
        fields = ['plant_sequence_number', 'pests_observed', 'diseases_observed', 'notes']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)