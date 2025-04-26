from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth_views
from . import views

app_name = 'core' # Add app namespace

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'), # Point root to dashboard
    path('dashboard/', views.dashboard_view, name='dashboard'), # Explicit dashboard URL
    path('myfarms/', views.home_view, name='myfarms'), # URL for the farm list (was home)
    path('signup/', views.signup_view, name='signup'),
    # Use Django's built-in LoginView, specifying our template
    path('login/', auth_views.LoginView.as_view(template_name='core/login.html'), name='login'),
    # Use Django's built-in LogoutView for simplicity for now
    path('logout/', auth_views.LogoutView.as_view(next_page='core:login'), name='logout'), # Redirect to login after logout
    # We'll add a simple home page later to redirect to after login
    # path('', views.home_view, name='home'), 
    # Add URL for creating a farm
    path('farms/create/', views.create_farm_view, name='create_farm'), 
    # Add URL for viewing farm details
    path('farms/<int:farm_id>/', views.farm_detail_view, name='farm_detail'), 
    # Add URL for editing a farm
    path('farms/<int:farm_id>/edit/', views.edit_farm_view, name='edit_farm'), 
    # Add URL for the calculator
    path('calculator/', views.calculator_view, name='calculator'), 
    # Add URL for recording surveillance for a specific farm
    path('farms/<int:farm_id>/record/', views.record_surveillance_view, name='record_surveillance'),
    # Add URL for deleting a farm
    path('farms/<int:farm_id>/delete/', views.delete_farm_view, name='delete_farm'),
    path('profile/', views.profile_view, name='profile'), # Add profile URL
    # Password Change
    path(
        'password_change/',
        auth_views.PasswordChangeView.as_view(
            template_name='core/password_change_form.html',
            success_url=reverse_lazy('core:password_change_done') # Redirect here on success
        ),
        name='password_change'
    ),
    path(
        'password_change/done/',
        auth_views.PasswordChangeDoneView.as_view(
            template_name='core/password_change_done.html'
        ),
        name='password_change_done'
    ),
    # Add URL for listing all records
    path('records/', views.record_list_view, name='record_list'), 
] 