# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build/Run Commands
- Server: `python manage.py runserver`
- Tests: `python manage.py test`
- Single test: `python manage.py test core.tests.TestClassName.test_method_name`
- Create migrations: `python manage.py makemigrations`
- Apply migrations: `python manage.py migrate`
- Create superuser: `python manage.py createsuperuser`
- Shell: `python manage.py shell`
- Run specific command: `python manage.py delete_duplicate_stages`

## Code Style Guidelines
- Follow PEP 8 for Python code
- Use 4 spaces for indentation
- Import order: standard library, Django imports, third-party, local application imports
- Model fields: use appropriate field types with validators and help_text
- Keep methods and functions under 100 lines with descriptive docstrings
- Use Django's built-in auth system for user authentication
- Include docstrings for models, views, and utility functions
- For templates, use Bootstrap 5 classes consistently
- Handle calculation errors with appropriate error messages and return complete input data
- For surveillance calculations, follow formulas in core/Surveillance Calculation Logic.md
- Log errors and warnings with proper context using Django's logging system
- Use constants for recurring values (e.g., SEASON_PREVALENCE, CONFIDENCE_Z_SCORES)
- Always validate user inputs before processing calculations
- When adding new models, include related_name for ForeignKey and ManyToManyField relations
- For image handling, use the Pillow library with proper file path handling
- Models should handle edge cases (e.g., null values) gracefully
- Use Django's timezone-aware datetime functionality consistently