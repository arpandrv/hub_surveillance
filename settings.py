# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.0/howto/static-files/

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static'] # Ensure this exists if you have project-level static files

# Default primary key field type
# https://docs.djangoproject.com/en/5.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = 'core:login'
LOGIN_REDIRECT_URL = 'core:dashboard' # Redirect to dashboard after login
LOGOUT_REDIRECT_URL = 'core:login' # Redirect to login after logout

# Media files (User uploaded content)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media' # Creates a 'media' directory at the project root 