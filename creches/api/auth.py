# creches/api/auth.py
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser

from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from creches.models import Creche, CrecheAttendant, Child, ChildAttendance, ChildAttendanceDetail, FoodMonitoring , TeaGarden, ChildPhoto, ChildPhotoEmbedding, ChildGrowthMonitoring, CrecheAttendantPhoto , CrecheAttendantPhotoEmbedding 
from healthcenter.models import HealthCenter, Doctor, Nurse, PatientTreatment, Medicine, HealthCenterMedicineStock, DoctorPhoto, DoctorPhotoEmbedding, NursePhoto, NursePhotoEmbedding ,MedicineStockTransaction, PatientTreatmentMedicine, WeeklyMedicineRequisition, WeeklyMedicineRequisitionDetail, DoctorAttendance, NurseAttendance
from creches.serializers import LoginSerializer , AttendantRegisterSerializer , CrecheCreateSerializer, ChildRegisterSerializer
from django.contrib.auth import get_user_model

from django.utils import timezone
# from creches.utils import get_face_encoding
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
import pickle
import requests
import json
import numpy as np

from rest_framework.permissions import AllowAny

User = get_user_model()

class LoginAPI(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        # -----------------------------
        # Validate user and generate JWT
        # -----------------------------
        try:
            serializer = LoginSerializer(data=request.data)
            if not serializer.is_valid():
                return Response({
                    'status_code': 401,
                    'message': 'Invalid credentials',
                    'errors': serializer.errors
                }, status=status.HTTP_401_UNAUTHORIZED)
            
            # Get user from validated data
            if 'user' not in serializer.validated_data:
                return Response({
                    'status_code': 401,
                    'message': 'Authentication failed',
                    'errors': {'user': ['User not found']}
                }, status=status.HTTP_401_UNAUTHORIZED)
            
            user = serializer.validated_data['user']
        except Exception as e:
            return Response({
                'status_code': 400,
                'message': f'Login error: {str(e)}'
            }, status=status.HTTP_400_BAD_REQUEST)

        refresh = RefreshToken.for_user(user)
        
        # Get personal details based on role
        name = None
        email = user.email or ''
        mobile_no = None
        address = None
        qualification = None
        specialization = None
        attendant_obj = None
        doctor_obj = None
        nurse_obj = None

        if user.role in ['attendant', 'super_attendant']:
            attendant_obj = CrecheAttendant.objects.filter(user=user).first()
            if attendant_obj:
                name = attendant_obj.attendant_name
                mobile_no = attendant_obj.mobile_no
                address = attendant_obj.address
        elif user.role == 'doctor':
            doctor_obj = Doctor.objects.filter(user=user).first()
            if doctor_obj:
                name = doctor_obj.name
                mobile_no = doctor_obj.mobile_no
                qualification = doctor_obj.qualification
                specialization = doctor_obj.specialization
        elif user.role in ['nurse', 'head_nurse']:
            nurse_obj = Nurse.objects.filter(user=user).first()
            if nurse_obj:
                name = nurse_obj.nurse_name
                mobile_no = nurse_obj.mobile_no
                qualification = nurse_obj.qualification

        # Main data structure
        data = {
            'user_id': user.id,
            'username': user.username,
            'email': email,
            'role': user.role,
            'name': name,
        }

        # Add role-specific profile details
        if user.role in ['attendant', 'super_attendant']:
            data['mobile_no'] = mobile_no
            data['address'] = address
        elif user.role == 'doctor':
            data['mobile_no'] = mobile_no
            data['qualification'] = qualification
            data['specialization'] = specialization
        elif user.role in ['nurse', 'head_nurse']:
            data['mobile_no'] = mobile_no
            data['qualification'] = qualification

        # -----------------------------
        # Helper: Get latest attendance for a child
        # -----------------------------
        def get_latest_attendance(child):
            latest_attendance = ChildAttendance.objects.filter(
                creche=child.creche
            ).order_by('-attendance_date').first()
            if latest_attendance:
                detail = ChildAttendanceDetail.objects.filter(
                    child_attendance=latest_attendance,
                    child=child
                ).first()
                return {
                    'attendance_date': latest_attendance.attendance_date,
                    'status': detail.attendance_status if detail else None
                }
            return None

        # -----------------------------
        # Preprocess medicine stocks for all roles
        # -----------------------------
        stocks = HealthCenterMedicineStock.objects.select_related('medicine', 'health_center').all()
        stock_list = [
            {
                'id': stock.id,
                'medicine_name': stock.medicine.medicine_name,
                'medicine_code': stock.medicine.medicine_code,
                'health_center_id': stock.health_center.id,
                'current_stock_qty': stock.current_stock_qty,
                'last_updated_at': stock.last_updated_at
            }
            for stock in stocks
        ]

        # -----------------------------
        # SUPERADMIN
        # -----------------------------
        if user.role == 'superadmin':
            # Creches
            creches = Creche.objects.select_related('tea_garden').all()
            data['creches'] = []

            for c in creches:
                attendants = [
                    {
                        'id': att.id,
                        'username': att.user.username if att.user else None,
                        'role': att.role,
                        'name': att.attendant_name
                    }
                    for att in c.attendants.select_related('user').all()
                ]
                children = [
                    {
                        'id': child.id,
                        'name': child.name,
                        'age_years': child.age_years,
                        'gender': child.gender,
                        'latest_attendance': get_latest_attendance(child)
                    } for child in c.children.all()
                ]
                food_monitorings = [
                    {
                        'meal_type': fm.meal_type,
                        'description': fm.food_description,
                        'calories': fm.estimated_calories,
                        'date': fm.monitoring_date
                    } for fm in c.food_logs.all()
                ]
                data['creches'].append({
                    'id': c.id,
                    'name': c.creche_name,
                    'tea_garden': c.tea_garden.tea_garden_name,
                    'attendants': attendants,
                    'children': children,
                    'food_monitorings': food_monitorings
                })

            # Health centers
            health_centers = HealthCenter.objects.select_related('tea_garden').all()
            data['health_centers'] = []

            for hc in health_centers:
                doctors = [
                    {'id': d.id, 'username': d.user.username, 'specialization': d.specialization , 'mobile': d.mobile_no , 'qualification': d.qualification ,'name': d.name}
                    for d in hc.doctors.all()
                ]
                nurses = [
                    {'id': n.id, 'username': n.user.username, 'role': n.role}
                    for n in hc.nurses.all()
                ]
                doctor_attendance = [
                    {'doctor_id': da.doctor.id, 'date': da.attendance_date, 'patients_visited': da.patients_visited_today}
                    for da in hc.doctor_attendances.all()
                ]
                nurse_attendance = [
                    {'nurse_id': na.nurse.id, 'date': na.attendance_date}
                    for na in hc.nurse_attendances.all()
                ]
                patients = [
                    {'id': pt.id, 'patient_name': pt.patient_name, 'age': pt.age}
                    for pt in hc.treatments.all()
                ]
                medicines = [
                    {'id': m.id, 'name': m.medicine_name, 'code': m.medicine_code}
                    for m in Medicine.objects.all()
                ]
                # Filter medicine stock for this health center
                medicine_stock = [
                    s for s in stock_list if s['health_center_id'] == hc.id
                ]

                data['health_centers'].append({
                    'id': hc.id,
                    'name': hc.name,
                    'tea_garden': hc.tea_garden.tea_garden_name,
                    'doctors': doctors,
                    'nurses': nurses,
                    'doctor_attendance': doctor_attendance,
                    'nurse_attendance': nurse_attendance,
                    'patients': patients,
                    'medicines': medicines,
                    'medicine_stock': medicine_stock
                })

        # -----------------------------
        # ATTENDANTS / SUPER ATTENDANTS
        # -----------------------------
        elif user.role in ['attendant', 'super_attendant']:
            creche_links = CrecheAttendant.objects.filter(user=user).select_related('creche__tea_garden')
            data['creches'] = []

            tea_garden_id = None
            for cl in creche_links:
                c = cl.creche
                if tea_garden_id is None:
                    tea_garden_id = c.tea_garden.id
                children = [
                    {
                        'id': child.id,
                        'name': child.name,
                        'age_years': child.age_years,
                        'gender': child.gender,
                        'latest_attendance': get_latest_attendance(child)
                    } for child in c.children.all()
                ]
                food_monitorings = [
                    {
                        'meal_type': fm.meal_type,
                        'description': fm.food_description,
                        'calories': fm.estimated_calories,
                        'date': fm.monitoring_date
                    } for fm in c.food_logs.all()
                ]
                data['creches'].append({
                    'id': c.id,
                    'name': c.creche_name,
                    'tea_garden': c.tea_garden.tea_garden_name,
                    'children': children,
                    'food_monitorings': food_monitorings
                })
            data['tea_garden_id'] = tea_garden_id

        # -----------------------------
        # HEALTH STAFF (doctor, head_nurse, nurse)
        # -----------------------------
        elif user.role in ['doctor', 'head_nurse', 'nurse']:
            staff = list(Doctor.objects.filter(user=user)) + list(Nurse.objects.filter(user=user))
            seen = set()
            data['health_centers'] = []
            tea_garden_id = None

            for s in staff:
                hc = s.health_center
                if hc.id in seen:
                    continue
                seen.add(hc.id)
                if tea_garden_id is None:
                    tea_garden_id = hc.tea_garden.id

                patients = [{'id': pt.id, 'patient_name': pt.patient_name, 'age': pt.age} for pt in hc.treatments.all()]
                medicines = [{'id': m.id, 'name': m.medicine_name, 'code': m.medicine_code} for m in Medicine.objects.all()]
                doctor_attendance = [{'doctor_id': da.doctor.id, 'date': da.attendance_date, 'patients_visited': da.patients_visited_today} for da in hc.doctor_attendances.all()]
                nurse_attendance = [{'nurse_id': na.nurse.id, 'date': na.attendance_date} for na in hc.nurse_attendances.all()]
                medicine_stock = [s for s in stock_list if s['health_center_id'] == hc.id]

                data['health_centers'].append({
                    'id': hc.id,
                    'name': hc.name,
                    'tea_garden': hc.tea_garden.tea_garden_name,
                    'patients': patients,
                    'medicines': medicines,
                    'medicine_stock': medicine_stock,
                    'doctor_attendance': doctor_attendance,
                    'nurse_attendance': nurse_attendance
                })
            
            data['tea_garden_id'] = tea_garden_id

        return Response({
            'access': str(refresh.access_token),
            'data': data
        }, status=status.HTTP_200_OK)

class GetRefreshTokenAPI(APIView):
    """
    API endpoint to refresh an expired access token using a valid refresh token.
    
    Accepts POST with JSON body:
    {
        "refresh_token": "<your-refresh-token-string>"
    }
    
    Returns a new access token and refresh token pair.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({
            "status_code": 405,
            "message": "Method not allowed. Use POST.",
            "data": {}
        }, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def post(self, request):
        refresh_token_str = request.data.get('refresh_token')
        
        if not refresh_token_str:
            return Response(
                {
                    "status_code": 400,
                    "message": "refresh_token is required in request body",
                    "data": {}
                },
                status=status.HTTP_200_OK
            )
        
        try:
            from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
            from rest_framework_simplejwt.tokens import AccessToken
            
            # First, verify this is a refresh token and not an access token
            try:
                # Try to decode as access token - should fail if it's a refresh token
                AccessToken(refresh_token_str)
                return Response(
                    {
                        "status_code": 400,
                        "message": "You passed an access token, but a refresh token is required. Please use the refresh_token from your login response, not the access_token.",
                        "data": {}
                    },
                    status=status.HTTP_200_OK
                )
            except:
                # Good - it's not an access token, proceed with refresh token validation
                pass
            
            # Validate the refresh token and get new tokens
            refresh = RefreshToken(refresh_token_str)
            
            # Generate new tokens
            new_access = str(refresh.access_token)
            new_refresh = str(refresh)
            
            return Response(
                {
                    "status_code": 200,
                    "message": "Token refreshed successfully",
                    "data": {
                        "access_token": new_access,
                        "refresh_token": new_refresh
                    }
                },
                status=status.HTTP_200_OK
            )
            
        except (TokenError, InvalidToken) as e:
            error_message = str(e)
            if "Token has wrong type" in error_message:
                return Response(
                    {
                        "status_code": 400,
                        "message": "Invalid token type. Make sure you're using the 'refresh_token' from login response, not the 'access_token'.",
                        "data": {}
                    },
                    status=status.HTTP_200_OK
                )
            return Response(
                {
                    "status_code": 401,
                    "message": f"Invalid or expired refresh token: {str(e)}",
                    "data": {}
                },
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {
                    "status_code": 500,
                    "message": f"An error occurred: {str(e)}",
                    "data": {}
                },
                status=status.HTTP_200_OK
            )



class LogoutAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Stateless JWT logout: client should delete the stored access/refresh tokens.
        return Response(
            {'detail': 'Successfully logged out.'},
            status=status.HTTP_200_OK
        )





    
class AttendantRegisterAPI(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = AttendantRegisterSerializer(data=request.data)
        
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        new_user = User.objects.create_user(
            username=data['username'],
            password=data['password'],
            role=data['role']
        )

        try:
            # =============================
            # ATTENDANT
            # =============================
            if data['role'] in ['attendant', 'super_attendant']:

                tea_garden = TeaGarden.objects.get(id=data['tea_garden_id'])
                creche = Creche.objects.get(
                    id=data['creche_id'],
                    tea_garden=tea_garden
                )
                
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
                embeddings_response = None
                embeddings_list = []
                
                try:
                    embedding_api_url = "http://45.64.107.97:5010/api/v1/photo-embedding"
                    
                    print(f"[DEBUG] Calling embedding API for attendant registration...")
                    embedding_response = requests.post(
                        embedding_api_url,
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
                    
                    # ✅ Embeddings successful - Now create attendant
                    attendant = CrecheAttendant.objects.create(
                        user=new_user,
                        creche=creche,
                        role=data['role'],
                        attendant_name=data.get('attendant_name'),
                        mobile_no=data.get('mobile_no'),
                        address=data.get('address'),
                        photo=data['photo']
                    )
                    
                    # Create CrecheAttendantPhoto record
                    attendant_photo = CrecheAttendantPhoto.objects.create(
                        attendant=attendant,
                        photo=data['photo']
                    )
                    
                    # Create CrecheAttendantPhotoEmbedding record with serialized embedding
                    embedding_data = embeddings_list[0]  # First embedding (list of floats)
                    # Serialize embedding as binary using numpy
                    embedding_bytes = np.array(embedding_data, dtype=np.float32).tobytes()
                    attendant_photo_embedding = CrecheAttendantPhotoEmbedding.objects.create(
                        attendant_photo=attendant_photo,
                        attendant=attendant,
                        embedding=embedding_bytes
                    )
                    
                    return Response({
                        "status_code": 200,
                        "message": f"{data['role']} registered successfully",
                        "data": {
                            "id": attendant.id,
                            "username": new_user.username,
                            "role": attendant.role,
                            "attendant_name": attendant.attendant_name,
                            "mobile_no": attendant.mobile_no,
                            "address": attendant.address,
                            "tea_garden_id": tea_garden.id,
                            "creche_id": creche.id,
                            "photo_url": request.build_absolute_uri(attendant.photo.url),
                            "attendant_photo_id": attendant_photo.id,
                            "embedding_id": attendant_photo_embedding.id
                        }
                    }, status=201)
                    
                except Exception as e:
                    new_user.delete()
                    return Response({"error": str(e)}, status=500)

            # =============================
            # DOCTOR
            # =============================
            elif data['role'] == 'doctor':

                tea_garden = TeaGarden.objects.get(id=data['tea_garden_id'])
                health_center = HealthCenter.objects.get(
                    id=data['health_center_id'],
                    tea_garden=tea_garden
                )

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
                embeddings_response = None
                embeddings_list = []
                
                try:
                    embedding_api_url = "http://45.64.107.97:5010/api/v1/photo-embedding"
                    
                    print(f"[DEBUG] Calling embedding API for doctor registration...")
                    embedding_response = requests.post(
                        embedding_api_url,
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
                        }, status=200)
                    
                    print(f"[DEBUG] Embeddings received: {len(embeddings_list)}")
                    
                    # ✅ Embeddings successful - Now create doctor
                    doctor = Doctor.objects.create(
                        user=new_user,
                        health_center=health_center,
                        name=data.get('doctor_name'),
                        specialization=data.get('specialization'),
                        qualification=data.get('qualification'),
                        mobile_no=data.get('mobile_no'),
                        photo=data['photo']
                    )
                    
                    # Create DoctorPhoto record
                    doctor_photo = DoctorPhoto.objects.create(
                        doctor=doctor,
                        photo=data['photo']
                    )
                    
                    # Create DoctorPhotoEmbedding record with serialized embedding
                    embedding_data = embeddings_list[0]  # First embedding (list of floats)
                    # Serialize embedding as binary using numpy
                    embedding_bytes = np.array(embedding_data, dtype=np.float32).tobytes()
                    doctor_photo_embedding = DoctorPhotoEmbedding.objects.create(
                        doctor_photo=doctor_photo,
                        doctor=doctor,
                        embedding=embedding_bytes
                    )
                    
                    return Response({
                        "status_code": 200,
                        "message": f"{data['role']} registered successfully",
                        "data": {
                            "id": doctor.id,
                            "username": new_user.username,
                            "role": "doctor",
                            "name": doctor.name,
                            "qualification": doctor.qualification,
                            "specialization": doctor.specialization,
                            "mobile_no": doctor.mobile_no,
                            "tea_garden_id": tea_garden.id,
                            "health_center_id": health_center.id,
                            "photo_url": request.build_absolute_uri(doctor.photo.url),
                            "doctor_photo_id": doctor_photo.id,
                            "embedding_id": doctor_photo_embedding.id
                        }
                    }, status=201)
                    
                except Exception as e:
                    new_user.delete()
                    return Response({"error": str(e)}, status=500)

            # =============================
            # NURSE / HEAD NURSE
            # =============================
            elif data['role'] in ['head_nurse', 'nurse']:

                tea_garden = TeaGarden.objects.get(id=data['tea_garden_id'])
                health_center = HealthCenter.objects.get(
                    id=data['health_center_id'],
                    tea_garden=tea_garden
                )

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
                embeddings_response = None
                embeddings_list = []
                
                try:
                    embedding_api_url = "http://45.64.107.97:5010/api/v1/photo-embedding"
                    
                    print(f"[DEBUG] Calling embedding API for nurse registration...")
                    embedding_response = requests.post(
                        embedding_api_url,
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
                    
                    # ✅ Embeddings successful - Now create nurse
                    nurse = Nurse.objects.create(
                        user=new_user,
                        health_center=health_center,
                        role=data['role'],  # ✅ important
                        nurse_name=data.get('nurse_name'),
                        mobile_no=data.get('mobile_no'),
                        qualification=data.get('qualification'),
                        photo=data['photo']
                    )
                    
                    # Create NursePhoto record
                    nurse_photo = NursePhoto.objects.create(
                        nurse=nurse,
                        photo=data['photo']
                    )
                    
                    # Create NursePhotoEmbedding record with serialized embedding
                    embedding_data = embeddings_list[0]  # First embedding (list of floats)
                    # Serialize embedding as binary using numpy
                    embedding_bytes = np.array(embedding_data, dtype=np.float32).tobytes()
                    nurse_photo_embedding = NursePhotoEmbedding.objects.create(
                        nurse_photo=nurse_photo,
                        nurse=nurse,
                        embedding=embedding_bytes
                    )
                    
                    return Response({
                        "status_code": 200,
                        "message": f"{data['role']} registered successfully",
                        "data": {
                            "id": nurse.id,
                            "username": new_user.username,
                            "role": nurse.role,
                            "nurse_name": nurse.nurse_name,
                            "qualification": nurse.qualification,
                            "mobile_no": nurse.mobile_no,
                            "tea_garden_id": tea_garden.id,
                            "health_center_id": health_center.id,
                            "photo_url": request.build_absolute_uri(nurse.photo.url),
                            "nurse_photo_id": nurse_photo.id,
                            "embedding_id": nurse_photo_embedding.id
                        }
                    }, status=201)
                    
                except Exception as e:
                    new_user.delete()
                    return Response({"message": str(e)}, status=500)

        except Exception as e:
            new_user.delete()
            return Response({"message": str(e)}, status=500)
        
        
        
        

class MobileLoginAPI_old(APIView):
    """
    Mobile Login API - Returns simplified login response for mobile clients
    Supports all user roles: superadmin, attendant, super_attendant, doctor, head_nurse, nurse
    Includes: user info, access token, tea_garden_id, and login timestamp
    """
    permission_classes = [AllowAny]

    def post(self, request):
        # Validate user and generate JWT
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        
       # print(user)
        #return Response({"error": "Debug - User authenticated successfully"}, status=200)

        # Generate refresh token (access token is derived from it)
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        
        # Get current login time
        login_time = timezone.now()

        # Get name based on role
        name = None
        attendant = None
        doctor = None
        nurse = None
        staff = None
        
        if user.role in ['attendant', 'super_attendant']:
            attendant = CrecheAttendant.objects.filter(user=user).first()
            name = attendant.attendant_name if attendant else None
        elif user.role == 'doctor':
            doctor = Doctor.objects.filter(user=user).first()
            name = doctor.name if doctor else None
        elif user.role in ['nurse', 'head_nurse']:
            nurse = Nurse.objects.filter(user=user).first()
            name = nurse.nurse_name if nurse else None

        # Get tea_garden_id based on role
        tea_garden_id = None
        if user.role in ['attendant', 'super_attendant']:
            # For attendants, get tea_garden from associated creche
            attendant = CrecheAttendant.objects.filter(user=user).select_related('creche__tea_garden').first()
            if attendant and attendant.creche:
                tea_garden_id = attendant.creche.tea_garden.id
        elif user.role in ['doctor', 'head_nurse', 'nurse']:
            # For health staff, get tea_garden from associated health center
            staff = Doctor.objects.filter(user=user).select_related('health_center__tea_garden').first() or \
                    Nurse.objects.filter(user=user).select_related('health_center__tea_garden').first()
            if staff and staff.health_center:
                tea_garden_id = staff.health_center.tea_garden.id

        # Build mobile response
        user_data = {
            'refresh_token': str(refresh),
            'user_id': user.id,
            'username': user.username,
            'role': user.role,
            'name': name,
            'login_time': login_time.isoformat(),
            'tea_garden_id': tea_garden_id,
            'creache_id' : attendant.creche.id if user.role in ['attendant', 'super_attendant'] and attendant and attendant.creche else None,
            'health_center_id' : staff.health_center.id if user.role in ['doctor', 'head_nurse', 'nurse'] and staff and staff.health_center else None
        }

        return Response({
            'status_code': 200,
            'message': 'success',
            'data': {
                'access_token': access_token,
                'refresh_token': str(refresh),
                'token_type': 'Bearer',
                'expires_in': 300,  # 5 minutes
                'user_data': user_data
            }
        }, status=status.HTTP_200_OK)
        
        
class MobileLoginAPI_oldddddd(APIView):
    """
    Mobile Login API - Returns simplified login response for mobile clients
    Supports all user roles: superadmin, attendant, super_attendant, doctor, head_nurse, nurse
    Includes: user info, access token, tea_garden_id, and login timestamp
    """
    permission_classes = [AllowAny]

    def post(self, request):
        # Validate user and generate JWT
        try:
            serializer = LoginSerializer(data=request.data)
            if not serializer.is_valid():
                return Response({
                    'status_code': 401,
                    'message': 'Invalid credentials',
                    'errors': serializer.errors
                }, status=status.HTTP_200_OK)
            
            # Get user from validated data
            if 'user' not in serializer.validated_data:
                return Response({
                    'status_code': 401,
                    'message': 'Authentication failed',
                    'errors': {'user': ['User not found']}
                }, status=status.HTTP_200_OK)
            
            user = serializer.validated_data['user']
        except Exception as e:
            return Response({
                'status_code': 400,
                'message': f'Login error: {str(e)}'
            }, status=status.HTTP_200_OK)

        # Generate refresh token (access token is derived from it)
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        
        # Get current login time
        login_time = timezone.now()

        # Get user-specific objects based on role
        name = None
        attendant = None
        doctor = None
        nurse = None
        tea_garden_id = None
        
        if user.role in ['attendant', 'super_attendant']:
            attendant = CrecheAttendant.objects.filter(user=user).select_related('creche__tea_garden').first()
            if attendant:
                name = attendant.attendant_name
                if attendant.creche:
                    tea_garden_id = attendant.creche.tea_garden.id
                    
        elif user.role == 'doctor':
            doctor = Doctor.objects.filter(user=user).select_related('health_center__tea_garden').first()
            if doctor:
                name = doctor.name
                if doctor.health_center:
                    tea_garden_id = doctor.health_center.tea_garden.id
                    
        elif user.role in ['nurse', 'head_nurse']:
            nurse = Nurse.objects.filter(user=user).select_related('health_center__tea_garden').first()
            if nurse:
                name = nurse.nurse_name
                if nurse.health_center:
                    tea_garden_id = nurse.health_center.tea_garden.id

        # Get photo URL based on role (with full absolute URL including IP/domain)
        photo_url = None
        if user.role in ['attendant', 'super_attendant'] and attendant:
            photo_url = request.build_absolute_uri(attendant.photo.url) if attendant.photo else None
        elif user.role == 'doctor' and doctor:
            photo_url = request.build_absolute_uri(doctor.photo.url) if doctor.photo else None
        elif user.role in ['nurse', 'head_nurse'] and nurse:
            photo_url = request.build_absolute_uri(nurse.photo.url) if nurse.photo else None

        # Build mobile response
        user_data = {
            'refresh_token': str(refresh),
            'user_id': user.id,
            'username': user.username,
            'role': user.role,
            'name': name,
            'photo_url': photo_url,
            'login_time': login_time.isoformat(),
            'tea_garden_id': tea_garden_id,
            'creache_id': attendant.creche.id if attendant and attendant.creche else None,
            'health_center_id': doctor.health_center.id if doctor and doctor.health_center else (nurse.health_center.id if nurse and nurse.health_center else None),
            'attendant_id': attendant.id if attendant else None,
            'doctor_id': doctor.id if doctor else None,
            'nurse_id': nurse.id if nurse else None,
        }

        return Response({
            'status_code': 200,
            'message': 'success',
            'data': {
                'access_token': access_token,
                'refresh_token': str(refresh),
                'token_type': 'Bearer',
                'expires_in': 300,  # 5 minutes
                'user_data': user_data
            }
        }, status=status.HTTP_200_OK)
        
        
class MobileLoginAPI(APIView):
    """
    Mobile Login API - Returns simplified login response for mobile clients
    Supports all user roles: superadmin, attendant, super_attendant, doctor, head_nurse, nurse
    Includes: user info, access token, tea_garden_id, and login timestamp
    """
    permission_classes = [AllowAny]

    def post(self, request):
        # Validate user and generate JWT
        try:
            serializer = LoginSerializer(data=request.data)
            if not serializer.is_valid():
                return Response({
                    'status_code': 401,
                    'message': 'Invalid credentials',
                    'errors': serializer.errors
                }, status=status.HTTP_200_OK)
            
            # Get user from validated data
            if 'user' not in serializer.validated_data:
                return Response({
                    'status_code': 401,
                    'message': 'Authentication failed',
                    'errors': {'user': ['User not found']}
                }, status=status.HTTP_200_OK)
            
            user = serializer.validated_data['user']
        except Exception as e:
            return Response({
                'status_code': 400,
                'message': f'Login error: {str(e)}'
            }, status=status.HTTP_200_OK)

        # Generate refresh token (access token is derived from it)
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        
        # Get current login time
        login_time = timezone.now()

        # Get user-specific objects based on role
        name = None
        attendant = None
        doctor = None
        nurse = None
        tea_garden_id = None
        
        if user.role in ['attendant', 'super_attendant']:
            attendant = CrecheAttendant.objects.filter(user=user).select_related('creche__tea_garden').first()
            if attendant:
                name = attendant.attendant_name
                if attendant.creche:
                    tea_garden_id = attendant.creche.tea_garden.id
                    
        elif user.role == 'doctor':
            doctor = Doctor.objects.filter(user=user).select_related('health_center__tea_garden').first()
            if doctor:
                name = doctor.name
                if doctor.health_center:
                    tea_garden_id = doctor.health_center.tea_garden.id
                    
        elif user.role in ['nurse', 'head_nurse']:
            nurse = Nurse.objects.filter(user=user).select_related('health_center__tea_garden').first()
            if nurse:
                name = nurse.nurse_name
                if nurse.health_center:
                    tea_garden_id = nurse.health_center.tea_garden.id

        # Get photo URL based on role (with full absolute URL including IP/domain)
        photo_url = None
        if user.role in ['attendant', 'super_attendant'] and attendant:
            photo_url = request.build_absolute_uri(attendant.photo.url) if attendant.photo else None
        elif user.role == 'doctor' and doctor:
            photo_url = request.build_absolute_uri(doctor.photo.url) if doctor.photo else None
        elif user.role in ['nurse', 'head_nurse'] and nurse:
            photo_url = request.build_absolute_uri(nurse.photo.url) if nurse.photo else None

        # Build mobile response
        user_data = {
            'refresh_token': str(refresh),
            'user_id': user.id,
            'username': user.username,
            'role': user.role,
            'name': name,
            'photo_url': photo_url,
            'login_time': login_time.isoformat(),
            'tea_garden_id': tea_garden_id,
            'tea_garden_name': attendant.creche.tea_garden.tea_garden_name if attendant and attendant.creche and attendant.creche.tea_garden else (doctor.health_center.tea_garden.tea_garden_name if doctor and doctor.health_center and doctor.health_center.tea_garden else (nurse.health_center.tea_garden.tea_garden_name if nurse and nurse.health_center and nurse.health_center.tea_garden else None)),
            'creache_id': attendant.creche.id if attendant and attendant.creche else None,
            'creche_name': attendant.creche.creche_name if attendant and attendant.creche else None,
            'health_center_id': doctor.health_center.id if doctor and doctor.health_center else (nurse.health_center.id if nurse and nurse.health_center else None),
            'health_center_name': doctor.health_center.name if doctor and doctor.health_center else (nurse.health_center.name if nurse and nurse.health_center else None),
            'attendant_id': attendant.id if attendant else None,
            'doctor_id': doctor.id if doctor else None,
            'nurse_id': nurse.id if nurse else None,
        }

        return Response({
            'status_code': 200,
            'message': 'success',
            'data': {
                'access_token': access_token,
                'refresh_token': str(refresh),
                'token_type': 'Bearer',
                'expires_in': 60,  # 5 minutes
                'user_data': user_data
            }
        }, status=status.HTTP_200_OK)
        
class ChildRegisterAPI(APIView):
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        serializer = ChildRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        creche = Creche.objects.get(id=data['creche_id'])

        # Get photos from request
        photos = data.get('photos', [])
        
        # Prepare files for embedding API BEFORE creating child
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
        
        # Call embedding API FIRST before creating any child records
        embeddings_response = None
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
                timeout=30
            )
            
            print(f"[DEBUG] API Response Status: {embedding_response.status_code}")
            print(f"[DEBUG] API Response: {embedding_response.text}")
            
            if embedding_response.status_code != 200:
                print(f"[DEBUG] API returned non-200 status: {embedding_response.status_code}")
                # Try to parse the response body for a detail message
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
            
            # ✅ Embeddings successful - Now create child
            child = Child.objects.create(
                creche=creche,
                name=data['name'],
                photo=data.get('photo'),
                age_years=data.get('age_years'),
                gender=data.get('gender'),
                height_cm=data.get('height_cm'),
                weight_kg=data.get('weight_kg'),
                guardian_name=data.get('guardian_name'),
                contact_person_name=data.get('contact_person_name'),
                contact_phone=data.get('contact_phone'),
                address=data.get('address'),
                created_by=request.user if request.user.is_authenticated else None
            )
            
            # Now create child photos with the child reference
            child_photos = []
            for photo in photos:
                cp = ChildPhoto.objects.create(child=child, photo=photo)
                child_photos.append(cp)
            
            # Get photo URLs
            photo_urls = [request.build_absolute_uri(p.photo.url) for p in child_photos]
            
            # Store embeddings in ChildPhotoEmbedding table
            for idx, embedding_data in enumerate(embeddings_list):
                if idx < len(child_photos):
                    child_photo = child_photos[idx]
                    # Serialize embedding as pickle
                    #embedding_bytes = pickle.dumps(embedding_data)
                    embedding_bytes = np.array(embedding_data, dtype=np.float32).tobytes()
                    ChildPhotoEmbedding.objects.create(
                        child_photo=child_photo,
                        child=child,
                        embedding=embedding_bytes
                    )
            
            # ✅ Store child height and weight in ChildGrowthMonitoring
            ChildGrowthMonitoring.objects.create(
                child=child,
                height_cm=data.get('height_cm'),
                weight_kg=data.get('weight_kg'),
                created_at= timezone.now(),
                measured_on =  timezone.now()
            )
            
            return Response({
                "status_code": 200,
                "message": "success",
                "data": [
                    {
                        "id": child.id,
                        "creche_id": creche.id,
                        "name": child.name,
                        "photo_url": request.build_absolute_uri(child.photo.url) if child.photo else None,
                        "photo_urls": photo_urls,
                        "age_years": child.age_years,
                        "gender": child.gender,
                        "height_cm": child.height_cm,
                        "weight_kg": child.weight_kg,
                        "guardian_name": child.guardian_name,
                        "contact_person_name": child.contact_person_name,
                        "contact_phone": child.contact_phone,
                        "address": child.address,
                        "created_by": request.user.username if request.user.is_authenticated else None
                    },
                    {
                        "embeddings_message": "Embeddings generated successfully",
                        "embeddings_count": embeddings_count
                    }
                ]
            }, status=200)
            
        except Exception as e:
            print(f"[DEBUG] Exception: {type(e).__name__}: {str(e)}")
            import traceback
            traceback.print_exc()
            return Response({
                "status_code": 500,
                "message": "error",
                "error": str(e)
            }, status=500)


        
        
        
        
        
class ChildRegisterAPI_2726(APIView):
    #permission_classes = [AllowAny]
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        serializer = ChildRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        creche = Creche.objects.get(id=data['creche_id'])

        # Get photos from request
        photos = data.get('photos', [])
        
        # Prepare files for embedding API BEFORE creating child
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
        
        # Call embedding API FIRST before creating any child records
        embeddings_response = None
        embeddings_count = 0
        embeddings_list = []
        
        try:
            embedding_api_url = "http://45.64.107.97:5010/api/v1/photo-embedding"
            
            print(f"[DEBUG] Preparing to call embedding API: {embedding_api_url}")
            print(f"[DEBUG] Total photos to send: {len(files)}")
            
            if len(files) == 0:
                return Response({
                    "status_code": 400,
                    "message": "Error In Photo Capture ",
                    "error": "No photos provided"
                }, status=400)
            
            # Call the embedding API
            print(f"[DEBUG] Calling embedding API...")
            embedding_response = requests.post(
                embedding_api_url,
                files=files,
                timeout=30
            )
            
            print(f"[DEBUG] API Response Status: {embedding_response.status_code}")
            print(f"[DEBUG] API Response: {embedding_response.text}")
            
            if embedding_response.status_code != 200:
                print(f"[DEBUG] API returned non-200 status: {embedding_response.status_code}")
                return Response({
                    "status_code": 400,
                    "message": "Embedding generation failed",
                    "error": f"API returned {embedding_response.status_code}",
                    "details": embedding_response.text
                }, status=200)
            
            embeddings_response = embedding_response.json()
            embeddings_list = embeddings_response.get('embeddings', [])
            embeddings_count = len(embeddings_list)
            
            if embeddings_count == 0:
                return Response({
                    "status_code": 400,
                    "message": "No embeddings generated",
                    "error": "Embedding API returned no embeddings"
                }, status=400)
            
            print(f"[DEBUG] Embeddings received: {embeddings_count}")
            
            # ✅ Embeddings successful - Now create child
            child = Child.objects.create(
                creche=creche,
                name=data['name'],
                photo=data.get('photo'),
                age_years=data.get('age_years'),
                gender=data.get('gender'),
                height_cm=data.get('height_cm'),
                weight_kg=data.get('weight_kg'),
                guardian_name=data.get('guardian_name'),
                contact_person_name=data.get('contact_person_name'),
                contact_phone=data.get('contact_phone'),
                address=data.get('address'),
                created_by=request.user if request.user.is_authenticated else None
            )
            
            # Now create child photos with the child reference
            child_photos = []
            for photo in photos:
                cp = ChildPhoto.objects.create(child=child, photo=photo)
                child_photos.append(cp)
            
            # Get photo URLs
            photo_urls = [request.build_absolute_uri(p.photo.url) for p in child_photos]
            
            # Store embeddings in ChildPhotoEmbedding table
            for idx, embedding_data in enumerate(embeddings_list):
                if idx < len(child_photos):
                    child_photo = child_photos[idx]
                    # Serialize embedding as pickle
                    #embedding_bytes = pickle.dumps(embedding_data)
                    embedding_bytes = np.array(embedding_data, dtype=np.float32).tobytes()
                    ChildPhotoEmbedding.objects.create(
                        child_photo=child_photo,
                        child=child,
                        embedding=embedding_bytes
                    )
            
            # ✅ Store child height and weight in ChildGrowthMonitoring
            ChildGrowthMonitoring.objects.create(
                child=child,
                height_cm=data.get('height_cm'),
                weight_kg=data.get('weight_kg'),
                created_at= timezone.now(),
                measured_on =  timezone.now()
            )
            
            return Response({
                "status_code": 200,
                "message": "success",
                "data": [
                    {
                        "id": child.id,
                        "creche_id": creche.id,
                        "name": child.name,
                        "photo_url": request.build_absolute_uri(child.photo.url) if child.photo else None,
                        "photo_urls": photo_urls,
                        "age_years": child.age_years,
                        "gender": child.gender,
                        "height_cm": child.height_cm,
                        "weight_kg": child.weight_kg,
                        "guardian_name": child.guardian_name,
                        "contact_person_name": child.contact_person_name,
                        "contact_phone": child.contact_phone,
                        "address": child.address,
                        "created_by": request.user.username if request.user.is_authenticated else None
                    },
                    {
                        "embeddings_message": "Embeddings generated successfully",
                        "embeddings_count": embeddings_count
                    }
                ]
            }, status=200)
            
        except Exception as e:
            print(f"[DEBUG] Exception: {type(e).__name__}: {str(e)}")
            import traceback
            traceback.print_exc()
            return Response({
                "status_code": 500,
                "message": "error",
                "error": str(e)
            }, status=500)


        


class ChildListAPI(APIView):
    #permission_classes = [AllowAny]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        tea_garden_id = request.data.get('tea_garden_id')
        creche_id = request.data.get('creche_id')
        
        # tea_garden_id is mandatory
        if not tea_garden_id:
            return Response({"msg": "tea_garden_id is required"}, status=400)
        
        try:
            tea_garden = TeaGarden.objects.get(id=tea_garden_id)
        except TeaGarden.DoesNotExist:
            return Response({"msg": "Tea garden not found"}, status=200)
        
        # If both tea_garden_id and creche_id are provided
        if creche_id:
            try:
                creches = Creche.objects.filter(id=creche_id, tea_garden=tea_garden)
                if not creches.exists():
                    return Response({"msg": "Creche not found under this tea garden"}, status=404)
            except Creche.DoesNotExist:
                return Response({"msg": "Creche not found"}, status=200)
        else:
            # Only tea_garden_id - get all creches under this tea garden
            creches = Creche.objects.filter(tea_garden=tea_garden)
        
        # Order by most recently created first (newest first)
        children = Child.objects.filter(creche__in=creches).select_related('creche').order_by('-created_at').all()
        
        children_data = []
        for child in children:
            # Get primary photo
            photo_url = request.build_absolute_uri(child.photo.url) if child.photo else None
            
            # Get gallery photos
            gallery_urls = [request.build_absolute_uri(p.photo.url) for p in child.photos.all()]
            
            children_data.append({
                'id': child.id,
                'creche_id': child.creche.id,
                'creche_name': child.creche.creche_name,
                'name': child.name,
                'age_years': child.age_years,
                'gender': child.gender,
                'height': child.height_cm,
                'weight' : child.weight_kg,
                'guardian_name' : child.guardian_name,
                'contact_person_name': child.contact_person_name,
                'contact_phone': child.contact_phone,
                'address': child.address,
                'enrollment_date': child.created_at,
                'photo_url': photo_url,
                'gallery_urls': gallery_urls,
                'created_at': child.created_at
            })
        
        return Response({
            'status_code': 200,
            'message': '',
            'data': {
                'tea_garden_id': tea_garden.id,
                'tea_garden_name': tea_garden.tea_garden_name,
                'children_count': len(children_data),
                'children': children_data
            }
        }, status=200)



class CrecheCreateAPI(APIView):
    permission_classes = [AllowAny]  # 🔥 change to IsAuthenticated later if needed

    def post(self, request):
        serializer = CrecheCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # ✅ Get TeaGarden
        tea_garden = TeaGarden.objects.get(id=data['tea_garden_id'])

        # ✅ Create Creche
        creche = Creche.objects.create(
            creche_name=data['creche_name'],
            creche_code=data['creche_code'],
            tea_garden=tea_garden,
            location_name=data['location'],
            latitude=data['latitude'],
            longitude=data['longitude'],
            geo_radius_meters=data['geo_radius_meters'],
            created_at=timezone.now()
        )

        return Response({
            "message": "Creche created successfully",
            "data": {
                "id": creche.id,
                "creche_name": creche.creche_name,
                "tea_garden_id": tea_garden.id,
                "tea_garden_name": tea_garden.tea_garden_name,
                "location": creche.location_name,
                "latitude": creche.latitude,
                "longitude": creche.longitude,
                "geo_radius_meters": creche.geo_radius_meters
            }
        }, status=201)
        
        
        
        
