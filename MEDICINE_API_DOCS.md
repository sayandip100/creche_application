# Medicine API Documentation

## Overview
The Medicine API provides endpoints to fetch and manage medicines across health centers in the Creche application.

---

## API Endpoints

### 1. Get Medicine List
**Fetch all active medicines with optional stock information**

#### Endpoint
```
GET /medicine/list/
```

#### Authentication
Required: Bearer Token (JWT)

#### Query Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `health_center_id` | Integer | Optional | Filter stock by specific health center ID |

#### Request Examples

**Without health center (get all medicines):**
```bash
curl -X GET "http://45.64.107.97/medicine/list/" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json"
```

**With health center (get medicines with stock info):**
```bash
curl -X GET "http://45.64.107.97/medicine/list/?health_center_id=1" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json"
```

#### Response (Success)
```json
{
    "status_code": 200,
    "message": "Medicines fetched successfully",
    "data": {
        "medicines": [
            {
                "id": 1,
                "name": "Medicine 1",
                "code": "MED001",
                "unit": "Unit",
                "min_stock_level": 5,
                "stock": {
                    "health_center_id": 1,
                    "health_center_name": "Health Center 1",
                    "current_stock_qty": 15,
                    "last_updated_at": "2026-06-02T04:48:04.848195+00:00",
                    "is_low_stock": false
                }
            },
            {
                "id": 2,
                "name": "Medicine 2",
                "code": "MED002",
                "unit": "Unit",
                "min_stock_level": 5,
                "stock": {
                    "health_center_id": 1,
                    "health_center_name": "Health Center 1",
                    "current_stock_qty": 39,
                    "last_updated_at": "2026-06-02T04:48:04.848195+00:00",
                    "is_low_stock": false
                }
            }
        ],
        "total_count": 2,
        "health_center_id": "1"
    }
}
```

#### Response (No medicines)
```json
{
    "status_code": 200,
    "message": "No medicines available",
    "data": {
        "medicines": [],
        "total_count": 0
    }
}
```

#### Response (Error)
```json
{
    "status_code": 500,
    "message": "Error fetching medicines: [error details]",
    "data": {}
}
```

---

### 2. Get Medicine Details
**Fetch detailed information about a specific medicine including stock across all health centers**

#### Endpoint
```
GET /medicine/<medicine_id>/
```

#### Authentication
Required: Bearer Token (JWT)

#### Path Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `medicine_id` | Integer | Yes | The ID of the medicine to fetch |

#### Request Examples

```bash
curl -X GET "http://45.64.107.97/medicine/1/" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json"
```

#### Response (Success)
```json
{
    "status_code": 200,
    "message": "Medicine details fetched",
    "data": {
        "id": 1,
        "name": "Medicine 1",
        "code": "MED001",
        "unit": "Unit",
        "min_stock_level": 5,
        "is_active": true,
        "created_at": "2026-06-02T04:48:04.848195+00:00",
        "stock_across_centers": [
            {
                "health_center_id": 1,
                "health_center_name": "Health Center 1",
                "current_stock_qty": 15,
                "last_updated_at": "2026-06-02T04:48:04.848195+00:00",
                "is_low_stock": false
            },
            {
                "health_center_id": 2,
                "health_center_name": "Health Center 2",
                "current_stock_qty": 8,
                "last_updated_at": "2026-06-02T04:48:04.848195+00:00",
                "is_low_stock": true
            }
        ],
        "total_stock": 23
    }
}
```

#### Response (Medicine Not Found)
```json
{
    "status_code": 404,
    "message": "Medicine not found",
    "data": {}
}
```

#### Response (Error)
```json
{
    "status_code": 500,
    "message": "Error fetching medicine details: [error details]",
    "data": {}
}
```

---

## Integration with Mobile UI

### Update the Mobile UI with Real API

Replace the hardcoded `medicinesList` in `prescription_mobile_ui.html` with a fetch call:

```javascript
// Fetch medicines from API on page load
async function loadMedicines() {
    try {
        const healthCenterId = document.getElementById('healthCenter').value;
        if (!healthCenterId) return;

        const url = `http://45.64.107.97/medicine/list/?health_center_id=${healthCenterId}`;
        const response = await fetch(url, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer YOUR_TOKEN_HERE'
            }
        });

        const result = await response.json();
        
        if (result.status_code === 200) {
            const medicineSelect = document.getElementById('medicineSelect');
            medicineSelect.innerHTML = '<option value="">-- Select Medicine --</option>';
            
            result.data.medicines.forEach(med => {
                const stock = med.stock?.current_stock_qty || 0;
                const option = document.createElement('option');
                option.value = med.id;
                option.textContent = `${med.name} (${med.code}) - Stock: ${stock}`;
                medicineSelect.appendChild(option);
            });
        }
    } catch (error) {
        console.error('Error loading medicines:', error);
    }
}

// Call on health center selection change
document.getElementById('healthCenter').addEventListener('change', loadMedicines);
```

---

## Error Handling

### Common Status Codes

| Code | Message | Meaning |
|------|---------|---------|
| 200 | Medicines fetched successfully | Request successful |
| 404 | Medicine not found | Medicine ID doesn't exist |
| 401 | Unauthorized | Invalid or missing authentication token |
| 500 | Server error | Internal server error |

### Authentication Errors
```json
{
    "detail": "Invalid token." / "Given token not valid for any token type."
}
```

---

## Use Cases

### 1. Populate Medicine Dropdown
Use the **Medicine List** endpoint to fill the medicine selection dropdown in prescription forms.

### 2. Check Stock Availability
Use `is_low_stock` flag to warn users when medicine stock is below minimum level.

### 3. View Cross-Center Stock
Use the **Medicine Details** endpoint to see total stock across all health centers.

### 4. Real-time Stock Updates
Call the API with `health_center_id` parameter to get the latest stock for a specific center.

---

## Sample Integration Code

### JavaScript/React

```javascript
// Fetch medicine list for a health center
async function fetchMedicines(healthCenterId) {
    const response = await fetch(
        `/medicine/list/?health_center_id=${healthCenterId}`,
        {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${authToken}`,
                'Content-Type': 'application/json'
            }
        }
    );
    
    return await response.json();
}

// Get medicine details
async function fetchMedicineDetails(medicineId) {
    const response = await fetch(
        `/medicine/${medicineId}/`,
        {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${authToken}`,
                'Content-Type': 'application/json'
            }
        }
    );
    
    return await response.json();
}
```

---

## Notes

- All endpoints require authentication
- Stock information is only available if `health_center_id` is provided for the list endpoint
- `is_low_stock` is calculated based on `current_stock_qty < min_stock_level`
- Medicines are returned in alphabetical order by name
- Maximum 100 medicines can be returned at once (scalable if needed)
