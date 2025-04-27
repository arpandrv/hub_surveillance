from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal

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
        """Returns the most recent surveillance records across all farms."""
        return SurveillanceRecord.objects.filter(
            performed_by=self
        ).order_by('-date_performed')[:limit]
    
    def total_plants_managed(self):
        """Returns the total number of plants across all farms."""
        total = 0
        for farm in self.farms.all():
            plants = farm.total_plants()
            if plants:
                total += plants
        return total if total > 0 else None

class Region(models.Model):
    """
    Represents a geographical region where farms may be located.
    """
    name = models.CharField(max_length=100, unique=True)
    climate_zone = models.CharField(max_length=50, blank=True, null=True)

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
        """Returns priority pests based on season and plant type."""
        # This method would normally have more advanced logic,
        # but for now we'll return a simple filter
        queryset = cls.objects.all()
        if plant_type:
            queryset = queryset.filter(affects_plant_types=plant_type)
        return queryset[:3]  # Return top 3 as an example

class SurveillanceRecord(models.Model):
    """
    Represents a record of a surveillance activity performed on a farm.
    """
    farm = models.ForeignKey('Farm', on_delete=models.CASCADE, related_name='surveillance_records')
    performed_by = models.ForeignKey(Grower, on_delete=models.CASCADE, related_name='surveillance_records')
    date_performed = models.DateTimeField(default=timezone.now)
    plants_surveyed = models.IntegerField()
    plant_parts_checked = models.ManyToManyField(PlantPart, related_name='surveillance_records', blank=True)
    pests_found = models.ManyToManyField(Pest, related_name='surveillance_records', blank=True)
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Survey on {self.farm.name} - {self.date_performed.strftime('%Y-%m-%d %H:%M')}"
    
    def coverage_percentage(self):
        """Calculate what percentage of the farm was surveyed."""
        total_plants = self.farm.total_plants()
        if total_plants and self.plants_surveyed:
            return round((self.plants_surveyed / total_plants) * 100, 1)
        return None

class Farm(models.Model):
    """
    Represents a farm managed by a grower.
    """
    DISTRIBUTION_CHOICES = [
        ('uniform', 'Uniform'),
        ('clustered', 'Clustered'),
        ('random', 'Random'),
    ]

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

    def total_plants(self):
        """Calculate the total number of plants on the farm."""
        if self.size_hectares and self.stocking_rate:
            # Convert from Decimal to int for a clean integer result
            return int(self.size_hectares * Decimal(str(self.stocking_rate)))
        return None
    
    def current_season(self):
        """Determine the current season based on month."""
        current_month = timezone.now().month
        if 5 <= current_month <= 10:  # May-Oct
            return 'Dry'
        return 'Wet'  # Nov-Apr
    
    def last_surveillance_date(self):
        """Return the date of the most recent surveillance record."""
        last_record = self.surveillance_records.order_by('-date_performed').first()
        return last_record.date_performed if last_record else None
    
    def next_due_date(self):
        """Calculate the next due date for surveillance."""
        # Default to 7 days after last surveillance, or today if none
        last_date = self.last_surveillance_date()
        if last_date:
            return last_date + timezone.timedelta(days=7)
        return timezone.now().date()

    def __str__(self):
        return f"{self.name} (Owner: {self.owner.user.username})"
