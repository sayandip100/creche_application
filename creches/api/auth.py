# creches/api/auth.py
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser

from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from creches.models import Creche, CrecheAttendant, Child, ChildAttendance, ChildAttendanceDetail, FoodMonitoring , TeaGarden, ChildPhoto, ChildPhotoEmbedding
from healthcenter.models import HealthCenter, Doctor, Nurse, PatientTreatment, Medicine, HealthCenterMedicineStock, MedicineStockTransaction, PatientTreatmentMedicine, WeeklyMedicineRequisition, WeeklyMedicineRequisitionDetail, DoctorAttendance, NurseAttendance
from creches.serializers import LoginSerializer , AttendantRegisterSerializer , CrecheCreateSerializer, ChildRegisterSerializer
from django.contrib.auth import get_user_model

from django.utils import timezone
from creches.utils import get_face_encoding
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
import pickle
import requests
import json

from rest_framework.permissions import AllowAny

User = get_user_model()

class LoginAPI(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        # -----------------------------
        # Validate user and generate JWT
        # -----------------------------
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']

        refresh = RefreshToken.for_user(user)
        
        # Get name based on role
        name = None
        if user.role in ['attendant', 'super_attendant']:
            attendant = CrecheAttendant.objects.filter(user=user).first()
            name = attendant.attendant_name if attendant else None
        elif user.role == 'doctor':
            doctor = Doctor.objects.filter(user=user).first()
            name = doctor.name if doctor else None
        elif user.role in ['nurse', 'head_nurse']:
            nurse = Nurse.objects.filter(user=user).first()
            name = nurse.nurse_name if nurse else None
        
        data = {
            'access': str(refresh.access_token),
            #'refresh': str(refresh.refresh_token),
            'user_id': user.id,
            'username': user.username,
            'role': user.role,
            'name': name,
        }

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

        return Response(data, status=status.HTTP_200_OK)


class GetRefreshTokenAPI(APIView):
    
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"error": "Method not allowed. Use POST."}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def post(self, request):
        user = request.user

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                #'refresh': str(refresh),
                 'access': str(refresh.access_token),
                'refresh': str(refresh)
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
                
                attendant = CrecheAttendant.objects.create(
                    user=new_user,
                    creche=creche,
                    role=data['role'],
                    attendant_name=data.get('attendant_name'),
                    mobile_no=data.get('mobile_no'),
                    address=data.get('address'),
                    photo=data['photo']
                )

                encoding, error = get_face_encoding(attendant.photo.path)

                if error:
                    attendant.delete()
                    new_user.delete()
                    return Response({"error": error}, status=400)

                import pickle
                attendant.face_encoding = pickle.dumps(encoding)
                attendant.save()

                return Response({
                    "message": "Attendant registered successfully",
                    "data": {
                        "id": attendant.id,
                        "username": new_user.username,
                        "role": attendant.role,
                        "tea_garden_id": tea_garden.id,
                        "creche_id": creche.id,
                        "photo_url": request.build_absolute_uri(attendant.photo.url)
                    }
                }, status=201)

            # =============================
            # DOCTOR
            # =============================
            elif data['role'] == 'doctor':

                tea_garden = TeaGarden.objects.get(id=data['tea_garden_id'])
                health_center = HealthCenter.objects.get(
                    id=data['health_center_id'],
                    tea_garden=tea_garden
                )

                doctor = Doctor.objects.create(
                    user=new_user,
                    health_center=health_center,
                    name=data.get('doctor_name'),
                    specialization=data.get('specialization'),
                    qualification =data.get('qualification'),
                    mobile_no=data.get('mobile_no'),
                    photo=data['photo']
                )

                encoding, error = get_face_encoding(doctor.photo.path)

                if error:
                    doctor.delete()
                    new_user.delete()
                    return Response({"error": error}, status=400)

                import pickle
                doctor.face_encoding = pickle.dumps(encoding)
                doctor.save()

                return Response({
                    "message": "Doctor registered successfully",
                    "data": {
                        "id": doctor.id,
                        "username": new_user.username,
                        "role": "doctor",
                        "tea_garden_id": tea_garden.id,
                        "health_center_id": health_center.id,
                        "photo_url": request.build_absolute_uri(doctor.photo.url)
                    }
                }, status=201)

            # =============================
            # NURSE / HEAD NURSE
            # =============================
            elif data['role'] in ['head_nurse', 'nurse']:

                tea_garden = TeaGarden.objects.get(id=data['tea_garden_id'])
                health_center = HealthCenter.objects.get(
                    id=data['health_center_id'],
                    tea_garden=tea_garden
                )

                nurse = Nurse.objects.create(
                    user=new_user,
                    health_center=health_center,
                    role=data['role'],  # ✅ important
                    nurse_name=data.get('nurse_name'),
                    mobile_no=data.get('mobile_no'),
                    qualification =data.get('qualification'),
                    photo=data['photo']
                )

                encoding, error = get_face_encoding(nurse.photo.path)

                if error:
                    nurse.delete()
                    new_user.delete()
                    return Response({"error": error}, status=400)

                import pickle
                nurse.face_encoding = pickle.dumps(encoding)
                nurse.save()

                return Response({
                    "message": "Nurse registered successfully",
                    "data": {
                        "id": nurse.id,
                        "username": new_user.username,
                        "role": nurse.role,
                        "tea_garden_id": tea_garden.id,
                        "health_center_id": health_center.id,
                        "photo_url": request.build_absolute_uri(nurse.photo.url)
                    }
                }, status=201)

        except Exception as e:
            new_user.delete()
            return Response({"error": str(e)}, status=500)
        
        
        
        
        
        
class ChildRegisterAPI(APIView):
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        serializer = ChildRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        creche = Creche.objects.get(id=data['creche_id'])

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

        # Handle multiple extra photos
        photos = data.get('photos', [])
        child_photos = []
        for photo in photos:
            cp = ChildPhoto.objects.create(child=child, photo=photo)
            child_photos.append(cp)

        # Get photo URLs
        photo_urls = [request.build_absolute_uri(p.photo.url) for p in child_photos]

        # Call external embedding API
        embeddings_response = None
        embeddings_count = 0
        try:
            embedding_api_url = "http://192.168.0.201:8000/api/v1/childregister"
            
            print(f"[DEBUG] Preparing to call embedding API: {embedding_api_url}")
            print(f"[DEBUG] Total photos to send: {len(child_photos)}")
            
            # Prepare files for the embedding API (read into memory first)
            files = []
            for idx, cp in enumerate(child_photos):
                try:
                    with open(cp.photo.path, 'rb') as f:
                        file_content = f.read()
                        files.append(('photo', (cp.photo.name, file_content)))
                       # print(f"[DEBUG] Added photo {idx}: {cp.photo.name} ({len(file_content)} bytes)")
                except Exception as photo_error:
                    print(f"[DEBUG] Error reading photo {idx}: {photo_error}")
            
           # print(f"[DEBUG] Total files prepared: {len(files)}")
            
            # Call the embedding API
            print(f"[DEBUG] Calling embedding API...")
            embedding_response = requests.post(
                embedding_api_url,
                files=files,
                timeout=30
            )
            
            print(f"[DEBUG] API Response Status: {embedding_response.status_code}")
            print(f"[DEBUG] API Response: {embedding_response.text}")
            
            if embedding_response.status_code == 200:
                embeddings_response = embedding_response.json()
                embeddings_list = embeddings_response.get('embeddings', [])
                embeddings_count = len(embeddings_list)
                print(f"[DEBUG] Embeddings received: {embeddings_count}")
                
                # Store embeddings in ChildPhotoEmbedding table
                for idx, embedding_data in enumerate(embeddings_list):
                    if idx < len(child_photos):
                        child_photo = child_photos[idx]
                        # Serialize embedding as pickle
                        embedding_bytes = pickle.dumps(embedding_data)
                        ChildPhotoEmbedding.objects.create(
                            child_photo=child_photo,
                            child=child,
                            embedding=embedding_bytes
                        )
            else:
                print(f"[DEBUG] API returned non-200 status: {embedding_response.status_code}")
                embeddings_response = {"error": f"API returned {embedding_response.status_code}", "details": embedding_response.text}
        except Exception as e:
            print(f"[DEBUG] Exception calling embedding API: {type(e).__name__}: {str(e)}")
            import traceback
            traceback.print_exc()
            embeddings_response = {"error": str(e)}

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
                    "embeddings_message": "Embeddings generated successfully" if embeddings_count > 0 else "No embeddings generated",
                    "embeddings_count": embeddings_count
                }
            ]
        }, status=200)


        


class ChildListAPI(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        creche_id = request.data.get('creche_id')
        
        if not creche_id:
            return Response({"error": "creche_id is required"}, status=400)
        
        try:
            creche = Creche.objects.get(id=creche_id)
        except Creche.DoesNotExist:
            return Response({"error": "Creche not found"}, status=404)
        
        children = Child.objects.filter(creche=creche).all()
        
        children_data = []
        for child in children:
            # Get primary photo
            photo_url = request.build_absolute_uri(child.photo.url) if child.photo else None
            
            # Get gallery photos
            gallery_urls = [request.build_absolute_uri(p.photo.url) for p in child.photos.all()]
            
            children_data.append({
                'id': child.id,
                'name': child.name,
                'age_years': child.age_years,
                'gender': child.gender,
                'photo_url': photo_url,
                'gallery_urls': gallery_urls,
                'created_at': child.created_at
            })
        
        return Response({
            'creche_id': creche.id,
            'creche_name': creche.creche_name,
            'children_count': len(children_data),
            'children': children_data
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