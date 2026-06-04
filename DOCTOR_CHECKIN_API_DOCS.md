# Doctor Check-In API Implementation

## Overview
Complete doctor check-in system with photo verification (via external face recognition API) and GPS location tracking.

## Database Model

### DoctorCheckIn Table
A new table has been added to track doctor check-ins:

```python
class DoctorCheckIn(models.Model):
    - doctor: ForeignKey to Doctor
    - health_center: ForeignKey to HealthCenter
    - check_in_date: DateField
    - check_in_time: DateTimeField (when doctor checked in)
    - check_in_photo: ImageField (stored in 'doctor_checkin_photos/')
    - check_in_latitude: DecimalField
    - check_in_longitude: DecimalField
    - check_in_geo_verified: BooleanField (location within radius)
    - face_match_score: FloatField (0.0 to 1.0)
    - face_verified: BooleanField (verified via external API)
    - check_out_time: DateTimeField (nullable)
    - check_out_photo: ImageField (nullable)
    - check_out_latitude: DecimalField (nullable)
    - check_out_longitude: DecimalField (nullable)
    - check_out_geo_verified: BooleanField
    - status: CharField (CHECKED_IN / CHECKED_OUT)
    - duration_minutes: IntegerField (total duration)
    - remarks: TextField
    - created_at: DateTimeField (auto)
    - updated_at: DateTimeField (auto)
```

## API Endpoints

### 1. Doctor Check-In
**Endpoint:** `POST /doctor/check-in/`

**Authentication:** Required (JWT Token)

**Request:**
```json
{
  "photo": "<image_file>",
  "latitude": 28.6139,
  "longitude": 77.2090,
  "health_center_id": 1
}
```

**Success Response (200):**
```json
{
  "status_code": 200,
  "message": "Check-in successful",
  "data": {
    "check_in_id": 123,
    "doctor_id": 7,
    "doctor_name": "Dr. Debasis",
    "check_in_time": "2025-05-27T10:30:00Z",
    "face_verified": true,
    "geo_verified": true,
    "health_center": "Health Center Name",
    "timer_duration_minutes": 120,
    "timer_end_time": "2025-05-27T12:30:00Z",
    "image_url": "http://45.64.107.97:5010/static/attendance/..."
  }
}
```

**Error Responses:**
- **400:** Missing required fields
- **401:** Face verification failed
- **403:** User is not a doctor or already checked in
- **404:** Health center or doctor profile not found
- **409:** Doctor already checked in today

**Face Verification Process:**
1. Extracts photo from request
2. Calls external API: `http://45.64.107.97:5010/api/v1/attendance/doctor`
3. External API returns detected doctors with their IDs
4. Verifies current doctor's ID is in the `present` list
5. Checks for spoof and unknown faces
6. Returns face verification status

**Geo Verification Process:**
1. Calculates distance between check-in location and health center using Haversine formula
2. Compares against health center's geo_radius_meters
3. Returns geo_verified status

**2-Hour Timer:**
- Automatically starts on successful check-in
- Timer duration: 120 minutes
- Mobile app should display countdown


### 2. Doctor Check-Out
**Endpoint:** `POST /doctor/check-out/`

**Authentication:** Required (JWT Token)

**Request:**
```json
{
  "check_in_id": 123,
  "photo": "<image_file>",
  "latitude": 28.6139,
  "longitude": 77.2090
}
```

**Success Response (200):**
```json
{
  "status_code": 200,
  "message": "Check-out successful",
  "data": {
    "check_in_id": 123,
    "check_in_time": "2025-05-27T10:30:00Z",
    "check_out_time": "2025-05-27T12:45:00Z",
    "duration_minutes": 135
  }
}
```

**Error Responses:**
- **400:** Missing required fields
- **403:** Unauthorized (check-in belongs to another doctor)
- **404:** Check-in record not found
- **409:** Doctor already checked out


### 3. Doctor Check-In Status
**Endpoint:** `GET /doctor/check-in/status/`

**Authentication:** Required (JWT Token)

**Success Response (200) - When Checked In:**
```json
{
  "status_code": 200,
  "message": "success",
  "data": {
    "is_checked_in": true,
    "check_in_id": 123,
    "check_in_time": "2025-05-27T10:30:00Z",
    "remaining_time_minutes": 95,
    "timer_expired": false,
    "health_center": "Health Center Name",
    "face_verified": true,
    "geo_verified": true
  }
}
```

**Success Response (200) - When Not Checked In:**
```json
{
  "status_code": 200,
  "message": "No active check-in",
  "data": {
    "is_checked_in": false,
    "check_in_id": null,
    "remaining_time_minutes": 0
  }
}
```

**Error Responses:**
- **403:** User is not a doctor
- **404:** Doctor profile not found


## Mobile Application Flow

### Check-In Workflow:
1. Doctor logs in with username/password
2. Navigate to "Home" menu
3. Click "Check-In" button
4. App requests camera permission
5. Doctor captures photo (selfie)
6. App gets current GPS location (latitude, longitude)
7. User selects or confirms health center
8. App calls `POST /doctor/check-in/` with:
   - Photo file
   - Latitude
   - Longitude
   - Health center ID
9. Backend verifies face via external API
10. If successful:
    - Check-in record created
    - 2-hour timer starts
    - Display success message with timer
11. If failed:
    - Display error reason
    - Allow retry

### Timer Management:
1. After successful check-in, start 120-minute countdown
2. Display remaining time on home menu
3. Call `GET /doctor/check-in/status/` periodically to sync remaining time
4. When timer reaches 0, show "Check-Out Required" notification
5. Timer expired does not prevent manual check-out

### Check-Out Workflow:
1. After 2-hour timer completes or doctor manually checks out
2. Click "Check-Out" button
3. Capture exit photo (selfie)
4. Get current GPS location
5. Call `POST /doctor/check-out/` with:
   - Check-in ID
   - Photo file
   - Latitude
   - Longitude
6. Backend records check-out and calculates duration
7. Display success message with total duration

## Migration Steps

1. **Generate Migration:**
   ```bash
   python manage.py makemigrations healthcenter
   ```

2. **Apply Migration:**
   ```bash
   python manage.py migrate healthcenter
   ```

3. **Collect Static Files (if needed):**
   ```bash
   python manage.py collectstatic --noinput
   ```

## Usage Examples

### Example 1: Doctor Check-In
```bash
curl -X POST http://localhost:8000/doctor/check-in/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "photo=@/path/to/photo.jpg" \
  -F "latitude=28.6139" \
  -F "longitude=77.2090" \
  -F "health_center_id=1"
```

### Example 2: Get Check-In Status
```bash
curl -X GET http://localhost:8000/doctor/check-in/status/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### Example 3: Doctor Check-Out
```bash
curl -X POST http://localhost:8000/doctor/check-out/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "check_in_id=123" \
  -F "photo=@/path/to/checkout_photo.jpg" \
  -F "latitude=28.6139" \
  -F "longitude=77.2090"
```

## External Face Recognition API

**API Endpoint:** `http://45.64.107.97:5010/api/v1/attendance/doctor`

**Request Parameters:**
- `file`: Image file (multipart)
- `health_center_id`: Health center ID

**Response Structure:**
```json
{
  "total_faces": 1,
  "present": [
    {
      "id": 7,
      "name": "debasis"
    }
  ],
  "already_present": [],
  "unknown_faces": 0,
  "spoof_faces": 0,
  "image_url": "http://45.64.107.97:5010/static/attendance/doctor-attendance-1-..."
}
```

**Response Fields:**
- `total_faces`: Total faces detected in image
- `present`: List of doctors detected (with id and name)
- `already_present`: Doctors already checked in today
- `unknown_faces`: Count of unrecognized faces
- `spoof_faces`: Count of spoofed faces detected
- `image_url`: URL to processed image

## Features

✅ **Face Recognition:** Integrated with external API for accurate face matching
✅ **GPS Location Verification:** Verifies doctor is within health center radius
✅ **2-Hour Timer:** Automatic timer that starts on check-in
✅ **Spoof Detection:** Detects and rejects spoof faces
✅ **Check-Out Tracking:** Records exit time and duration
✅ **Role-Based Access:** Only doctors can check in/out
✅ **Duplicate Prevention:** Prevents multiple check-ins on same day
✅ **Error Handling:** Comprehensive error messages
✅ **Photo Storage:** Stores check-in and check-out photos
✅ **Audit Trail:** Maintains complete check-in/out history

## Configuration

The face recognition API endpoint can be configured in `healthcenter/api/doctor_checkin.py`:
```python
FACE_API_URL = "http://45.64.107.97:5010/api/v1/attendance/doctor"
```

## Notes

- All timestamps are stored in UTC (Django's default)
- Photos are stored in `media/doctor_checkin_photos/` and `media/doctor_checkout_photos/`
- Latitude/Longitude are stored with 7 decimal places (accuracy ~1.1cm)
- Distance calculation uses Haversine formula with Earth radius = 6371km
- Face matching scores stored (0.0 = no match, 1.0 = perfect match)
- All API requests require JWT authentication except login
