from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

# Create your models here.

class Grower(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='grower_profile') # Use related_name to avoid clash if User has other profiles
    farm_name = models.CharField(max_length=100) # Let's keep this for now, maybe represents the main farm or business name?
    contact_number = models.CharField(max_length=20, blank=True, null=True) # Allow blank and null

    def __str__(self):
        # Use the user's username for a more informative string representation
        return f"{self.user.username}'s Profile ({self.farm_name})"

# Add PlantType model for extensibility
class PlantType(models.Model):
    name = models.CharField(max_length=100, unique=True) # e.g., Mango, Avocado
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

class PlantPart(models.Model):
    name = models.CharField(max_length=50, unique=True)  # e.g., leaf, trunk, fruit
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

class Pest(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    affects_plant_types = models.ManyToManyField(PlantType, related_name='pests', blank=True)
    affects_plant_parts = models.ManyToManyField(PlantPart, related_name='pests', blank=True)
    # Add other fields later if needed (e.g., risk level, visibility)

    def __str__(self):
        return self.name

class SurveillanceRecord(models.Model):
    farm = models.ForeignKey('Farm', on_delete=models.CASCADE, related_name='surveillance_records')
    performed_by = models.ForeignKey(Grower, on_delete=models.CASCADE, related_name='surveillance_records')
    date_performed = models.DateTimeField(default=timezone.now)
    plants_surveyed = models.IntegerField()
    plant_parts_checked = models.ManyToManyField(PlantPart, related_name='surveillance_records', blank=True)
    pests_found = models.ManyToManyField(Pest, related_name='surveillance_records', blank=True)
    notes = models.TextField(blank=True, null=True)
    # Add location fields later (latitude, longitude)

    def __str__(self):
        return f"Survey on {self.farm.name} - {self.date_performed.strftime('%Y-%m-%d %H:%M')}"

class Farm(models.Model):
    owner = models.ForeignKey(Grower, on_delete=models.CASCADE, related_name='farms') # Link to Grower, one grower can have many farms
    name = models.CharField(max_length=100)
    # Add fields relevant to surveillance calculation
    size_hectares = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Total farm size in hectares")
    stocking_rate = models.IntegerField(null=True, blank=True, help_text="Number of plants per hectare")
    plant_type = models.ForeignKey(PlantType, on_delete=models.SET_NULL, null=True, blank=True, related_name='farms') # Link to the primary plant type
    location_description = models.CharField(max_length=255, blank=True, null=True) # Simple text location for now

    # Add a method to calculate total plants (useful later)
    def total_plants(self):
        if self.size_hectares and self.stocking_rate:
            return int(self.size_hectares * self.stocking_rate)
        return None

    def __str__(self):
        return f"{self.name} (Owner: {self.owner.user.username})"
