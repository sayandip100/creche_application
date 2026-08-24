# Creche App - Complete API Documentation

This document provides a comprehensive reference for all REST API endpoints in the Creche App project.

**Base URL:** `http://<server-ip>:<port>/`

**Authentication:** Most endpoints require a JWT Bearer token in the `Authorization` header:
```
Authorization: Bearer <access_token>
```

**User Roles:** `superadmin`, `attendant`, `super_attendant`, `doctor`, `head_nurse`, `nurse`, `teagarden_head`

---

## Table of Contents

1. [Authentication & User Management](#1-authentication--user-management)
2. [Reports](#2-reports)
3. [Child Attendance](#3-child-attendance)
4. [Child Growth Monitoring](#4-child-growth-monitoring)
5. [Patient Management](#5-patient-management)
6. [Doctor Check-In / Check-Out](#6-doctor-check-in--check-out)
7. [Doctor List](#7-doctor-list)
8. [e-Prescription & Medicine](#8-e-prescription--medicine)
9. [Medicine Units](#9-medicine-units)
10. [Medicine Min Stock Level](#10-medicine-min-stock-level)
11. [Medicine Requisition](#11-medicine-requisition)
12. [Unified Check-In (Attendant/Nurse)](#12-unified-check-in-attendantnurse)
13. [Attendant & Nurse Management (Admin)](#13-attendant--nurse-management-admin)

---

## 1. Authentication & User Management

### 1.1 Login
- **URL:** `POST /login/`
- **Auth:** None (AllowAny)
- **Content-Type:** `application/json`

**Request Body:**
```json
{
  "username": "john",
  "password": "password123"
}
```

**Response (200 OK):**
```json
{
  "access": "<jwt-access-token>",
  "data": {
    "user_id": 1,
    "username": "john",
    "email": "john@example.com",
    "role": "attendant",
    "name": "John Doe",
    "mobile_no": "1234567890",
    "address": "Tea Garden Area",
    "creches": [
      {
        "id": 1,
        "name": "Creche A",
        "tea_garden": "Garden A",
        "children": [
          {
            "id": 1,
            "name": "Child Name",
            "age_years": 4,
            "gender": "M",
            "latest_attendance": {
              "attendance_date": "2026-08-10",
              "status": "PRESENT"
            }
          }
        ],
        "food_monitorings": []
      }
    ],
    "tea_garden_id": 285
  }
}
```

**Notes:**
- Response structure varies by role:
  - **superadmin:** Returns `creches` and `health_centers` with full details.
  - **attendant/super_attendant:** Returns `creches` and `tea_garden_id`.
  - **doctor/head_nurse/nurse:** Returns `health_centers` and `tea_garden_id`.
- On invalid credentials returns `401` with `status_code: 401`.

---

### 1.2 Mobile Login
- **URL:** `POST /mobile-login/`
- **Auth:** None (AllowAny)
- **Content-Type:** `application/json`

**Request Body:**
```json
{
  "username": "john",
  "password": "password123"
}
```

**Response (200 OK):**
```json
{
  "status_code": 200,
  "message": "success",
  "data": {
    "access_token": "<jwt-access-token>",
    "refresh_token": "<jwt-refresh-token>",
    "token_type": "Bearer",
    "expires_in": 60,
    "user_data": {
      "refresh_token": "<jwt-refresh-token>",
      "user_id": 1,
      "username": "john",
      "role": "attendant",
      "name": "John Doe",
      "photo_url": "http://server/media/attendants/photo.jpg",
      "login_time": "2026-08-10T16:00:00+05:30",
      "tea_garden_id": 285,
      "tea_garden_name": "Garden A",
      "creache_id": 1,
      "creche_name": "Creche A",
      "health_center_id": null,
      "health_center_name": null,
      "attendant_id": 1,
      "doctor_id": null,
      "nurse_id": null
    }
  }
}
```

**Notes:** Simplified login for mobile clients. Returns `photo_url`, `tea_garden_id`, `creche_id`, `health_center_id`, and role-specific IDs.

---

### 1.3 Get Refresh Token
- **URL:** `POST /getrefreshtoken/`
- **Auth:** None (AllowAny)
- **Content-Type:** `application/json`

**Request Body:**
```json
{
  "refresh_token": "<your-refresh-token-string>"
}
```

**Response (200 OK):**
```json
{
  "status_code": 200,
  "message": "Token refreshed successfully",
  "data": {
    "access_token": "<new-access-token>",
    "refresh_token": "<new-refresh-token>"
  }
}
```

**Error Responses:**
- `400` - `refresh_token` missing, or an access token was passed instead of a refresh token.
- `401` - Invalid or expired refresh token.

---

### 1.4 Logout
- **URL:** `POST /logout/`
- **Auth:** Bearer Token (IsAuthenticated)

**Response (200 OK):**
```json
{
  "detail": "Successfully logged out."
}
```

**Notes:** Stateless JWT logout. Client should delete stored tokens.

---

### 1.5 Register Attendant / Doctor / Nurse
- **URL:** `POST /register/`
- **Auth:** None (AllowAny)
- **Content-Type:** `multipart/form-data`

**Request Body (Attendant / Super Attendant):**
```
username: john
password: password123
role: attendant            # or super_attendant
attendant_name: John Doe
mobile_no: 1234567890
address: Tea Garden Area
tea_garden_id: 285
creche_id: 1
photo: <image file>        # required
```

**Request Body (Doctor):**
```
username: drsmith
password: password123
role: doctor
doctor_name: Dr. Smith
specialization: General Medicine
qualification: MBBS
mobile_no: 1234567890
tea_garden_id: 285
health_center_id: 1
photo: <image file>        # required
```

**Request Body (Nurse / Head Nurse):**
```
username: jane
password: password123
role: nurse                # or head_nurse
nurse_name: Jane Doe
qualification: GNM
mobile_no: 9876543210
tea_garden_id: 285
health_center_id: 1
photo: <image file>        # required
```

**Response (201 Created) - Attendant:**
```json
{
  "message": "Attendant registered successfully",
  "data": {
    "id": 1,
    "username": "john",
    "role": "attendant",
    "attendant_name": "John Doe",
    "mobile_no": "1234567890",
    "address": "Tea Garden Area",
    "tea_garden_id": 285,
    "creche_id": 1,
    "photo_url": "http://server/media/attendants/photo.jpg",
    "attendant_photo_id": 1,
    "embedding_id": 1
  }
}
```

**Notes:** The photo is sent to an external face-embedding API (`http://45.64.107.97:5010/api/v1/photo-embedding`) to generate face embeddings before creating the record.

---

### 1.6 Register Child
- **URL:** `POST /childrenregister/`
- **Auth:** None (AllowAny)
- **Content-Type:** `multipart/form-data`

**Request Body:**
```
creche_id: 1
name: Child Name
photos: <image file 1>     # required, multiple allowed
photo: <image file>        # optional primary photo
age_years: 4
gender: M
height_cm: 100.5
weight_kg: 16.2
guardian_name: Guardian Name
contact_person_name: Contact Person
contact_phone: 1234567890
address: Address
```

**Response (200 OK):**
```json
{
  "status_code": 200,
  "message": "success",
  "data": [
    {
      "id": 1,
      "creche_id": 1,
      "name": "Child Name",
      "photo_url": "http://server/media/children/photo.jpg",
      "photo_urls": ["http://server/media/children/photo1.jpg"],
      "age_years": 4,
      "gender": "M",
      "height_cm": 100.5,
      "weight_kg": 16.2,
      "guardian_name": "Guardian Name",
      "contact_person_name": "Contact Person",
      "contact_phone": "1234567890",
      "address": "Address",
      "created_by": "john"
    },
    {
      "embeddings_message": "Embeddings generated successfully",
      "embeddings_count": 1
    }
  ]
}
```

**Notes:** Photos are sent to the external embedding API. Initial height/weight are also stored in `ChildGrowthMonitoring`.

---

### 1.7 Child List
- **URL:** `POST /children/list/`
- **Auth:** Bearer Token (IsAuthenticated)
- **Content-Type:** `application/json`

**Request Body:**
```json
{
  "tea_garden_id": 285,
  "creche_id": 1
}
```
- `tea_garden_id` is **required**.
- `creche_id` is **optional** (if omitted, returns children from all creches in the tea garden).

**Response (200 OK):**
```json
{
  "status_code": 200,
  "message": "success",
  "data": {
    "tea_garden_id": 285,
    "tea_garden_name": "Garden A",
    "children_count": 2,
    "children": [
      {
        "id": 1,
        "creche_id": 1,
        "creche_name": "Creche A",
        "name": "Child Name",
        "age_years": 4,
        "gender": "M",
        "height": 100.5,
        "weight": 16.2,
        "guardian_name": "Guardian",
        "contact_person_name": "Contact",
        "contact_phone": "1234567890",
        "address": "Address",
        "enrollment_date": "2026-01-01T00:00:00Z",
        "photo_url": "http://server/media/children/photo.jpg",
        "gallery_urls": ["http://server/media/children/photo1.jpg"],
        "created_at": "2026-01-01T00:00:00Z"
      }
    ]
  }
}
```

---

### 1.8 Create Creche
- **URL:** `POST /creches/create/`
- **Auth:** None (AllowAny)
- **Content-Type:** `application/json`

**Request Body:**
```json
{
  "creche_name": "Creche A",
  "creche_code": "CR001",
  "tea_garden_id": 285,
  "location": "Location Name",
  "latitude": 26.1234,
  "longitude": 88.1234,
  "geo_radius_meters": 100
}
```

**Response (201 Created):**
```json
{
  "message": "Creche created successfully",
  "data": {
    "id": 1,
    "creche_name": "Creche A",
    "tea_garden_id": 285,
    "tea_garden_name": "Garden A",
    "location": "Location Name",
    "latitude": 26.1234,
    "longitude": 88.1234,
    "geo_radius_meters": 100
  }
}
```

---

## 2. Reports

### 2.1 Child Attendance Report
- **URL:** `POST /reports/child-attendance/`
- **Auth:** None
- **Content-Type:** `application/json`

**Request Body:**
```json
{
  "tea_garden_id": 285,
  "creche_id": 1,
  "end_date": "2026-08-10",
  "report_format": "datewise"
}
```
- `tea_garden_id`, `creche_id`, `end_date` are **required**.
- `report_format`: `datewise` (default) or `childwise`.

**Response (200 OK) - datewise:**
```json
{
  "status_code": 200,
  "message": "success",
  "data": {
    "tea_garden_id": 285,
    "creche_id": 1,
    "creche_name": "Creche A",
    "report_format": "datewise",
    "period": {
      "start_date": "2026-01-01",
      "end_date": "2026-08-10",
      "total_days": 5,
      "total_working_days": 5
    },
    "summary": {
      "total_records": 50,
      "total_present": 45,
      "total_absent": 5,
      "total_possible_days": 50,
      "total_children": 10,
      "attendance_percentage": 90.0
    },
    "attendance_by_date": [
      {
        "date": "2026-08-10",
        "day": "Monday",
        "present_children": [{"child_id": 1, "name": "Child", "age_years": 4, "gender": "M", "roll_number": null}],
        "absent_children": [],
        "total_present": 10,
        "total_absent": 0,
        "total_strength": 10,
        "total_enrolled": 10,
        "attendance_percentage": 100.0
      }
    ]
  }
}
```

**Response (200 OK) - childwise:**
```json
{
  "status_code": 200,
  "message": "success",
  "data": {
    "tea_garden_id": 285,
    "creche_id": 1,
    "creche_name": "Creche A",
    "report_format": "childwise",
    "period": {
      "start_date": "2026-01-01",
      "end_date": "2026-08-10",
      "total_working_days": 5
    },
    "summary": {
      "total_records": 50,
      "total_present": 45,
      "total_absent": 5,
      "total_possible_days": 50,
      "attendance_percentage": 90.0
    },
    "children": [
      {
        "child_id": 1,
        "name": "Child",
        "age_years": 4,
        "gender": "M",
        "enrollment_date": "2026-01-01",
        "attendance_records": [
          {"attendance_date": "2026-08-10", "day": "Monday", "status": "PRESENT"}
        ],
        "total_expected_days": 5,
        "present_days": 5,
        "absent_days": 0,
        "attendance_percentage": 100.0
      }
    ]
  }
}
```

---

### 2.2 Food Monitoring Report
- **URL:** `POST /reports/food-monitoring/`
- **Auth:** None
- **Content-Type:** `application/json`

**Request Body:**
```json
{
  "tea_garden_id": 285,
  "creche_id": 1,
  "start_date": "2026-08-01",
  "end_date": "2026-08-10",
  "entered_by_id": 1
}
```
- All fields are **required**. `entered_by_id` can be a CrecheAttendant ID or a User ID.

**Response (200 OK):**
```json
{
  "status_code": 200,
  "message": "success",
  "data": {
    "creche": {
      "id": 1,
      "name": "Creche A",
      "tea_garden": "Garden A"
    },
    "period": {
      "start_date": "2026-08-01",
      "end_date": "2026-08-10",
      "total_meals": 10
    },
    "nutrition": {
      "grade": "GOOD",
      "average": {
        "calories": 450.5,
        "protein_g": 12.3,
        "carbs_g": 60.2,
        "fibre_g": 5.1
      },
      "insights": ["Meals are nutritionally adequate"]
    },
    "records": [
      {
        "monitoring_date": "2026-08-10",
        "meal_type": "Lunch",
        "food_description": "Food Items:\n- Rice",
        "calories": 450.5,
        "protein_g": 12.3,
        "carbs_g": 60.2,
        "fibre_g": 5.1
      }
    ]
  }
}
```

**Nutrition Grades:** `GOOD` (calories ≥ 400 & protein ≥ 10), `POOR` (calories ≥ 300 & protein ≥ 5), `CRITICAL` (otherwise).

---

### 2.3 Store Food Monitoring
- **URL:** `POST /reports/food-monitoring/store/`
- **Auth:** None
- **Content-Type:** `multipart/form-data`

**Request Body:**
```
food_image: <image file>       # required (also accepts 'file' or 'image')
creche_id: 1                   # required
meal_type: Lunch               # optional, default "Lunch"
food_date: 2026-08-10          # optional (YYYY-MM-DD)
entered_by_id: 1               # optional (CrecheAttendant ID or User ID)
```

**Response (200 OK):**
```json
{
  "status_code": 200,
  "message": "Food monitoring data stored successfully",
  "data": {
    "id": 1,
    "creche_id": 1,
    "creche_name": "Creche A",
    "monitoring_date": "2026-08-10",
    "meal_type": "Lunch",
    "food_items_count": 3,
    "health_score": 8,
    "nutrition": {
      "calories": 450.5,
      "protein": 12.3,
      "carbs": 60.2,
      "fiber": 5.1
    },
    "external_image_url": "http://...",
    "external_image_path": "/path/to/image.jpg",
    "food_items": [{"name": "Rice", "nutrition": {"calories": 200, "protein": 4, "carbs": 40, "fiber": 1}}],
    "food_matching": {
      "matched_items": [],
      "unmatched_llm_items": [],
      "unmatched_db_items": [],
      "overall_match_score": 100,
      "summary": ""
    },
    "food_saved": true,
    "entered_by_id": 1,
    "entered_by_name": "John Doe"
  }
}
```

**Notes:**
- The image is sent to an external food monitoring API (`http://45.64.107.97:5011/api/v1/food_monitoring`).
- If `unmatched_llm_items` is not empty, data is **NOT saved** and an error response is returned.
- If `unmatched_db_items` is not empty, data is saved but a warning is included.
- Returns `409` if a record already exists for the same creche/date/meal_type.

---

### 2.4 Create Food Record
- **URL:** `POST /food-record/create/`
- **Auth:** None
- **Content-Type:** `application/json`

**Request Body:**
```json
{
  "creche_id": 1,
  "food_items": ["Biscuits", "Khichdi", "Sambar"],
  "food_time": "lunch",
  "added_by_id": 1
}
```
- `creche_id`, `food_items` (array) are **required**.
- `food_time`: `breakfast`, `lunch`, or `dinner` (optional).
- `added_by_id`: CrecheAttendant ID (optional).

**Response (200 OK):**
```json
{
  "status_code": 200,
  "message": "Food record created successfully",
  "data": {
    "id": 1,
    "creche_id": 1,
    "creche_name": "Creche A",
    "food_items": ["Biscuits", "Khichdi", "Sambar"],
    "food_time": "lunch",
    "added_by_id": 1,
    "food_update_date": "2026-08-10T16:00:00"
  }
}
```

---

### 2.5 Update Food Record Attendant
- **URL:** `POST /food-record-attendent/update/`
- **Auth:** None
- **Content-Type:** `application/json`

**Request Body:**
```json
{
  "creche_id": 1,
  "food_items": ["Biscuits", "Khichdi", "Sambar"],
  "reason": "Menu updated due to festival",
  "added_by_id": 2,
  "food_time": "lunch"
}
```
- `creche_id`, `food_items` (array) are **required**.
- `reason`, `added_by_id`, `food_time` are optional.

**Response (200 OK):**
```json
{
  "status_code": 200,
  "message": "Food record attendent created successfully",
  "data": {
    "id": 1,
    "creche_id": 1,
    "creche_name": "Creche A",
    "food_items": ["Biscuits", "Khichdi", "Sambar"],
    "food_time": "lunch",
    "reason": "Menu updated due to festival",
    "added_by_id": 2,
    "food_update_date": "2026-08-10T16:00:00"
  }
}
```

---

### 2.6 List Food Record Attendant
- **URL:** `POST /food-record-attendent/list/`
- **Auth:** None
- **Content-Type:** `application/json`

**Request Body:**
```json
{
  "start_date": "2026-06-01",
  "end_date": "2026-06-23",
  "creche_id": 1,
  "food_time": "lunch"
}
```
- `start_date`, `end_date` (YYYY-MM-DD) are **required**.
- `creche_id`, `food_time` are optional filters.

**Response (200 OK):**
```json
{
  "status_code": 200,
  "message": "success",
  "data": {
    "total_records": 5,
    "total_dates": 3,
    "date_wise": [
      {
        "date": "2026-06-23",
        "records": [
          {
            "id": 1,
            "creche_id": 1,
            "creche_name": "Creche A",
            "food_items": ["Biscuits", "Khichdi"],
            "food_time": "lunch",
            "reason": null,
            "added_by_id": 1,
            "added_by_name": "John Doe",
            "food_update_date": "2026-06-23T12:00:00",
            "created_at": "2026-06-23T12:00:00",
            "updated_at": "2026-06-23T12:00:00"
          }
        ]
      }
    ]
  }
}
```

---

### 2.7 Creche List
- **URL:** `POST /reports/crechelist/`
- **Auth:** None
- **Content-Type:** `application/json`

**Request Body:**
```json
{
  "tea_garden_id": 285
}
```

**Response (200 OK):**
```json
[
  {
    "id": 1,
    "creche_code": "CR001",
    "creche_name": "Creche A",
    "attendants_count": 3,
    "children_count": 10
  }
]
```

---

### 2.8 Health Center List
- **URL:** `POST /reports/healthcenterlist/`
- **Auth:** None
- **Content-Type:** `application/json`

**Request Body:**
```json
{
  "tea_garden_id": 285
}
```

**Response (200 OK):**
```json
{
  "status_code": 200,
  "message": "success",
  "data": [
    {
      "id": 1,
      "code": "HC001",
      "name": "Health Center A"
    }
  ]
}
```

---

### 2.9 Tea Garden List
- **URL:** `GET /reports/teagardenlist/`
- **Auth:** None

**Response (200 OK):**
```json
{
  "status_code": 200,
  "message": "success",
  "data": [
    {
      "id": 285,
      "tea_garden_code": "TG001",
      "tea_garden_name": "Garden A"
    }
  ]
}
```

---

### 2.10 Attendant Attendance Report
- **URL:** `POST /reports/attendant-attendance/`
- **Auth:** None
- **Content-Type:** `application/json`

**Request Body:**
```json
{
  "tea_garden_id": 285,
  "creche_id": 1,
  "start_date": "2026-08-01",
  "end_date": "2026-08-10"
}
```

**Response (200 OK):**
```json
{
  "creche_id": 1,
  "creche_name": "Creche A",
  "tea_garden": "Garden A",
  "total_attendants": 3,
  "total_days": 10,
  "attendants": [
    {
      "attendant_id": 1,
      "name": "john",
      "role": "attendant",
      "present_days": 8,
      "absent_days": 2,
      "total_days": 10,
      "attendance_percentage": 80.0
    }
  ]
}
```

---

### 2.11 Creche Child Details
- **URL:** `POST /reports/children/`
- **Auth:** None
- **Content-Type:** `application/json`

**Request Body:**
```json
{
  "creche_id": 1,
  "child_id": 1
}
```

**Response (200 OK):**
```json
{
  "creche_id": 1,
  "creche_name": "Creche A",
  "tea_garden_id": 285,
  "tea_garden_name": "Garden A",
  "child": {
    "id": 1,
    "name": "Child Name",
    "age_years": 4,
    "gender": "M",
    "height_cm": 100.5,
    "weight_kg": 16.2,
    "guardian_name": "Guardian",
    "contact_person_name": "Contact",
    "contact_phone": "1234567890",
    "address": "Address",
    "photo_url": "http://server/media/children/photo.jpg",
    "gallery_urls": ["http://server/media/children/photo1.jpg"],
    "is_active": true,
    "enrollment_date": "2026-01-01",
    "created_by": "john",
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-01-01T00:00:00Z",
    "attendance_summary": {
      "total_present": 45,
      "total_absent": 5,
      "total_records": 50,
      "latest_attendance_date": "2026-08-10",
      "latest_attendance_status": "PRESENT"
    }
  }
}
```

---

### 2.12 Attendant Details
- **URL:** `POST /reports/attendant/details/`
- **Auth:** None
- **Content-Type:** `application/json`

**Request Body:**
```json
{
  "creche_id": 1,
  "attendant_id": 1
}
```

**Response (200 OK):**
```json
{
  "creche_id": 1,
  "creche_name": "Creche A",
  "tea_garden_id": 285,
  "tea_garden_name": "Garden A",
  "attendant": {
    "id": 1,
    "username": "john",
    "role": "attendant",
    "attendant_name": "John Doe",
    "mobile_no": "1234567890",
    "address": "Address",
    "photo_url": "http://server/media/attendants/photo.jpg",
    "is_active": true,
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-01-01T00:00:00Z"
  },
  "attendance_summary": {
    "total_attendance_days": 20,
    "latest_attendance_date": "2026-08-10",
    "latest_check_in_time": "2026-08-10T09:00:00Z",
    "latest_remarks": "Face verified via external API. Geo verified: True"
  },
  "attendance_records": [
    {
      "id": 1,
      "attendance_date": "2026-08-10",
      "check_in_time": "2026-08-10T09:00:00Z",
      "latitude": 26.1234,
      "longitude": 88.1234,
      "geo_verified": true,
      "remarks": "Face verified via external API. Geo verified: True"
    }
  ]
}
```

---

### 2.13 Creche Details
- **URL:** `POST /reports/crechedetails/`
- **Auth:** None
- **Content-Type:** `application/json`

**Request Body:**
```json
{
  "tea_garden_id": 285,
  "creche_id": 1
}
```

**Response (200 OK):**
```json
{
  "tea_garden_id": 285,
  "tea_garden_name": "Garden A",
  "creche": {
    "id": 1,
    "creche_name": "Creche A",
    "creche_code": "CR001",
    "location_name": "Location",
    "latitude": 26.1234,
    "longitude": 88.1234,
    "geo_radius_meters": 100,
    "is_active": true,
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-01-01T00:00:00Z"
  },
  "attendants": {
    "count": 3,
    "list": [
      {
        "id": 1,
        "username": "john",
        "role": "attendant",
        "name": "John Doe",
        "mobile_no": "1234567890",
        "address": "Address",
        "photo_url": "http://server/media/attendants/photo.jpg",
        "is_active": true,
        "recent_attendance": [
          {"attendance_date": "2026-08-10", "check_in_time": "2026-08-10T09:00:00Z", "remarks": "..."}
        ]
      }
    ]
  },
  "children": {
    "count": 10,
    "list": [
      {
        "id": 1,
        "name": "Child",
        "age_years": 4,
        "gender": "M",
        "guardian_name": "Guardian",
        "contact_person_name": "Contact",
        "contact_phone": "1234567890",
        "address": "Address",
        "photo_url": "http://server/media/children/photo.jpg",
        "gallery_urls": [],
        "is_active": true,
        "enrollment_date": "2026-01-01"
      }
    ]
  },
  "attendance_summary": {
    "total_present": 45,
    "total_absent": 5,
    "total_records": 50,
    "latest_attendance_date": "2026-08-10",
    "latest_attendance_status": "PRESENT",
    "recent_dates": [
      {"attendance_date": "2026-08-10", "attendance_mode": "GROUP", "present_count": 10, "absent_count": 0, "total_count": 10}
    ]
  },
  "attendant_attendance": {
    "total_records": 20
  },
  "food_monitoring": {
    "total_records": 5,
    "latest_monitoring_date": "2026-08-10",
    "records": [
      {
        "id": 1,
        "meal_type": "Lunch",
        "food_description": "Food Items:\n- Rice",
        "estimated_calories": 450.5,
        "estimated_protein_g": 12.3,
        "estimated_carbs_g": 60.2,
        "estimated_fibre_g": 5.1,
        "monitoring_date": "2026-08-10",
        "preparation_photo_url": null,
        "distribution_photo_url": null,
        "ambience_photo_url": null
      }
    ]
  }
}
```

---

### 2.14 Health Center Details
- **URL:** `POST /reports/healthcenter/details/`
- **Auth:** None
- **Content-Type:** `application/json`

**Request Body:**
```json
{
  "teagarden_id": 285,
  "healthcenter_id": 1
}
```

**Response (200 OK):**
```json
{
  "health_center": {
    "id": 1,
    "code": "HC001",
    "name": "Health Center A",
    "location_name": "Location",
    "latitude": 26.1234,
    "longitude": 88.1234,
    "geo_radius_meters": 100,
    "is_active": true,
    "tea_garden_name": "Garden A"
  },
  "doctors": {
    "count": 2,
    "list": [
      {
        "id": 1,
        "username": "drsmith",
        "name": "Dr. Smith",
        "specialization": "General Medicine",
        "qualification": "MBBS",
        "mobile_no": "1234567890",
        "photo_url": "http://server/media/doctors/photo.jpg",
        "is_active": true
      }
    ]
  },
  "nurses": {
    "count": 2,
    "list": [
      {
        "id": 1,
        "username": "jane",
        "nurse_name": "Jane Doe",
        "role": "nurse",
        "qualification": "GNM",
        "mobile_no": "9876543210",
        "photo_url": "http://server/media/nurses/photo.jpg",
        "is_active": true
      }
    ]
  },
  "head_nurses": {
    "count": 1,
    "list": []
  },
  "patients": {
    "count": 5,
    "recent_list": [
      {
        "id": 1,
        "patient_name": "Patient Name",
        "age": 30,
        "contact_number": "1234567890",
        "treatment_date": "2026-08-10",
        "whatsapp_sent": true,
        "remarks": "Remarks"
      }
    ]
  },
  "medicine_stock": {
    "count": 10,
    "list": [
      {
        "id": 1,
        "medicine_name": "Paracetamol",
        "medicine_code": "PARA001",
        "current_stock_qty": 15,
        "last_updated_at": "2026-08-10T00:00:00Z"
      }
    ]
  },
  "doctor_attendance": {
    "count": 2,
    "recent_list": [
      {
        "id": 1,
        "doctor_id": 1,
        "doctor_name": "Dr. Smith",
        "attendance_date": "2026-08-10",
        "check_in_time": "2026-08-10T09:00:00Z",
        "exit_time": "2026-08-10T12:00:00Z",
        "patients_visited_today": 5,
        "nurse_present": true,
        "hygiene_maintained": true,
        "remarks": "Remarks"
      }
    ]
  },
  "nurse_attendance": {
    "count": 2,
    "recent_list": [
      {
        "id": 1,
        "nurse_id": 1,
        "nurse_name": "Jane Doe",
        "role": "nurse",
        "attendance_date": "2026-08-10",
        "check_in_time": "2026-08-10T08:00:00Z",
        "remarks": "Remarks"
      }
    ]
  },
  "medicine_reports": {
    "low_stock_alerts": {
      "count": 1,
      "alerts": [
        {
          "medicine_id": 1,
          "medicine_name": "Paracetamol",
          "medicine_code": "PARA001",
          "current_stock": 3,
          "minimum_level": 5,
          "shortage": 2,
          "last_updated": "2026-08-10T00:00:00Z"
        }
      ]
    },
    "medicine_usage": {
      "count": 1,
      "recent_usage": [
        {
          "id": 1,
          "medicine_name": "Paracetamol",
          "medicine_code": "PARA001",
          "patient_name": "Patient",
          "treatment_date": "2026-08-10",
          "prescribed_qty": 10,
          "issued_qty": 10,
          "notes": "Prescribed by Dr. Smith"
        }
      ]
    },
    "medicine_transactions": {
      "count": 1,
      "recent_transactions": [
        {
          "id": 1,
          "medicine_name": "Paracetamol",
          "medicine_code": "PARA001",
          "transaction_type": "OUT",
          "quantity": 10,
          "reference_type": "PRESCRIPTION",
          "reference_id": 1,
          "transaction_at": "2026-08-10T00:00:00Z",
          "remarks": "Prescribed for patient"
        }
      ]
    },
    "medicine_requisitions": {
      "count": 1,
      "recent_requisitions": [
        {
          "id": 1,
          "requisition_week_start": "2026-08-03",
          "requisition_week_end": "2026-08-09",
          "requisition_date": "2026-08-03",
          "status": "SUBMITTED",
          "nurse_name": "Jane Doe",
          "remarks": "Weekly requisition",
          "medicines_count": 3,
          "medicines": [
            {
              "medicine_name": "Paracetamol",
              "medicine_code": "PARA001",
              "available_stock_qty": 5,
              "requested_qty": 50,
              "auto_low_stock_flag": true,
              "remarks": "Low stock"
            }
          ]
        }
      ]
    },
    "medicine_statistics": {
      "count": 10,
      "statistics": [
        {
          "medicine_id": 1,
          "medicine_name": "Paracetamol",
          "medicine_code": "PARA001",
          "current_stock": 15,
          "min_stock_level": 5,
          "unit_name": "Tablet",
          "recent_usage": {
            "total_prescribed": 30,
            "total_issued": 30,
            "usage_count": 3
          },
          "transaction_summary": {
            "total_in": 50,
            "total_out": 30,
            "total_adjustment": 0
          }
        }
      ]
    }
  }
}
```

---

## 3. Child Attendance

### 3.1 Mark Attendance (Group Photo)
- **URL:** `POST /attendance/mark/`
- **Auth:** None (AllowAny)
- **Content-Type:** `multipart/form-data`

**Request Body:**
```
file: <group photo image>     # required (also accepts 'photo', 'image', 'attendance_photo')
creche_id: 1                  # required
marked_by_id: 1               # required (CrecheAttendant ID; also accepts 'mark_by_id')
```

**Response (200 OK):**
```json
{
  "status_code": 200,
  "message": "success",
  "data": {
    "attendance_id": 1,
    "creche_id": 1,
    "creche_name": "Creche A",
    "attendance_date": "2026-08-10",
    "attendance_mode": "GROUP",
    "total_faces_detected": 10,
    "total_faces_recognized": 8,
    "unknown_faces": 2,
    "spoof_faces": 0,
    "total_children": 10,
    "present_count": 8,
    "absent_count": 2,
    "present_children": [
      {"child_id": 1, "child_name": "Child 1"}
    ],
    "already_present_children": [],
    "absent_children": [
      {"child_id": 9, "child_name": "Child 9"}
    ],
    "external_attendance_id": 123,
    "attendance_photo": "/path/to/photo.jpg",
    "annotated_image_base64": "",
    "attendance_photo_url": "http://server/media/attendance_photos/photo.jpg",
    "external_photo_path": "/path/to/photo.jpg"
  }
}
```

**Notes:** The group photo is forwarded to an external face recognition API (`http://45.64.107.97:5010/api/v1/attendance/child`) which detects and recognizes children.

---

### 3.2 Mark Individual Child Attendance
- **URL:** `POST /attendance/mark-individual/`
- **Auth:** None (AllowAny)
- **Content-Type:** `application/json`

**Request Body:**
```json
{
  "child_id": [1, 2, 3],
  "creche_id": 1,
  "attendance_status": "PRESENT",
  "marked_by_id": 1
}
```
- `child_id`: single ID or array of IDs (**required**).
- `attendance_status`: `PRESENT` or `ABSENT` (default `PRESENT`).
- `creche_id`, `marked_by_id`: optional.

**Response (200 OK):**
```json
{
  "status_code": 200,
  "message": "Attendance marked successfully for 3 children as PRESENT",
  "data": {
    "attendance_id": 1,
    "creche_id": 1,
    "creche_name": "Creche A",
    "attendance_date": "2026-08-10",
    "attendance_status": "PRESENT",
    "attendance_mode": "INDIVIDUAL",
    "total_marked": 3,
    "children": [
      {
        "child_id": 1,
        "child_name": "Child 1",
        "front_image": "http://server/media/children/photo.jpg",
        "attendance_status": "PRESENT",
        "is_newly_created": true
      }
    ]
  }
}
```

---

### 3.3 Detect Children From Photo
- **URL:** `POST /attendance/detect-children/`
- **Auth:** None (AllowAny)
- **Content-Type:** `multipart/form-data`

**Request Body:**
```
file: <group photo image>     # required (also accepts 'photo', 'image', 'attendance_photo')
creche_id: 1                  # required
marked_by_id: 1               # optional
```

**Response (200 OK):**
```json
{
  "status_code": 200,
  "message": "Detection successful",
  "data": {
    "total_faces_detected": 8,
    "unknown_faces": 2,
    "spoof_faces": 0,
    "children": [
      {
        "child_id": 1,
        "front_image": "http://server/media/children/photo.jpg",
        "name": "Child 1",
        "child_status": "Mark Attendance"
      }
    ]
  }
}
```

**Notes:** Detects children from a photo **without** updating the database. `child_status` is either `"Mark Attendance"` or `"Already Mark Attendance"`.

---

### 3.4 Get Attendance By Date
- **URL:** `GET /attendance/by-date/?creche_id=1&date=2026-08-10`
- **Auth:** None (AllowAny)

**Query Parameters:**
- `creche_id` (**required**)
- `date` (**required**, format `YYYY-MM-DD`)

**Response (200 OK):**
```json
{
  "attendance_id": 1,
  "creche_id": 1,
  "creche_name": "Creche A",
  "attendance_date": "2026-08-10",
  "attendance_mode": "GROUP",
  "remarks": "Total faces detected: 10, Unknown: 2, Spoof: 0",
  "total_children": 10,
  "present_count": 8,
  "absent_count": 2,
  "children": [
    {
      "child_id": 1,
      "child_name": "Child 1",
      "age_years": 4,
      "gender": "M",
      "status": "PRESENT"
    }
  ]
}
```

**Notes:** If no attendance exists for the date, returns all children with default `ABSENT` status and `attendance_id: null`.

---

### 3.5 Child Attendance History
- **URL:** `GET /attendance/child-history/?child_id=1`
- **Auth:** None (AllowAny)

**Query Parameters:**
- `child_id` (**required**)

**Response (200 OK):**
```json
{
  "child_id": 1,
  "child_name": "Child 1",
  "creche_id": 1,
  "creche_name": "Creche A",
  "total_records": 50,
  "present_count": 45,
  "absent_count": 5,
  "attendance_percentage": 90.0,
  "history": [
    {
      "attendance_id": 1,
      "attendance_date": "2026-08-10",
      "attendance_mode": "GROUP",
      "creche_id": 1,
      "creche_name": "Creche A",
      "status": "PRESENT"
    }
  ]
}
```

---

### 3.6 Attendance By Date Range
- **URL:** `GET /attendance/date-range/?creche_id=1&from=2026-08-01&to=2026-08-10`
- **Auth:** None (AllowAny)

**Query Parameters:**
- `creche_id` (**required**)
- `from` (**required**, format `YYYY-MM-DD`)
- `to` (**required**, format `YYYY-MM-DD`)

**Response (200 OK):**
```json
{
  "creche_id": 1,
  "creche_name": "Creche A",
  "date_range": {
    "from": "2026-08-01",
    "to": "2026-08-10"
  },
  "total_children": 10,
  "total_days_marked": 8,
  "total_present_entries": 70,
  "total_absent_entries": 10,
  "daily_breakdown": [
    {
      "attendance_id": 1,
      "attendance_date": "2026-08-10",
      "attendance_mode": "GROUP",
      "present_count": 8,
      "absent_count": 2,
      "total_marked": 10,
      "remarks": "Total faces detected: 10"
    }
  ]
}
```

---

## 4. Child Growth Monitoring

### 4.1 Create / Update Child Growth
- **URL:** `POST /child-growth/create/`
- **Auth:** None (AllowAny)
- **Content-Type:** `multipart/form-data`

**Request Body:**
```
child_id: 1                  # required
height_cm: 100.5             # optional
weight_kg: 16.2              # optional
notes: Some notes            # optional
weight_pic: <image file>     # optional
height_pic: <image file>     # optional
```

**Response (200 OK):**
```json
{
  "status_code": 200,
  "message": "Growth monitoring record saved successfully",
  "data": {
    "id": 1,
    "child_id": 1,
    "child_name": "Child 1",
    "measured_on": "2026-08-10",
    "height_cm": "100.5",
    "weight_kg": "16.2",
    "notes": "Some notes",
    "weight_pic": "http://server/media/growth/weight.jpg",
    "height_pic": "http://server/media/growth/height.jpg",
    "is_newly_created": true
  }
}
```

**Notes:** `measured_on` is automatically set to the current date. If a record already exists for the same child on the same date, it is updated.

---

### 4.2 Child Growth History
- **URL:** `GET /child-growth/history/?child_id=1`
- **Auth:** None (AllowAny)

**Query Parameters:**
- `child_id` (**required**)

**Response (200 OK):**
```json
{
  "status_code": 200,
  "message": "Success",
  "data": {
    "child_id": 1,
    "child_name": "Child 1",
    "creche_id": 1,
    "creche_name": "Creche A",
    "total_records": 5,
    "records": [
      {
        "id": 1,
        "measured_on": "2026-08-10",
        "height_cm": "100.5",
        "weight_kg": "16.2",
        "notes": "Some notes",
        "weight_pic": "http://server/media/growth/weight.jpg",
        "height_pic": "http://server/media/growth/height.jpg",
        "created_at": "2026-08-10T00:00:00Z"
      }
    ]
  }
}
```

---

### 4.3 Child Growth Detail
- **URL:** `GET /child-growth/detail/?record_id=1`
- **Auth:** None (AllowAny)

**Query Parameters:**
- `record_id` (**required**)

**Response (200 OK):**
```json
{
  "status_code": 200,
  "message": "Success",
  "data": {
    "id": 1,
    "child_id": 1,
    "child_name": "Child 1",
    "creche_id": 1,
    "creche_name": "Creche A",
    "measured_on": "2026-08-10",
    "height_cm": "100.5",
    "weight_kg": "16.2",
    "notes": "Some notes",
    "weight_pic": "http://server/media/growth/weight.jpg",
    "height_pic": "http://server/media/growth/height.jpg",
    "created_at": "2026-08-10T00:00:00Z"
  }
}
```

---

### 4.4 Delete Child Growth
- **URL:** `DELETE /child-growth/delete/?record_id=1`
- **Auth:** None (AllowAny)

**Query Parameters:**
- `record_id` (**required**)

**Response (200 OK):**
```json
{
  "status_code": 200,
  "message": "Growth monitoring record deleted successfully"
}
```

---

### 4.5 Child Growth By Date Range
- **URL:** `GET /child-growth/date-range/?child_id=1&from=2026-01-01&to=2026-12-31`
- **Auth:** None (AllowAny)

**Query Parameters:**
- `child_id` (**required**)
- `from` (**required**, format `YYYY-MM-DD`)
- `to` (**required**, format `YYYY-MM-DD`)

**Response (200 OK):**
```json
{
  "status_code": 200,
  "message": "Success",
  "data": {
    "child_id": 1,
    "child_name": "Child 1",
    "creche_id": 1,
    "creche_name": "Creche A",
    "date_range": {
      "from": "2026-01-01",
      "to": "2026-12-31"
    },
    "total_records": 5,
    "records": [
      {
        "id": 1,
        "measured_on": "2026-08-10",
        "height_cm": "100.5",
        "weight_kg": "16.2",
        "notes": "Some notes",
        "weight_pic": "http://server/media/growth/weight.jpg",
        "height_pic": "http://server/media/growth/height.jpg",
        "created_at": "2026-08-10T00:00:00Z"
      }
    ]
  }
}
```

---

## 5. Patient Management

### 5.1 Add Patient
- **URL:** `POST /patient/add/`
- **Auth:** None (AllowAny)
- **Content-Type:** `application/json`

**Request Body:**
```json
{
  "patient_name": "Patient Name",
  "age": 30,
  "contact_number": "1234567890",
  "health_center_id": 1,
  "nurse_id": 1,
  "doctor_id": 1,
  "status": 1,
  "remarks": "Remarks"
}
```
- `patient_name`, `health_center_id` are **required**.
- Others are optional.

**Response (201 Created):**
```json
{
  "status_code": 201,
  "message": "Patient added successfully",
  "data": {
    "patient_id": 1,
    "patient_name": "Patient Name",
    "age": 30,
    "contact_number": "1234567890",
    "health_center_id": 1,
    "health_center_name": "Health Center A",
    "nurse_id": 1,
    "nurse_name": "Jane Doe",
    "doctor_id": 1,
    "doctor_name": "Dr. Smith",
    "status": 1,
    "treatment_date": "2026-08-10",
    "remarks": "Remarks",
    "created_at": "2026-08-10T00:00:00Z"
  }
}
```

---

### 5.2 Patient List
- **URL:** `GET /patient/list/` or `POST /patient/list/`
- **Auth:** None (AllowAny)

**GET Query Parameters (all optional):**
- `health_center_id`
- `nurse_id`
- `doctor_id`

**POST Request Body (all optional):**
```json
{
  "health_center_id": 2,
  "nurse_id": 1,
  "doctor_id": 3
}
```

**Response (200 OK):**
```json
{
  "status_code": 200,
  "message": "Patients retrieved successfully",
  "data": [
    {
      "id": 1,
      "patient_name": "Patient Name",
      "age": 30,
      "contact_number": "1234567890",
      "health_center": 1,
      "nurse": 1,
      "doctor": 1,
      "status": 1,
      "treatment_date": "2026-08-10",
      "remarks": "Remarks",
      "created_at": "2026-08-10T00:00:00Z"
    }
  ],
  "total_count": 1
}
```

---

### 5.3 Patient Detail
- **URL:** `GET /patient/<patient_id>/`, `PUT /patient/<patient_id>/`, `DELETE /patient/<patient_id>/`
- **Auth:** None (AllowAny)

**GET Response (200 OK):**
```json
{
  "status_code": 200,
  "message": "Patient retrieved successfully",
  "data": {
    "id": 1,
    "patient_name": "Patient Name",
    "age": 30,
    "contact_number": "1234567890",
    "health_center": 1,
    "nurse": 1,
    "doctor": 1,
    "status": 1,
    "treatment_date": "2026-08-10",
    "remarks": "Remarks",
    "created_at": "2026-08-10T00:00:00Z"
  }
}
```

**PUT Request Body (all optional):**
```json
{
  "patient_name": "Updated Name",
  "age": 31,
  "contact_number": "0987654321",
  "status": 2,
  "remarks": "Updated remarks",
  "nurse_id": 2,
  "doctor_id": 2
}
```

**DELETE Response (200 OK):**
```json
{
  "status_code": 200,
  "message": "Patient deleted successfully",
  "data": {}
}
```

---

## 6. Doctor Check-In / Check-Out

### 6.1 Doctor Check-In
- **URL:** `POST /doctor/check-in/`
- **Auth:** Bearer Token (IsAuthenticated, role must be `doctor`)
- **Content-Type:** `multipart/form-data`

**Request Body:**
```
photo: <image file>              # required
latitude: 26.1234                # required
longitude: 88.1234               # required
health_center_id: 1              # required
attendance_date: 2026-08-10      # optional
nurse_present: true              # optional
hygiene_maintained: true         # optional
patients_visited_today: 5        # optional
```

**Response (200 OK):**
```json
{
  "status_code": 200,
  "message": "Check-in successful",
  "data": {
    "check_in_id": 1,
    "doctor_id": 1,
    "doctor_name": "Dr. Smith",
    "check_in_date": "2026-08-10",
    "attendance_date": "2026-08-10",
    "check_in_time": "2026-08-10T09:00:00Z",
    "face_verified": true,
    "geo_verified": true,
    "health_center": "Health Center A",
    "nurse_present": true,
    "hygiene_maintained": true,
    "patients_visited_today": 5,
    "timer_duration_minutes": 120,
    "timer_end_time": "2026-08-10T11:00:00Z",
    "image_url": "http://..."
  }
}
```

**Notes:**
- Face verification is done via external API (`http://45.64.107.97:5010/api/v1/attendance/doctor`).
- Geo verification uses Haversine distance against the health center's coordinates and radius.
- Returns `409` if already checked in today.
- Returns `401` if face verification fails.

---

### 6.2 Doctor Check-Out
- **URL:** `POST /doctor/check-out/`
- **Auth:** Bearer Token (IsAuthenticated, role must be `doctor`)
- **Content-Type:** `multipart/form-data`

**Request Body:**
```
check_in_id: 1                   # required
photo: <image file>              # required
latitude: 26.1234                # required
longitude: 88.1234               # required
nurse_present: true              # optional
hygiene_maintained: true         # optional
patients_visited_today: 5        # optional
```

**Response (200 OK):**
```json
{
  "status_code": 200,
  "message": "Check-out successful",
  "data": {
    "check_in_id": 1,
    "check_in_time": "2026-08-10T09:00:00Z",
    "check_out_time": "2026-08-10T12:00:00Z",
    "duration_minutes": 180,
    "nurse_present": true,
    "hygiene_maintained": true,
    "patients_visited_today": 5
  }
}
```

**Notes:** If the 2.5-hour timer expires and the doctor did not provide optional fields, the doctor is automatically marked as checked out with a remark.

---

### 6.3 Doctor Check-In Status
- **URL:** `GET /doctor/check-in/status/`
- **Auth:** Bearer Token (IsAuthenticated, role must be `doctor`)

**Response (200 OK) - Checked in:**
```json
{
  "status_code": 200,
  "message": "success",
  "data": {
    "is_checked_in": true,
    "check_in_id": 1,
    "check_in_time": "2026-08-10T09:00:00Z",
    "remaining_time_minutes": 95,
    "timer_expired": false,
    "health_center": "Health Center A",
    "face_verified": true,
    "geo_verified": true
  }
}
```

**Response (200 OK) - Not checked in:**
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

---

## 7. Doctor List

### 7.1 Doctor List
- **URL:** `POST /doctors/list/`
- **Auth:** Bearer Token (IsAuthenticated)
- **Content-Type:** `application/json`

**Request Body:**
```json
{
  "health_center_id": 1,
  "is_active": true
}
```
- `health_center_id` is **required**.
- `is_active` is optional.

**Response (200 OK):**
```json
{
  "status_code": 200,
  "message": "Doctors retrieved successfully",
  "data": [
    {
      "id": 1,
      "user_id": 5,
      "username": "doctor1",
      "health_center_id": 1,
      "health_center_name": "Health Center A",
      "name": "Dr. John Doe",
      "mobile_no": "1234567890",
      "qualification": "MBBS",
      "specialization": "General Medicine",
      "photo": "http://server/media/doctors/photo.jpg",
      "is_active": true,
      "created_at": "2026-01-01T10:00:00Z",
      "updated_at": "2026-01-15T10:00:00Z"
    }
  ]
}
```

---

### 7.2 Doctor Detail
- **URL:** `GET /doctor/<doctor_id>/`
- **Auth:** Bearer Token (IsAuthenticated)

**Response (200 OK):**
```json
{
  "status_code": 200,
  "message": "Doctor retrieved successfully",
  "data": {
    "id": 1,
    "user_id": 5,
    "username": "doctor1",
    "health_center_id": 1,
    "health_center_name": "Health Center A",
    "name": "Dr. John Doe",
    "mobile_no": "1234567890",
    "qualification": "MBBS",
    "specialization": "General Medicine",
    "photo": "http://server/media/doctors/photo.jpg",
    "is_active": true,
    "created_at": "2026-01-01T10:00:00Z",
    "updated_at": "2026-01-15T10:00:00Z"
  }
}
```

---

## 8. e-Prescription & Medicine

### 8.1 Generate Prescription
- **URL:** `POST /prescription/generate/`
- **Auth:** Bearer Token (IsAuthenticated)
- **Content-Type:** `multipart/form-data`

**Request Body:**
```
health_center_id: 1                    # required
nurse_id: 1                            # required
doctor_id: 1                           # required
patient_treatment_id: 1                # required
medicines: [{"id": 1, "quantity": 10}, {"id": 2, "quantity": 5}]   # required (JSON array)
doctor_remarks: Take medicine twice daily   # required
doctor_prescription_image: <image file>    # required
send_whatsapp: true                    # optional (default true)
```

**Response (200 OK):**
```json
{
  "status_code": 200,
  "message": "Prescription generated successfully",
  "data": {
    "prescription_id": 1,
    "prescription_url": "http://server/media/prescriptions/prescription_1.pdf",
    "doctor_prescription_image_url": "http://server/media/prescriptions/doctor_prescription_1.jpg",
    "pdf_generated": true,
    "pdf_error": null,
    "patient": {
      "id": 1,
      "name": "Patient Name",
      "age": 30,
      "contact_number": "1234567890",
      "remarks": "Remarks"
    },
    "health_center": {
      "id": 1,
      "name": "Health Center A"
    },
    "nurse": {
      "id": 1,
      "name": "Jane Doe"
    },
    "doctor": {
      "id": 1,
      "name": "Dr. Smith",
      "qualification": "MBBS",
      "specialization": "General Medicine"
    },
    "prescription_data": {
      "medicines": [
        {"medicine_id": 1, "medicine_name": "Paracetamol", "medicine_code": "PARA001", "quantity": 10}
      ],
      "generated_at": "2026-08-10T00:00:00Z"
    },
    "stock_deductions": [
      {
        "medicine_id": 1,
        "medicine_name": "Paracetamol",
        "previous_stock": 15,
        "deducted": 10,
        "remaining_stock": 5
      }
    ],
    "insufficient_stock": [],
    "whatsapp_status": "sent",
    "whatsapp_details": "WhatsApp message sent to 1234567890"
  }
}
```

**Notes:**
- Generates a professional PDF prescription (via reportlab) and stores it in `PatientTreatment.prescription_image`.
- Deducts prescribed medicine quantities from `HealthCenterMedicineStock`.
- Creates `MedicineStockTransaction` (type `OUT`, reference `PRESCRIPTION`) and `PatientTreatmentMedicine` records.
- Optionally sends the prescription via WhatsApp to the patient's contact number.
- `whatsapp_status`: `sent`, `failed`, or `skipped`.

---

### 8.2 Medicine List
- **URL:** `POST /medicine/list/`
- **Auth:** Bearer Token (IsAuthenticated)
- **Content-Type:** `application/json`

**Request Body:**
```json
{
  "health_center_id": 1
}
```

**Response (200 OK):**
```json
{
  "status_code": 200,
  "message": "Medicines fetched successfully",
  "data": {
    "medicines": [
      {
        "id": 1,
        "name": "Paracetamol",
        "code": "PARA001",
        "unit": "Tablet",
        "min_stock_level": 5,
        "current_stock_qty": 15,
        "last_updated_at": "2026-08-10T00:00:00Z",
        "is_low_stock": false
      }
    ],
    "total_count": 10,
    "health_center_id": 1
  }
}
```

**Notes:** Lists all active medicines with their stock at the given health center. `is_low_stock` is `true` when `current_stock_qty < min_stock_level`.

---

### 8.3 Medicine Entry (Stock Inward)
- **URL:** `POST /medicine/entry/`
- **Auth:** Bearer Token (IsAuthenticated)
- **Content-Type:** `application/json`

**Request Body:**
```json
{
  "health_center_id": 1,
  "nurse_id": 1,
  "requisition_week_start": "2026-06-01",
  "requisition_week_end": "2026-06-07",
  "medicines": [
    {
      "medicine_id": 1,
      "received_qty": 50,
      "remarks": "Weekly stock received"
    },
    {
      "medicine_name": "Paracetamol",
      "received_qty": 30,
      "unit_name": "Tablet",
      "min_stock_level": 10
    }
  ]
}
```
- `health_center_id`, `nurse_id`, `medicines` (non-empty array) are **required**.

**Response (200 OK):**
```json
{
  "status_code": 200,
  "message": "Medicine entry recorded successfully",
  "data": {
    "requisition_id": 1,
    "requisition_date": "2026-06-03",
    "status": "FULFILLED",
    "requisition_matched": true,
    "health_center_id": 1,
    "health_center_name": "Health Center A",
    "nurse_id": 1,
    "nurse_name": "Jane Doe",
    "medicines": [
      {
        "medicine_id": 1,
        "medicine_name": "Paracetamol",
        "medicine_code": "PARA001",
        "previous_stock": 10,
        "received_qty": 50,
        "current_stock": 60,
        "transaction_id": 5,
        "requisition_detail_matched": true
      }
    ],
    "total_medicines": 1
  }
}
```

**Notes:**
- Processes medicines against an existing `SUBMITTED` or `APPROVED` requisition, or creates a new `FULFILLED` requisition.
- Medicine resolution: by `medicine_id` → by `medicine_name` → create new Medicine record.
- `received_qty` must be ≥ the medicine's `min_stock_level`.
- Creates `MedicineStockTransaction` (type `IN`, reference `REQUISITION`).

---

### 8.4 Medicine Detail
- **URL:** `GET /medicine/<medicine_id>/`
- **Auth:** Bearer Token (IsAuthenticated)

**Response (200 OK):**
```json
{
  "status_code": 200,
  "message": "Medicine details fetched",
  "data": {
    "id": 1,
    "name": "Paracetamol",
    "code": "PARA001",
    "unit": "Tablet",
    "min_stock_level": 5,
    "is_active": true,
    "created_at": "2026-06-02T04:48:04Z",
    "stock_across_centers": [
      {
        "health_center_id": 1,
        "health_center_name": "Health Center 1",
        "current_stock_qty": 15,
        "last_updated_at": "2026-06-02T04:48:04Z",
        "is_low_stock": false
      }
    ],
    "total_stock": 15
  }
}
```

---

## 9. Medicine Units

### 9.1 Medicine Unit List / Create
- **URL:** `GET /medicine/units/` and `POST /medicine/units/`
- **Auth:** Bearer Token (IsAuthenticated)

**GET Response (200 OK):**
```json
{
  "status_code": 200,
  "message": "Medicine units retrieved successfully",
  "data": [
    {"id": 1, "unit_name": "Syrup"}
  ]
}
```

**POST Request Body:**
```json
{
  "unit_name": "Syrup"
}
```

**POST Response (201 Created):**
```json
{
  "status_code": 201,
  "message": "Medicine unit created successfully",
  "data": {
    "id": 1,
    "unit_name": "Syrup"
  }
}
```

---

### 9.2 Medicine Unit Detail
- **URL:** `GET /medicine/units/<unit_id>/`, `PUT /medicine/units/<unit_id>/`, `DELETE /medicine/units/<unit_id>/`
- **Auth:** Bearer Token (IsAuthenticated)

**GET Response (200 OK):**
```json
{
  "status_code": 200,
  "message": "Medicine unit retrieved successfully",
  "data": {
    "id": 1,
    "unit_name": "Syrup"
  }
}
```

**PUT Request Body:**
```json
{
  "unit_name": "Capsule"
}
```

**DELETE Response (200 OK):**
```json
{
  "status_code": 200,
  "message": "Medicine unit deleted successfully"
}
```

---

## 10. Medicine Min Stock Level

### 10.1 Update Min Stock Level / Add Medicine
- **URL:** `POST /medicine/min-stock/update/`
- **Auth:** Bearer Token (IsAuthenticated)
- **Content-Type:** `application/json`

**Request Body - Update existing medicine:**
```json
{
  "medicine_id": 1,
  "min_stock_level": 10
}
```

**Request Body - Add new medicine:**
```json
{
  "medicine_name": "New Medicine",
  "medicine_code": "MED001",
  "unit_name": "Capsule",
  "min_stock_level": 10
}
```

**Request Body - Bulk mode:**
```json
{
  "medicines": [
    {"medicine_id": 1, "min_stock_level": 10},
    {"medicine_name": "Paracetamol", "medicine_code": "MED002", "min_stock_level": 8}
  ]
}
```

**Response (200 OK):**
```json
{
  "status_code": 200,
  "message": "Processed 1 medicine(s) successfully",
  "data": {
    "updated_medicines": [
      {
        "medicine_id": 1,
        "medicine_name": "Paracetamol",
        "medicine_code": "MED001",
        "previous_min_stock_level": 5,
        "new_min_stock_level": 10,
        "is_new_medicine": false
      }
    ],
    "total_updated": 1,
    "errors": []
  }
}
```

**Medicine Resolution Logic:**
1. If `medicine_id` provided → update that existing medicine.
2. If `medicine_name` matches an existing medicine → update it.
3. If `medicine_name` is new → create a new medicine record.
4. If neither resolves → error.

---

## 11. Medicine Requisition

### 11.1 Create Medicine Requisition
- **URL:** `POST /medicine/requisition/create/`
- **Auth:** None
- **Content-Type:** `application/json`

**Request Body:**
```json
{
  "health_center_id": 1,
  "nurse_id": 1,
  "requisition_week_start": "2026-07-20",
  "requisition_week_end": "2026-07-26",
  "medicines": [
    {
      "medicine_id": 1,
      "requested_qty": 50,
      "remarks": "Low stock, need replenishment"
    },
    {
      "medicine_name": "Paracetamol",
      "requested_qty": 30,
      "unit_name": "Tablet",
      "min_stock_level": 10
    }
  ],
  "remarks": "Weekly requisition for July 4th week"
}
```
- `health_center_id`, `nurse_id`, `medicines` (non-empty array) are **required**.

**Response (200 OK):**
```json
{
  "status_code": 200,
  "message": "Medicine requisition created successfully",
  "data": {
    "requisition_id": 1,
    "requisition_date": "2026-07-23",
    "status": "SUBMITTED",
    "health_center_id": 1,
    "health_center_name": "Health Center A",
    "nurse_id": 1,
    "nurse_name": "Jane Doe",
    "week_start": "2026-07-20",
    "week_end": "2026-07-26",
    "remarks": "Weekly requisition for July 4th week",
    "medicines": [
      {
        "medicine_id": 1,
        "medicine_name": "Paracetamol",
        "medicine_code": "PARA001",
        "current_stock_qty": 5,
        "min_stock_level": 5,
        "available_stock_qty": 5,
        "requested_qty": 50,
        "auto_low_stock_flag": false,
        "remarks": "Low stock, need replenishment"
      }
    ],
    "total_medicines": 1
  }
}
```

**Notes:**
- `available_stock_qty` is automatically fetched from `HealthCenterMedicineStock.current_stock_qty` (defaults to 0 if no record).
- `auto_low_stock_flag` is `true` when current stock is below `min_stock_level`.
- Medicine resolution: by `medicine_id` → by `medicine_name` → create new Medicine record.

---

### 11.2 List Medicine Requisitions
- **URL:** `POST /medicine/requisition/list/`
- **Auth:** None
- **Content-Type:** `application/json`

**Request Body:**
```json
{
  "health_center_id": 1,
  "status": "SUBMITTED",
  "start_date": "2026-07-01",
  "end_date": "2026-07-31"
}
```
- `health_center_id` is **required**.
- `status`: `DRAFT`, `SUBMITTED`, `APPROVED`, `REJECTED`, `FULFILLED` (optional).
- `start_date`, `end_date`: filter by `requisition_date` (optional).

**Response (200 OK):**
```json
{
  "status_code": 200,
  "message": "success",
  "data": {
    "total_requisitions": 5,
    "requisitions": [
      {
        "requisition_id": 1,
        "requisition_date": "2026-07-23",
        "status": "SUBMITTED",
        "health_center_id": 1,
        "health_center_name": "Health Center A",
        "nurse_id": 1,
        "nurse_name": "Jane Doe",
        "week_start": "2026-07-20",
        "week_end": "2026-07-26",
        "remarks": "Weekly requisition",
        "total_medicines": 3,
        "medicines": [
          {
            "id": 1,
            "name": "Paracetamol",
            "code": "PARA001",
            "current_stock_qty": 5,
            "requested_qty": 50,
            "auto_low_stock_flag": true,
            "remarks": "Low stock"
          }
        ]
      }
    ]
  }
}
```

---

### 11.3 Medicine Requisition Detail
- **URL:** `POST /medicine/requisition/detail/`
- **Auth:** None
- **Content-Type:** `application/json`

**Request Body:**
```json
{
  "requisition_id": 1
}
```

**Response (200 OK):**
```json
{
  "status_code": 200,
  "message": "success",
  "data": {
    "requisition_id": 1,
    "requisition_date": "2026-07-23",
    "status": "SUBMITTED",
    "health_center_id": 1,
    "health_center_name": "Health Center A",
    "nurse_id": 1,
    "nurse_name": "Jane Doe",
    "week_start": "2026-07-20",
    "week_end": "2026-07-26",
    "remarks": "Weekly requisition",
    "total_medicines": 3,
    "medicines": [
      {
        "medicine_id": 1,
        "medicine_name": "Paracetamol",
        "medicine_code": "PARA001",
        "available_stock_qty": 5,
        "requested_qty": 50,
        "auto_low_stock_flag": true,
        "remarks": "Low stock"
      }
    ]
  }
}
```

---

### 11.4 Update Medicine Requisition Status
- **URL:** `POST /medicine/requisition/status-update/`
- **Auth:** None
- **Content-Type:** `application/json`

**Request Body:**
```json
{
  "requisition_id": 1,
  "status": "APPROVED",
  "remarks": "Approved by admin"
}
```
- `requisition_id`, `status` are **required**.
- Valid statuses: `DRAFT`, `SUBMITTED`, `APPROVED`, `REJECTED`, `FULFILLED`.

**Response (200 OK):**
```json
{
  "status_code": 200,
  "message": "Requisition status updated to APPROVED",
  "data": {
    "requisition_id": 1,
    "status": "APPROVED",
    "previous_status": "SUBMITTED",
    "remarks": "[2026-08-10 16:00] Status changed to APPROVED: Approved by admin"
  }
}
```

---

## 12. Unified Check-In (Attendant/Nurse)

### 12.1 Check-In
- **URL:** `POST /check-in/`
- **Auth:** Bearer Token (IsAuthenticated; user must be attendant, super_attendant, nurse, or head_nurse)
- **Content-Type:** `multipart/form-data`

**Request Body (Attendant / Super Attendant):**
```
file: <image file>           # required
latitude: 26.1234            # required
longitude: 88.1234           # required
creche_id: 1                 # required
```

**Request Body (Nurse / Head Nurse):**
```
file: <image file>           # required
latitude: 26.1234            # required
longitude: 88.1234           # required
health_center_id: 1          # required
```

**Response (200 OK):**
```json
{
  "status_code": 200,
  "message": "Check-in successful",
  "data": {
    "attendance_id": 1,
    "profile_id": 1,
    "person_name": "John Doe",
    "role": "attendant",
    "location_id": 1,
    "location_name": "Creche A",
    "check_in_date": "2026-08-10",
    "check_in_time": "2026-08-10T09:00:00Z",
    "face_verified": true,
    "geo_verified": true,
    "image_url": "http://..."
  }
}
```

**Notes:**
- Role is determined automatically from the authenticated user's profile.
- Face verification via external API (`/api/v1/attendance/attendant` for attendants, `/api/v1/attendance/nurse` for nurses).
- Geo verification uses Haversine distance against the location's coordinates and radius.
- Returns `409` if already checked in today.
- Returns `401` if face verification fails.

---

### 12.2 Check-In Status
- **URL:** `GET /check-in/status/`
- **Auth:** Bearer Token (IsAuthenticated)

**Response (200 OK) - Checked in:**
```json
{
  "status_code": 200,
  "message": "success",
  "data": {
    "is_checked_in": true,
    "role": "attendant",
    "attendance_id": 1,
    "person_name": "John Doe",
    "profile_id": 1,
    "location_name": "Creche A",
    "check_in_time": "2026-08-10T09:00:00Z",
    "face_verified": true,
    "geo_verified": true,
    "remarks": "Face verified via external API. Geo verified: True"
  }
}
```

**Response (200 OK) - Not checked in:**
```json
{
  "status_code": 200,
  "message": "No active check-in found",
  "data": {
    "is_checked_in": false,
    "role": "attendant",
    "person_name": "John Doe",
    "attendance_id": null,
    "check_in_time": null
  }
}
```

---

## 13. Attendant & Nurse Management (Admin)

### 13.1 Attendant List By Tea Garden
- **URL:** `POST /attendants/list/`
- **Auth:** Bearer Token (IsAuthenticated; role must be `superadmin` or `teagarden_head`)
- **Content-Type:** `application/json`

**Request Body:**
```json
{
  "tea_garden_id": 285,
  "creche_id": 1
}
```
- `tea_garden_id` is **required**.
- `creche_id` is optional.

**Response (200 OK):**
```json
{
  "status_code": 200,
  "message": "success",
  "data": [
    {
      "id": 1,
      "user_id": 5,
      "username": "john",
      "name": "John Doe",
      "role": "attendant",
      "mobile_no": "1234567890",
      "address": "Address",
      "creche_id": 1,
      "creche_name": "Creche A",
      "tea_garden_id": 285,
      "tea_garden_name": "Garden A",
      "is_active": true
    }
  ]
}
```

---

### 13.2 Nurse List By Tea Garden
- **URL:** `POST /nurses/list/`
- **Auth:** Bearer Token (IsAuthenticated; role must be `superadmin` or `teagarden_head`)
- **Content-Type:** `application/json`

**Request Body:**
```json
{
  "tea_garden_id": 285,
  "health_center_id": 1
}
```
- `tea_garden_id` is **required**.
- `health_center_id` is optional.

**Response (200 OK):**
```json
{
  "status_code": 200,
  "message": "success",
  "data": [
    {
      "id": 1,
      "user_id": 6,
      "username": "jane",
      "name": "Jane Doe",
      "role": "nurse",
      "mobile_no": "9876543210",
      "qualification": "GNM",
      "health_center_id": 1,
      "health_center_name": "Health Center A",
      "tea_garden_id": 285,
      "tea_garden_name": "Garden A",
      "is_active": true
    }
  ]
}
```

---

### 13.3 Promote To Super (Attendant → Super Attendant / Nurse → Head Nurse)
- **URL:** `POST /promote-to-super/`
- **Auth:** Bearer Token (IsAuthenticated; role must be `superadmin` or `teagarden_head`)
- **Content-Type:** `application/json`

**Request Body (promote attendant):**
```json
{
  "attendant_id": 1
}
```

**Request Body (promote nurse):**
```json
{
  "nurse_id": 1
}
```
- Provide exactly one of `attendant_id` or `nurse_id`.

**Response (200 OK) - Attendant promoted:**
```json
{
  "status_code": 200,
  "message": "Attendant promoted to Super Attendant successfully",
  "data": {
    "id": 1,
    "user_id": 5,
    "username": "john",
    "name": "John Doe",
    "type": "attendant",
    "old_role": "attendant",
    "new_role": "super_attendant",
    "creche_id": 1,
    "creche_name": "Creche A",
    "tea_garden_id": 285,
    "tea_garden_name": "Garden A"
  }
}
```

**Response (200 OK) - Nurse promoted:**
```json
{
  "status_code": 200,
  "message": "Nurse promoted to Head Nurse successfully",
  "data": {
    "id": 1,
    "user_id": 6,
    "username": "jane",
    "name": "Jane Doe",
    "type": "nurse",
    "old_role": "nurse",
    "new_role": "head_nurse",
    "health_center_id": 1,
    "health_center_name": "Health Center A",
    "tea_garden_id": 285,
    "tea_garden_name": "Garden A"
  }
}
```

---

## Appendix A: External APIs Used

The application integrates with several external services:

| Service | URL | Purpose |
|---------|-----|---------|
| Face Embedding | `http://45.64.107.97:5010/api/v1/photo-embedding` | Generate face embeddings during registration |
| Child Attendance | `http://45.64.107.97:5010/api/v1/attendance/child` | Detect/recognize children in group photos |
| Attendant Attendance | `http://45.64.107.97:5010/api/v1/attendance/attendant` | Verify attendant face during check-in |
| Nurse Attendance | `http://45.64.107.97:5010/api/v1/attendance/nurse` | Verify nurse face during check-in |
| Doctor Attendance | `http://45.64.107.97:5010/api/v1/attendance/doctor` | Verify doctor face during check-in |
| Food Monitoring | `http://45.64.107.97:5011/api/v1/food_monitoring` | Analyze food photos and estimate nutrition |
| WhatsApp | `http://45.64.107.97:5010/api/v1/whatsapp/send` | Send prescriptions via WhatsApp |

---

## Appendix B: Common Error Response Format

Most APIs return errors in a consistent format:
```json
{
  "status_code": 400,
  "message": "Error description",
  "data": {}
}
```

Common HTTP status codes:
- `200` - Success
- `201` - Created
- `400` - Bad request / validation error
- `401` - Unauthorized / authentication failed
- `403` - Forbidden / insufficient permissions
- `404` - Resource not found
- `409` - Conflict (e.g., already checked in, duplicate record)
- `500` - Internal server error