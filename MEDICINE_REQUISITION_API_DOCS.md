# Medicine Requisition API Documentation

## Overview
The Medicine Requisition API provides endpoints to create, list, view, and manage weekly medicine requisitions for health centers in the Creche application. A requisition is a formal request from a health center nurse to replenish medicine stock for a specific week.

---

## API Endpoints

| # | Endpoint | Method | Description |
|---|----------|--------|-------------|
| 1 | `/medicine/requisition/create/` | POST | Create a new weekly medicine requisition |
| 2 | `/medicine/requisition/list/` | POST | List requisitions for a health center (with filters) |
| 3 | `/medicine/requisition/detail/` | POST | Get details of a specific requisition |
| 4 | `/medicine/requisition/status-update/` | POST | Update the status of a requisition |

---

## Authentication
All endpoints require authentication via **Bearer Token (JWT)**.

```
Authorization: Bearer YOUR_TOKEN
```

---

## 1. Create Medicine Requisition

**Creates a weekly medicine requisition header and its detail items (medicines requested).**

### Endpoint
```
POST /medicine/requisition/create/
```

### Request Body
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

### Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `health_center_id` | Integer | Yes | ID of the health center making the requisition |
| `nurse_id` | Integer | Yes | ID of the nurse creating the requisition |
| `requisition_week_start` | Date (YYYY-MM-DD) | No | Start date of the requisition week (defaults to today) |
| `requisition_week_end` | Date (YYYY-MM-DD) | No | End date of the requisition week (defaults to today) |
| `medicines` | Array | Yes | List of medicines being requested (non-empty) |
| `remarks` | String | No | Overall remarks for the requisition |

### Medicine Item Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `medicine_id` | Integer | No* | ID of an existing medicine |
| `medicine_name` | String | No* | Name of the medicine |
| `requested_qty` | Integer | Yes | Quantity requested (must be > 0) |
| `medicine_code` | String | No | Code for new medicine creation |
| `unit_name` | String | No | Unit name for new medicine creation (default: "Unit") |
| `min_stock_level` | Integer | No | Min stock level for new medicine creation (default: 5) |
| `remarks` | String | No | Remarks for this specific medicine item |

> **Note:** Either `medicine_id` OR `medicine_name` must be provided. If both are provided, `medicine_id` takes priority.

### Medicine Resolution Logic (in order)
1. If `medicine_id` is provided and exists → use it
2. If `medicine_name` is provided and matches an existing active Medicine → use it
3. If `medicine_name` is provided but no match exists → create a new Medicine record using optional fields (`medicine_code`, `unit_name`, `min_stock_level`)
4. If neither `medicine_id` nor `medicine_name` resolves → item is skipped

### Auto-Calculated Fields
- **`available_stock_qty`**: Automatically fetched from the `healthcenter_healthcentermedicinestock` table (`current_stock_qty` column). Defaults to `0` if no stock record exists.
- **`auto_low_stock_flag`**: Automatically set to `true` if `current_stock_qty < min_stock_level`, otherwise `false`.

### cURL Example
```bash
curl -X POST "http://45.64.107.97/medicine/requisition/create/" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "health_center_id": 1,
    "nurse_id": 1,
    "requisition_week_start": "2026-07-20",
    "requisition_week_end": "2026-07-26",
    "medicines": [
        {
            "medicine_id": 1,
            "requested_qty": 50,
            "remarks": "Low stock, need replenishment"
        }
    ],
    "remarks": "Weekly requisition for July 4th week"
  }'
```

### Response (Success - 200)
```json
{
    "status_code": 200,
    "message": "Medicine requisition created successfully",
    "data": {
        "requisition_id": 1,
        "requisition_date": "2026-07-23",
        "status": "SUBMITTED",
        "health_center_id": 1,
        "health_center_name": "Health Center Name",
        "nurse_id": 1,
        "nurse_name": "Nurse Name",
        "week_start": "2026-07-20",
        "week_end": "2026-07-26",
        "remarks": "Weekly requisition for July 4th week",
        "medicines": [
            {
                "medicine_id": 1,
                "medicine_name": "Paracetamol",
                "medicine_code": "PARA001",
                "current_stock_qty": 5,
                "min_stock_level": 10,
                "available_stock_qty": 5,
                "requested_qty": 50,
                "auto_low_stock_flag": true,
                "remarks": "Low stock, need replenishment"
            }
        ],
        "total_medicines": 1
    }
}
```

### Error Responses

**Missing health_center_id (400):**
```json
{
    "status_code": 400,
    "message": "health_center_id is required",
    "data": {}
}
```

**Missing nurse_id (400):**
```json
{
    "status_code": 400,
    "message": "nurse_id is required",
    "data": {}
}
```

**Empty medicines array (400):**
```json
{
    "status_code": 400,
    "message": "medicines must be a non-empty array",
    "data": {}
}
```

**Health center not found (404):**
```json
{
    "status_code": 404,
    "message": "Health center not found",
    "data": {}
}
```

**Nurse not found (404):**
```json
{
    "status_code": 404,
    "message": "Nurse not found",
    "data": {}
}
```

**No valid medicines (400):**
```json
{
    "status_code": 400,
    "message": "No valid medicines found to process requisition",
    "data": {}
}
```

**Server error (500):**
```json
{
    "status_code": 500,
    "message": "Error creating medicine requisition: [error details]",
    "data": {}
}
```

---

## 2. List Medicine Requisitions

**Lists all medicine requisitions for a health center with optional filters.**

### Endpoint
```
POST /medicine/requisition/list/
```

### Request Body
```json
{
    "health_center_id": 1,
    "status": "SUBMITTED",
    "start_date": "2026-07-01",
    "end_date": "2026-07-31"
}
```

### Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `health_center_id` | Integer | Yes | ID of the health center |
| `status` | String | No | Filter by status: `DRAFT`, `SUBMITTED`, `APPROVED`, `REJECTED`, `FULFILLED` (null/empty = all) |
| `start_date` | Date (YYYY-MM-DD) | No | Filter by `requisition_date` (>=) from the `healthcenter_weeklymedicinerequisition` table |
| `end_date` | Date (YYYY-MM-DD) | No | Filter by `requisition_date` (<=) from the `healthcenter_weeklymedicinerequisition` table |

> **Note:** Date filtering is based on the `requisition_date` column of the `healthcenter_weeklymedicinerequisition` table, **not** the week start/end dates. If `status` is null/empty, all requisitions between `start_date` and `end_date` are returned. If `status` is provided, only matching status is returned.

### cURL Example
```bash
curl -X POST "http://45.64.107.97/medicine/requisition/list/" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "health_center_id": 1,
    "status": "SUBMITTED"
  }'
```

### Response (Success - 200)
```json
{
    "status_code": 200,
    "message": "success",
    "data": {
        "total_requisitions": 2,
        "requisitions": [
            {
                "requisition_id": 1,
                "requisition_date": "2026-07-23",
                "status": "SUBMITTED",
                "health_center_id": 1,
                "health_center_name": "Health Center Name",
                "nurse_id": 1,
                "nurse_name": "Nurse Name",
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
            },
            {
                "requisition_id": 2,
                "requisition_date": "2026-07-16",
                "status": "APPROVED",
                "health_center_id": 1,
                "health_center_name": "Health Center Name",
                "nurse_id": 1,
                "nurse_name": "Nurse Name",
                "week_start": "2026-07-13",
                "week_end": "2026-07-19",
                "remarks": "Weekly requisition",
                "total_medicines": 2,
                "medicines": [
                    {
                        "medicine_id": 2,
                        "medicine_name": "Ibuprofen",
                        "medicine_code": "IBU001",
                        "available_stock_qty": 3,
                        "requested_qty": 40,
                        "auto_low_stock_flag": true,
                        "remarks": ""
                    }
                ]
            }
        ]
    }
}
```

### Error Responses

**Missing health_center_id (400):**
```json
{
    "status_code": 400,
    "message": "health_center_id is required",
    "data": {}
}
```

**Health center not found (404):**
```json
{
    "status_code": 404,
    "message": "Health center not found",
    "data": {}
}
```

**Server error (500):**
```json
{
    "status_code": 500,
    "message": "Error listing medicine requisitions: [error details]",
    "data": {}
}
```

---

## 3. Get Medicine Requisition Detail

**Fetches the full details of a specific medicine requisition including all its medicine items.**

### Endpoint
```
POST /medicine/requisition/detail/
```

### Request Body
```json
{
    "requisition_id": 1
}
```

### Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `requisition_id` | Integer | Yes | ID of the requisition to fetch |

### cURL Example
```bash
curl -X POST "http://45.64.107.97/medicine/requisition/detail/" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "requisition_id": 1
  }'
```

### Response (Success - 200)
```json
{
    "status_code": 200,
    "message": "success",
    "data": {
        "requisition_id": 1,
        "requisition_date": "2026-07-23",
        "status": "SUBMITTED",
        "health_center_id": 1,
        "health_center_name": "Health Center Name",
        "nurse_id": 1,
        "nurse_name": "Nurse Name",
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
            },
            {
                "medicine_id": 2,
                "medicine_name": "Ibuprofen",
                "medicine_code": "IBU001",
                "available_stock_qty": 3,
                "requested_qty": 40,
                "auto_low_stock_flag": true,
                "remarks": ""
            }
        ]
    }
}
```

### Error Responses

**Missing requisition_id (400):**
```json
{
    "status_code": 400,
    "message": "requisition_id is required",
    "data": {}
}
```

**Requisition not found (404):**
```json
{
    "status_code": 404,
    "message": "Requisition not found",
    "data": {}
}
```

**Server error (500):**
```json
{
    "status_code": 500,
    "message": "Error fetching medicine requisition detail: [error details]",
    "data": {}
}
```

---

## 4. Update Medicine Requisition Status

**Updates the status of a medicine requisition (e.g., from SUBMITTED to APPROVED or REJECTED).**

### Endpoint
```
POST /medicine/requisition/status-update/
```

### Request Body
```json
{
    "requisition_id": 1,
    "status": "APPROVED",
    "remarks": "Approved by admin"
}
```

### Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `requisition_id` | Integer | Yes | ID of the requisition to update |
| `status` | String | Yes | New status. Must be one of: `DRAFT`, `SUBMITTED`, `APPROVED`, `REJECTED`, `FULFILLED` |
| `remarks` | String | No | Additional remarks appended to the requisition with a timestamp |

### Valid Status Values

| Status | Description |
|--------|-------------|
| `DRAFT` | Requisition is in draft state, not yet submitted |
| `SUBMITTED` | Requisition has been submitted by the nurse |
| `APPROVED` | Requisition has been approved by admin |
| `REJECTED` | Requisition has been rejected by admin |
| `FULFILLED` | Requisition has been fulfilled (stock delivered) |

### cURL Example
```bash
curl -X POST "http://45.64.107.97/medicine/requisition/status-update/" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "requisition_id": 1,
    "status": "APPROVED",
    "remarks": "Approved by admin"
  }'
```

### Response (Success - 200)
```json
{
    "status_code": 200,
    "message": "Requisition status updated to APPROVED",
    "data": {
        "requisition_id": 1,
        "status": "APPROVED",
        "previous_status": "SUBMITTED",
        "remarks": "Weekly requisition\n[2026-07-23 10:30] Status changed to APPROVED: Approved by admin"
    }
}
```

### Error Responses

**Missing requisition_id (400):**
```json
{
    "status_code": 400,
    "message": "requisition_id is required",
    "data": {}
}
```

**Missing status (400):**
```json
{
    "status_code": 400,
    "message": "status is required",
    "data": {}
}
```

**Invalid status (400):**
```json
{
    "status_code": 400,
    "message": "Invalid status. Must be one of: DRAFT, SUBMITTED, APPROVED, REJECTED, FULFILLED",
    "data": {}
}
```

**Requisition not found (404):**
```json
{
    "status_code": 404,
    "message": "Requisition not found",
    "data": {}
}
```

**Server error (500):**
```json
{
    "status_code": 500,
    "message": "Error updating requisition status: [error details]",
    "data": {}
}
```

---

## Requisition Lifecycle

```
DRAFT → SUBMITTED → APPROVED → FULFILLED
                ↘ REJECTED
```

1. **DRAFT**: Nurse creates a draft requisition (optional state)
2. **SUBMITTED**: Nurse submits the requisition for approval (default status on creation)
3. **APPROVED**: Admin approves the requisition
4. **FULFILLED**: Stock is delivered and the requisition is fulfilled (set by the Medicine Entry API)
5. **REJECTED**: Admin rejects the requisition

---

## Integration with Medicine Entry API

The **Medicine Entry API** (`POST /medicine/entry/`) works in conjunction with this requisition API:

1. A nurse creates a requisition via `/medicine/requisition/create/` (status: `SUBMITTED`)
2. Admin approves it via `/medicine/requisition/status-update/` (status: `APPROVED`)
3. When stock arrives, the nurse records the entry via `/medicine/entry/`
4. The entry API finds the existing `SUBMITTED` or `APPROVED` requisition, updates its details, and marks it as `FULFILLED`

---

## Error Handling

### Common Status Codes

| Code | Message | Meaning |
|------|---------|---------|
| 200 | Success | Request completed successfully |
| 400 | Validation error | Missing or invalid parameters |
| 401 | Unauthorized | Invalid or missing authentication token |
| 404 | Not found | Health center, nurse, or requisition not found |
| 500 | Server error | Internal server error |

### Authentication Errors
```json
{
    "detail": "Invalid token." / "Given token not valid for any token type."
}
```

---

## Use Cases

### 1. Weekly Stock Replenishment
Nurses create weekly requisitions to request medicine stock replenishment for their health center.

### 2. Approval Workflow
Admins review submitted requisitions and approve or reject them based on stock availability.

### 3. Stock Monitoring
The `auto_low_stock_flag` in each medicine item indicates whether the current stock is below the minimum level, helping prioritize urgent requests.

### 4. Fulfillment Tracking
The `FULFILLED` status tracks which requisitions have been delivered, providing a complete audit trail.

---

## Sample Integration Code

### JavaScript/React

```javascript
// Create a medicine requisition
async function createRequisition(payload) {
    const response = await fetch('/medicine/requisition/create/', {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${authToken}`,
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
    });
    return await response.json();
}

// List requisitions for a health center
async function listRequisitions(healthCenterId, status = null) {
    const payload = { health_center_id: healthCenterId };
    if (status) payload.status = status;
    
    const response = await fetch('/medicine/requisition/list/', {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${authToken}`,
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
    });
    return await response.json();
}

// Get requisition detail
async function getRequisitionDetail(requisitionId) {
    const response = await fetch('/medicine/requisition/detail/', {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${authToken}`,
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ requisition_id: requisitionId })
    });
    return await response.json();
}

// Update requisition status
async function updateRequisitionStatus(requisitionId, status, remarks = '') {
    const response = await fetch('/medicine/requisition/status-update/', {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${authToken}`,
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ requisition_id: requisitionId, status, remarks })
    });
    return await response.json();
}
```

### Python (Requests)

```python
import requests

BASE_URL = "http://45.64.107.97"
TOKEN = "YOUR_JWT_TOKEN"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

# Create requisition
def create_requisition(health_center_id, nurse_id, medicines, week_start, week_end, remarks=""):
    payload = {
        "health_center_id": health_center_id,
        "nurse_id": nurse_id,
        "requisition_week_start": week_start,
        "requisition_week_end": week_end,
        "medicines": medicines,
        "remarks": remarks
    }
    response = requests.post(f"{BASE_URL}/medicine/requisition/create/", json=payload, headers=HEADERS)
    return response.json()

# List requisitions
def list_requisitions(health_center_id, status=None):
    payload = {"health_center_id": health_center_id}
    if status:
        payload["status"] = status
    response = requests.post(f"{BASE_URL}/medicine/requisition/list/", json=payload, headers=HEADERS)
    return response.json()

# Get requisition detail
def get_requisition_detail(requisition_id):
    payload = {"requisition_id": requisition_id}
    response = requests.post(f"{BASE_URL}/medicine/requisition/detail/", json=payload, headers=HEADERS)
    return response.json()

# Update requisition status
def update_requisition_status(requisition_id, status, remarks=""):
    payload = {"requisition_id": requisition_id, "status": status, "remarks": remarks}
    response = requests.post(f"{BASE_URL}/medicine/requisition/status-update/", json=payload, headers=HEADERS)
    return response.json()
```

---

## Notes

- All endpoints require authentication via JWT Bearer token
- Requisitions are created with status `SUBMITTED` by default
- `available_stock_qty` is automatically fetched from the health center's current stock for each medicine
- `auto_low_stock_flag` is automatically calculated as `current_stock_qty < min_stock_level`
- If a medicine doesn't exist by `medicine_id` or `medicine_name`, a new Medicine record is created automatically
- Items with `requested_qty <= 0` are skipped
- If no valid medicines are found, the API returns a 400 error
- Status update remarks are appended with a timestamp for audit trail