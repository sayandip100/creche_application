# creches/api/attendance.py
import os
import requests
import json
from datetime import date

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.parsers import MultiPartParser, FormParser
from django.db import transaction
from django.utils import timezone
from django.conf import settings

from creches.models import Child, ChildAttendance, ChildAttendanceDetail, Creche, CrecheAttendant


EXTERNAL_ATTENDANCE_API_URL = "http://45.64.107.97:5010/api/v1/attendance"


class MarkAttendanceAPI(APIView):
   
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    @transaction.atomic
    def post(self, request):
        # --- Extract request parameters ---
        # Try multiple possible file field names (file, photo, image, attendance_photo)
        group_photo = (
            request.FILES.get('file') or
            request.FILES.get('photo') or
            request.FILES.get('image') or
            request.FILES.get('attendance_photo')
        )
        creche_id = request.data.get('creche_id') or request.POST.get('creche_id')
        # Accept both 'marked_by_id' and 'mark_by_id' for backward compatibility
        marked_by_id = (
            request.data.get('marked_by_id') or
            request.POST.get('marked_by_id') or
            request.data.get('mark_by_id') or
            request.POST.get('mark_by_id')
        )

        # --- Debug logging ---
        print(f"[MarkAttendanceAPI] FILES keys: {list(request.FILES.keys())}")
        print(f"[MarkAttendanceAPI] DATA keys: {list(request.data.keys())}")
        print(f"[MarkAttendanceAPI] POST keys: {list(request.POST.keys())}")
        print(f"[MarkAttendanceAPI] group_photo: {group_photo}")
        print(f"[MarkAttendanceAPI] creche_id: {creche_id}")
        print(f"[MarkAttendanceAPI] marked_by_id: {marked_by_id}")
        print(f"[MarkAttendanceAPI] content_type: {request.content_type}")

        # --- Validation ---
        if not group_photo:
            return Response(
                {
                    "error": "file (group photo) is required",
                    "debug": {
                        "files_keys": list(request.FILES.keys()),
                        "data_keys": list(request.data.keys()),
                        "post_keys": list(request.POST.keys()),
                        "content_type": request.content_type
                    }
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if not creche_id:
            return Response(
                {"error": "creche_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not marked_by_id:
            return Response(
                {"error": "marked_by_id (CrecheAttendant ID) is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            creche = Creche.objects.get(id=creche_id)
        except Creche.DoesNotExist:
            return Response(
                {"error": "Creche not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            marked_by = CrecheAttendant.objects.get(id=marked_by_id)
        except CrecheAttendant.DoesNotExist:
            return Response(
                {"error": "Attendant (marked_by_id) not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        # --- Forward the group photo to external face recognition API ---
        try:
            files = {'file': (group_photo.name, group_photo.read(), group_photo.content_type)}
            payload = {
                'creche_id': creche_id,
                'marked_by_id': marked_by_id,   # external API expects 'marked_by_id'
            }
            
            ext_response = requests.post(
                EXTERNAL_ATTENDANCE_API_URL,
                files=files,
                data=payload,
                timeout=60
            )

            if ext_response.status_code != 200:
                return Response(
                    {
                        "error": "External face recognition API error",
                        "external_status": ext_response.status_code,
                        "external_response": ext_response.text
                    },
                    status=status.HTTP_502_BAD_GATEWAY
                )

            ext_data = ext_response.json()

        except requests.exceptions.Timeout:
            return Response(
                {"error": "External face recognition API timed out"},
                status=status.HTTP_504_GATEWAY_TIMEOUT
            )
        except requests.exceptions.ConnectionError as e:
            return Response(
                {"error": f"Cannot connect to external face recognition API: {str(e)}"},
                status=status.HTTP_502_BAD_GATEWAY
            )
        except Exception as e:
            return Response(
                {"error": f"Error calling external API: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # --- Parse external API response ---
        total_faces = ext_data.get('total_faces', 0)
        present_ids = ext_data.get('present', [])       # list of child IDs recognized as present
        already_present_ids = ext_data.get('already_present', [])  # list of child IDs already marked
        unknown_faces = ext_data.get('unknown_faces', 0)
        spoof_faces = ext_data.get('spoof_faces', 0)
        annotated_image_base64 = ext_data.get('annotated_image_base64', '')
        child_attendance_id_ext = ext_data.get('child_attendance_id')      # external attendance ID
        attendance_photo_path = ext_data.get('attendance_photo', '')       # external photo path

        # --- Determine attendance date (use today if not provided by external API) ---
        today = date.today()

        # --- Build remarks from face recognition results ---
        remarks = f"Total faces detected: {total_faces}, Unknown: {unknown_faces}, Spoof: {spoof_faces}"
        if attendance_photo_path:
            remarks += f" | External photo: {attendance_photo_path}"

        # --- Create or get local ChildAttendance record ---
        attendance, created = ChildAttendance.objects.get_or_create(
            creche=creche,
            attendance_date=today,
            attendance_mode='GROUP',
            defaults={
                'marked_by': marked_by,
                'remarks': remarks,
            }
        )

        # --- Save the uploaded group photo to attendance_photo field ---
        # Reset file pointer to beginning since we already read it for the external API
        group_photo.seek(0)
        attendance.attendance_photo.save(
            group_photo.name,
            group_photo,
            save=False
        )

        # --- Update remarks if record already existed ---
        if not created:
            attendance.remarks = remarks
        attendance.save(update_fields=['attendance_photo', 'remarks'])

        # --- Combine all child IDs that are present (newly detected + already present) ---
        all_present_ids = list(set(present_ids + already_present_ids))

        # --- Get all active children in this creche ---
        all_children = Child.objects.filter(creche=creche, is_active=True)
        all_child_ids = set(all_children.values_list('id', flat=True))
        present_set = set(all_present_ids)

        # --- Upsert attendance details ---
        present_count = 0
        absent_count = 0
        present_children = []
        absent_children = []
        already_present_children = []

        for child in all_children:
            if child.id in present_set:
                # Child is present
                status_val = 'PRESENT'
                present_count += 1
                if child.id in already_present_ids:
                    already_present_children.append({
                        'child_id': child.id,
                        'child_name': child.name
                    })
                else:
                    present_children.append({
                        'child_id': child.id,
                        'child_name': child.name
                    })
            else:
                # Child is absent
                status_val = 'ABSENT'
                absent_count += 1
                absent_children.append({
                    'child_id': child.id,
                    'child_name': child.name
                })

            ChildAttendanceDetail.objects.update_or_create(
                child_attendance=attendance,
                child=child,
                defaults={'attendance_status': status_val}
            )

        # --- Build response ---
        return Response({
            "message": "Attendance processed successfully",
            "attendance_id": attendance.id,
            "creche_id": creche.id,
            "creche_name": creche.creche_name,
            "attendance_date": today,
            "attendance_mode": "GROUP",

            # Face recognition summary
            "total_faces_detected": total_faces,
            "total_faces_recognized": len(all_present_ids),
            "unknown_faces": unknown_faces,
            "spoof_faces": spoof_faces,

            # Children breakdown
            "total_children": all_children.count(),
            "present_count": present_count,
            "absent_count": absent_count,
            "present_children": present_children,
            "already_present_children": already_present_children,
            "absent_children": absent_children,

            # External API reference
            "external_attendance_id": child_attendance_id_ext,
            "attendance_photo": attendance_photo_path,
            "annotated_image_base64": annotated_image_base64,
            # Photo URL
            "attendance_photo_url": request.build_absolute_uri(attendance.attendance_photo.url) if attendance.attendance_photo else None,
            "external_photo_path": attendance_photo_path,
        }, status=status.HTTP_200_OK)


class GetAttendanceByDateAPI(APIView):
    """
    GET /attendance/by-date/?creche_id=1&date=2026-05-08
    
    Get attendance for a creche on a specific date.
    If no attendance exists for that date, returns all children with default ABSENT status.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        creche_id = request.query_params.get('creche_id')
        attendance_date = request.query_params.get('date')

        if not creche_id or not attendance_date:
            return Response(
                {"error": "creche_id and date query params are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            creche = Creche.objects.get(id=creche_id)
        except Creche.DoesNotExist:
            return Response({"error": "Creche not found"}, status=status.HTTP_404_NOT_FOUND)

        # Try to find attendance for this date (GROUP mode preferred, then INDIVIDUAL)
        attendance = ChildAttendance.objects.filter(
            creche=creche,
            attendance_date=attendance_date
        ).order_by('-attendance_mode').first()

        children = Child.objects.filter(creche=creche, is_active=True)
        children_data = []

        if attendance:
            # Get existing details
            details = {
                d.child_id: d.attendance_status
                for d in attendance.details.select_related('child').all()
            }

            for child in children:
                status_val = details.get(child.id, 'ABSENT')
                children_data.append({
                    'child_id': child.id,
                    'child_name': child.name,
                    'age_years': child.age_years,
                    'gender': child.gender,
                    'status': status_val
                })

            return Response({
                "attendance_id": attendance.id,
                "creche_id": creche.id,
                "creche_name": creche.creche_name,
                "attendance_date": attendance.attendance_date,
                "attendance_mode": attendance.attendance_mode,
                "remarks": attendance.remarks,
                "total_children": len(children_data),
                "present_count": sum(1 for c in children_data if c['status'] == 'PRESENT'),
                "absent_count": sum(1 for c in children_data if c['status'] == 'ABSENT'),
                "children": children_data
            }, status=status.HTTP_200_OK)
        else:
            # No attendance marked yet - return all children as ABSENT (not marked)
            for child in children:
                children_data.append({
                    'child_id': child.id,
                    'child_name': child.name,
                    'age_years': child.age_years,
                    'gender': child.gender,
                    'status': 'ABSENT'
                })

            return Response({
                "attendance_id": None,
                "creche_id": creche.id,
                "creche_name": creche.creche_name,
                "attendance_date": attendance_date,
                "attendance_mode": None,
                "remarks": None,
                "total_children": len(children_data),
                "present_count": 0,
                "absent_count": len(children_data),
                "children": children_data
            }, status=status.HTTP_200_OK)


class ChildAttendanceHistoryAPI(APIView):
    """
    GET /attendance/child-history/?child_id=1
    
    Get attendance history for a specific child.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        child_id = request.query_params.get('child_id')

        if not child_id:
            return Response(
                {"error": "child_id query param is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            child = Child.objects.get(id=child_id)
        except Child.DoesNotExist:
            return Response({"error": "Child not found"}, status=status.HTTP_404_NOT_FOUND)

        details = ChildAttendanceDetail.objects.filter(child=child).select_related(
            'child_attendance__creche'
        ).order_by('-child_attendance__attendance_date')

        history = []
        for d in details:
            history.append({
                'attendance_id': d.child_attendance.id,
                'attendance_date': d.child_attendance.attendance_date,
                'attendance_mode': d.child_attendance.attendance_mode,
                'creche_id': d.child_attendance.creche.id,
                'creche_name': d.child_attendance.creche.creche_name,
                'status': d.attendance_status
            })

        total_days = len(history)
        present_days = sum(1 for h in history if h['status'] == 'PRESENT')
        absent_days = sum(1 for h in history if h['status'] == 'ABSENT')

        return Response({
            'child_id': child.id,
            'child_name': child.name,
            'creche_id': child.creche.id,
            'creche_name': child.creche.creche_name,
            'total_records': total_days,
            'present_count': present_days,
            'absent_count': absent_days,
            'attendance_percentage': round((present_days / total_days * 100), 2) if total_days > 0 else 0,
            'history': history
        }, status=status.HTTP_200_OK)


class AttendanceByDateRangeAPI(APIView):
    """
    GET /attendance/date-range/?creche_id=1&from=2026-05-01&to=2026-05-08
    
    Get attendance summary for a creche over a date range.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        creche_id = request.query_params.get('creche_id')
        from_date = request.query_params.get('from')
        to_date = request.query_params.get('to')

        if not creche_id or not from_date or not to_date:
            return Response(
                {"error": "creche_id, from, and to query params are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            creche = Creche.objects.get(id=creche_id)
        except Creche.DoesNotExist:
            return Response({"error": "Creche not found"}, status=status.HTTP_404_NOT_FOUND)

        attendances = ChildAttendance.objects.filter(
            creche=creche,
            attendance_date__gte=from_date,
            attendance_date__lte=to_date
        ).order_by('-attendance_date')

        children = Child.objects.filter(creche=creche, is_active=True)
        total_children = children.count()

        # Build daily breakdown
        daily_data = []
        total_present = 0
        total_absent = 0
        total_days = 0

        for attendance in attendances:
            details = attendance.details.all()
            present_count = details.filter(attendance_status='PRESENT').count()
            absent_count = details.filter(attendance_status='ABSENT').count()
            total_present += present_count
            total_absent += absent_count
            total_days += 1

            daily_data.append({
                'attendance_id': attendance.id,
                'attendance_date': attendance.attendance_date,
                'attendance_mode': attendance.attendance_mode,
                'present_count': present_count,
                'absent_count': absent_count,
                'total_marked': present_count + absent_count,
                'remarks': attendance.remarks
            })

        return Response({
            'creche_id': creche.id,
            'creche_name': creche.creche_name,
            'date_range': {
                'from': from_date,
                'to': to_date
            },
            'total_children': total_children,
            'total_days_marked': total_days,
            'total_present_entries': total_present,
            'total_absent_entries': total_absent,
            'daily_breakdown': daily_data
        }, status=status.HTTP_200_OK)