from django.contrib import admin
from .models import (
    Grower, Farm, PlantType, PlantPart, Pest, Disease, 
    SurveillanceRecord, Region, SurveillanceCalculation, BoundaryMappingToken
)

# Register your models here.

@admin.register(Grower)
class GrowerAdmin(admin.ModelAdmin):
    list_display = ('user', 'farm_name', 'contact_number')
    search_fields = ('user__username', 'farm_name')

@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ('name', 'climate_zone', 'state_abbreviation')
    search_fields = ('name',)

@admin.register(PlantType)
class PlantTypeAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

@admin.register(PlantPart)
class PlantPartAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

@admin.register(Pest)
class PestAdmin(admin.ModelAdmin):
    list_display = ('name', 'get_affected_types', 'get_affected_parts')
    search_fields = ('name',)
    filter_horizontal = ('affects_plant_types', 'affects_plant_parts')

    def get_affected_types(self, obj):
        return ", ".join([p.name for p in obj.affects_plant_types.all()])
    get_affected_types.short_description = 'Affects Plant Types'

    def get_affected_parts(self, obj):
        return ", ".join([p.name for p in obj.affects_plant_parts.all()])
    get_affected_parts.short_description = 'Affects Plant Parts'

# Register the new Disease model
@admin.register(Disease)
class DiseaseAdmin(admin.ModelAdmin):
    list_display = ('name', 'get_affected_types', 'get_affected_parts')
    search_fields = ('name',)
    filter_horizontal = ('affects_plant_types', 'affects_plant_parts')

    def get_affected_types(self, obj):
        return ", ".join([p.name for p in obj.affects_plant_types.all()])
    get_affected_types.short_description = 'Affects Plant Types'

    def get_affected_parts(self, obj):
        return ", ".join([p.name for p in obj.affects_plant_parts.all()])
    get_affected_parts.short_description = 'Affects Plant Parts'

@admin.register(Farm)
class FarmAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'region', 'plant_type', 'size_hectares', 'stocking_rate', 'total_plants')
    list_filter = ('region', 'plant_type', 'owner')
    search_fields = ('name', 'owner__user__username', 'location_description')
    readonly_fields = ('total_plants',) # Example of readonly calculated field

@admin.register(SurveillanceRecord)
class SurveillanceRecordAdmin(admin.ModelAdmin):
    list_display = ('farm', 'performed_by', 'date_performed', 'plants_surveyed')
    list_filter = ('farm', 'performed_by', 'date_performed')
    search_fields = ('farm__name', 'performed_by__user__username', 'notes')
    filter_horizontal = ('plant_parts_checked', 'pests_found', 'diseases_found')
    date_hierarchy = 'date_performed'

@admin.register(SurveillanceCalculation)
class SurveillanceCalculationAdmin(admin.ModelAdmin):
    list_display = ('farm', 'date_created', 'created_by', 'season', 'confidence_level', 'required_plants', 'is_current')
    list_filter = ('farm', 'created_by', 'season', 'confidence_level', 'is_current')
    search_fields = ('farm__name', 'created_by__username')
    date_hierarchy = 'date_created'
    list_editable = ('is_current',)
    readonly_fields = ('date_created',)

@admin.register(BoundaryMappingToken)
class BoundaryMappingTokenAdmin(admin.ModelAdmin):
    list_display = ('farm', 'token', 'created_at', 'expires_at', 'is_valid')
    list_filter = ('farm',)
    readonly_fields = ('token', 'created_at', 'expires_at', 'is_valid')
