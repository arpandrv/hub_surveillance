# Project Report: Mango Farm Surveillance Platform

## 1. Project Goal & Target Product

The primary objective of this project is to develop a modern, mobile-first web platform tailored for mango farmers in Northern Australia. The platform aims to streamline and enhance pest and disease surveillance practices by integrating:

*   **Dynamic Recommendations:** Automatically suggesting priority pests, diseases, and plant parts to inspect based on the current, automatically determined farming stage (derived from the month and stored in the database).
*   **Scientifically Calculated Sampling:** Calculating the statistically appropriate number of plants to survey (sample size) based on farm size, stocking rate, desired confidence level, and stage-specific prevalence data.
*   **Mobile-Centric Data Capture:** Enabling farmers to easily record surveillance observations directly in the field using their mobile devices, capturing GPS coordinates, pest/disease findings, notes, and photographic evidence for each observation point.
*   **Data Visualization:** Providing visual feedback, including maps showing farm boundaries (fetched via Geoscape API or mapped manually) and visualizations (like heatmaps or marker maps) of recorded observation data on the session detail page.
*   **Reporting:** Generating informative summaries and potentially downloadable reports of survey sessions.

Ultimately, the target product is a user-friendly, data-driven tool that assists growers in performing efficient, targeted, and well-documented pest and disease surveillance, leading to better farm management decisions.

## 2. Current Status: Implemented Features

Significant progress has been made on the core structure and functionality:

*   **User & Farm Management:**
    *   User registration (Signup) with associated Grower profile (farm name, contact).
    *   User login/logout and password change functionality.
    *   CRUD (Create, Read, Update, Delete) operations for Farms, linked to the Grower.
    *   Farm details include name, region, size, stocking rate, distribution pattern, plant type (defaulting to Mango).
*   **Geospatial Integration:**
    *   Integration with Geoscape Predictive Address API for searching and selecting exact farm addresses.
    *   Integration with Geoscape Cadastral API to automatically fetch and store farm boundary polygons (as GeoJSON in a `JSONField`) when an exact address ID is provided.
    *   Display of the stored farm boundary polygon on the Farm Detail page using Leaflet.js (with panning/zoom restrictions and recenter button).
*   **Seasonal Logic (Database-Driven):**
    *   A `SeasonalStage` model allows defining distinct farming stages (Flowering, Early Fruit Dev, etc.) via the admin interface.
    *   Each stage maps specific months (via a comma-separated string) to an estimated prevalence (`p`), and links to active `Pest` and `Disease` objects.
    *   Utility functions (`season_utils.py`) query this model based on the current month (or a debug override) to determine the active stage, prevalence, and associated threats.
    *   Recommended `PlantPart`s are now dynamically derived based on the parts affected by the active Pests/Diseases for the current stage.
*   **Surveillance Calculator:**
    *   A dedicated calculator page allows users to select a farm and confidence level.
    *   It automatically determines the current stage and prevalence (`p`) using `season_utils.py`.
    *   It calculates the required sample size using the finite population correction formula from `approach.md`.
    *   Saves the calculation parameters (including stage used) and results to the `SurveillanceCalculation` model for historical reference and use on the Farm Detail page.
    *   Includes a debug feature to override the month used for stage determination.
*   **Survey Session Workflow (Core):**
    *   `SurveySession`, `Observation`, `ObservationImage` models created.
    *   Ability to start a new survey session from the Farm Detail page (`start_survey_session_view`).
    *   The session stores the target plant count based on the latest calculation.
    *   An active survey session page (`active_survey_session.html` / `active_survey_session_view`) is accessible.
    *   Ability to finish a survey session, updating its status and end time (`finish_survey_session_api`).
*   **Per-Observation Recording:**
    *   The active session page includes a form (`ObservationForm`) to record data for a single observation point.
    *   Captures selected Pests/Diseases (checkboxes), notes (collapsible textarea), and a Plant Sequence Number.
    *   Includes basic single image upload functionality (via `ObservationImage` model).
    *   Uses JavaScript (`getCurrentPosition`) to acquire GPS coordinates (lat, lon, accuracy) when the form is submitted.
    *   Submits observation data (including GPS) asynchronously via AJAX to `create_observation_api`.
    *   The API saves the `Observation` and links Pests/Diseases/Image.
    *   The UI dynamically updates the list of recorded observations and progress counters upon successful save.
*   **Survey Session List & Detail:**
    *   A page lists past survey sessions for a farm (`survey_session_list.html`).
    *   A detail page (`survey_session_detail.html`) displays summary information for a completed/abandoned session and lists all its observations (including image thumbnails and links to Google Maps for coordinates).
    *   The detail page includes a Leaflet map visualizing observation locations as a heatmap (intensity based crudely on number of pests/diseases found).
*   **Manual Boundary Mapping:**
    *   Workflow implemented using unique, expiring tokens (`BoundaryMappingToken`) generated via a link/QR code (`generate_mapping_link_view`, `mapping_link_page.html`).
    *   Desktop users accessing the active survey page are redirected to a QR code prompt (`desktop_redirect_qr.html`).
    *   A dedicated mobile page (`map_boundary_corners.html`) allows users to record corners sequentially via GPS (`map_boundary_via_token_view`).
    *   Saves the recorded corners as a GeoJSON Polygon to the `Farm.boundary` field.
*   **Admin Interface:**
    *   All core models (including `SeasonalStage`, `SurveySession`, `Observation`) are registered for management via the Django admin. `filter_horizontal` used for M2M fields.

## 3. Remaining Work & Future Enhancements

While the core foundation is in place, significant features outlined in the workflow design remain to be implemented or enhanced:

*   **Mobile Device Enforcement (#3):** No explicit checks requiring GPS to *start* the survey or enforcement ensuring the page is only used on mobile (beyond the QR code redirect which can be bypassed).
*   **Enhanced Recording UI/UX (#4, #5):**
    *   No explicit "Begin Recording" step or upfront permission request flow.
    *   No tutorial tips.
    *   "Notes" field isn't collapsed by default in the manual field rendering (currently using `as_p`).
    *   Visual highlighting of recommended Pests/Diseases in the Observation form checkboxes is missing.
*   **High-Precision GPS Logging (#6):** No averaging of multiple readings, no specific fallback logic (currently relies on browser default). Plant sequence number is recorded, but not explicitly linked to a predefined plant ID/location within the farm.
*   **Plant Skipping Logic & Detailed Progress (#7):** No UI guidance for survey patterns (zigzag, skipping). Progress bar only shows observation count, not remaining count or live pest/disease tallies within the bar itself.
*   **Auto-Save & Resume (#8):** No functionality to auto-save partially entered observation data or resume an interrupted session exactly where the user left off. No offline storage/fallback implemented.
*   **Daily Auto-Deletion (#9):** No background task or mechanism for deleting incomplete surveys or sending email reminders.
*   **Refined Finish Workflow (#10):** The finish button doesn't show a summary before locking. It is currently disabled/enabled based on target count, but this relies on simple observation count, not necessarily *surveyed plants* count.
*   **AI Scan Feature (#11):** Placeholder UI elements and backend hooks are missing.
*   **Heatmap Visualization (#12):**
    *   Does not integrate/overlay the actual farm boundary polygon.
    *   Lacks filtering options (by pest, disease, date).
    *   No toggle between heatmap and point marker views.
    *   No data export options (CSV, PNG, GeoJSON).
*   **PDF Report Generation (#13):**
    *   **Blocked:** Requires resolving WeasyPrint system dependencies (GTK+) on the development machine (Windows) and planning for Linux deployment dependencies.
    *   Current template (`survey_session_pdf.html`) is basic, lacking the dashboard layout, charts, map visuals, weather data, sign-off fields etc.
    *   No email functionality implemented.
*   **General:**
    *   Multiple image upload needs to be revisited/fixed.
    *   Security: API endpoints currently use `@csrf_exempt` and basic `@login_required` instead of robust token/session authentication suitable for AJAX/mobile use.
    *   Testing: Lack of automated tests (unit, integration).
    *   Deployment configuration not yet addressed.
    *   General UI/UX polish across all new views.

## 4. Key Technologies Used

*   **Backend:** Python, Django
*   **Frontend:** HTML, CSS, JavaScript, Bootstrap 5
*   **Mapping:** Leaflet.js, Leaflet.heat
*   **PDF Generation:** WeasyPrint (selected, but installation pending)
*   **QR Code:** qrcode[pil]
*   **Database:** SQLite (default, may need PostGIS if advanced spatial queries are required later)

## 5. Potential Challenges & Considerations

*   **WeasyPrint Dependencies:** Correctly installing and managing GTK+ dependencies across development (Windows) and deployment (likely Linux) environments.
*   **GPS Accuracy/Reliability:** The variability and potential inaccuracy of browser-based geolocation remain a challenge, requiring robust error handling and user guidance.
*   **Offline Support:** Implementing reliable offline data storage (IndexedDB/localStorage) and synchronization adds significant complexity.
*   **Background Tasks:** Implementing daily cleanup and email notifications requires setting up and managing a task queue system (e.g., Celery with Redis/RabbitMQ).
*   **Scalability:** Database queries (especially for stats/reporting) may need optimization if dealing with very large numbers of farms, sessions, or observations.
*   **UI/UX:** Designing an intuitive mobile-first interface for the complex recording workflow requires careful consideration.

This report provides a snapshot of the project's current state and the substantial but exciting work remaining to fully realize the envisioned platform. 