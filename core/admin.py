from django.contrib import admin
from .models import Grower, Farm, PlantType # Import PlantType

# Register your models here.

admin.site.register(Grower)
admin.site.register(Farm)
admin.site.register(PlantType) # Register PlantType
