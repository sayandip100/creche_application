# creches/api/child_growth.py
"""
API for Child Growth Monitoring - height and weight tracking with photos.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.parsers import MultiPartParser, FormParser
from django.db import transaction
from datetime import date

from creches.models import Child, ChildGrowthMonitoring, Creche


class ChildGrowthMonitoringAPI(APIView):
    """
    POST /child-growth/create/
    Create or update a child growth monitoring record with height and weight measurements,
    along with optional weight_pic and height_pic.

    Required params: child_id
    Optional params: height_cm, weight_kg, notes, weight_pic (file), height_pic (file)

    measured_on is automatically set to the current date.
    If a record already exists for the same child on the same date, it will be updated.
    """
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    @transaction.atomic
    def post(self, request):
        # --- Extract params ---
        child_id = request.data.get('child_id') or request.POST.get('child_id')
        measured_on = date.today()
        height_cm = request.data.get('height_cm') or request.POST.get('height_cm')
        weight_kg = request.data.get('weight_kg') or request.POST.get('weight_kg')
        notes = request.data.get('notes') or request.POST.get('notes')

        weight_pic = request.FILES.get('weight_pic')
        height_pic = request.FILES.get('height_pic')

        # --- Validation ---
        if not child_id:
            return Response({
                "status_code": 400,
                "message": "child_id is required"
            }, status=status.HTTP_200_OK)


        try:
            child = Child.objects.get(id=child_id, is_active=True)
        except Child.DoesNotExist:
            return Response({
                "status_code": 404,
                "message": "Child not found"
            }, status=status.HTTP_200_OK)

        # --- Create or update growth record ---
        growth_record, created = ChildGrowthMonitoring.objects.update_or_create(
            child=child,
            measured_on=measured_on,
            defaults={
                'height_cm': height_cm if height_cm else None,
                'weight_kg': weight_kg if weight_kg else None,
                'notes': notes if notes else None,
            }
        )

        # --- Save weight_pic if provided ---
        if weight_pic:
            growth_record.weight_pic.save(
                f"weight_{child.id}_{measured_on}_{weight_pic.name}",
                weight_pic,
                save=False
            )

        # --- Save height_pic if provided ---
        if height_pic:
            growth_record.height_pic.save(
                f"height_{child.id}_{measured_on}_{height_pic.name}",
                height_pic,
                save=False
            )

        # Save only if photos were updated
        if weight_pic or height_pic:
            update_fields = []
            if weight_pic:
                update_fields.append('weight_pic')
            if height_pic:
                update_fields.append('height_pic')
            if created or update_fields:
                growth_record.save(update_fields=update_fields)
        elif created:
            growth_record.save()

        # --- Build response ---
        return Response({
            "status_code": 200,
            "message": "Growth monitoring record saved successfully",
            "data": {
                "id": growth_record.id,
                "child_id": child.id,
                "child_name": child.name,
                "measured_on": growth_record.measured_on,
                "height_cm": str(growth_record.height_cm) if growth_record.height_cm else None,
                "weight_kg": str(growth_record.weight_kg) if growth_record.weight_kg else None,
                "notes": growth_record.notes,
                "weight_pic": request.build_absolute_uri(growth_record.weight_pic.url) if growth_record.weight_pic else None,
                "height_pic": request.build_absolute_uri(growth_record.height_pic.url) if growth_record.height_pic else None,
                "is_newly_created": created
            }
        }, status=status.HTTP_200_OK)


class ChildGrowthHistoryAPI(APIView):
    """
    GET /child-growth/history/?child_id=1
    Get growth monitoring history for a specific child.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        child_id = request.query_params.get('child_id')

        if not child_id:
            return Response({
                "status_code": 400,
                "message": "child_id query param is required"
            }, status=status.HTTP_200_OK)

        try:
            child = Child.objects.get(id=child_id, is_active=True)
        except Child.DoesNotExist:
            return Response({
                "status_code": 404,
                "message": "Child not found"
            }, status=status.HTTP_200_OK)

        records = ChildGrowthMonitoring.objects.filter(child=child).order_by('-measured_on')

        history = []
        for record in records:
            history.append({
                "id": record.id,
                "measured_on": record.measured_on,
                "height_cm": str(record.height_cm) if record.height_cm else None,
                "weight_kg": str(record.weight_kg) if record.weight_kg else None,
                "notes": record.notes,
                "weight_pic": request.build_absolute_uri(record.weight_pic.url) if record.weight_pic else None,
                "height_pic": request.build_absolute_uri(record.height_pic.url) if record.height_pic else None,
                "created_at": record.created_at
            })

        return Response({
            "status_code": 200,
            "message": "Success",
            "data": {
                "child_id": child.id,
                "child_name": child.name,
                "creche_id": child.creche.id,
                "creche_name": child.creche.creche_name,
                "total_records": len(history),
                "records": history
            }
        }, status=status.HTTP_200_OK)


class ChildGrowthDetailAPI(APIView):
    """
    GET /child-growth/detail/?record_id=1
    Get a single growth monitoring record by its ID.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        record_id = request.query_params.get('record_id')

        if not record_id:
            return Response({
                "status_code": 400,
                "message": "record_id query param is required"
            }, status=status.HTTP_200_OK)

        try:
            record = ChildGrowthMonitoring.objects.select_related('child__creche').get(id=record_id)
        except ChildGrowthMonitoring.DoesNotExist:
            return Response({
                "status_code": 404,
                "message": "Growth monitoring record not found"
            }, status=status.HTTP_200_OK)

        return Response({
            "status_code": 200,
            "message": "Success",
            "data": {
                "id": record.id,
                "child_id": record.child.id,
                "child_name": record.child.name,
                "creche_id": record.child.creche.id,
                "creche_name": record.child.creche.creche_name,
                "measured_on": record.measured_on,
                "height_cm": str(record.height_cm) if record.height_cm else None,
                "weight_kg": str(record.weight_kg) if record.weight_kg else None,
                "notes": record.notes,
                "weight_pic": request.build_absolute_uri(record.weight_pic.url) if record.weight_pic else None,
                "height_pic": request.build_absolute_uri(record.height_pic.url) if record.height_pic else None,
                "created_at": record.created_at
            }
        }, status=status.HTTP_200_OK)


class ChildGrowthDeleteAPI(APIView):
    """
    DELETE /child-growth/delete/?record_id=1
    Delete a growth monitoring record by its ID.
    """
    permission_classes = [AllowAny]

    def delete(self, request):
        record_id = request.query_params.get('record_id') or request.data.get('record_id')

        if not record_id:
            return Response({
                "status_code": 400,
                "message": "record_id is required"
            }, status=status.HTTP_200_OK)

        try:
            record = ChildGrowthMonitoring.objects.get(id=record_id)
        except ChildGrowthMonitoring.DoesNotExist:
            return Response({
                "status_code": 404,
                "message": "Growth monitoring record not found"
            }, status=status.HTTP_200_OK)

        record.delete()

        return Response({
            "status_code": 200,
            "message": "Growth monitoring record deleted successfully"
        }, status=status.HTTP_200_OK)


class ChildGrowthByDateRangeAPI(APIView):
    """
    GET /child-growth/date-range/?child_id=1&from=2026-01-01&to=2026-12-31
    Get growth monitoring records for a child within a date range.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        child_id = request.query_params.get('child_id')
        from_date = request.query_params.get('from')
        to_date = request.query_params.get('to')

        if not child_id or not from_date or not to_date:
            return Response({
                "status_code": 400,
                "message": "child_id, from, and to query params are required"
            }, status=status.HTTP_200_OK)

        try:
            child = Child.objects.get(id=child_id, is_active=True)
        except Child.DoesNotExist:
            return Response({
                "status_code": 404,
                "message": "Child not found"
            }, status=status.HTTP_200_OK)

        records = ChildGrowthMonitoring.objects.filter(
            child=child,
            measured_on__gte=from_date,
            measured_on__lte=to_date
        ).order_by('-measured_on')

        history = []
        for record in records:
            history.append({
                "id": record.id,
                "measured_on": record.measured_on,
                "height_cm": str(record.height_cm) if record.height_cm else None,
                "weight_kg": str(record.weight_kg) if record.weight_kg else None,
                "notes": record.notes,
                "weight_pic": request.build_absolute_uri(record.weight_pic.url) if record.weight_pic else None,
                "height_pic": request.build_absolute_uri(record.height_pic.url) if record.height_pic else None,
                "created_at": record.created_at
            })

        return Response({
            "status_code": 200,
            "message": "Success",
            "data": {
                "child_id": child.id,
                "child_name": child.name,
                "creche_id": child.creche.id,
                "creche_name": child.creche.creche_name,
                "date_range": {
                    "from": from_date,
                    "to": to_date
                },
                "total_records": len(history),
                "records": history
            }
        }, status=status.HTTP_200_OK)