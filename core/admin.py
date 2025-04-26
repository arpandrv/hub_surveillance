from django.contrib import admin
from .models import Grower, Farm, PlantType, PlantPart, Pest, SurveillanceRecord, Region # Import Region

# Register your models here.

admin.site.register(Grower)
admin.site.register(Farm)
admin.site.register(PlantType) # Register PlantType
admin.site.register(Region) # Register Region
admin.site.register(PlantPart)
admin.site.register(Pest)
admin.site.register(SurveillanceRecord)
