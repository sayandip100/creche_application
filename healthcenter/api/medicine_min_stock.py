from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from healthcenter.models import Medicine, MedicineUnit

import logging
logger = logging.getLogger(__name__)


class MedicineMinStockUpdateAPI(APIView):
    """
    API to manage the healthcenter_medicine table —
    update min_stock_level OR add a new medicine.

    Endpoint: POST /medicine/min-stock/update/

    === Update existing medicine ===
    {
        "medicine_id": 1,
        "min_stock_level": 10
    }

    === Add a new medicine ===
    {
        "medicine_name": "New Medicine",
        "medicine_code": "MED001",     // optional
        "unit_name": "Capsule",         // optional
        "min_stock_level": 10           // optional, defaults to 5
    }

    === Bulk mode (mix of both) ===
    {
        "medicines": [
            {"medicine_id": 1, "min_stock_level": 10},
            {"medicine_name": "Paracetamol", "medicine_code": "MED002", "min_stock_level": 8}
        ]
    }

    Medicine Resolution Logic:
      1. If medicine_id provided → update that existing medicine
      2. If medicine_name matches an existing medicine → update it
      3. If medicine_name is new → create a new medicine record
      4. If neither resolves → error

    Response:
    {
        "status_code": 200,
        "message": "Processed N medicine(s) successfully",
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
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            # Support both single and bulk formats
            medicines_data = request.data.get('medicines')

            if medicines_data and isinstance(medicines_data, list):
                return self._process_medicines(medicines_data)
            else:
                single_item = {
                    'medicine_id': request.data.get('medicine_id'),
                    'medicine_name': request.data.get('medicine_name', '').strip(),
                    'medicine_code': request.data.get('medicine_code', '').strip(),
                    'unit_name': request.data.get('unit_name', '').strip(),
                    'min_stock_level': request.data.get('min_stock_level'),
                }
                return self._process_medicines([single_item])

        except Exception as e:
            logger.exception("Medicine update error")
            return Response({
                'status_code': 500,
                'message': f'Error processing medicine: {str(e)}',
                'data': {}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _process_medicines(self, medicines_list):
        if not medicines_list or len(medicines_list) == 0:
            return Response({
                'status_code': 400,
                'message': 'Provide medicine details or a non-empty medicines array',
                'data': {}
            }, status=status.HTTP_400_BAD_REQUEST)

        updated_medicines = []
        errors = []

        for idx, item in enumerate(medicines_list):
            medicine_id = item.get('medicine_id')
            medicine_name = item.get('medicine_name', '').strip()
            medicine_code = item.get('medicine_code', '').strip()
            unit_name = item.get('unit_name', '').strip()
            min_stock_level = item.get('min_stock_level')

            # ─── Resolve or create medicine ───
            medicine = None
            is_new_medicine = False

            # 1) By ID
            if medicine_id:
                try:
                    medicine = Medicine.objects.get(id=medicine_id)
                except Medicine.DoesNotExist:
                    errors.append({
                        'index': idx,
                        'medicine_id': medicine_id,
                        'message': f'Medicine with ID {medicine_id} not found'
                    })
                    continue

            # 2) By name (case insensitive)
            if not medicine and medicine_name:
                try:
                    medicine = Medicine.objects.get(medicine_name__iexact=medicine_name)
                except Medicine.DoesNotExist:
                    # 3) Create new
                    unit = None
                    if unit_name:
                        unit, _ = MedicineUnit.objects.get_or_create(unit_name=unit_name)

                    medicine = Medicine.objects.create(
                        medicine_name=medicine_name,
                        medicine_code=medicine_code or '',
                        unit=unit,
                        unit_name=unit_name or 'Unit',
                        min_stock_level=int(min_stock_level) if min_stock_level is not None else 5,
                        is_active=True
                    )
                    is_new_medicine = True
                    logger.info(f"Created new medicine: {medicine_name} (ID: {medicine.id})")

            if not medicine:
                errors.append({
                    'index': idx,
                    'message': 'Could not resolve medicine. Provide medicine_id or medicine_name.',
                    'input': item
                })
                continue

            # ─── Set medicine_code if missing ───
            if medicine_code and not medicine.medicine_code:
                medicine.medicine_code = medicine_code
                medicine.save(update_fields=['medicine_code'])

            # ─── Build result ───
            result = {
                'medicine_id': medicine.id,
                'medicine_name': medicine.medicine_name,
                'medicine_code': medicine.medicine_code or '',
                'is_new_medicine': is_new_medicine,
            }

            # ─── Update min_stock_level ───
            if min_stock_level is not None:
                try:
                    min_stock_level_int = int(min_stock_level)
                    if min_stock_level_int < 0:
                        raise ValueError("min_stock_level cannot be negative")

                    result['previous_min_stock_level'] = medicine.min_stock_level
                    medicine.min_stock_level = min_stock_level_int
                    medicine.save(update_fields=['min_stock_level'])
                    result['new_min_stock_level'] = medicine.min_stock_level

                except (ValueError, TypeError):
                    errors.append({
                        'index': idx,
                        'medicine_id': medicine.id,
                        'medicine_name': medicine.medicine_name,
                        'message': f'Invalid min_stock_level value: {min_stock_level}'
                    })
                    continue

            updated_medicines.append(result)

        response_data = {
            'updated_medicines': updated_medicines,
            'total_updated': len(updated_medicines),
        }

        if errors:
            response_data['errors'] = errors
            response_data['total_errors'] = len(errors)

        if not updated_medicines and errors:
            return Response({
                'status_code': 400,
                'message': f'Failed to process any medicines. {len(errors)} error(s).',
                'data': response_data
            }, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'status_code': 200,
            'message': f'Processed {len(updated_medicines)} medicine(s) successfully',
            'data': response_data
        }, status=status.HTTP_200_OK)