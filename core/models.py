from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
import uuid
from datetime import timedelta

# Constants for choices
DISTRIBUTION_CHOICES = [
    ('uniform', 'Uniform'),
    ('clustered', 'Clustered'),
    ('random', 'Random'),
]

SEASON_CHOICES = [
    ('Wet', 'Wet Season'),
    ('Dry', 'Dry Season'),
    ('Flowering', 'Flowering Period'),
]

CONFIDENCE_CHOICES = [
    (90, '90%'),
    (95, '95%'),
    (99, '99%'),
]


class Grower(models.Model):
    """
    Represents a farm grower profile linked to a Django User account.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='grower_profile')
    farm_name = models.CharField(max_length=100)
    contact_number = models.CharField(max_length=20, blank=True, null=True)

    def __str__(self):
        return f"{self.user.username}'s Profile ({self.farm_name})"
    
    def recent_surveillance_records(self, limit=5):
        """
        Returns the most recent surveillance records across all farms.
        
        Args:
            limit: Maximum number of records to return
            
        Returns:
            QuerySet of SurveillanceRecord instances
        """
        return SurveillanceRecord.objects.filter(
            performed_by=self
        ).order_by('-date_performed')[:limit]
    
    def total_plants_managed(self):
        """
        Returns the total number of plants across all farms.
        
        Returns:
            Integer count of plants or None if no valid plant counts
        """
        # Use aggregate instead of iterating to improve performance
        from django.db.models import Sum, F, ExpressionWrapper, DecimalField
        
        farms_with_counts = self.farms.filter(
            size_hectares__isnull=False, 
            stocking_rate__isnull=False
        )
        
        total_expr = ExpressionWrapper(
            F('size_hectares') * F('stocking_rate'), 
            output_field=DecimalField()
        )
        
        result = farms_with_counts.aggregate(
            total=Sum(total_expr)
        )
        
        # Convert to int and handle None case
        total = result['total']
        return int(total) if total is not None else None


class Region(models.Model):
    """
    Represents a geographical region where farms may be located.
    """
    name = models.CharField(max_length=100, unique=True)
    climate_zone = models.CharField(max_length=50, blank=True, null=True)
    state_abbreviation = models.CharField(
        max_length=3, 
        blank=True, 
        null=True, 
        help_text="State/Territory abbreviation (e.g., NT, QLD, WA)"
    )

    def __str__(self):
        return self.name


class PlantType(models.Model):
    """
    Represents a type of plant (e.g., Mango, Avocado).
    """
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name


class PlantPart(models.Model):
    """
    Represents a specific part of a plant that can be checked during surveillance.
    """
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name


class Pest(models.Model):
    """
    Represents a pest that can affect plants.
    """
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    affects_plant_types = models.ManyToManyField(PlantType, related_name='pests', blank=True)
    affects_plant_parts = models.ManyToManyField(PlantPart, related_name='pests', blank=True)

    def __str__(self):
        return self.name
    
    @classmethod
    def get_priority_pests_for_season(cls, season, plant_type=None):
        """
        Returns priority pests based on season and plant type.
        (Placeholder: Orders differently by season for now)
        """
        queryset = cls.objects.all()
        if plant_type:
            queryset = queryset.filter(affects_plant_types=plant_type)
        
        # Placeholder: Change ordering based on season
        if season == 'Wet':
            queryset = queryset.order_by('name')
        else: # Dry or Flowering
            queryset = queryset.order_by('-name')
            
        return queryset[:3]


class Disease(models.Model):
    """
    Represents a disease that can affect plants.
    """
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    affects_plant_types = models.ManyToManyField(PlantType, related_name='diseases', blank=True)
    affects_plant_parts = models.ManyToManyField(PlantPart, related_name='diseases', blank=True)

    def __str__(self):
        return self.name
    
    # ADDED Placeholder Method
    @classmethod
    def get_priority_diseases_for_season(cls, season, plant_type=None):
        """
        Returns priority diseases based on season and plant type.
        (Placeholder: Orders differently by season for now)
        """
        queryset = cls.objects.all()
        if plant_type:
            queryset = queryset.filter(affects_plant_types=plant_type)

        # Placeholder: Change ordering based on season
        if season == 'Wet':
            queryset = queryset.order_by('-name')
        else: # Dry or Flowering
            queryset = queryset.order_by('name')
            
        return queryset[:3]


class SeasonalStage(models.Model):
    """
    Represents a specific stage in the farming cycle, mapping months 
    to expected pests, diseases, parts to check, and prevalence.
    This replaces the hardcoded logic in season_utils.py.
    """
    name = models.CharField(
        max_length=100, 
        unique=True, 
        help_text="Descriptive name for the stage (e.g., 'Flowering', 'Early Fruit Development')"
    )
    # Store months as a comma-separated string for simple querying
    # Example: "6,7,8" for June-August
    # Example: "11,12,1,2,3,4" for Nov-Apr (handled by query)
    months = models.CharField(
        max_length=50, 
        help_text="Comma-separated list of month numbers (1-12) this stage applies to. Handles year rollover."
    )
    prevalence_p = models.DecimalField(
        max_digits=4, 
        decimal_places=3, 
        help_text="Estimated pest/disease prevalence (e.g., 0.05 for 5%) during this stage, used in calculations."
    )
    active_pests = models.ManyToManyField(
        Pest, 
        related_name='seasonal_stages',
        blank=True,
        help_text="Pests that are typically active during this stage."
    )
    active_diseases = models.ManyToManyField(
        Disease, 
        related_name='seasonal_stages',
        blank=True,
        help_text="Diseases that are typically active during this stage."
    )

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['id'] # Or define a specific order if needed
        verbose_name = "Seasonal Stage Mapping"
        verbose_name_plural = "Seasonal Stage Mappings"


class Farm(models.Model):
    """
    Represents a farm managed by a grower.
    """
    owner = models.ForeignKey(Grower, on_delete=models.CASCADE, related_name='farms')
    name = models.CharField(max_length=100)
    region = models.ForeignKey(Region, on_delete=models.SET_NULL, null=True, blank=True, related_name='farms')
    size_hectares = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True, 
        help_text="Total farm size in hectares"
    )
    stocking_rate = models.IntegerField(
        null=True, 
        blank=True, 
        help_text="Number of plants per hectare"
    )
    plant_type = models.ForeignKey(
        PlantType, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='farms'
    )
    distribution_pattern = models.CharField(
        max_length=20,
        choices=DISTRIBUTION_CHOICES,
        default='uniform'
    )
    location_description = models.CharField(
        max_length=255, 
        blank=True, 
        null=True, 
        help_text="e.g., \"Near Katherine River\", \"Smith Property via XYZ Road\""
    )
    # Fields for Geoscape API address results
    geoscape_address_id = models.CharField(
        max_length=50, 
        blank=True, 
        null=True, 
        unique=True, # Assume one farm per Geoscape ID
        help_text="Unique identifier from Geoscape API for the selected address"
    )
    formatted_address = models.CharField(
        max_length=500, # Allow ample space for long addresses
        blank=True, 
        null=True, 
        help_text="Full address string selected via Geoscape API"
    )
    has_exact_address = models.BooleanField(
        default=False,
        help_text="Indicates if the user provided an exact address via search"
    )
    # GIS Field for storing the cadastral boundary
    boundary = models.JSONField(
        null=True,
        blank=True,
        help_text="Cadastral boundary polygon data (e.g., GeoJSON) from Geoscape API"
    )

    def __str__(self):
        return f"{self.name} (Owner: {self.owner.user.username})"

    def total_plants(self):
        """
        Calculate the total number of plants on the farm.
        
        Returns:
            Integer count of plants or None if size or stocking rate not set
        """
        if self.size_hectares and self.stocking_rate:
            # Convert from Decimal to int for a clean integer result
            return int(self.size_hectares * Decimal(str(self.stocking_rate)))
        return None
    
    def current_season(self):
        """
        Determine the current season based on month.
        
        Returns:
            String representing the current season ('Wet', 'Dry', or 'Flowering')
        """
        current_month = timezone.now().month
        if 5 <= current_month <= 10:  # May-Oct
            return 'Dry'
        return 'Wet'  # Nov-Apr
    
    def last_surveillance_date(self):
        """
        Return the date of the most recent surveillance record.
        
        Returns:
            Datetime of last surveillance or None if no records
        """
        last_record = self.surveillance_records.order_by('-date_performed').first()
        return last_record.date_performed if last_record else None
    
    def next_due_date(self):
        """
        Calculate the next due date for surveillance.
        
        Returns:
            Date object for next recommended surveillance
        """
        # Default to 7 days after last surveillance, or today if none
        last_date = self.last_surveillance_date()
        if last_date:
            return last_date + timezone.timedelta(days=7)
        return timezone.now().date()


class SurveillanceRecord(models.Model):
    """
    Represents a record of a surveillance activity performed on a farm.
    """
    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name='surveillance_records')
    performed_by = models.ForeignKey(Grower, on_delete=models.CASCADE, related_name='surveillance_records')
    date_performed = models.DateTimeField(default=timezone.now)
    plants_surveyed = models.IntegerField()
    plant_parts_checked = models.ManyToManyField(PlantPart, related_name='surveillance_records', blank=True)
    pests_found = models.ManyToManyField(Pest, related_name='surveillance_records', blank=True)
    diseases_found = models.ManyToManyField(Disease, related_name='surveillance_records', blank=True)
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Survey on {self.farm.name} - {self.date_performed.strftime('%Y-%m-%d %H:%M')}"
    
    def coverage_percentage(self):
        """
        Calculate what percentage of the farm was surveyed.
        
        Returns:
            Float percentage or None if cannot calculate
        """
        total_plants = self.farm.total_plants()
        if total_plants and self.plants_surveyed:
            return round((self.plants_surveyed / total_plants) * 100, 1)
        return None


class SurveillanceCalculation(models.Model):
    """
    Stores historical records of surveillance calculations for farms.
    """
    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name='calculations')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='calculations')
    date_created = models.DateTimeField(default=timezone.now)
    
    # Input parameters
    season = models.CharField(max_length=20, choices=SEASON_CHOICES)
    confidence_level = models.IntegerField(choices=CONFIDENCE_CHOICES)
    
    # Calculation parameters
    population_size = models.IntegerField(help_text="Total number of plants in the farm")
    prevalence_percent = models.DecimalField(max_digits=5, decimal_places=2, help_text="Assumed pest prevalence percentage")
    margin_of_error = models.DecimalField(max_digits=5, decimal_places=2, default=5.00, help_text="Margin of error percentage")
    
    # Results
    required_plants = models.IntegerField(help_text="Number of plants that should be surveyed")
    percentage_of_total = models.DecimalField(max_digits=5, decimal_places=2, help_text="Percentage of total plants to survey")
    survey_frequency = models.IntegerField(null=True, blank=True, help_text="Recommended survey frequency (1 in X plants)")
    
    # Metadata
    is_current = models.BooleanField(default=True, help_text="Whether this is the current calculation for this farm")
    notes = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-date_created']
        
    def __str__(self):
        return f"Calculation for {self.farm.name} - {self.date_created.strftime('%Y-%m-%d')}"
        
    def save(self, *args, **kwargs):
        # When saving a new record as current, mark all other records for this farm as not current
        if self.is_current:
            SurveillanceCalculation.objects.filter(farm=self.farm, is_current=True).update(is_current=False)
        super().save(*args, **kwargs)


class BoundaryMappingToken(models.Model):
    """
    Stores a temporary, unique token for mapping a farm boundary.
    """
    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name='mapping_tokens')
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    def save(self, *args, **kwargs):
        # Set expiration time (e.g., 24 hours from creation)
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(hours=24)
        super().save(*args, **kwargs)

    def is_valid(self):
        """
        Check if the token is still valid.
        
        Returns:
            Boolean indicating if the token is still valid
        """
        return self.expires_at > timezone.now()

    def __str__(self):
        return f"Token for {self.farm.name} (Expires: {self.expires_at.strftime('%Y-%m-%d %H:%M')})"