from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from django.db import transaction

from healthcenter.models import PatientTreatment, HealthCenter, Nurse, Doctor
from healthcenter.serializers import AddPatientSerializer, PatientTreatmentSerializer


class AddPatientAPI(APIView):
    """
    API endpoint to add a new patient treatment record
    
    Accepts:
    - patient_name (required): Name of the patient
    - age (optional): Age of the patient
    - contact_number (optional): Contact number
    - health_center_id (required): ID of the health center
    - nurse_id (optional): ID of the nurse
    - doctor_id (optional): ID of the doctor
    - status (optional, default=1): Treatment status
    - remarks (optional): Additional remarks
    """
    
    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request):
        try:
            # Validate input
            serializer = AddPatientSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(
                    {
                        "status_code": 400,
                        "message": "Validation failed",
                        "errors": serializer.errors,
                        "data": {}
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Extract validated data
            validated_data = serializer.validated_data
            patient_name = validated_data.get('patient_name')
            age = validated_data.get('age')
            contact_number = validated_data.get('contact_number')
            health_center_id = validated_data.get('health_center_id')
            nurse_id = validated_data.get('nurse_id')
            doctor_id = validated_data.get('doctor_id')
            patient_status = validated_data.get('status', 1)
            remarks = validated_data.get('remarks')
            
            # Get health center
            try:
                health_center = HealthCenter.objects.get(id=health_center_id)
            except HealthCenter.DoesNotExist:
                return Response(
                    {
                        "status_code": 404,
                        "message": "Health center not found",
                        "data": {}
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Get nurse if provided
            nurse = None
            if nurse_id:
                try:
                    nurse = Nurse.objects.get(id=nurse_id)
                except Nurse.DoesNotExist:
                    return Response(
                        {
                            "status_code": 404,
                            "message": "Nurse not found",
                            "data": {}
                        },
                        status=status.HTTP_201_CREATED
                    )
            
            # Get doctor if provided
            doctor = None
            if doctor_id:
                try:
                    doctor = Doctor.objects.get(id=doctor_id)
                except Doctor.DoesNotExist:
                    return Response(
                        {
                            "status_code": 404,
                            "message": "Doctor not found",
                            "data": {}
                        },
                        status=status.HTTP_201_CREATED
                    )
            
            # Create patient treatment record
            patient_treatment = PatientTreatment.objects.create(
                patient_name=patient_name,
                age=age,
                contact_number=contact_number,
                health_center=health_center,
                nurse=nurse,
                doctor=doctor,
                status=patient_status,
                remarks=remarks
            )
            
            # Serialize the response
            treatment_serializer = PatientTreatmentSerializer(patient_treatment, context={'request': request})
            treatment_data = treatment_serializer.data
            
            return Response(
                {
                    "status_code": 201,
                    "message": "Patient added successfully",
                    "data": {
                        "patient_id": patient_treatment.id,
                        "patient_name": patient_treatment.patient_name,
                        "age": patient_treatment.age,
                        "contact_number": patient_treatment.contact_number,
                        "health_center_id": patient_treatment.health_center.id,
                        "health_center_name": patient_treatment.health_center.name,
                        "nurse_id": patient_treatment.nurse.id if patient_treatment.nurse else None,
                        "nurse_name": patient_treatment.nurse.nurse_name if patient_treatment.nurse else None,
                        "doctor_id": patient_treatment.doctor.id if patient_treatment.doctor else None,
                        "doctor_name": patient_treatment.doctor.name if patient_treatment.doctor else None,
                        "status": patient_treatment.status,
                        "treatment_date": patient_treatment.treatment_date.isoformat() if patient_treatment.treatment_date else None,
                        "remarks": patient_treatment.remarks,
                        "created_at": patient_treatment.created_at.isoformat() if patient_treatment.created_at else None,
                    }
                },
                status=status.HTTP_201_CREATED
            )
            
        except Exception as e:
            return Response(
                {
                    "status_code": 500,
                    "message": f"An error occurred: {str(e)}",
                    "data": {}
                },
                status=status.HTTP_201_CREATED
            )


class PatientListAPI(APIView):
    
     
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            # Get optional filter parameters from query params
            health_center_id = request.query_params.get('health_center_id')
            nurse_id = request.query_params.get('nurse_id')
            doctor_id = request.query_params.get('doctor_id')
           
            # Build query
            queryset = PatientTreatment.objects.all()
            
            if health_center_id:
                queryset = queryset.filter(health_center_id=health_center_id)
            
            if nurse_id:
                queryset = queryset.filter(nurse_id=nurse_id)

            if doctor_id:
                queryset = queryset.filter(doctor_id=doctor_id)
            
            # Order by most recent first
            queryset = queryset.order_by('-created_at')
            
            # Serialize
            serializer = PatientTreatmentSerializer(queryset, many=True, context={'request': request})
            
            return Response(
                {
                    "status_code": 200,
                    "message": "Patients retrieved successfully",
                    "data": serializer.data,
                    "total_count": queryset.count()
                },
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            return Response(
                {
                    "status_code": 500,
                    "message": f"An error occurred: {str(e)}",
                    "data": []
                },
                status=status.HTTP_200_OK
            )

    def post(self, request):
        """
        POST endpoint to list patients filtered by health_center_id, nurse_id, and/or doctor_id.
        
        Accepts JSON body:
        {
            "health_center_id": 2,
            "nurse_id": 1,
            "doctor_id": 3
        }
        All parameters are optional.
        """
        try:
            # Get optional filter parameters from request body
            health_center_id = request.data.get('health_center_id')
            nurse_id = request.data.get('nurse_id')
            doctor_id = request.data.get('doctor_id')
            
            # Build query
            queryset = PatientTreatment.objects.all()
            
            if health_center_id:
                queryset = queryset.filter(health_center_id=health_center_id)
            
            if nurse_id:
                queryset = queryset.filter(nurse_id=nurse_id)

            if doctor_id:
                queryset = queryset.filter(doctor_id=doctor_id)
            
            # Order by most recent first
            queryset = queryset.order_by('-created_at')
            
            # Serialize
            serializer = PatientTreatmentSerializer(queryset, many=True, context={'request': request})
            
            return Response(
                {
                    "status_code": 200,
                    "message": "Patients retrieved successfully",
                    "data": serializer.data,
                    "total_count": queryset.count()
                },
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            return Response(
                {
                    "status_code": 500,
                    "message": f"An error occurred: {str(e)}",
                    "data": []
                },
                status=status.HTTP_200_OK
            )


class PatientDetailAPI(APIView):
    """
    API endpoint to get, update, or delete a patient
    """
    
    permission_classes = [AllowAny]

    def get(self, request, patient_id):
        try:
            patient = PatientTreatment.objects.get(id=patient_id)
            serializer = PatientTreatmentSerializer(patient, context={'request': request})
            
            return Response(
                {
                    "status_code": 200,
                    "message": "Patient retrieved successfully",
                    "data": serializer.data
                },
                status=status.HTTP_200_OK
            )
        except PatientTreatment.DoesNotExist:
            return Response(
                {
                    "status_code": 404,
                    "message": "Patient not found",
                    "data": {}
                },
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {
                    "status_code": 500,
                    "message": f"An error occurred: {str(e)}",
                    "data": {}
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def put(self, request, patient_id):
        try:
            patient = PatientTreatment.objects.get(id=patient_id)
            
            # Update fields if provided
            patient.patient_name = request.data.get('patient_name', patient.patient_name)
            patient.age = request.data.get('age', patient.age)
            patient.contact_number = request.data.get('contact_number', patient.contact_number)
            patient.status = request.data.get('status', patient.status)
            patient.remarks = request.data.get('remarks', patient.remarks)
            
            if 'nurse_id' in request.data and request.data.get('nurse_id'):
                try:
                    patient.nurse = Nurse.objects.get(id=request.data.get('nurse_id'))
                except Nurse.DoesNotExist:
                    return Response(
                        {
                            "status_code": 404,
                            "message": "Nurse not found",
                            "data": {}
                        },
                        status=status.HTTP_404_NOT_FOUND
                    )
            
            if 'doctor_id' in request.data and request.data.get('doctor_id'):
                try:
                    patient.doctor = Doctor.objects.get(id=request.data.get('doctor_id'))
                except Doctor.DoesNotExist:
                    return Response(
                        {
                            "status_code": 404,
                            "message": "Doctor not found",
                            "data": {}
                        },
                        status=status.HTTP_404_NOT_FOUND
                    )
            
            patient.save()
            serializer = PatientTreatmentSerializer(patient, context={'request': request})
            
            return Response(
                {
                    "status_code": 200,
                    "message": "Patient updated successfully",
                    "data": serializer.data
                },
                status=status.HTTP_200_OK
            )
        except PatientTreatment.DoesNotExist:
            return Response(
                {
                    "status_code": 404,
                    "message": "Patient not found",
                    "data": {}
                },
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {
                    "status_code": 500,
                    "message": f"An error occurred: {str(e)}",
                    "data": {}
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def delete(self, request, patient_id):
        try:
            patient = PatientTreatment.objects.get(id=patient_id)
            patient.delete()
            
            return Response(
                {
                    "status_code": 200,
                    "message": "Patient deleted successfully",
                    "data": {}
                },
                status=status.HTTP_200_OK
            )
        except PatientTreatment.DoesNotExist:
            return Response(
                {
                    "status_code": 404,
                    "message": "Patient not found",
                    "data": {}
                },
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {
                    "status_code": 500,
                    "message": f"An error occurred: {str(e)}",
                    "data": {}
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )