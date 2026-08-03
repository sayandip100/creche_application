from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from healthcenter.models import Doctor, HealthCenter
from healthcenter.serializers import DoctorSerializer


class DoctorListAPI(APIView):
    """
    Doctor List API
    Retrieves all doctors assigned to a specific health center
    
    Endpoint: POST /doctors/list/
    
    Request Body: {
        "health_center_id": 1
    }
    
    Optional Body: {
        "health_center_id": 1,
        "is_active": true
    }
    
    Response: {
        "status_code": 200,
        "message": "Doctors retrieved successfully",
        "data": [
            {
                "id": 1,
                "user_id": 5,
                "username": "doctor1",
                "health_center_id": 1,
                "health_center_name": "Health Center A",
                "name": "Dr. John Doe",
                "mobile_no": "1234567890",
                "qualification": "MBBS",
                "specialization": "General Medicine",
                "photo": "http://example.com/media/doctors/photo1.jpg",
                "is_active": true,
                "created_at": "2025-01-01T10:00:00Z",
                "updated_at": "2025-01-15T10:00:00Z"
            },
            ...
        ]
    }
    """
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        try:
            # Get health_center_id from request body
            health_center_id = request.data.get('health_center_id')
            
            if not health_center_id:
                return Response(
                    {
                        "status_code": 400,
                        "message": "health_center_id is required",
                        "data": None
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate that the health center exists
            try:
                health_center = HealthCenter.objects.get(id=health_center_id)
            except HealthCenter.DoesNotExist:
                return Response(
                    {
                        "status_code": 404,
                        "message": "Health center not found",
                        "data": None
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Filter doctors by health center
            doctors = Doctor.objects.filter(health_center_id=health_center_id)
            
            # Optional filter by active status
            is_active = request.data.get('is_active')
            if is_active is not None:
                doctors = doctors.filter(is_active=bool(is_active))
            
            # Serialize all doctors (no pagination)
            serializer = DoctorSerializer(doctors, many=True)
            
            return Response(
                {
                    "status_code": 200,
                    "message": "Doctors retrieved successfully",
                    "data": serializer.data
                },
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            return Response(
                {
                    "status_code": 500,
                    "message": f"Error retrieving doctors: {str(e)}",
                    "data": None
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DoctorDetailAPI(APIView):
    """
    Doctor Detail API
    Retrieves details of a specific doctor
    
    Endpoint: GET /doctor/<doctor_id>/
    
    Response: {
        "status_code": 200,
        "message": "Doctor retrieved successfully",
        "data": {
            "id": 1,
            "user_id": 5,
            "username": "doctor1",
            "health_center_id": 1,
            "health_center_name": "Health Center A",
            "name": "Dr. John Doe",
            "mobile_no": "1234567890",
            "qualification": "MBBS",
            "specialization": "General Medicine",
            "photo": "http://example.com/media/doctors/photo1.jpg",
            "is_active": true,
            "created_at": "2025-01-01T10:00:00Z",
            "updated_at": "2025-01-15T10:00:00Z"
        }
    }
    """
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request, doctor_id):
        try:
            doctor = Doctor.objects.get(id=doctor_id)
            serializer = DoctorSerializer(doctor)
            
            return Response(
                {
                    "status_code": 200,
                    "message": "Doctor retrieved successfully",
                    "data": serializer.data
                },
                status=status.HTTP_200_OK
            )
            
        except Doctor.DoesNotExist:
            return Response(
                {
                    "status_code": 404,
                    "message": "Doctor not found",
                    "data": None
                },
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {
                    "status_code": 500,
                    "message": f"Error retrieving doctor: {str(e)}",
                    "data": None
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
