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
    
    This processes medicines against an existing requisition from 
    the `healthcenter_weeklymedicinerequisition` table. For each medicine,
    it checks if the medicine_id exists in the 
    `healthcenter_weeklymedicinerequisitiondetail` table linked to a 
    SUBMITTED or APPROVED requisition. If found, it updates the 
    requisition detail and fulfills the stock entry.
    
    Flow:
      1. Looks for an existing SUBMITTED or APPROVED requisition for 
         this health center
      2. For each medicine, checks if it exists as a detail in that 
         requisition
      3. If found → updates the detail (available_stock_qty, etc.) and 
         marks status to FULFILLED after all items are processed
      4. If no existing requisition found → creates a new one (FULFILLED)
    
    Endpoint: POST /medicine/entry/
    
    Request Body: {
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
    
    Note: `requested_qty` is optional here. The API will use the 
    `requested_qty` from the existing requisition detail if available.
    
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
            "requisition_matched": true,
            "medicines": [
                {
                    "medicine_id": 1,
                    "medicine_name": "Paracetamol",
                    "previous_stock": 10,
                    "received_qty": 50,
                    "current_stock": 60,
                    "transaction_id": 5,
                    "requisition_detail_matched": true
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
            # LOOK FOR EXISTING SUBMITTED/APPROVED REQUISITION
            # ============================================
            # Try to find an existing requisition that is still open (SUBMITTED or APPROVED)
            existing_requisition = WeeklyMedicineRequisition.objects.filter(
                health_center=health_center,
                status__in=['SUBMITTED', 'APPROVED']
            ).order_by('-requisition_date').first()

            requisition_matched = existing_requisition is not None

            if existing_requisition:
                # Use the existing requisition
                requisition = existing_requisition
                logger.info(f"Found existing requisition #{requisition.id} (status: {requisition.status}) for health center {health_center.id}")
            else:
                # Create a new requisition with FULFILLED status
                requisition = WeeklyMedicineRequisition.objects.create(
                    health_center=health_center,
                    nurse=nurse,
                    requisition_week_start=requisition_week_start or timezone.now().date(),
                    requisition_week_end=requisition_week_end or timezone.now().date(),
                    status='FULFILLED'
                )
                logger.info(f"Created new requisition #{requisition.id} for health center {health_center.id}")

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
                    medicine_code = med_item.get('medicine_code')
                    if not medicine_code or medicine_code.strip() == '':
                        medicine_code = None
                    
                    medicine = Medicine.objects.create(
                        medicine_name=medicine_name,
                        medicine_code=medicine_code,
                        unit_name=med_item.get('unit_name', 'Unit'),
                        min_stock_level=med_item.get('min_stock_level', 5),
                        is_active=True
                    )
                    logger.info(f"Created new medicine: {medicine_name} (ID: {medicine.id})")

                # 4) If still no medicine resolved, skip this item
                if not medicine:
                    continue

                # ------------------------------------------------------------
                # VALIDATE RECEIVED QTY AGAINST MEDICINE MIN STOCK LEVEL
                # ------------------------------------------------------------
                if received_qty < medicine.min_stock_level:
                    return Response({
                        'status_code': 400,
                        'message': f"received_qty ({received_qty}) must be greater than medicine min stock level ({medicine.min_stock_level}) for medicine '{medicine.medicine_name}'",
                        'data': {
                            'medicine_id': medicine.id,
                            'medicine_name': medicine.medicine_name,
                            'received_qty': received_qty,
                            'min_stock_level': medicine.min_stock_level,
                        }
                    }, status=status.HTTP_400_BAD_REQUEST)

                # Get current stock before entry
                stock, stock_created = HealthCenterMedicineStock.objects.get_or_create(
                    health_center=health_center,
                    medicine=medicine,
                    defaults={'current_stock_qty': 0}
                )
                previous_stock = stock.current_stock_qty

                # ------------------------------------------------------------
                # CHECK IF MEDICINE EXISTS IN EXISTING REQUISITION DETAIL
                # ------------------------------------------------------------
                detail_matched = False
                if existing_requisition:
                    try:
                        existing_detail = WeeklyMedicineRequisitionDetail.objects.get(
                            requisition=existing_requisition,
                            medicine=medicine
                        )
                        # Update existing detail with received quantities
                        existing_detail.available_stock_qty = previous_stock
                        if requested_qty > 0:
                            existing_detail.requested_qty = requested_qty
                        existing_detail.auto_low_stock_flag = (previous_stock < medicine.min_stock_level)
                        if remarks:
                            existing_detail.remarks = remarks
                        existing_detail.save()
                        detail_matched = True
                        logger.info(f"Updated existing requisition detail for medicine #{medicine.id} in requisition #{existing_requisition.id}")
                    except WeeklyMedicineRequisitionDetail.DoesNotExist:
                        # Medicine not in existing requisition — will create a new detail
                        pass

                # If no existing detail was updated, create a new requisition detail
                if not detail_matched:
                    WeeklyMedicineRequisitionDetail.objects.create(
                        requisition=requisition,
                        medicine=medicine,
                        available_stock_qty=previous_stock,
                        requested_qty=requested_qty if requested_qty > 0 else received_qty,
                        auto_low_stock_flag=(previous_stock < medicine.min_stock_level),
                        remarks=remarks
                    )

                # Update stock
                stock.current_stock_qty = previous_stock + received_qty
                stock.last_updated_at = timezone.now()
                stock.save(update_fields=['current_stock_qty', 'last_updated_at'])

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
                    'requisition_detail_matched': detail_matched,
                })

            if not processed_medicines:
                raise ValueError("No valid medicines found to process entry")

            # If we used an existing requisition, update its status to FULFILLED
            if existing_requisition and existing_requisition.status != 'FULFILLED':
                existing_requisition.status = 'FULFILLED'
                existing_requisition.save(update_fields=['status'])
                requisition.status = 'FULFILLED'

            return Response({
                'status_code': 200,
                'message': 'Medicine entry recorded successfully',
                'data': {
                    'requisition_id': requisition.id,
                    'requisition_date': requisition.requisition_date.isoformat(),
                    'status': requisition.status,
                    'requisition_matched': requisition_matched,
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
