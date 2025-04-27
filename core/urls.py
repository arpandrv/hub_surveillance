from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth_views
from . import views

app_name = 'core'

# Organize URL patterns by category for maintainability
urlpatterns = [
    # Main pages
    path('', views.dashboard_view, name='dashboard'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    
    # Authentication URLs
    path('signup/', views.signup_view, name='signup'),
    path('login/', 
         auth_views.LoginView.as_view(template_name='core/login.html'), 
         name='login'),
    path('logout/', 
         auth_views.LogoutView.as_view(next_page='core:login'), 
         name='logout'),
    path('password_change/',
         auth_views.PasswordChangeView.as_view(
             template_name='core/password_change_form.html',
             success_url=reverse_lazy('core:password_change_done')
         ),
         name='password_change'),
    path('password_change/done/',
         auth_views.PasswordChangeDoneView.as_view(
             template_name='core/password_change_done.html'
         ),
         name='password_change_done'),
    
    # Farm management
    path('myfarms/', views.home_view, name='myfarms'),
    path('farms/create/', views.create_farm_view, name='create_farm'),
    path('farms/<int:farm_id>/', views.farm_detail_view, name='farm_detail'),
    path('farms/<int:farm_id>/edit/', views.edit_farm_view, name='edit_farm'),
    path('farms/<int:farm_id>/delete/', views.delete_farm_view, name='delete_farm'),
    
    # Surveillance
    path('calculator/', views.calculator_view, name='calculator'),
    path('farms/<int:farm_id>/record/', views.record_surveillance_view, name='record_surveillance'),
    path('records/', views.record_list_view, name='record_list'),
    
    # User profile
    path('profile/', views.profile_view, name='profile'),
    
    # API Endpoints
    path('api/address-suggestions/', views.address_suggestion_view, name='api_address_suggestions'),
]