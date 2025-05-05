from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
import datetime
from django.db.models import Count
from .models import Farm, SurveySession
from .season_utils import get_seasonal_stage_info

@login_required
def dashboard_preview(request):
    """
    A temporary view to preview the new dashboard design.
    Creates the same context data as the original dashboard view.
    """
    grower = request.user.grower_profile
    farms = grower.farms.all()
    
    # Get counts and summary information
    surveillance_count = grower.surveillance_records.count()
    latest_record = grower.surveillance_records.order_by('-date_performed').first()
    total_plants = grower.total_plants_managed()
    
    # Get recent records
    recent_records = grower.surveillance_records.order_by('-date_performed')[:5]
    
    # Get farms due for surveillance (simple calculation - needs improvement)
    today = timezone.now().date()
    week_ago = today - datetime.timedelta(days=7)
    
    # Get farms that haven't been checked in the last 7 days
    due_farms = []
    for farm in farms:
        last_date = farm.last_surveillance_date()
        if not last_date or last_date.date() < week_ago:
            due_farms.append(farm)
    
    due_farms_count = len(due_farms)
    
    # Get current season information from the database
    seasonal_info = get_seasonal_stage_info()
    current_season = seasonal_info['stage_name'] if seasonal_info['stage_name'] else 'Unknown'
    
    # Get the month ranges for the current season
    month_used = seasonal_info['month_used']
    
    # Create a label based on the seasonal stage data
    month_names = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
    season_label = f"Current month: {month_names[month_used-1]}"
    
    context = {
        'grower': grower,
        'surveillance_count': surveillance_count,
        'latest_record': latest_record,
        'total_plants': total_plants,
        'recent_records': recent_records,
        'due_farms': due_farms,
        'due_farms_count': due_farms_count,
        'current_season': current_season,
        'season_label': season_label,
        'seasonal_info': seasonal_info  # Pass the full seasonal info to the template
    }
    
    # Render with the new template
    return render(request, 'core/dashboard_new.html', context)
