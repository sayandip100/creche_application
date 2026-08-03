from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from healthcenter.models import (
    HealthCenter,
    HealthCenterMedicineStock,
    Medicine,
    Nurse,
    WeeklyMedicineRequisition,
    WeeklyMedicineRequisitionDetail,
)

import logging
logger = logging.getLogger(__name__)


class MedicineRequisitionCreateAPI(APIView):
    """
    API to create a weekly medicine requisition for a health center.
    
    Creates a requisition header and its detail items (medicines requested).
    
    Endpoint: POST /medicine/requisition/create/
    
    Request Body: {
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
    
    Note: `available_stock_qty` is automatically fetched from the 
    `healthcenter_healthcentermedicinestock` table (`current_stock_qty` column).
    If no stock record exists, it defaults to 0.
    
    Medicine Resolution Logic (in order):
      1. If `medicine_id` is provided and exists → use it
      2. If `medicine_name` is provided and matches an existing active Medicine → use it
      3. If `medicine_name` is provided but no match exists → create a new Medicine record
         using these optional fields: `medicine_code`, `unit_name` (default "Unit"),
         `min_stock_level` (default 5)
      4. If neither `medicine_id` nor `medicine_name` resolves → item is skipped
    
    Response: {
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
            "medicines": [
                {
                    "medicine_id": 1,
                    "medicine_name": "Paracetamol",
                    "current_stock_qty": 5,
                    "available_stock_qty": 5,
                    "requested_qty": 50,
                    "auto_low_stock_flag": false,
                    "remarks": "Low stock, need replenishment"
                }
            ],
            "total_medicines": 1
        }
    }
    """

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
            remarks = request.data.get('remarks', '')

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
            # CREATE REQUISITION HEADER
            # ============================================
            requisition = WeeklyMedicineRequisition.objects.create(
                health_center=health_center,
                nurse=nurse,
                requisition_week_start=requisition_week_start or timezone.now().date(),
                requisition_week_end=requisition_week_end or timezone.now().date(),
                status='SUBMITTED',
                remarks=remarks
            )

            # ============================================
            # PROCESS EACH MEDICINE
            # ============================================
            processed_medicines = []

            for med_item in medicines_list:
                medicine_id = med_item.get('medicine_id')
                medicine_name = med_item.get('medicine_name', '').strip()
                requested_qty = med_item.get('requested_qty', 0)
                med_remarks = med_item.get('remarks', '')

                try:
                    requested_qty = int(requested_qty) if requested_qty else 0
                except (ValueError, TypeError):
                    requested_qty = 0

                if requested_qty <= 0:
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

                # Get current stock from healthcenter_healthcentermedicinestock table
                try:
                    stock = HealthCenterMedicineStock.objects.get(
                        health_center=health_center,
                        medicine=medicine
                    )
                    current_stock_qty = stock.current_stock_qty
                except HealthCenterMedicineStock.DoesNotExist:
                    current_stock_qty = 0

                # auto_low_stock_flag: True if current stock is below min_stock_level
                auto_low_stock = current_stock_qty < medicine.min_stock_level

                # available_stock_qty is automatically taken from current_stock_qty
                available_stock_qty = current_stock_qty

                # Create requisition detail
                WeeklyMedicineRequisitionDetail.objects.create(
                    requisition=requisition,
                    medicine=medicine,
                    available_stock_qty=available_stock_qty,
                    requested_qty=requested_qty,
                    auto_low_stock_flag=auto_low_stock,
                    remarks=med_remarks
                )

                processed_medicines.append({
                    'medicine_id': medicine.id,
                    'medicine_name': medicine.medicine_name,
                    'medicine_code': medicine.medicine_code or '',
                    'current_stock_qty': current_stock_qty,
                    'min_stock_level': medicine.min_stock_level,
                    'available_stock_qty': available_stock_qty,
                    'requested_qty': requested_qty,
                    'auto_low_stock_flag': auto_low_stock,
                    'remarks': med_remarks,
                })

            if not processed_medicines:
                raise ValueError("No valid medicines found to process requisition")

            return Response({
                'status_code': 200,
                'message': 'Medicine requisition created successfully',
                'data': {
                    'requisition_id': requisition.id,
                    'requisition_date': requisition.requisition_date.isoformat(),
                    'status': requisition.status,
                    'health_center_id': health_center.id,
                    'health_center_name': health_center.name,
                    'nurse_id': nurse.id,
                    'nurse_name': nurse.nurse_name or nurse.user.username,
                    'week_start': str(requisition.requisition_week_start),
                    'week_end': str(requisition.requisition_week_end),
                    'remarks': requisition.remarks,
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
            logger.exception("Medicine requisition creation error")
            return Response({
                'status_code': 500,
                'message': f'Error creating medicine requisition: {str(e)}',
                'data': {}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MedicineRequisitionListAPI(APIView):
    """
    API to list medicine requisitions for a health center.
    
    Endpoint: POST /medicine/requisition/list/
    
    Request Body: {
        "health_center_id": 1,
        "status": "SUBMITTED",        # Optional filter: DRAFT, SUBMITTED, APPROVED, REJECTED, FULFILLED
        "start_date": "2026-07-01",   # Optional filter by week start date
        "end_date": "2026-07-31"      # Optional filter by week end date
    }
    
    Response: {
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
                }
            ]
        }
    }
    """

    def post(self, request):
        try:
            health_center_id = request.data.get('health_center_id')
            status_filter = request.data.get('status')
            start_date = request.data.get('start_date')
            end_date = request.data.get('end_date')

            if not health_center_id:
                return Response({
                    'status_code': 400,
                    'message': 'health_center_id is required',
                    'data': {}
                }, status=status.HTTP_400_BAD_REQUEST)

            try:
                health_center = HealthCenter.objects.get(id=health_center_id)
            except HealthCenter.DoesNotExist:
                return Response({
                    'status_code': 404,
                    'message': 'Health center not found',
                    'data': {}
                }, status=status.HTTP_404_NOT_FOUND)

            # Build filters
            filters = {'health_center': health_center}

            if status_filter:
                valid_statuses = ['DRAFT', 'SUBMITTED', 'APPROVED', 'REJECTED', 'FULFILLED']
                if status_filter.upper() in valid_statuses:
                    filters['status'] = status_filter.upper()

            if start_date:
                filters['requisition_week_start__gte'] = start_date

            if end_date:
                filters['requisition_week_end__lte'] = end_date

            requisitions = WeeklyMedicineRequisition.objects.filter(
                **filters
            ).select_related('health_center', 'nurse__user').order_by('-requisition_date')

            result = []
            for req in requisitions:
                details = WeeklyMedicineRequisitionDetail.objects.filter(
                    requisition=req
                ).select_related('medicine')

                medicines_data = []
                for detail in details:
                    medicines_data.append({
                        'medicine_id': detail.medicine.id,
                        'medicine_name': detail.medicine.medicine_name,
                        'medicine_code': detail.medicine.medicine_code or '',
                        'available_stock_qty': detail.available_stock_qty,
                        'requested_qty': detail.requested_qty,
                        'auto_low_stock_flag': detail.auto_low_stock_flag,
                        'remarks': detail.remarks,
                    })

                result.append({
                    'requisition_id': req.id,
                    'requisition_date': req.requisition_date.isoformat(),
                    'status': req.status,
                    'health_center_id': health_center.id,
                    'health_center_name': health_center.name,
                    'nurse_id': req.nurse.id if req.nurse else None,
                    'nurse_name': req.nurse.nurse_name or (req.nurse.user.username if req.nurse else None),
                    'week_start': str(req.requisition_week_start),
                    'week_end': str(req.requisition_week_end),
                    'remarks': req.remarks,
                    'total_medicines': len(medicines_data),
                    'medicines': medicines_data,
                })

            return Response({
                'status_code': 200,
                'message': 'success',
                'data': {
                    'total_requisitions': len(result),
                    'requisitions': result,
                }
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception("Medicine requisition list error")
            return Response({
                'status_code': 500,
                'message': f'Error listing medicine requisitions: {str(e)}',
                'data': {}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MedicineRequisitionDetailAPI(APIView):
    """
    API to get details of a specific medicine requisition.
    
    Endpoint: POST /medicine/requisition/detail/
    
    Request Body: {
        "requisition_id": 1
    }
    
    Response: {
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
                }
            ]
        }
    }
    """

    def post(self, request):
        try:
            requisition_id = request.data.get('requisition_id')

            if not requisition_id:
                return Response({
                    'status_code': 400,
                    'message': 'requisition_id is required',
                    'data': {}
                }, status=status.HTTP_400_BAD_REQUEST)

            try:
                requisition = WeeklyMedicineRequisition.objects.select_related(
                    'health_center', 'nurse__user'
                ).get(id=requisition_id)
            except WeeklyMedicineRequisition.DoesNotExist:
                return Response({
                    'status_code': 404,
                    'message': 'Requisition not found',
                    'data': {}
                }, status=status.HTTP_404_NOT_FOUND)

            details = WeeklyMedicineRequisitionDetail.objects.filter(
                requisition=requisition
            ).select_related('medicine')

            medicines_data = []
            for detail in details:
                medicines_data.append({
                    'medicine_id': detail.medicine.id,
                    'medicine_name': detail.medicine.medicine_name,
                    'medicine_code': detail.medicine.medicine_code or '',
                    'available_stock_qty': detail.available_stock_qty,
                    'requested_qty': detail.requested_qty,
                    'auto_low_stock_flag': detail.auto_low_stock_flag,
                    'remarks': detail.remarks,
                })

            return Response({
                'status_code': 200,
                'message': 'success',
                'data': {
                    'requisition_id': requisition.id,
                    'requisition_date': requisition.requisition_date.isoformat(),
                    'status': requisition.status,
                    'health_center_id': requisition.health_center.id,
                    'health_center_name': requisition.health_center.name,
                    'nurse_id': requisition.nurse.id if requisition.nurse else None,
                    'nurse_name': requisition.nurse.nurse_name or (requisition.nurse.user.username if requisition.nurse else None),
                    'week_start': str(requisition.requisition_week_start),
                    'week_end': str(requisition.requisition_week_end),
                    'remarks': requisition.remarks,
                    'total_medicines': len(medicines_data),
                    'medicines': medicines_data,
                }
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception("Medicine requisition detail error")
            return Response({
                'status_code': 500,
                'message': f'Error fetching medicine requisition detail: {str(e)}',
                'data': {}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MedicineRequisitionStatusUpdateAPI(APIView):
    """
    API to update the status of a medicine requisition.
    
    Endpoint: POST /medicine/requisition/status-update/
    
    Request Body: {
        "requisition_id": 1,
        "status": "APPROVED",     # DRAFT, SUBMITTED, APPROVED, REJECTED, FULFILLED
        "remarks": "Approved by admin"   # Optional additional remarks
    }
    
    Response: {
        "status_code": 200,
        "message": "Requisition status updated to APPROVED",
        "data": {
            "requisition_id": 1,
            "status": "APPROVED",
            "previous_status": "SUBMITTED",
            "remarks": "Approved by admin"
        }
    }
    """

    def post(self, request):
        try:
            requisition_id = request.data.get('requisition_id')
            new_status = request.data.get('status')
            additional_remarks = request.data.get('remarks', '')

            if not requisition_id:
                return Response({
                    'status_code': 400,
                    'message': 'requisition_id is required',
                    'data': {}
                }, status=status.HTTP_400_BAD_REQUEST)

            if not new_status:
                return Response({
                    'status_code': 400,
                    'message': 'status is required',
                    'data': {}
                }, status=status.HTTP_400_BAD_REQUEST)

            valid_statuses = ['DRAFT', 'SUBMITTED', 'APPROVED', 'REJECTED', 'FULFILLED']
            new_status = new_status.upper()
            if new_status not in valid_statuses:
                return Response({
                    'status_code': 400,
                    'message': f"Invalid status. Must be one of: {', '.join(valid_statuses)}",
                    'data': {}
                }, status=status.HTTP_400_BAD_REQUEST)

            try:
                requisition = WeeklyMedicineRequisition.objects.get(id=requisition_id)
            except WeeklyMedicineRequisition.DoesNotExist:
                return Response({
                    'status_code': 404,
                    'message': 'Requisition not found',
                    'data': {}
                }, status=status.HTTP_404_NOT_FOUND)

            previous_status = requisition.status
            requisition.status = new_status

            if additional_remarks:
                if requisition.remarks:
                    requisition.remarks += f"\n[{timezone.now().strftime('%Y-%m-%d %H:%M')}] Status changed to {new_status}: {additional_remarks}"
                else:
                    requisition.remarks = f"[{timezone.now().strftime('%Y-%m-%d %H:%M')}] Status changed to {new_status}: {additional_remarks}"

            requisition.save(update_fields=['status', 'remarks'])

            return Response({
                'status_code': 200,
                'message': f'Requisition status updated to {new_status}',
                'data': {
                    'requisition_id': requisition.id,
                    'status': requisition.status,
                    'previous_status': previous_status,
                    'remarks': requisition.remarks,
                }
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception("Medicine requisition status update error")
            return Response({
                'status_code': 500,
                'message': f'Error updating requisition status: {str(e)}',
                'data': {}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)