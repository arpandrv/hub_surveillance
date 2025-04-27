# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build/Run Commands
- Server: `python manage.py runserver`
- Tests: `python manage.py test`
- Single test: `python manage.py test core.tests.TestClassName.test_method_name`
- Create migrations: `python manage.py makemigrations`
- Apply migrations: `python manage.py migrate`

## Code Style Guidelines
- Follow PEP 8 for Python code
- Use 4 spaces for indentation
- Import order: standard library, third-party, local application imports
- Model fields: use appropriate field types with validators
- Keep methods and functions under 100 lines
- Use Django's built-in auth system for user authentication
- Include docstrings for models, views, and utility functions
- For templates, use Bootstrap classes consistently
- Handle calculation errors with appropriate error messages
- For surveillance calculations, follow formulas in core/Surveillance Calculation Logic.md