# school/api/student_attendance.py
import requests
from datetime import date

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.parsers import MultiPartParser, FormParser
from django.db import transaction

from school.models import (Student, StudentGroup, StudentPhoto,
                           StudentAttendance, Staff)


EXTERNAL_STUDENT_ATTENDANCE_API_URL = "http://45.64.107.97:5010/api/v1/attendance/student"


class DetectStudentFromPhotoAPI(APIView):
    """
    API endpoint to detect students from a group photo without updating the database.
    Returns the list of detected students with their status.
    Forwarded to the external student face recognition API.
    """
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        # --- Extract request parameters ---
        group_photo = (
            request.FILES.get('file') or
            request.FILES.get('photo') or
            request.FILES.get('image') or
            request.FILES.get('attendance_photo')
        )
        group_id = request.data.get('group_id') or request.POST.get('group_id')
        marked_by_id = (
            request.data.get('marked_by_id') or
            request.POST.get('marked_by_id') or
            request.data.get('mark_by_id') or
            request.POST.get('mark_by_id')
        )

        # --- Validation ---
        if not group_photo:
            return Response(
                {
                    "status_code": 400,
                    "message": "file (group photo) is required",
                },
                status=status.HTTP_200_OK
            )

        if not group_id:
            return Response(
                {
                    "status_code": 400,
                    "message": "group_id is required"
                },
                status=status.HTTP_200_OK
            )

        try:
            group = StudentGroup.objects.get(id=group_id)
        except StudentGroup.DoesNotExist:
            return Response(
                {
                    "status_code": 404,
                    "message": "Student group not found"
                },
                status=status.HTTP_200_OK
            )

        # --- Forward the group photo to external face recognition API ---
        try:
            files = {'file': (group_photo.name, group_photo.read(), group_photo.content_type)}
            payload = {
                'group_id': group_id,
            }

            if marked_by_id:
                payload['marked_by_id'] = marked_by_id

            ext_response = requests.post(
                EXTERNAL_STUDENT_ATTENDANCE_API_URL,
                files=files,
                data=payload,
                timeout=60
            )

            if ext_response.status_code != 200:
                return Response(
                    {
                        "status_code": ext_response.status_code,
                        "message": "External face recognition API error",
                        "external_response": ext_response.text
                    },
                    status=status.HTTP_200_OK
                )

            ext_data = ext_response.json()

        except requests.exceptions.Timeout:
            return Response(
                {
                    "status_code": 408,
                    "message": "External face recognition API timed out"
                },
                status=status.HTTP_200_OK
            )
        except requests.exceptions.ConnectionError as e:
            return Response(
                {
                    "status_code": 503,
                    "message": f"Cannot connect to external face recognition API: {str(e)}"
                },
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {
                    "status_code": 500,
                    "message": f"Error calling external API: {str(e)}"
                },
                status=status.HTTP_200_OK
            )

        # --- Parse external API response ---
        present_ids = ext_data.get('present', [])
        already_present_ids = ext_data.get('already_present', [])
        unknown_faces = ext_data.get('unknown_faces', 0)
        spoof_faces = ext_data.get('spoof_faces', 0)

        # --- Handle case where API might return dicts or IDs ---
        def extract_id(item):
            if isinstance(item, dict):
                return item.get('id', item.get('student_id', item))
            return item

        present_ids_clean = [extract_id(item) for item in present_ids]
        already_present_ids_clean = [extract_id(item) for item in already_present_ids]

        # --- Get all detected student IDs ---
        all_detected_ids = set(present_ids_clean + already_present_ids_clean)

        # --- Get today's attendance to check if already marked ---
        today = date.today()
        already_marked_ids = set(
            StudentAttendance.objects.filter(
                student_id__in=all_detected_ids,
                date=today,
                status='present'
            ).values_list('student_id', flat=True)
        )
# --- Get student details and photos ---
        students_response = []

        for student_id in all_detected_ids:
            try:
                student = Student.objects.get(id=student_id, group=group, is_active=True)

                # Try to get the first reference photo
                front_image_url = None
                student_photo = StudentPhoto.objects.filter(student=student).first()
                if student_photo:
                    front_image_url = request.build_absolute_uri(student_photo.photo.url)

                # Determine if already marked
                is_already_marked = (
                    student_id in already_marked_ids or
                    student_id in already_present_ids_clean
                )
                student_status = ("Already Mark Attendance"
                                  if is_already_marked else "Mark Attendance")

                students_response.append({
                    "student_id": student_id,
                    "front_image": front_image_url or "",
                    "name": student.name,
                    "admission_number": student.admission_number,
                    "student_status": student_status
                })

            except Student.DoesNotExist:
                # Student not found in this group, skip
                continue

        # --- Build response ---
        return Response({
            "status_code": 200,
            "message": "Detection successful",
            "data": {
                "total_faces_detected": len(all_detected_ids),
                "unknown_faces": unknown_faces,
                "spoof_faces": spoof_faces,
                "students": students_response
            }
        }, status=status.HTTP_200_OK)
class MarkIndividualStudentAttendanceAPI(APIView):
    """
    API endpoint to mark individual student attendance as present or absent.
    Required params: student_id (single ID or array of IDs)
    Optional params: attendance_status (present/absent/late/leave), group_id, marked_by_id
    """
    permission_classes = [AllowAny]

    @staticmethod
    def _extract_student_ids(student_id_param):
        """
        Extract a list of student IDs from a flexible input value.

        Accepts any of the following:
          - a single integer / numeric string :  3  or  "3"
          - a list of integers / strings     :  [1, 2, 3]  or  ["1", "2"]
          - a comma separated string         :  "1,2,3"
          - a JSON-encoded list string       :  "[1, 2, 3]"
        """
        import json

        if student_id_param is None:
            return []

        if isinstance(student_id_param, (list, tuple)):
            raw_items = student_id_param
        else:
            try:
                # Already a JSON list representation
                parsed = json.loads(student_id_param)
                if isinstance(parsed, (list, tuple)):
                    raw_items = parsed
                else:
                    raw_items = [parsed]
            except (ValueError, TypeError):
                # Fallback to comma separated string
                raw_items = str(student_id_param).split(',')

        ids = []
        for item in raw_items:
            if item in (None, '', ' '):
                continue
            try:
                ids.append(int(str(item).strip()))
            except (ValueError, TypeError):
                continue
        return ids

    @transaction.atomic
    def post(self, request):
        # --- Extract request parameters ---
        student_id_param = request.data.get('student_id')
        group_id = request.data.get('group_id')
        attendance_status = (
            request.data.get('attendance_status', 'present')
        ).lower()
        marked_by_id = request.data.get('marked_by_id')

        # --- Validation ---
        if not student_id_param:
            return Response({
                "status_code": 400,
                "message": "student_id is required (can be single ID or array of IDs)"
            }, status=status.HTTP_200_OK)

        if attendance_status not in ['present', 'absent', 'late', 'leave']:
            return Response({
                "status_code": 400,
                "message": "attendance_status must be 'present', 'absent', 'late' or 'leave'"
            }, status=status.HTTP_200_OK)

        # --- Convert to list if single value ---
        student_ids = self._extract_student_ids(student_id_param)

        if not student_ids:
            return Response({
                "status_code": 400,
                "message": "No valid student IDs provided"
            }, status=status.HTTP_200_OK)

        # --- Get all students ---
        students = Student.objects.filter(id__in=student_ids, is_active=True)

        if not students.exists():
            return Response({
                "status_code": 404,
                "message": "No valid students found"
            }, status=status.HTTP_200_OK)

        # --- Get group (from first student if not provided) ---
        first_student = students.first()
        group = first_student.group
        if group_id:
            try:
                group = StudentGroup.objects.get(id=group_id)
            except StudentGroup.DoesNotExist:
                return Response({
                    "status_code": 404,
                    "message": "Student group not found"
                }, status=status.HTTP_200_OK)

        # --- Create or update attendance records for today ---
        today = date.today()
        remarks = f"Individual attendance marked for {len(students)} students"

        marked_by = None
        if marked_by_id:
            try:
                marked_by = Staff.objects.get(id=marked_by_id)
                remarks += f" by {marked_by.name}"
            except Staff.DoesNotExist:
                pass

        marked_students = []

        for student in students:
            attendance, created = StudentAttendance.objects.update_or_create(
                student=student,
                date=today,
                defaults={
                    'group': group,
                    'status': attendance_status,
                    'marked_by': marked_by,
                    'remarks': remarks,
                }
            )

            # --- Get student photo ---
            front_image_url = None
            student_photo = StudentPhoto.objects.filter(student=student).first()
            if student_photo:
                front_image_url = request.build_absolute_uri(student_photo.photo.url)

            marked_students.append({
                "student_id": student.id,
                "student_name": student.name,
                "admission_number": student.admission_number,
                "front_image": front_image_url or "",
                "attendance_status": attendance_status,
                "is_newly_created": created
            })

        # --- Build response ---
        return Response({
            "status_code": 200,
            "message": (f"Attendance marked successfully for "
                        f"{len(marked_students)} students as {attendance_status}"),
            "data": {
                "group_id": group.id,
                "attendance_date": today,
                "attendance_status": attendance_status,
                "total_marked": len(marked_students),
                "students": marked_students
            }
        }, status=status.HTTP_200_OK)