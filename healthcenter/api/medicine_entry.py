from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from healthcenter.models import (
    HealthCenter,
    HealthCenterMedicineStock,
    Medicine,
    MedicineStockTransaction,
    Nurse,
    WeeklyMedicineRequisition,
    WeeklyMedicineRequisitionDetail,
)

import logging
logger = logging.getLogger(__name__)


class MedicineEntryAPI(APIView):
    """
    API to record medicine stock entry/inward for a health center.
    
    This creates/updates a weekly requisition, updates stock, 
    and records stock transactions.
    
    Endpoint: POST /medicine/entry/
    
    Request Body: {
        "health_center_id": 1,
        "nurse_id": 1,
        "requisition_week_start": "2026-06-01",
        "requisition_week_end": "2026-06-07",
        "medicines": [
            {
                "medicine_id": 1,
                "requested_qty": 50,
                "received_qty": 50,
                "remarks": "Weekly stock received"
            },
            {
                "medicine_name": "Paracetamol",
                "requested_qty": 30,
                "received_qty": 30,
                "unit_name": "Tablet",
                "min_stock_level": 10
            }
        ]
    }
    
    Medicine Resolution Logic (in order):
      1. If `medicine_id` is provided and exists → use it
      2. If `medicine_name` is provided and matches an existing active Medicine → use it
      3. If `medicine_name` is provided but no match exists → create a new Medicine record
         using these optional fields: `medicine_code`, `unit_name` (default "Unit"),
         `min_stock_level` (default 5)
      4. If neither `medicine_id` nor `medicine_name` resolves → item is skipped
    
    Response: {
        "status_code": 200,
        "message": "Medicine entry recorded successfully",
        "data": {
            "requisition_id": 1,
            "requisition_date": "2026-06-03",
            "status": "FULFILLED",
            "medicines": [
                {
                    "medicine_id": 1,
                    "medicine_name": "Paracetamol",
                    "previous_stock": 10,
                    "received_qty": 50,
                    "current_stock": 60,
                    "transaction_id": 5
                }
            ]
        }
    }
    """
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        try:
            # ============================================
            # EXTRACT AND VALIDATE PARAMETERS
            # ============================================
            health_center_id = request.data.get('health_center_id')
            nurse_id = request.data.get('nurse_id')
            requisition_week_start = request.data.get('requisition_week_start')
            requisition_week_end = request.data.get('requisition_week_end')
            medicines_list = request.data.get('medicines')

            # Validate required fields
            if not health_center_id:
                return Response({
                    'status_code': 400,
                    'message': 'health_center_id is required',
                    'data': {}
                }, status=status.HTTP_400_BAD_REQUEST)

            if not nurse_id:
                return Response({
                    'status_code': 400,
                    'message': 'nurse_id is required',
                    'data': {}
                }, status=status.HTTP_400_BAD_REQUEST)

            if not medicines_list or not isinstance(medicines_list, list) or len(medicines_list) == 0:
                return Response({
                    'status_code': 400,
                    'message': 'medicines must be a non-empty array',
                    'data': {}
                }, status=status.HTTP_400_BAD_REQUEST)

            # ============================================
            # VERIFY REFERENCES
            # ============================================
            try:
                health_center = HealthCenter.objects.get(id=health_center_id)
            except HealthCenter.DoesNotExist:
                return Response({
                    'status_code': 404,
                    'message': 'Health center not found',
                    'data': {}
                }, status=status.HTTP_404_NOT_FOUND)

            try:
                nurse = Nurse.objects.get(id=nurse_id, is_active=True)
            except Nurse.DoesNotExist:
                return Response({
                    'status_code': 404,
                    'message': 'Nurse not found',
                    'data': {}
                }, status=status.HTTP_404_NOT_FOUND)

            # ============================================
            # CREATE OR GET WEEKLY REQUISITION
            # ============================================
            requisition = WeeklyMedicineRequisition.objects.create(
                health_center=health_center,
                nurse=nurse,
                requisition_week_start=requisition_week_start or timezone.now().date(),
                requisition_week_end=requisition_week_end or timezone.now().date(),
                status='FULFILLED'
            )

            # ============================================
            # PROCESS EACH MEDICINE
            # ============================================
            processed_medicines = []

            for med_item in medicines_list:
                medicine_id = med_item.get('medicine_id')
                medicine_name = med_item.get('medicine_name', '').strip()
                requested_qty = med_item.get('requested_qty', 0)
                received_qty = med_item.get('received_qty', 0)
                remarks = med_item.get('remarks', '')

                try:
                    requested_qty = int(requested_qty) if requested_qty else 0
                except (ValueError, TypeError):
                    requested_qty = 0

                try:
                    received_qty = int(received_qty) if received_qty else 0
                except (ValueError, TypeError):
                    received_qty = 0

                if received_qty <= 0:
                    continue

                # Resolve medicine: by ID, then by name, then create new
                medicine = None

                # 1) Look up by medicine_id if provided
                if medicine_id:
                    try:
                        medicine = Medicine.objects.get(id=medicine_id, is_active=True)
                    except Medicine.DoesNotExist:
                        logger.warning(f"Medicine ID {medicine_id} not found or inactive, will attempt by name")

                # 2) If not found by ID, look up by medicine_name
                if not medicine and medicine_name:
                    try:
                        medicine = Medicine.objects.get(
                            medicine_name__iexact=medicine_name,
                            is_active=True
                        )
                    except Medicine.DoesNotExist:
                        logger.info(f"Medicine '{medicine_name}' not found, creating new record")

                # 3) If still not found and we have a name, create a new Medicine record
                if not medicine and medicine_name:
                    medicine = Medicine.objects.create(
                        medicine_name=medicine_name,
                        medicine_code=med_item.get('medicine_code', ''),
                        unit_name=med_item.get('unit_name', 'Unit'),
                        min_stock_level=med_item.get('min_stock_level', 5),
                        is_active=True
                    )
                    logger.info(f"Created new medicine: {medicine_name} (ID: {medicine.id})")

                # 4) If still no medicine resolved, skip this item
                if not medicine:
                    continue

                # Create requisition detail
                WeeklyMedicineRequisitionDetail.objects.create(
                    requisition=requisition,
                    medicine=medicine,
                    available_stock_qty=0,
                    requested_qty=requested_qty,
                    auto_low_stock_flag=False,
                    remarks=remarks
                )

                # Get or create stock record
                stock, created = HealthCenterMedicineStock.objects.get_or_create(
                    health_center=health_center,
                    medicine=medicine,
                    defaults={'current_stock_qty': 0}
                )

                previous_stock = stock.current_stock_qty
                stock.current_stock_qty += received_qty
                stock.save()

                # Create stock transaction
                transaction_record = MedicineStockTransaction.objects.create(
                    health_center=health_center,
                    medicine=medicine,
                    transaction_type='IN',
                    quantity=received_qty,
                    reference_type='REQUISITION',
                    reference_id=requisition.id,
                    remarks=remarks or f"Stock entry via requisition #{requisition.id}"
                )

                processed_medicines.append({
                    'medicine_id': medicine.id,
                    'medicine_name': medicine.medicine_name,
                    'medicine_code': medicine.medicine_code or '',
                    'previous_stock': previous_stock,
                    'received_qty': received_qty,
                    'current_stock': stock.current_stock_qty,
                    'transaction_id': transaction_record.id,
                })

            if not processed_medicines:
                # No valid medicines processed, rollback via exception
                raise ValueError("No valid medicines found to process entry")

            return Response({
                'status_code': 200,
                'message': 'Medicine entry recorded successfully',
                'data': {
                    'requisition_id': requisition.id,
                    'requisition_date': requisition.requisition_date.isoformat(),
                    'status': requisition.status,
                    'health_center_id': health_center.id,
                    'health_center_name': health_center.name,
                    'nurse_id': nurse.id,
                    'nurse_name': nurse.nurse_name or nurse.user.username,
                    'medicines': processed_medicines,
                    'total_medicines': len(processed_medicines),
                }
            }, status=status.HTTP_200_OK)

        except ValueError as e:
            return Response({
                'status_code': 400,
                'message': str(e),
                'data': {}
            }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.exception("Medicine entry error")
            return Response({
                'status_code': 500,
                'message': f'Error processing medicine entry: {str(e)}',
                'data': {}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)