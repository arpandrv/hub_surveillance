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
- Lint: `flake8`
- Type check: `mypy .`
- Check imports: `isort --check .`

## Code Architecture

### Project Structure
- Django-based web application for agricultural surveillance
- Main app: `core` - contains all functionality for the hub surveillance system
- Services-oriented architecture with business logic separated into service modules

### Main Components
1. **Models**: Farm, Grower, SurveySession, Observation, etc. in `core/models.py`
2. **Services**: Modular business logic in `core/services/` directory
   - `calculation_service.py`: Handles surveillance calculation logic
   - `farm_service.py`: Handles farm CRUD operations
   - `surveillance_service.py`: Manages surveillance records
   - `boundary_service.py`: Manages farm boundary mapping
   - `geoscape_service.py`: Interacts with external Geoscape API

### Key Features
1. **Surveillance Calculation System**:
   - Statistical sample size calculation based on farm size, confidence level, and seasonal pest prevalence
   - Formulas documented in `core/Surveillance Calculation Logic.md`
   - Implementation in `core/calculations.py` and `core/services/calculation_service.py`

2. **Session-based Surveillance Recording**:
   - Mobile-friendly survey interface with GPS tracking
   - Multi-stage observations with draft/complete states
   - Image upload capabilities for documentation
   
3. **Seasonal Stage Management**:
   - Dynamic recommendations based on current season
   - Plant part, pest, and disease recommendations that change over seasons
   - Implementation in `core/season_utils.py`

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
- For calculations, use Decimal type for precision in statistical formulas
- Follow services-oriented architecture with separate service modules
- Use Django forms for input validation and sanitization
- Follow the existing pattern for error handling and logging

## Surveillance Calculation Guidelines
- Sample size calculation uses this formula: n = (N z² p(1-p))/(d²(N-1) + z² p(1-p))
- Where:
  - N: Total population (plants in farm)
  - z: Z-score based on confidence level (1.645 for 90%, 1.96 for 95%, 2.575 for 99%)
  - p: Expected prevalence (varies by season: Wet: 0.10, Dry: 0.02, Flowering: 0.05)
  - d: Margin of error (fixed at 0.05 or 5%)
- Use Decimal type for all calculation values to maintain precision
- Handle edge cases (zero values, division by zero, etc.)
- Return complete calculation results with all inputs and outputs

## Key Database Models
- User/Grower: Authentication and profile information
- Farm: Central entity storing farm details, boundaries, and plant information
- SeasonalStage: Configures seasonal-specific data like prevalence rates
- SurveySession: Groups related observations during a single surveillance activity
- Observation: Individual data points with GPS coordinates, pest/disease findings
- SurveillanceCalculation: Stores calculation history and recommendations