# core/services/user_service.py
import logging
from typing import Dict, Any, Optional, Tuple
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login
from ..models import Grower

logger = logging.getLogger(__name__)


def create_user_with_profile(user_data: Dict[str, Any]) -> Tuple[Optional[User], Optional[str]]:
    """
    Creates a new user with an associated grower profile.
    
    Args:
        user_data: Dictionary containing user and profile data
        
    Returns:
        Tuple containing (created_user, error_message)
    """
    try:
        # Extract user fields
        username = user_data.get('username')
        email = user_data.get('email')
        password = user_data.get('password')
        
        # Extract profile fields
        farm_name = user_data.get('farm_name')
        contact_number = user_data.get('contact_number')
        
        # Validate required fields
        if not username or not email or not password or not farm_name:
            missing = []
            if not username:
                missing.append('username')
            if not email:
                missing.append('email')
            if not password:
                missing.append('password')
            if not farm_name:
                missing.append('farm name')
            return None, f"Missing required fields: {', '.join(missing)}"
        
        # Check if user already exists
        if User.objects.filter(username=username).exists():
            return None, f"User with username '{username}' already exists."
        
        if User.objects.filter(email=email).exists():
            return None, f"User with email '{email}' already exists."
        
        # Create user
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )
        
        # Create grower profile
        Grower.objects.create(
            user=user,
            farm_name=farm_name,
            contact_number=contact_number
        )
        
        return user, None
    
    except Exception as e:
        logger.exception(f"Error creating user and profile: {e}")
        return None, f"An unexpected error occurred: {e}"


def update_user_profile(user: User, user_data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Updates a user and associated grower profile.
    
    Args:
        user: The User instance to update
        user_data: Dictionary containing updated data
        
    Returns:
        Tuple containing (success_flag, error_message)
    """
    try:
        # Update User model fields
        if 'username' in user_data and user_data['username'] != user.username:
            if User.objects.filter(username=user_data['username']).exclude(id=user.id).exists():
                return False, f"Username '{user_data['username']}' is already taken."
            user.username = user_data['username']
        
        if 'email' in user_data and user_data['email'] != user.email:
            if User.objects.filter(email=user_data['email']).exclude(id=user.id).exists():
                return False, f"Email '{user_data['email']}' is already registered."
            user.email = user_data['email']
        
        # Change password if provided
        if 'password' in user_data and user_data['password']:
            user.set_password(user_data['password'])
        
        # Save user model
        user.save()
        
        # Update Grower profile if exists
        try:
            grower = user.grower_profile
            
            if 'farm_name' in user_data:
                grower.farm_name = user_data['farm_name']
            
            if 'contact_number' in user_data:
                grower.contact_number = user_data['contact_number']
            
            grower.save()
        
        except Grower.DoesNotExist:
            logger.warning(f"No grower profile found for user {user.username}")
            # Create profile if it doesn't exist
            if 'farm_name' in user_data:
                Grower.objects.create(
                    user=user,
                    farm_name=user_data.get('farm_name', 'My Farm'),
                    contact_number=user_data.get('contact_number', '')
                )
        
        return True, None
    
    except Exception as e:
        logger.exception(f"Error updating user and profile: {e}")
        return False, f"An unexpected error occurred: {e}"


def login_user(request, username: str, password: str) -> Tuple[Optional[User], Optional[str]]:
    """
    Authenticates and logs in a user.
    
    Args:
        request: The HTTP request object
        username: The username to authenticate
        password: The password to authenticate
        
    Returns:
        Tuple containing (authenticated_user, error_message)
    """
    try:
        user = authenticate(username=username, password=password)
        if user is None:
            return None, "Invalid username or password."
        
        if not user.is_active:
            return None, "This account is inactive."
        
        login(request, user)
        return user, None
    
    except Exception as e:
        logger.exception(f"Error logging in user: {e}")
        return None, f"An unexpected error occurred: {e}"