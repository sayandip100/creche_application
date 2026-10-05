# school/api/register.py
"""Unified role-based registration API for students and teachers.

A single endpoint handles both roles. The `role` field decides which model
set is used:

  - role='student' -> Student / StudentPhoto / StudentPhotoEmbedding
  - role='teacher' -> Teacher / TeacherPhoto / TeacherPhotoEmbedding
"""

from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

import numpy as np
import requests

from school.models import (
    StudentGroup,
    Student,
    StudentPhoto,
    StudentPhotoEmbedding,
    School,
    Staff,
    Teacher,
    TeacherPhoto,
    TeacherPhotoEmbedding,
)
from school.serializers import RoleRegisterSerializer

# External embedding API used for face vectors
EMBEDDING_API_URL = "http://45.64.107.97:5010/api/v1/photo-embedding"


class RegisterAPI(APIView):
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        serializer = RoleRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        role = data["role"]

        # Collect photos: prefer the list, fall back to a single photo.
        photos = self._collect_photos(data)

        # Prepare files for the embedding API BEFORE creating any record.
        files = self._prepare_files(photos)
        if isinstance(files, Response):
            return files

        # Generate face embeddings FIRST.
        result = self._generate_embeddings(files)
        if isinstance(result, Response):
            return result
        embeddings_list, model_name = result

        try:
            if role == "student":
                return self._register_student(
                    request, data, photos, embeddings_list, model_name
                )
            return self._register_teacher(
                request, data, photos, embeddings_list, model_name
            )
        except Exception as e:
            import traceback

            print(f"[DEBUG] Exception: {type(e).__name__}: {str(e)}")
            traceback.print_exc()
            return Response({
                "status_code": 500,
                "message": "error",
                "error": str(e),
            }, status=500)

    def _collect_photos(self, data):
        photos = list(data.get("photos") or [])
        single_photo = data.get("photo")
        if single_photo is not None:
            photos.insert(0, single_photo)
        return photos

    def _prepare_files(self, photos):
        files = []
        for idx, photo in enumerate(photos):
            try:
                files.append(("photo", (photo.name, photo.read())))
            except Exception as photo_error:
                print(f"[DEBUG] Error reading photo {idx}: {photo_error}")
                return Response({
                    "status_code": 400,
                    "message": "error",
                    "error": f"Failed to read photo {idx}: {str(photo_error)}"
                }, status=400)
        return files

    def _generate_embeddings(self, files):
        if len(files) == 0:
            return Response({
                "status_code": 400,
                "message": "error",
                "error": "No photos provided"
            }, status=400)

        try:
            print(f"[DEBUG] Calling embedding API: {EMBEDDING_API_URL}")
            print(f"[DEBUG] Total photos to send: {len(files)}")

            embedding_response = requests.post(
                EMBEDDING_API_URL,
                files=files,
                timeout=30,
            )

            print(f"[DEBUG] API Response Status: {embedding_response.status_code}")
            print(f"[DEBUG] API Response: {embedding_response.text}")

            if embedding_response.status_code != 200:
                try:
                    error_body = embedding_response.json()
                    detail_msg = error_body.get("detail", {})
                    if isinstance(detail_msg, dict):
                        error_message = detail_msg.get("message", embedding_response.text)
                    else:
                        error_message = str(detail_msg)
                except Exception:
                    error_message = embedding_response.text

                return Response({
                    "status_code": 400,
                    "message": error_message,
                    "error": f"API returned {embedding_response.status_code}",
                    "details": embedding_response.text
                }, status=200)

            embeddings_response = embedding_response.json()

            # Check for a detail message (e.g. face already registered).
            response_detail = embeddings_response.get("detail")
            if response_detail:
                if isinstance(response_detail, dict):
                    detail_message = response_detail.get("message", "")
                else:
                    detail_message = str(response_detail)
                if detail_message:
                    return Response({
                        "status_code": 400,
                        "message": detail_message,
                        "error": detail_message,
                        "details": embedding_response.text
                    }, status=200)

            embeddings_list = embeddings_response.get("embeddings", [])

            if len(embeddings_list) == 0:
                return Response({
                    "status_code": 400,
                    "message": "No embeddings generated",
                    "error": "Embedding API returned no embeddings"
                }, status=400)

            print(f"[DEBUG] Embeddings received: {len(embeddings_list)}")
            model_name = embeddings_response.get("model", "face_recognition")
            return embeddings_list, model_name

        except Exception as e:
            import traceback

            print(f"[DEBUG] Exception: {type(e).__name__}: {str(e)}")
            traceback.print_exc()
            return Response({
                "status_code": 500,
                "message": "error",
                "error": str(e),
            }, status=500)

    def _register_student(self, request, data, photos, embeddings_list, model_name):
        group = StudentGroup.objects.get(id=data["group_id"])

        registered_by = None
        if data.get("registered_by_id"):
            registered_by = Staff.objects.filter(id=data["registered_by_id"]).first()

        student = Student.objects.create(
            group=group,
            admission_number=data["admission_number"],
            name=data["name"],
            date_of_birth=data.get("date_of_birth"),
            gender=data.get("gender"),
            guardian_name=data["guardian_name"],
            guardian_phone=data["guardian_phone"],
            address=data.get("address"),
            registered_by=registered_by,
        )

        # Create student photos with the student reference.
        student_photos = []
        for photo in photos:
            student_photos.append(StudentPhoto.objects.create(student=student, photo=photo))

        photo_urls = [request.build_absolute_uri(p.photo.url) for p in student_photos]

        # Store embeddings in the StudentPhotoEmbedding table.
        for idx, embedding_data in enumerate(embeddings_list):
            if idx < len(student_photos):
                student_photo = student_photos[idx]
                embedding_bytes = np.array(embedding_data, dtype=np.float32).tobytes()
                StudentPhotoEmbedding.objects.create(
                    student_photo=student_photo,
                    embedding=embedding_bytes,
                    model_name=model_name,
                    dimensions=len(embedding_data),
                )

        return Response({
            "status_code": 200,
            "message": "success",
            "role": "student",
            "data": [
                {
                    "id": student.id,
                    "group_id": group.id,
                    "admission_number": student.admission_number,
                    "name": student.name,
                    "date_of_birth": student.date_of_birth,
                    "gender": student.gender,
                    "guardian_name": student.guardian_name,
                    "guardian_phone": student.guardian_phone,
                    "address": student.address,
                    "enrollment_date": student.enrollment_date,
                    "registered_by_id": student.registered_by_id,
                    "photo_url": request.build_absolute_uri(
                        student_photos[0].photo.url) if student_photos else None,
                    "photo_urls": photo_urls,
                },
                {
                    "embeddings_message": "Embeddings generated successfully",
                    "embeddings_count": len(embeddings_list),
                },
            ],
        }, status=200)

    def _register_teacher(self, request, data, photos, embeddings_list, model_name):
        school = School.objects.get(id=data["school_id"])

        registered_by = None
        if data.get("registered_by_id"):
            registered_by = Staff.objects.filter(id=data["registered_by_id"]).first()

        teacher = Teacher.objects.create(
            school=school,
            employee_number=data["employee_number"],
            name=data["name"],
            phone=data.get("phone", ""),
            qualification=data.get("qualification", ""),
            date_of_birth=data.get("date_of_birth"),
            gender=data.get("gender"),
            address=data.get("address"),
            registered_by=registered_by,
        )

        # Create teacher photos with the teacher reference.
        teacher_photos = []
        for photo in photos:
            teacher_photos.append(TeacherPhoto.objects.create(teacher=teacher, photo=photo))

        photo_urls = [request.build_absolute_uri(p.photo.url) for p in teacher_photos]

        # Store embeddings in the TeacherPhotoEmbedding table.
        for idx, embedding_data in enumerate(embeddings_list):
            if idx < len(teacher_photos):
                teacher_photo = teacher_photos[idx]
                embedding_bytes = np.array(embedding_data, dtype=np.float32).tobytes()
                TeacherPhotoEmbedding.objects.create(
                    teacher_photo=teacher_photo,
                    embedding=embedding_bytes,
                    model_name=model_name,
                    dimensions=len(embedding_data),
                )

        return Response({
            "status_code": 200,
            "message": "success",
            "role": "teacher",
            "data": [
                {
                    "id": teacher.id,
                    "school_id": school.id,
                    "school_name": school.name,
                    "employee_number": teacher.employee_number,
                    "name": teacher.name,
                    "phone": teacher.phone,
                    "qualification": teacher.qualification,
                    "date_of_birth": teacher.date_of_birth,
                    "gender": teacher.gender,
                    "address": teacher.address,
                    "registration_date": teacher.registration_date,
                    "registered_by_id": teacher.registered_by_id,
                    "photo_url": request.build_absolute_uri(
                        teacher_photos[0].photo.url) if teacher_photos else None,
                    "photo_urls": photo_urls,
                },
                {
                    "embeddings_message": "Embeddings generated successfully",
                    "embeddings_count": len(embeddings_list),
                },
            ],
        }, status=200)