# GPS Functionality Bug Report - Agricultural Surveillance App

## Issue Summary
The surveillance recording feature in the agricultural monitoring application is experiencing significant GPS functionality issues when accessed through ngrok tunnel on mobile devices. Despite implementing watchPosition functionality matching the boundary mapping feature (which works at 12-14m accuracy), the surveillance recording feature still experiences both timeouts and very poor accuracy (2000m).

## Environment Information
- **Application**: Hub Surveillance (Agricultural Monitoring)
- **Access Method**: Mobile phone browser via ngrok tunnel
- **Browser**: Multiple browsers tested
- **Location**: Outdoor with good visibility (balcony)
- **Date/Time**: May 5, 2025

## Debug Information
From the debug panel logs:
```
[21:18:31] Starting GPS acquisition (initial), desktop mode: false
[21:18:31] GPS status update: waiting - Acquiring GPS signal... - Accuracy: N/A
[21:18:31] Initial GPS check, starting acquisition
[21:18:31] GPS acquisition started with timeout: 30s, high accuracy: true
[21:19:01] GPS acquisition took 30 seconds
[21:19:01] GPS status update: waiting - Retrying GPS acquisition... - Accuracy: N/A
[21:19:01] TIMEOUT: GPS acquisition timed out after 30s, scheduling retry...
[21:19:03] Executing scheduled GPS retry
[21:19:03] Starting GPS acquisition (retry), desktop mode: false
[21:19:03] GPS acquisition started with timeout: 30s, high accuracy: true
[21:19:33] GPS acquisition took 30 seconds
[21:19:33] GPS status update: waiting - Retrying GPS acquisition... - Accuracy: N/A
[21:19:33] TIMEOUT: GPS acquisition timed out after 30s, scheduling retry...
[21:19:35] Executing scheduled GPS retry
[21:19:35] Starting GPS acquisition (retry), desktop mode: false
[21:19:35] GPS acquisition started with timeout: 30s, high accuracy: true
[21:20:05] GPS acquisition took 30 seconds
[21:20:05] GPS status update: waiting - Retrying GPS acquisition... - Accuracy: N/A
[21:20:05] TIMEOUT: GPS acquisition timed out after 30s, scheduling retry...
[21:20:07] Executing scheduled GPS retry
[21:20:07] Starting GPS acquisition (retry), desktop mode: false
[21:20:07] GPS acquisition started with timeout: 30s, high accuracy: true
[21:20:12] GPS acquisition took 4 seconds
[21:20:12] SUCCESS! GPS Acquired: Lat: -12.378378378378379, Lon: 130.8434885678717, Acc: 2000m
[21:20:12] GPS accuracy level: Very Poor (2000m)
[21:20:12] GPS status update: warning - GPS accuracy is 2000m (Very Poor). This may affect data quality. - Accuracy: 2000.0m
[21:20:12] WARNING: GPS accuracy is 2000m (Very Poor). This may affect data quality.
[21:20:12] Continuing with survey despite poor accuracy
[21:20:12] GPS status update: ready -  - Accuracy: 2000.0m
```

## Critical Observations
1. The same mobile device works with the boundary mapping feature at 12-14m accuracy levels
2. Other GPS applications on the same device work correctly
3. Testing was done outdoors with good sky visibility (balcony)
4. The application gets timeouts for 3 attempts before finally getting a very low-accuracy reading (2000m)
5. Subsequent attempts failed to improve accuracy despite implementing watchPosition

## Technical Analysis

Despite implementing the same GPS strategy from the boundary mapping feature (which works at 12-14m accuracy), the surveillance recording feature continues to experience issues:

1. **Initial timeouts**: Multiple 30-second timeouts before getting a position
2. **Poor final accuracy**: When a position is finally obtained, accuracy is 2000m (extremely poor)
3. **No progressive improvement**: The watchPosition implementation isn't improving accuracy over time

## Recent Changes Made
1. Added detailed GPS debug logging
2. Extended timeout from 10s to 30s
3. Implemented continuous watching via watchPosition
4. Added visual indicators and warnings
5. Added retry mechanism for timeouts
6. Fixed JavaScript syntax issues in the GPS implementation

## Key Differences from Boundary Mapping Feature
Both features now use similar code approaches:
- Both use watchPosition for continuous GPS updates
- Both use the same timeout settings (30s)
- Both request high accuracy mode
- The same phone works with one feature but not the other

## Hypothesis
Possible causes:
1. JavaScript execution context issues or closure problems in the surveillance feature
2. Geolocation API blocked or limited when accessed via ngrok for security reasons
3. HTTPS requirements not fully satisfied through the ngrok tunnel
4. The surveillance feature may have other browser/JavaScript errors preventing proper GPS functionality

## Next Steps Recommended
1. Complete a full code structure review of both features
2. Test with direct HTTPS connection (not through ngrok)
3. Implement a native app approach for testing (such as a WebView or PWA)
4. Add comprehensive application-level logging for all geolocation API calls
5. Check for any browser console errors during GPS initialization
6. Test a minimal reproduction case with only geolocation functionality

## Impact on Agricultural Surveillance
The poor GPS accuracy (2000m) makes the surveillance feature unusable for its intended purpose, as accurate location data is essential for properly mapping and tracking agricultural pests and diseases.
