# Surveillance Recording Page - Bug Report
**Date:** May 4, 2025
**Environment:** Desktop browser with `?force_desktop=true` parameter  
**Page:** Active Survey Session / Surveillance Recording

## Summary
The surveillance recording page has several critical issues preventing proper functionality. Despite multiple code changes and fixes, the core functionality is broken. This report details the specific issues encountered and the attempted fixes for developer reference.

## Critical Issues

### 1. Form Display and Field Issues
- **Observation form is not fully rendering or is incorrectly configured**
  - Image upload field is visible but unable to upload multiple images
  - Priority pests/diseases section is not displaying recommended items

### 2. GPS and Form Activation Issues
- **Save button remains inactive** despite having GPS coordinates
  - The logic to enable the form after GPS acquisition is not working
  - The `force_desktop=true` parameter is not properly bypassing GPS requirements
  - Enhanced JavaScript function to update GPS status not triggering properly


## Attempted Fixes


### JavaScript Fixes
1. Added `updateGpsDisplay()` function to handle different GPS states
2. Enhanced `getGPSLocation()` with special handling for desktop testing mode
3. Added detection for `force_desktop=true` parameter to bypass GPS requirements
4. Added image preview functionality for selected files

### Backend Fixes
1. Added `recommended_pests` and `recommended_diseases` lists to template context
2. Modified `create_observation_api` to auto-calculate plant sequence numbers
3. Updated API response format to match frontend expectations (for images and counts)

## Next Steps for Developer

1. **Debug Django Template Rendering**
   - Check if form instance is properly passed to template
   - Verify that form fields are correctly defined and named

2. **Debug JavaScript Execution**
   - Ensure JavaScript functions are running in correct order
   - Check browser console for errors in GPS and form handling

3. **Review Data Flow**
   - Verify API endpoints are correctly receiving and responding with appropriate data
   - Check how form data is processed when submitted

4. **Specific Code Areas to Review**
   - `active_survey_session_view` in `views.py` - context data for template
   - `active_survey_session.html` - form rendering and JavaScript initialization
   - `ObservationForm` in `forms.py` - form field definitions
   - `create_observation_api` in `views.py` - API response formatting

## Additional Notes
- The "Skip for Now" button for desktop testing works correctly to bypass QR code scanning
- The core Django application structure seems sound
- Frontend UI improvements for enhanced image previews and GPS status indicators are in place but not functioning due to underlying issues

