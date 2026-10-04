# school/api/student_register.py
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

import numpy as np
import requests

from school.models import StudentGroup, Student, StudentPhoto, StudentPhotoEmbedding, Staff
from school.serializers import StudentRegisterSerializer


class StudentRegisterAPI(APIView):
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        serializer = StudentRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        group = StudentGroup.objects.get(id=data['group_id'])

        # Get photos from request
        photos = data.get('photos', [])

        # Prepare files for embedding API BEFORE creating student
        files = []
        for idx, photo in enumerate(photos):
            try:
                files.append(('photo', (photo.name, photo.read())))
            except Exception as photo_error:
                print(f"[DEBUG] Error reading photo {idx}: {photo_error}")
                return Response({
                    "status_code": 400,
                    "message": "error",
                    "error": f"Failed to read photo {idx}: {str(photo_error)}"
                }, status=400)

        # Call embedding API FIRST before creating any student records
        embeddings_count = 0
        embeddings_list = []

        try:
            embedding_api_url = "http://45.64.107.97:5010/api/v1/photo-embedding"

            print(f"[DEBUG] Preparing to call embedding API: {embedding_api_url}")
            print(f"[DEBUG] Total photos to send: {len(files)}")

            if len(files) == 0:
                return Response({
                    "status_code": 400,
                    "message": "error",
                    "error": "No photos provided"
                }, status=400)

            # Call the embedding API
            print(f"[DEBUG] Calling embedding API...")
            embedding_response = requests.post(
                embedding_api_url,
                files=files,
                timeout=30,
            )

            print(f"[DEBUG] API Response Status: {embedding_response.status_code}")
            print(f"[DEBUG] API Response: {embedding_response.text}")

            if embedding_response.status_code != 200:
                try:
                    error_body = embedding_response.json()
                    detail_msg = error_body.get('detail', {})
                    if isinstance(detail_msg, dict):
                        error_message = detail_msg.get('message', embedding_response.text)
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

            # Check if the response contains a detail message (e.g. face already registered)
            response_detail = embeddings_response.get('detail')
            if response_detail:
                if isinstance(response_detail, dict):
                    detail_message = response_detail.get('message', '')
                else:
                    detail_message = str(response_detail)
                if detail_message:
                    return Response({
                        "status_code": 400,
                        "message": detail_message,
                        "error": detail_message,
                        "details": embedding_response.text
                    }, status=200)

            embeddings_list = embeddings_response.get('embeddings', [])
            embeddings_count = len(embeddings_list)

            if embeddings_count == 0:
                return Response({
                    "status_code": 400,
                    "message": "No embeddings generated",
                    "error": "Embedding API returned no embeddings"
                }, status=400)

            print(f"[DEBUG] Embeddings received: {embeddings_count}")

            model_name = embeddings_response.get('model', 'face_recognition')

            # ✅ Embeddings successful - Now create student
            registered_by = None
            if data.get('registered_by_id'):
                registered_by = Staff.objects.filter(id=data['registered_by_id']).first()

            student = Student.objects.create(
                group=group,
                admission_number=data['admission_number'],
                name=data['name'],
                date_of_birth=data.get('date_of_birth'),
                gender=data.get('gender'),
                guardian_name=data['guardian_name'],
                guardian_phone=data['guardian_phone'],
                address=data.get('address'),
                registered_by=registered_by,
            )

            # Now create student photos with the student reference
            student_photos = []
            for photo in photos:
                sp = StudentPhoto.objects.create(student=student, photo=photo)
                student_photos.append(sp)

            # Get photo URLs
            photo_urls = [request.build_absolute_uri(p.photo.url) for p in student_photos]

            # Store embeddings in StudentPhotoEmbedding table
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
                        "embeddings_count": embeddings_count,
                    },
                ],
            }, status=200)

        except Exception as e:
            print(f"[DEBUG] Exception: {type(e).__name__}: {str(e)}")
            import traceback
            traceback.print_exc()
            return Response({
                "status_code": 500,
                "message": "error",
                "error": str(e),
            }, status=500)