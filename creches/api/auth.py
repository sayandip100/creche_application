# creches/api/auth.py
from rest_framework.views import APIView

from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from creches.models import Creche, CrecheAttendant, Child, ChildAttendance, ChildAttendanceDetail, FoodMonitoring
from healthcenter.models import HealthCenter, Doctor, Nurse, PatientTreatment, Medicine, HealthCenterMedicineStock, NurseAttendance
from creches.serializers import LoginSerializer , AttendantRegisterSerializer
from django.contrib.auth import get_user_model

from rest_framework.utils import timezone
from creches.utils import get_face_encoding
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
import pickle

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
        data = {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user_id': user.id,
            'username': user.username,
            'role': user.role,
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
                    {'id': att.id, 'username': att.user.username, 'role': att.role}
                    for att in c.attendants.all()
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

            for cl in creche_links:
                c = cl.creche
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

        # -----------------------------
        # HEALTH STAFF (doctor, head_nurse, nurse)
        # -----------------------------
        elif user.role in ['doctor', 'head_nurse', 'nurse']:
            staff = list(Doctor.objects.filter(user=user)) + list(Nurse.objects.filter(user=user))
            seen = set()
            data['health_centers'] = []

            for s in staff:
                hc = s.health_center
                if hc.id in seen:
                    continue
                seen.add(hc.id)

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

        return Response(data, status=status.HTTP_200_OK)
    
class AttendantRegisterAPI(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = AttendantRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # ✅ Create user
        new_user = User.objects.create_user(
            username=data['username'],
            password=data['password'],
            role=data['role']
        )

        # ✅ Get creche directly
        creche = Creche.objects.get(id=data['creche_id'])

        # ✅ Create attendant
        attendant = CrecheAttendant.objects.create(
            user=new_user,
            creche=creche,
            role=data['role'],
            attendant_name=data['attendant_name'],
            mobile_no=data.get('mobile_no'),
            address=data.get('address'),
            photo=data['photo']
        )

        # ✅ Face encoding
        encoding, error = get_face_encoding(attendant.photo.path)

        if error:
            attendant.delete()
            new_user.delete()
            return Response({"error": error}, status=400)

        attendant.face_encoding = pickle.dumps(encoding)
        attendant.save()

        return Response({
            "message": "Attendant registered successfully",
            "data": {
                "id": attendant.id,
                "username": new_user.username,
                "attendant_name": attendant.attendant_name,
                "role": attendant.role,
                "creche_id": creche.id,
                "photo_url": request.build_absolute_uri(attendant.photo.url) if attendant.photo else None
 
            }
            
        }, status=status.HTTP_201_CREATED)