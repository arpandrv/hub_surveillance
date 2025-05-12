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

SURVEY_STATUS_CHOICES = [
    ('not_started', 'Not Started'),
    ('in_progress', 'In Progress'),
    ('completed', 'Completed'),
    ('abandoned', 'Abandoned'),
]

OBSERVATION_STATUS_CHOICES = [
    ('draft', 'Draft'),         # For auto-save
    ('completed', 'Completed'),   # For final save
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
            limit (int): Maximum number of records to return
            
        Returns:
            QuerySet: Recent SurveillanceRecord instances, ordered by date
        """
        return SurveillanceRecord.objects.filter(
            performed_by=self
        ).order_by('-date_performed')[:limit]
    
    def total_plants_managed(self):
        """
        Returns the total number of plants across all farms using efficient aggregation.
        
        Returns:
            int or None: Total number of plants or None if no valid plant counts
        """
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
    Represents a type of plant (e.g., Mango, Avocado) that can be grown on farms.
    
    This is a core model used throughout the application to associate pests, diseases,
    and farming practices with specific types of plants.
    """
    name = models.CharField(max_length=100, unique=True, db_index=True)
    description = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = "Plant Type"
        verbose_name_plural = "Plant Types"

    def __str__(self):
        return self.name
        
    def get_farms(self):
        """
        Get all farms growing this plant type.
        
        Returns:
            QuerySet: Farm instances growing this plant type
        """
        return self.farms.all()
        
    def get_pests(self):
        """
        Get all pests that can affect this plant type.
        
        Returns:
            QuerySet: Pest instances that affect this plant type
        """
        return self.pests.all()
        
    def get_diseases(self):
        """
        Get all diseases that can affect this plant type.
        
        Returns:
            QuerySet: Disease instances that affect this plant type
        """
        return self.diseases.all()


class PlantPart(models.Model):
    """
    Represents a specific part of a plant that can be checked during surveillance.
    
    Different plant parts may be susceptible to different pests and diseases,
    and seasonal recommendations often include specific parts to inspect.
    """
    name = models.CharField(max_length=50, unique=True, db_index=True)
    description = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = "Plant Part"
        verbose_name_plural = "Plant Parts"

    def __str__(self):
        return self.name
        
    def get_pests(self):
        """
        Get all pests that affect this plant part.
        
        Returns:
            QuerySet: Pest instances that affect this plant part
        """
        return self.pests.all()
        
    def get_diseases(self):
        """
        Get all diseases that affect this plant part.
        
        Returns:
            QuerySet: Disease instances that affect this plant part
        """
        return self.diseases.all()


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
        
        Args:
            season (str): Season name ('Wet', 'Dry', or 'Flowering')
            plant_type (PlantType, optional): Filter by plant type
            
        Returns:
            QuerySet: Top 3 priority pests for the season and plant type
        """
        queryset = cls.objects.all()
        if plant_type:
            queryset = queryset.filter(affects_plant_types=plant_type)
        
        # Change ordering based on season
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
    
    @classmethod
    def get_priority_diseases_for_season(cls, season, plant_type=None):
        """
        Returns priority diseases based on season and plant type.
        
        Args:
            season (str): Season name ('Wet', 'Dry', or 'Flowering')
            plant_type (PlantType, optional): Filter by plant type
            
        Returns:
            QuerySet: Top 3 priority diseases for the season and plant type
        """
        queryset = cls.objects.all()
        if plant_type:
            queryset = queryset.filter(affects_plant_types=plant_type)

        # Change ordering based on season
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
    Represents a farm managed by a grower for agricultural surveillance purposes.
    
    This model stores information about a farm including its physical characteristics,
    location details, and relationship to plant types and growing patterns.
    """
    owner = models.ForeignKey(
        Grower, 
        on_delete=models.CASCADE, 
        related_name='farms',
        db_index=True
    )
    name = models.CharField(max_length=100, db_index=True)
    region = models.ForeignKey(
        Region, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='farms'
    )
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
    geoscape_address_id = models.CharField(
        max_length=50, 
        blank=True, 
        null=True, 
        unique=True, 
        help_text="Unique identifier from Geoscape API for the selected address"
    )
    formatted_address = models.CharField(
        max_length=500,
        blank=True, 
        null=True, 
        help_text="Full address string selected via Geoscape API"
    )
    has_exact_address = models.BooleanField(
        default=False,
        help_text="Indicates if the user provided an exact address via search"
    )
    boundary = models.JSONField(
        null=True,
        blank=True,
        help_text="Cadastral boundary polygon data (e.g., GeoJSON) from Geoscape API"
    )
    
    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['owner']),
            models.Index(fields=['plant_type']),
            models.Index(fields=['region']),
        ]

    def __str__(self):
        return self.name
    
    def total_plants(self):
        """
        Calculate the total number of plants on the farm.
        
        Returns:
            int or None: Total plant count or None if required fields are missing
        """
        if self.size_hectares is None or self.stocking_rate is None:
            return None
            
        # Cast Decimal to float first to avoid precision issues
        return int(float(self.size_hectares) * self.stocking_rate)
    
    def current_season(self):
        """
        Determine the current season based on month.
        
        Returns:
            str: Season name ('Wet', 'Dry', or 'Flowering')
        """
        current_month = timezone.now().month
        
        # Use a mapping dictionary for cleaner code
        season_map = {
            1: 'Wet', 2: 'Wet', 3: 'Wet',  # Jan-Mar: Wet season
            4: 'Flowering', 5: 'Flowering', 6: 'Flowering', 7: 'Flowering',  # Apr-Jul: Flowering
            8: 'Dry', 9: 'Dry', 10: 'Dry',  # Aug-Oct: Dry season
            11: 'Wet', 12: 'Wet'  # Nov-Dec: Wet season
        }
        
        return season_map.get(current_month, 'Unknown')
    
    def last_surveillance_date(self):
        """
        Return the date of the most recent surveillance record.
        
        Returns:
            datetime or None: Date of last surveillance or None if no records
        """
        latest = self.surveillance_records.order_by('-date_performed').first()
        return latest.date_performed if latest else None
        
    def days_since_last_surveillance(self):
        """
        Calculate the number of days since the last surveillance check.
        
        Returns:
            int or None: Number of days since last check, or None if never checked
        """
        last_date = self.last_surveillance_date()
        if not last_date:
            return None
            
        # Ensure we're working with date objects
        if isinstance(last_date, datetime):
            last_date = last_date.date()
            
        today = timezone.now().date()
        return (today - last_date).days
    
    def next_due_date(self):
        """
        Calculate the next due date for surveillance based on a 30-day cycle.
        
        Returns:
            date: Recommended date for next surveillance
        """
        last_date = self.last_surveillance_date()
        today = timezone.now().date()
        
        if not last_date:
            return today
            
        thirty_days_after = last_date.date() if isinstance(last_date, datetime) else last_date + timedelta(days=30)
        
        return today if thirty_days_after <= today else thirty_days_after
    
    def active_survey_sessions(self):
        """
        Returns active (not completed or abandoned) survey sessions for this farm.
        
        Returns:
            QuerySet: Active SurveySession instances
        """
        return self.survey_sessions.filter(status__in=['not_started', 'in_progress'])
    
    def completed_survey_sessions(self):
        """
        Returns completed survey sessions for this farm.
        
        Returns:
            QuerySet: Completed SurveySession instances
        """
        return self.survey_sessions.filter(status='completed')
        
    def has_active_sessions(self):
        """
        Check if the farm has any active survey sessions in progress.
        
        Returns:
            bool: True if there are active sessions, False otherwise
        """
        return self.active_survey_sessions().exists()
        
    def get_seasonal_recommendations(self):
        """
        Get season-appropriate pest and disease recommendations for this farm.
        
        Returns:
            dict: Dictionary containing recommended pests, diseases, and plant parts
        """
        current_season = self.current_season()
        
        # Get recommendations based on farm's plant type if available
        recommended_pests = Pest.get_priority_pests_for_season(current_season, self.plant_type)
        recommended_diseases = Disease.get_priority_diseases_for_season(current_season, self.plant_type)
        
        # Get seasonal plant parts to check from SeasonalStage
        try:
            from django.db.models import Q
            current_month = timezone.now().month
            stage = SeasonalStage.objects.filter(Q(months__contains=str(current_month))).first()
            
            # Get plant parts specific to this stage, or default to common ones
            if stage and hasattr(stage, 'plant_parts_to_check'):
                plant_parts = stage.plant_parts_to_check.all()
            else:
                # Fallback to most common plant parts
                plant_parts = PlantPart.objects.all()[:3]
                
        except Exception:
            # Fallback if relationship doesn't exist
            plant_parts = PlantPart.objects.all()[:3]
            
        return {
            'pests': recommended_pests,
            'diseases': recommended_diseases,
            'plant_parts': plant_parts,
            'season': current_season
        }


class SurveillanceRecord(models.Model):
    """
    Represents a record of a surveillance activity performed on a farm.
    
    This model is used for the original surveillance tracking functionality
    before the more detailed SurveySession/Observation system was implemented.
    It's maintained for backward compatibility with existing data.
    """
    farm = models.ForeignKey(
        Farm, 
        on_delete=models.CASCADE, 
        related_name='surveillance_records',
        db_index=True
    )
    performed_by = models.ForeignKey(
        Grower, 
        on_delete=models.CASCADE, 
        related_name='surveillance_records',
        db_index=True
    )
    date_performed = models.DateTimeField(
        default=timezone.now,
        db_index=True
    )
    plants_surveyed = models.IntegerField()
    plant_parts_checked = models.ManyToManyField(
        PlantPart, 
        related_name='surveillance_records', 
        blank=True
    )
    pests_found = models.ManyToManyField(
        Pest, 
        related_name='surveillance_records', 
        blank=True
    )
    diseases_found = models.ManyToManyField(
        Disease, 
        related_name='surveillance_records', 
        blank=True
    )
    notes = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-date_performed']
        verbose_name = "Surveillance Record"
        verbose_name_plural = "Surveillance Records"
        indexes = [
            models.Index(fields=['farm', '-date_performed']),
            models.Index(fields=['performed_by', '-date_performed']),
        ]

    def __str__(self):
        return f"Survey at {self.farm.name} on {self.date_performed.strftime('%Y-%m-%d')}"

    def coverage_percentage(self):
        """
        Calculate what percentage of the farm was surveyed.
        
        Returns:
            float or None: Percentage of plants surveyed or None if cannot calculate
        """
        total_plants = self.farm.total_plants()
        if not total_plants:
            return None
        return round((self.plants_surveyed / total_plants) * 100, 1)
        
    def has_findings(self):
        """
        Check if any pests or diseases were found during surveillance.
        
        Returns:
            bool: True if any pests or diseases were found
        """
        return self.pests_found.exists() or self.diseases_found.exists()
        
    def create_summary(self):
        """
        Create a textual summary of the surveillance findings.
        
        Returns:
            str: Summary of surveillance findings
        """
        pest_count = self.pests_found.count()
        disease_count = self.diseases_found.count()
        parts_checked = self.plant_parts_checked.count()
        
        summary = f"Surveyed {self.plants_surveyed} plants"
        if parts_checked > 0:
            part_names = ", ".join([p.name for p in self.plant_parts_checked.all()])
            summary += f", checking {part_names}"
        
        if pest_count > 0 or disease_count > 0:
            summary += ". Found "
            findings = []
            if pest_count > 0:
                findings.append(f"{pest_count} pest{'s' if pest_count != 1 else ''}")
            if disease_count > 0:
                findings.append(f"{disease_count} disease{'s' if disease_count != 1 else ''}")
            summary += " and ".join(findings)
        else:
            summary += ". No pests or diseases found"
            
        return summary


class SurveillanceCalculation(models.Model):
    """
    Stores historical records of surveillance calculations for farms.
    
    These calculations determine how many plants should be surveyed
    based on statistical parameters like confidence level and prevalence.
    """
    farm = models.ForeignKey(
        Farm, 
        on_delete=models.CASCADE, 
        related_name='calculations',
        db_index=True
    )
    created_by = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='calculations',
        db_index=True
    )
    date_created = models.DateTimeField(
        default=timezone.now,
        db_index=True
    )
    season = models.CharField(
        max_length=20, 
        choices=SEASON_CHOICES,
        db_index=True
    )
    confidence_level = models.IntegerField(
        choices=CONFIDENCE_CHOICES,
        help_text="Statistical confidence level for the calculation"
    )
    population_size = models.IntegerField(
        help_text="Total number of plants in the farm"
    )
    prevalence_percent = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        help_text="Assumed pest prevalence percentage"
    )
    margin_of_error = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=5.00, 
        help_text="Margin of error percentage"
    )
    required_plants = models.IntegerField(
        help_text="Number of plants that should be surveyed"
    )
    percentage_of_total = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        help_text="Percentage of total plants to survey"
    )
    survey_frequency = models.IntegerField(
        null=True, 
        blank=True, 
        help_text="Recommended survey frequency (1 in X plants)"
    )
    is_current = models.BooleanField(
        default=True, 
        db_index=True,
        help_text="Whether this is the current calculation for this farm"
    )
    notes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-date_created']
        verbose_name = "Surveillance Calculation"
        verbose_name_plural = "Surveillance Calculations"
        indexes = [
            models.Index(fields=['farm', '-date_created']),
            models.Index(fields=['farm', 'is_current']),
        ]

    def __str__(self):
        return f"{self.farm.name} calculation from {self.date_created.strftime('%Y-%m-%d')}"

    def save(self, *args, **kwargs):
        """
        Override save to ensure only one calculation is current for a farm.
        
        When a calculation is marked as current, all other calculations for
        the same farm are automatically set to not current.
        """
        if self.is_current:
            # Set all other calculations for this farm as not current
            SurveillanceCalculation.objects.filter(
                farm=self.farm, 
                is_current=True
            ).exclude(pk=self.pk).update(is_current=False)
        super().save(*args, **kwargs)
        
    def get_confidence_level_display_text(self):
        """
        Get a human-readable display of the confidence level.
        
        Returns:
            str: Formatted confidence level text
        """
        return f"{self.get_confidence_level_display()}% confidence"
        
    def get_prevalence_display_text(self):
        """
        Get a human-readable display of the prevalence percentage.
        
        Returns:
            str: Formatted prevalence text
        """
        return f"{self.prevalence_percent}% prevalence"
        
    def to_dict(self):
        """
        Convert calculation to a dictionary for API responses.
        
        Returns:
            dict: Dictionary representation of the calculation
        """
        return {
            'id': self.id,
            'farm_id': self.farm.id,
            'farm_name': self.farm.name,
            'date_created': self.date_created,
            'season': self.season,
            'confidence_level': self.confidence_level,
            'prevalence_percent': float(self.prevalence_percent),
            'margin_of_error': float(self.margin_of_error),
            'population_size': self.population_size,
            'required_plants': self.required_plants,
            'percentage_of_total': float(self.percentage_of_total),
            'survey_frequency': self.survey_frequency,
            'is_current': self.is_current
        }


class BoundaryMappingToken(models.Model):
    """
    Stores a temporary, unique token for mapping a farm boundary.
    
    These tokens are used to authenticate mobile devices when they 
    submit boundary coordinates for a farm, without requiring the 
    full user login credentials.
    """
    farm = models.ForeignKey(
        Farm, 
        on_delete=models.CASCADE, 
        related_name='mapping_tokens',
        db_index=True
    )
    token = models.UUIDField(
        default=uuid.uuid4, 
        editable=False, 
        unique=True, 
        db_index=True
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True
    )
    expires_at = models.DateTimeField(
        db_index=True,
        help_text="When this token will expire and become invalid"
    )
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Boundary Mapping Token"
        verbose_name_plural = "Boundary Mapping Tokens"
        indexes = [
            models.Index(fields=['farm', '-created_at']),
            models.Index(fields=['expires_at']),
        ]

    def save(self, *args, **kwargs):
        """
        Override save to set default expiration time if not provided.
        """
        if not self.expires_at:
            # Default expiration is 1 day from creation
            self.expires_at = timezone.now() + timezone.timedelta(days=1)
        super().save(*args, **kwargs)

    def is_valid(self):
        """
        Check if the token is still valid (not expired).
        
        Returns:
            bool: True if the token is still valid, False otherwise
        """
        return timezone.now() < self.expires_at
        
    def time_until_expiry(self):
        """
        Calculate time remaining until token expiry.
        
        Returns:
            timedelta: Time remaining until expiry
        """
        return self.expires_at - timezone.now()
        
    def extend_expiry(self, hours=24):
        """
        Extend the token's expiration time.
        
        Args:
            hours (int): Number of hours to extend the expiry time
            
        Returns:
            BoundaryMappingToken: The updated token instance
        """
        self.expires_at = timezone.now() + timezone.timedelta(hours=hours)
        self.save()
        return self

    def __str__(self):
        return f"Mapping token for {self.farm.name} (Expires: {self.expires_at.strftime('%Y-%m-%d %H:%M')})"


# ---> NEW MODELS FOR PER-LOCATION SURVEILLANCE <---

class SurveySessionManager(models.Manager):
    """
    Custom manager for the SurveySession model, providing helpful querysets.
    """
    def active(self):
        """Return only active sessions (not completed or abandoned)"""
        return self.filter(status__in=['not_started', 'in_progress'])
        
    def completed(self):
        """Return only completed sessions"""
        return self.filter(status='completed')
        
    def abandoned(self):
        """Return only abandoned sessions"""
        return self.filter(status='abandoned')
        
    def by_farm(self, farm_id):
        """Return sessions for a specific farm"""
        return self.filter(farm_id=farm_id)
        
    def recent(self, limit=10):
        """Return most recent sessions"""
        return self.all().order_by('-start_time')[:limit]


class SurveySession(models.Model):
    """
    Represents a single, distinct surveillance activity undertaken by a user for a specific farm.
    
    A survey session contains multiple observations and tracks the overall surveillance
    activity from start to finish, including status and timing information.
    """
    farm = models.ForeignKey(
        Farm, 
        on_delete=models.CASCADE, 
        related_name='survey_sessions',
        db_index=True
    )
    surveyor = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='survey_sessions',
        db_index=True,
        help_text="The user who performed the survey."
    )
    start_time = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        help_text="Timestamp when the survey session was initiated."
    )
    end_time = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="Timestamp when the survey session was marked as completed."
    )
    status = models.CharField(
        max_length=20, 
        choices=SURVEY_STATUS_CHOICES, 
        default='not_started',
        db_index=True,
        help_text="The current status of the survey session."
    )
    target_plants_surveyed = models.PositiveIntegerField(
        null=True, 
        blank=True, 
        help_text="Recommended number of plants based on calculation at session start."
    )
    session_id = models.UUIDField(
        default=uuid.uuid4, 
        editable=False, 
        unique=True, 
        db_index=True,
        help_text="Unique ID for this specific session instance."
    )
    
    # Add custom manager
    objects = SurveySessionManager()

    class Meta:
        ordering = ['-start_time']
        verbose_name = "Survey Session"
        verbose_name_plural = "Survey Sessions"
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['farm', 'status']),
            models.Index(fields=['surveyor', '-start_time']),
        ]
    
    def __str__(self):
        return f"Survey on {self.farm.name} ({self.start_time.strftime('%Y-%m-%d')})"

    def get_status_badge_class(self):
        """
        Returns a Bootstrap background class based on session status.
        
        Returns:
            str: CSS class for the appropriate badge color
        """
        status_classes = {
            'not_started': 'bg-secondary',
            'in_progress': 'bg-primary',
            'completed': 'bg-success',
            'abandoned': 'bg-danger'
        }
        return status_classes.get(self.status, 'bg-secondary')
    
    def duration(self):
        """
        Calculate the duration of the survey session in minutes if completed.
        
        Returns:
            float or None: Duration in minutes rounded to 1 decimal place, or None if incomplete
        """
        if not self.end_time or self.status not in ['completed', 'abandoned']:
            return None
            
        duration = self.end_time - self.start_time
        return round(duration.total_seconds() / 60, 1)
        
    def observation_count(self):
        """
        Get the count of completed observations in this session.
        
        Returns:
            int: Number of completed observations
        """
        return self.observations.filter(status='completed').count()
        
    def is_active(self):
        """
        Check if this session is currently active (not completed or abandoned).
        
        Returns:
            bool: True if the session is active, False otherwise
        """
        return self.status in ['not_started', 'in_progress']
        
    def get_progress_percentage(self):
        """
        Calculate the percentage of completion based on observations vs target.
        
        Returns:
            int: Percentage of completion (0-100)
        """
        if not self.target_plants_surveyed or self.target_plants_surveyed <= 0:
            return 0
            
        completed = self.observation_count()
        percentage = (completed / self.target_plants_surveyed) * 100
        
        # Ensure value is between 0-100
        return min(max(int(percentage), 0), 100)
        
    def get_unique_pests(self):
        """
        Get all unique pests observed across all observations in this session.
        
        Returns:
            QuerySet: Unique Pest instances
        """
        return Pest.objects.filter(observations__session=self, observations__status='completed').distinct()
        
    def get_unique_diseases(self):
        """
        Get all unique diseases observed across all observations in this session.
        
        Returns:
            QuerySet: Unique Disease instances
        """
        return Disease.objects.filter(observations__session=self, observations__status='completed').distinct()
        
    def summarize(self):
        """
        Generate a summary of the surveillance session.
        
        Returns:
            dict: Summary information including counts, timing, and findings
        """
        return {
            'id': self.session_id,
            'farm_name': self.farm.name,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'status': self.status,
            'duration_minutes': self.duration(),
            'observations_count': self.observation_count(),
            'target_plants': self.target_plants_surveyed,
            'progress_percentage': self.get_progress_percentage(),
            'unique_pests_count': self.get_unique_pests().count(),
            'unique_diseases_count': self.get_unique_diseases().count(),
            'surveyor_name': f"{self.surveyor.first_name} {self.surveyor.last_name}".strip() or self.surveyor.username
        }

class ObservationManager(models.Manager):
    """
    Custom manager for the Observation model providing helpful querysets.
    """
    def completed(self):
        """Return only completed observations"""
        return self.filter(status='completed')
        
    def drafts(self):
        """Return only draft observations"""
        return self.filter(status='draft')
        
    def with_pests(self):
        """Return only observations that have pests recorded"""
        return self.filter(pests_observed__isnull=False).distinct()
        
    def with_diseases(self):
        """Return only observations that have diseases recorded"""
        return self.filter(diseases_observed__isnull=False).distinct()
        
    def with_coordinates(self):
        """Return only observations that have valid coordinates"""
        return self.filter(latitude__isnull=False, longitude__isnull=False)
        
    def by_session(self, session_id):
        """Return observations for a specific session"""
        return self.filter(session__session_id=session_id)


class Observation(models.Model):
    """
    Represents a single data point recorded at a specific location during a SurveySession.
    
    Each observation records the presence of pests or diseases at a specific plant location,
    along with GPS coordinates, timestamp, and optional images and notes.
    """
    session = models.ForeignKey(
        SurveySession, 
        on_delete=models.CASCADE, 
        related_name='observations',
        db_index=True
    )
    observation_time = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        help_text="Timestamp when this specific observation was recorded."
    )
    latitude = models.DecimalField(
        max_digits=12, 
        decimal_places=9, 
        null=True, 
        blank=True,
        help_text="Latitude coordinate (WGS84)."
    )
    longitude = models.DecimalField(
        max_digits=12, 
        decimal_places=9, 
        null=True, 
        blank=True,
        help_text="Longitude coordinate (WGS84)."
    )
    gps_accuracy = models.DecimalField(
        max_digits=6, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Estimated accuracy of the GPS coordinates in meters."
    )
    pests_observed = models.ManyToManyField(
        Pest, 
        related_name='observations', 
        blank=True
    )
    diseases_observed = models.ManyToManyField(
        Disease, 
        related_name='observations', 
        blank=True
    )
    notes = models.TextField(blank=True, null=True)
    plant_sequence_number = models.PositiveIntegerField(
        null=True, 
        blank=True, 
        db_index=True,
        help_text="Sequential number of the plant checked in this session (e.g., 1, 2, 3...)"
    )
    status = models.CharField(
        max_length=10,
        choices=OBSERVATION_STATUS_CHOICES,
        default='draft',
        db_index=True,
        help_text="Status of the observation (Draft or Completed)"
    )
    
    # Add custom manager
    objects = ObservationManager()

    class Meta:
        ordering = ['observation_time']
        verbose_name = "Observation Point"
        verbose_name_plural = "Observation Points"
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['session', 'status']),
            models.Index(fields=['observation_time']),
            models.Index(fields=['plant_sequence_number']),
        ]
    
    def __str__(self):
        return f"Observation {self.plant_sequence_number or 'n/a'} on {self.observation_time.strftime('%Y-%m-%d %H:%M')}"
        
    def has_coordinates(self):
        """
        Check if the observation has valid latitude and longitude coordinates.
        
        Returns:
            bool: True if valid coordinates exist, False otherwise
        """
        return self.latitude is not None and self.longitude is not None
        
    def has_pests(self):
        """
        Check if any pests were recorded in this observation.
        
        Returns:
            bool: True if pests were recorded, False otherwise
        """
        return self.pests_observed.exists()
        
    def has_diseases(self):
        """
        Check if any diseases were recorded in this observation.
        
        Returns:
            bool: True if diseases were recorded, False otherwise
        """
        return self.diseases_observed.exists()
        
    def has_images(self):
        """
        Check if any images are associated with this observation.
        
        Returns:
            bool: True if images exist, False otherwise
        """
        return self.images.exists()
        
    def finalize(self, save=True):
        """
        Mark the observation as completed.
        
        Args:
            save (bool): Whether to save the changes to the database
            
        Returns:
            Observation: The updated observation instance
        """
        self.status = 'completed'
        if save:
            self.save()
        return self
        
    def to_dict(self):
        """
        Convert observation to a dictionary for API responses.
        
        Returns:
            dict: Dictionary representation of the observation
        """
        return {
            'id': self.id,
            'observation_time': self.observation_time,
            'latitude': float(self.latitude) if self.latitude else None,
            'longitude': float(self.longitude) if self.longitude else None,
            'gps_accuracy': float(self.gps_accuracy) if self.gps_accuracy else None,
            'plant_sequence_number': self.plant_sequence_number,
            'status': self.status,
            'notes': self.notes,
            'pests': list(self.pests_observed.values('id', 'name')),
            'diseases': list(self.diseases_observed.values('id', 'name')),
            'has_images': self.has_images(),
            'image_count': self.images.count()
        }


# Function to define upload path for observation images
def observation_image_path(instance, filename):
    """
    Determines the file path for uploaded observation images.
    
    Args:
        instance (ObservationImage): The image instance being uploaded
        filename (str): Original filename of the uploaded image
        
    Returns:
        str: Path where the file should be stored
    """
    # Get the session UUID for organizing images
    session_uuid = instance.observation.session.session_id
    
    # Ensure filename doesn't have problematic characters
    import re
    safe_filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
    
    # Add a unique identifier to prevent filename collisions
    import uuid
    unique_prefix = str(uuid.uuid4())[:8]
    
    # file will be uploaded to: MEDIA_ROOT/survey_images/<session_uuid>/<unique>_<filename>
    return f'survey_images/{session_uuid}/{unique_prefix}_{safe_filename}'


class ObservationImage(models.Model):
    """
    Stores an image associated with a specific Observation point.
    
    These images are uploaded during surveillance and provide visual evidence
    of pest/disease presence or other notable conditions in the field.
    Requires Pillow to be installed and MEDIA_ROOT/MEDIA_URL configured.
    """
    observation = models.ForeignKey(
        Observation, 
        on_delete=models.CASCADE, 
        related_name='images',
        db_index=True
    )
    image = models.ImageField(upload_to=observation_image_path)
    caption = models.CharField(max_length=255, blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['uploaded_at']
        verbose_name = "Observation Image"
        verbose_name_plural = "Observation Images"
        indexes = [
            models.Index(fields=['observation']),
            models.Index(fields=['uploaded_at']),
        ]

    def __str__(self):
        return f"Image for Observation {self.observation.id} uploaded at {self.uploaded_at.strftime('%Y-%m-%d %H:%M')}"
    
    def get_file_size(self):
        """
        Get the file size of the image in KB.
        
        Returns:
            float: Size of the image in KB or 0 if file doesn't exist
        """
        try:
            return self.image.size / 1024  # Convert bytes to KB
        except:
            return 0
    
    def get_thumbnail_url(self):
        """
        Get URL for thumbnail version of the image.
        This is a placeholder for future image processing features.
        
        Returns:
            str: URL to the thumbnail or full image if thumbnail doesn't exist
        """
        # In the future, this could use django-imagekit or similar
        # for now, just return the regular URL
        return self.image.url

# ---> END NEW MODELS <---