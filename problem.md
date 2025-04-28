## Problem: Geolocation API Consistently Returns Stale/Inaccurate Coordinates in Web App

**Summary:**

A Django web application attempting to capture GPS coordinates using the `navigator.geolocation` API (both `getCurrentPosition` and `watchPosition`) in a mobile browser consistently receives the *exact same, highly inaccurate coordinates* (-12.378378, 130.843489 with ~2000m accuracy). This occurs regardless of the user's actual location (tested outdoors while moving) and persists across multiple attempts. Critically, *other native applications on the same mobile device* successfully obtain accurate (e.g., 2m accuracy) and updating GPS coordinates in the same physical environment.

**Context:**

*   **Application:** Django web application.
*   **Feature:** Manual Farm Boundary Mapping - allowing users to record the GPS coordinates of their farm corners using their mobile device's browser.
*   **Frontend Library:** Leaflet.js for map display.
*   **Testing Environment:** Django development server (`runserver`) exposed publicly via `ngrok` (e.g., `https://<dynamic_subdomain>.ngrok-free.app`) and accessed via a mobile browser.

**Goal:**

To use the mobile browser's Geolocation API (`navigator.geolocation`) to obtain reasonably accurate GPS coordinates reflecting the user's current physical location at the time they click a "Record Corner" button.

**Observed Problem:**

1.  **Consistent Incorrect Coordinates:** Every call to `navigator.geolocation.getCurrentPosition` or `navigator.geolocation.watchPosition` within the web app returns latitude `~ -12.378378` and longitude `~ 130.843489`.
2.  **Poor Accuracy:** The associated `coords.accuracy` value is consistently very high (around 2000 meters).
3.  **No Updates:** Even when using `watchPosition` and physically moving outdoors, the logged coordinates remain fixed at the incorrect value.
4.  **Contradiction with Native Apps:** Native GPS/mapping apps on the *same phone*, tested in the *same outdoor location*, report accurate (~2m) and dynamically updating coordinates.

**Expected Behavior:**

1.  Calls to `navigator.geolocation.getCurrentPosition` or `watchPosition` should return coordinates reflecting the user's actual location when outdoors.
2.  The `coords.accuracy` should be reasonably low (e.g., below 50m) after a short period outdoors.
3.  The coordinates returned by consecutive calls (or updates from `watchPosition`) should change if the user physically moves.


**Code Implemented & Attempts:**

1.  **`getCurrentPosition` with Accuracy Check:**

    ```javascript
    // Inside event handler for "Record Corner" button
    navigator.geolocation.getCurrentPosition(
        (position) => {
            const lat = position.coords.latitude;
            const lng = position.coords.longitude;
            const accuracy = position.coords.accuracy;
            console.log(`Received position: Lat=${lat}, Lng=${lng}, Acc=${accuracy}`);
            
            const ACCURACY_THRESHOLD_METERS = 50;
            if (accuracy > ACCURACY_THRESHOLD_METERS) {
                alert(`GPS accuracy is currently ${accuracy.toFixed(1)}m...`);
                // Does not record
            } else {
                // Records [lat, lng]
            }
        },
        (error) => { console.error("Geolocation error:", error); },
        {
            enableHighAccuracy: true, 
            timeout: 10000, 
            maximumAge: 0 // Force fresh reading
        }
    );
    ```
    *Result:* Always logs the same inaccurate coordinates and triggers the accuracy alert.*

2.  **`getCurrentPosition` without Accuracy Check:**

    ```javascript
    // Accuracy check removed, otherwise same as above
    navigator.geolocation.getCurrentPosition(
        (position) => {
            const lat = position.coords.latitude;
            const lng = position.coords.longitude;
            const accuracy = position.coords.accuracy;
            console.log(`Received position: Lat=${lat}, Lng=${lng}, Acc=${accuracy}`);
            // Records [lat, lng] regardless of accuracy
        },
        (error) => { console.error("Geolocation error:", error); },
        { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
    );
    ```
    *Result:* Always logs and records the *exact same* inaccurate coordinates (-12.378378, 130.843489).*

3.  **`watchPosition` for Debugging:**

    ```javascript
    // Inside event handler for "Start Logging" button
    watchId = navigator.geolocation.watchPosition(
        (position) => {
            const lat = position.coords.latitude;
            const lng = position.coords.longitude;
            const accuracy = position.coords.accuracy;
            // Log EVERY update
            console.log(`WATCH UPDATE: Lat=${lat.toFixed(6)}, Lng=${lng.toFixed(6)}, Acc=${accuracy.toFixed(1)}m`);
            // Update marker on map
        },
        (error) => { console.error("watchPosition error:", error); },
        {
            enableHighAccuracy: true,
            timeout: 30000,
            maximumAge: 0
        }
    );
    // Stop logging via clearWatch(watchId) later
    ```
    *Result:* Continuously logs the *exact same* inaccurate coordinates (-12.378378, 130.843489) even while physically moving outdoors.*

**Troubleshooting Steps Taken:**

*   Verified no hardcoded coordinates in the JavaScript application code.
*   Used `maximumAge: 0` to prevent the browser from using a cached position.
*   Tested both `getCurrentPosition` and `watchPosition`.
*   Tested with and without an accuracy check.
*   Confirmed user was testing outdoors with a clear sky view and waited >30s for GPS lock.
*   Confirmed native apps on the same device/location get accurate, updating GPS fixes.
*   Confirmed browser location permissions are granted for the ngrok site.
*   Restarted the mobile device.
*   Added console logging to observe the exact data returned by the Geolocation API.

**Key Question:**

Why would the Web Geolocation API, when accessed through a mobile browser (even with `enableHighAccuracy: true` and `maximumAge: 0`), consistently return the exact same, highly inaccurate, non-updating coordinates (-12.378378, 130.843489) for this specific web application context, while native apps on the same device can access accurate GPS data? Are there known browser bugs, specific permission interactions (beyond standard prompts), interactions with ngrok, or other factors that could cause the browser to persistently provide a stale/fallback network location instead of attempting a proper GPS fix? 