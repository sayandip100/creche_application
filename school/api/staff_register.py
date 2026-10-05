# school/api/staff_register.py
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

import numpy as np
import requests

from django.contrib.auth import get_user_model

from school.models import School, Staff, StaffPhoto, StaffPhotoEmbedding
from school.serializers import StaffRegisterSerializer


User = get_user_model()

# External embedding API for staff registration
STAFF_EMBEDDING_API_URL = "http://45.64.107.97:5010/api/v1/photo-embedding"


class StaffRegisterAPI(APIView):
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        serializer = StaffRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        new_user = User.objects.create_user(
            username=data['username'],
            password=data['password'],
            role='teacher',
        )

        try:
            school = School.objects.get(id=data['school_id'])

            # Get photo from request
            photo = data['photo']

            # Prepare file for embedding API
            files = []
            try:
                files.append(('photo', (photo.name, photo.read())))
            except Exception as photo_error:
                new_user.delete()
                return Response({
                    "status_code": 400,
                    "message": "error",
                    "error": f"Failed to read photo: {str(photo_error)}"
                }, status=400)

            # Call embedding API
            embeddings_list = []

            try:
                print(f"[DEBUG] Calling embedding API for staff registration...")
                embedding_response = requests.post(
                    STAFF_EMBEDDING_API_URL,
                    files=files,
                    timeout=30
                )

                print(f"[DEBUG] API Response Status: {embedding_response.status_code}")
                print(f"[DEBUG] API Response: {embedding_response.text}")

                if embedding_response.status_code != 200:
                    new_user.delete()
                    return Response({
                        "status_code": 400,
                        "message": "Embedding generation failed",
                        "error": f"API returned {embedding_response.status_code}",
                        "details": embedding_response.text
                    }, status=200)

                embeddings_response = embedding_response.json()
                embeddings_list = embeddings_response.get('embeddings', [])

                if len(embeddings_list) == 0:
                    new_user.delete()
                    return Response({
                        "status_code": 400,
                        "message": "error",
                        "error": "No embeddings generated from API"
                    }, status=400)

                print(f"[DEBUG] Embeddings received: {len(embeddings_list)}")

                model_name = embeddings_response.get('model', 'face_recognition')

                # ✅ Embeddings successful - Now create staff
                staff = Staff.objects.create(
                    user=new_user,
                    school=school,
                    name=data['staff_name'],
                    phone=data.get('phone', ''),
                    qualification=data.get('qualification', ''),
                )

                # Create staff photo and embedding
                staff_photo = StaffPhoto.objects.create(
                    staff=staff,
                    photo=photo,
                )

                staff_photo_embedding = None
                if len(embeddings_list) > 0:
                    embedding_data = embeddings_list[0]
                    embedding_bytes = np.array(
                        embedding_data, dtype=np.float32
                    ).tobytes()
                    staff_photo_embedding = StaffPhotoEmbedding.objects.create(
                        staff_photo=staff_photo,
                        staff=staff,
                        embedding=embedding_bytes,
                    )

                return Response({
                    "message": "Staff registered successfully",
                    "data": {
                        "id": staff.id,
                        "username": new_user.username,
                        "role": 'teacher',
                        "staff_name": staff.name,
                        "school_id": school.id,
                        "school_name": school.name,
                        "phone": staff.phone,
                        "qualification": staff.qualification,
                        "photo_url": request.build_absolute_uri(staff_photo.photo.url),
                        "staff_photo_id": staff_photo.id,
                        "embedding_id": staff_photo_embedding.id if staff_photo_embedding else None
                    }
                }, status=201)

            except Exception as e:
                new_user.delete()
                return Response({"error": str(e)}, status=500)

        except Exception as e:
            new_user.delete()
            return Response({"error": str(e)}, status=500)