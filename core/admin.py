from django.contrib import admin
from .models import (
    Grower, Farm, PlantType, PlantPart, Pest, 
    SurveillanceRecord, Region, SurveillanceCalculation
)

# Register your models here.

admin.site.register(Grower)
admin.site.register(Farm)
admin.site.register(PlantType)
admin.site.register(Region)
admin.site.register(PlantPart)
admin.site.register(Pest)

@admin.register(SurveillanceRecord)
class SurveillanceRecordAdmin(admin.ModelAdmin):
    list_display = ('farm', 'performed_by', 'date_performed', 'plants_surveyed')
    list_filter = ('farm', 'performed_by', 'date_performed')
    search_fields = ('farm__name', 'performed_by__user__username', 'notes')
    date_hierarchy = 'date_performed'

@admin.register(SurveillanceCalculation)
class SurveillanceCalculationAdmin(admin.ModelAdmin):
    list_display = ('farm', 'season', 'confidence_level', 'required_plants', 
                   'date_created', 'is_current')
    list_filter = ('farm', 'season', 'confidence_level', 'is_current', 'date_created')
    search_fields = ('farm__name', 'notes')
    date_hierarchy = 'date_created'
    list_editable = ('is_current',)
    readonly_fields = ('date_created',)
