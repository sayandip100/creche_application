from datetime import datetime
from django.db import models
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
import requests

from healthcenter.models import (
    HealthCenter, Nurse, NurseAttendance, PatientTreatment, DoctorAttendance,
    HealthCenterMedicineStock, Doctor, Medicine, MedicineStockTransaction,
    PatientTreatmentMedicine, WeeklyMedicineRequisition, WeeklyMedicineRequisitionDetail
)
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from creches.models import Creche, Child, ChildAttendanceDetail, FoodMonitoring, AttendantAttendance, CrecheAttendant, TeaGarden

class ChildAttendanceReportAPI(APIView):
   

    def post(self, request):
        tea_garden_id = request.data.get('tea_garden_id')
        creche_id = request.data.get('creche_id')
        start_date = request.data.get('start_date')
        end_date = request.data.get('end_date')
        
        # Report format: 'datewise' or 'childwise' (default: datewise)
        report_format = request.data.get('report_format', 'datewise')
        
        # -----------------------------
        # VALIDATION (ALL REQUIRED)
        # -----------------------------
        if not all([tea_garden_id, creche_id, start_date, end_date]):
            return Response(
                {"error": "tea_garden_id, creche_id, start_date, end_date are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
            end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            return Response(
                {"error": "Invalid date format. Use YYYY-MM-DD"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # -----------------------------
        # GET CRECHE (STRICT MATCH)
        # -----------------------------
        try:
            creche = Creche.objects.select_related('tea_garden').get(
                id=creche_id,
                tea_garden_id=tea_garden_id
            )
        except Creche.DoesNotExist:
            return Response(
                {"error": "Invalid tea garden or creche"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Get all children in creche
        all_children = creche.children.all()
        
        # Fetch all attendance records for date range
        attendance_qs = ChildAttendanceDetail.objects.filter(
            child__in=all_children,
            child_attendance__creche=creche,
            child_attendance__attendance_date__range=[start_date_obj, end_date_obj]
        ).select_related('child', 'child_attendance')

        # Calculate totals
        total_records = attendance_qs.count()
        total_present = attendance_qs.filter(attendance_status='PRESENT').count()
        total_absent = total_records - total_present

        attendance_percentage = (
            (total_present / total_records) * 100
            if total_records > 0 else 0
        )

        # ============================================
        # DATEWISE REPORT FORMAT
        # ============================================
        if report_format == 'datewise':
            # Group by date
            date_dict = {}
            
            for detail in attendance_qs.order_by('child_attendance__attendance_date', 'child__name'):
                att_date = detail.child_attendance.attendance_date
                
                if att_date not in date_dict:
                    date_dict[att_date] = {
                        'date': str(att_date),
                        'day': att_date.strftime('%A'),
                        'present_children': [],
                        'absent_children': [],
                        'total_present': 0,
                        'total_absent': 0,
                        'total_strength': 0
                    }
                
                child_data = {
                    'child_id': detail.child.id,
                    'name': detail.child.name,
                    'age_years': detail.child.age_years,
                    'gender': detail.child.gender,
                    'roll_number': getattr(detail.child, 'roll_number', None)
                }
                
                if detail.attendance_status == 'PRESENT':
                    date_dict[att_date]['present_children'].append(child_data)
                    date_dict[att_date]['total_present'] += 1
                else:
                    date_dict[att_date]['absent_children'].append(child_data)
                    date_dict[att_date]['total_absent'] += 1
                
                date_dict[att_date]['total_strength'] = (
                    date_dict[att_date]['total_present'] + date_dict[att_date]['total_absent']
                )
            
            # Convert to sorted list
            datewise_data = []
            for date_key in sorted(date_dict.keys()):
                date_entry = date_dict[date_key]
                # Calculate attendance percentage for the day
                day_total = date_entry['total_strength']
                day_percentage = (
                    (date_entry['total_present'] / day_total) * 100
                    if day_total > 0 else 0
                )
                date_entry['attendance_percentage'] = round(day_percentage, 2)
                datewise_data.append(date_entry)
            
            return Response({
                "status_code": 200,
                "message": "success",
                "data": {
                    "tea_garden_id": tea_garden_id,
                    "creche_id": creche.id,
                    "creche_name": creche.creche_name,
                    "report_format": "datewise",
                    "period": {
                        "start_date": start_date,
                        "end_date": end_date,
                        "total_days": len(datewise_data)
                    },
                    "summary": {
                        "total_records": total_records,
                        "total_present": total_present,
                        "total_absent": total_absent,
                        "attendance_percentage": round(attendance_percentage, 2)
                    },
                    "attendance_by_date": datewise_data
                }
            }, status=status.HTTP_200_OK)
        
        # ============================================
        # CHILDWISE REPORT FORMAT (Original)
        # ============================================
        else:
            children_data = []

            for child in all_children:
                attendance_qs_child = ChildAttendanceDetail.objects.filter(
                    child=child,
                    child_attendance__creche=creche,
                    child_attendance__attendance_date__range=[start_date_obj, end_date_obj]
                ).select_related('child_attendance')

                attendance_list = []

                for detail in attendance_qs_child.order_by('child_attendance__attendance_date'):
                    attendance_list.append({
                        'attendance_date': str(detail.child_attendance.attendance_date),
                        'day': detail.child_attendance.attendance_date.strftime('%A'),
                        'status': detail.attendance_status
                    })

                children_data.append({
                    'child_id': child.id,
                    'name': child.name,
                    'age_years': child.age_years,
                    'gender': child.gender,
                    'attendance_records': attendance_list,
                    'total_days': len(attendance_list),
                    'present_days': sum(1 for a in attendance_list if a['status'] == 'PRESENT'),
                    'absent_days': sum(1 for a in attendance_list if a['status'] == 'ABSENT'),
                })

            return Response({
                "status_code": 200,
                "message": "success",
                "data": {
                    "tea_garden_id": tea_garden_id,
                    "creche_id": creche.id,
                    "creche_name": creche.creche_name,
                    "report_format": "childwise",
                    "period": {
                        "start_date": start_date,
                        "end_date": end_date,
                        "total_days": len(set(
                            att.child_attendance.attendance_date 
                            for att in attendance_qs
                        ))
                    },
                    "summary": {
                        "total_records": total_records,
                        "total_present": total_present,
                        "total_absent": total_absent,
                        "attendance_percentage": round(attendance_percentage, 2)
                    },
                    "children": children_data
                }
            }, status=status.HTTP_200_OK)    
    
class FoodMonitoringReportAPI(APIView):
    
    # -----------------------------
    # NUTRITION GRADING
    # -----------------------------
    def get_nutrition_grade(self, avg_calories, avg_protein):
        if avg_calories >= 400 and avg_protein >= 10:
            return "GOOD"
        elif avg_calories >= 300 and avg_protein >= 5:
            return "POOR"
        else:
            return "CRITICAL"

    # -----------------------------
    # INSIGHTS (AI-LIKE)
    # -----------------------------
    def generate_insights(self, avg_calories, avg_protein, avg_fiber):
        insights = []

        if avg_calories < 300:
            insights.append("Calories are too low")

        if avg_protein < 5:
            insights.append("Protein intake is insufficient")

        if avg_fiber < 3:
            insights.append("Fiber intake is low")

        if avg_calories >= 400 and avg_protein >= 10:
            insights.append("Meals are nutritionally adequate")

        return insights

    # -----------------------------
    # MAIN API
    # -----------------------------
    def post(self, request):

        # REQUIRED INPUT
        tea_garden_id = request.data.get('tea_garden_id')
        creche_id = request.data.get('creche_id')
        start_date = request.data.get('start_date')
        end_date = request.data.get('end_date')
        entered_by_id = request.data.get('entered_by_id')

        # -----------------------------
        # VALIDATION
        # -----------------------------
        if not all([tea_garden_id, creche_id, start_date, end_date, entered_by_id]):
            return Response(
                {"error": "tea_garden_id, creche_id, start_date, end_date, entered_by_id are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            return Response(
                {"error": "Invalid date format. Use YYYY-MM-DD"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # -----------------------------
        # GET CRECHE
        # -----------------------------
        try:
            creche = Creche.objects.select_related('tea_garden').get(
                id=creche_id,
                tea_garden_id=tea_garden_id
            )
        except Creche.DoesNotExist:
            return Response(
                {"error": "Invalid creche or tea garden"},
                status=status.HTTP_404_NOT_FOUND
            )

        # -----------------------------
        # FETCH FOOD DATA
        # -----------------------------
        filters = {
            'creche': creche,
            'monitoring_date__range': [start_date, end_date]
        }

        # Optional filter by entered_by (CrecheAttendant ID or user ID)
        if entered_by_id:
            try:
                # Try as CrecheAttendant ID first
                entered_by = CrecheAttendant.objects.get(id=entered_by_id)
                filters['entered_by'] = entered_by
            except CrecheAttendant.DoesNotExist:
                # Try as user ID
                from django.contrib.auth import get_user_model
                User = get_user_model()
                try:
                    user = User.objects.get(id=entered_by_id)
                    attendant = CrecheAttendant.objects.filter(
                        user=user, creche=creche
                    ).first()
                    if attendant:
                        filters['entered_by'] = attendant
                except User.DoesNotExist:
                    pass

        food_qs = FoodMonitoring.objects.filter(**filters).order_by('monitoring_date')

        total_meals = food_qs.count()

        # -----------------------------
        # NO DATA CHECK
        # -----------------------------
        if total_meals == 0:
            return Response({
                "status_code": 200,
                "message": "No food monitoring data found for this period",
                "data": {
                    "creche": {
                        "id": creche.id,
                        "name": creche.creche_name,
                        "tea_garden": creche.tea_garden.tea_garden_name
                    },
                    "period": {
                        "start_date": str(start_date),
                        "end_date": str(end_date),
                        "total_meals": 0
                    },
                    "nutrition": None,
                    "records": []
                }
            }, status=status.HTTP_200_OK)

        total_calories = 0
        total_protein = 0
        total_carbs = 0
        total_fiber = 0

        food_records = []

        # -----------------------------
        # LOOP DATA
        # -----------------------------
        for fm in food_qs:

            calories = float(fm.estimated_calories or 0)
            protein = float(fm.estimated_protein_g or 0)
            carbs = float(fm.estimated_carbs_g or 0)
            fiber = float(fm.estimated_fibre_g or 0)

            # Raw records
            food_records.append({
                "monitoring_date": str(fm.monitoring_date),
                "meal_type": fm.meal_type,
                "food_description": fm.food_description,
                "calories": calories,
                "protein_g": protein,
                "carbs_g": carbs,
                "fibre_g": fiber,
            })

            # Totals
            total_calories += calories
            total_protein += protein
            total_carbs += carbs
            total_fiber += fiber

        # -----------------------------
        # AVERAGES
        # -----------------------------
        avg_calories = (total_calories / total_meals) if total_meals else 0
        avg_protein = (total_protein / total_meals) if total_meals else 0
        avg_carbs = (total_carbs / total_meals) if total_meals else 0
        avg_fiber = (total_fiber / total_meals) if total_meals else 0

        # -----------------------------
        # GRADING + INSIGHTS
        # -----------------------------
        nutrition_grade = self.get_nutrition_grade(avg_calories, avg_protein)
        insights = self.generate_insights(avg_calories, avg_protein, avg_fiber)

        # -----------------------------
        # RESPONSE
        # -----------------------------
        return Response({
            "status_code": 200,
            "message": "success",
            "data": {
                "creche": {
                    "id": creche.id,
                    "name": creche.creche_name,
                    "tea_garden": creche.tea_garden.tea_garden_name
                },
                "period": {
                    "start_date": str(start_date),
                    "end_date": str(end_date),
                    "total_meals": total_meals
                },
                "nutrition": {
                    "grade": nutrition_grade,
                    "average": {
                        "calories": round(avg_calories, 2),
                        "protein_g": round(avg_protein, 2),
                        "carbs_g": round(avg_carbs, 2),
                        "fibre_g": round(avg_fiber, 2)
                    },
                    "insights": insights
                },
                "records": food_records
            }
        }, status=status.HTTP_200_OK)
    
class AttendantAttendanceReportAPI(APIView):
    
    def post(self, request):
       
        tea_garden_id = request.data.get('tea_garden_id')
        creche_id = request.data.get('creche_id')
        start_date = request.data.get('start_date')
        end_date = request.data.get('end_date')

        # -----------------------------
        # VALIDATION
        # -----------------------------
        if not all([tea_garden_id, creche_id, start_date, end_date]):
            return Response(
                {"error": "tea_garden_id, creche_id, start_date, end_date are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Convert date
        try:
            start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            return Response(
                {"error": "Invalid date format. Use YYYY-MM-DD"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Total days
        total_days = (end_date - start_date).days + 1

        # -----------------------------
        # GET CRECHE
        # -----------------------------
        try:
            creche = Creche.objects.select_related('tea_garden').get(
                id=creche_id,
                tea_garden_id=tea_garden_id
            )
        except Creche.DoesNotExist:
            return Response({"error": "Invalid creche or tea garden"}, status=404)

        # -----------------------------
        # ATTENDANTS
        # -----------------------------
        attendants = CrecheAttendant.objects.filter(creche=creche)
        total_attendants = attendants.count()

        report_data = []

        for att in attendants:
            attendance_qs = AttendantAttendance.objects.filter(
                attendant=att,
                attendance_date__range=[start_date, end_date]
            )

            present_days = attendance_qs.count()
           
            attendance_percentage = (
                (present_days / total_days) * 100
                if total_days > 0 else 0
            )

            report_data.append({
                "attendant_id": att.id,
                "name": att.user.username,
                "role": att.role,
                "present_days": present_days,

                "absent_days": total_days - present_days,
                 "total_days": total_days,
                "attendance_percentage": round(attendance_percentage, 2)
            })

        return Response({
            "creche_id": creche.id,
            "creche_name": creche.creche_name,
            "tea_garden": creche.tea_garden.tea_garden_name,

            "total_attendants": total_attendants,
            
            "total_days": total_days,

            "attendants": report_data
        }, status=status.HTTP_200_OK)
        
        
class Teagardenlist(APIView):
    
    #permission_classes = [AllowAny]
    def get(self, request):
        tea_gardens = TeaGarden.objects.all()
        data = []
        for tg in tea_gardens:
            data.append({
                "id": tg.id,
                "tea_garden_code": tg.tea_garden_code,
                "tea_garden_name": tg.tea_garden_name
            })
        return Response({
            "status_code": 200,
            "message": "success",
            "data": data
        }, status=status.HTTP_200_OK)
    
class Creachelist(APIView):
     def post(self, request):
         
        tea_garden_id = request.data.get('tea_garden_id') 
        
        if not all([tea_garden_id]):
            return Response(
                {"error": "tea_garden_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        creches = Creche.objects.filter(tea_garden_id=tea_garden_id)
        data = []
        for c in creches:
            data.append({
                "id": c.id,
                "creche_code": c.creche_code,
                "creche_name": c.creche_name
            })
        return Response(data, status=status.HTTP_200_OK)
    
class CrecheDetailsAPI(APIView):
    def post(self, request):
        tea_garden_id = request.data.get('tea_garden_id')
        creche_id = request.data.get('creche_id')

        if not tea_garden_id or not creche_id:
            return Response({
                'error': 'Both teagarden_id and creche_id are required'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            tea_garden = TeaGarden.objects.get(id=tea_garden_id)
        except TeaGarden.DoesNotExist:
            return Response({
                'error': 'Tea garden not found'
            }, status=status.HTTP_404_NOT_FOUND)

        try:
            creche = Creche.objects.select_related('tea_garden').get(
                id=creche_id,
                tea_garden=tea_garden
            )
        except Creche.DoesNotExist:
            return Response({
                'error': 'Creche not found or does not belong to the specified tea garden'
            }, status=status.HTTP_404_NOT_FOUND)

        attendants = CrecheAttendant.objects.filter(creche=creche).select_related('user')
        attendant_data = []
        for attendant in attendants:
            attendant_data.append({
                'id': attendant.id,
                'username': attendant.user.username,
                'role': attendant.role,
                'name': attendant.attendant_name,
                'mobile_no': attendant.mobile_no,
                'address': attendant.address,
                'photo_url': request.build_absolute_uri(attendant.photo.url) if attendant.photo else None,
                'is_active': attendant.is_active
            })

        children = Child.objects.filter(creche=creche).prefetch_related('photos')
        child_data = []
        for child in children:
            child_data.append({
                'id': child.id,
                'name': child.name,
                'age_years': child.age_years,
                'gender': child.gender,
                'guardian_name': child.guardian_name,
                'contact_person_name': child.contact_person_name,
                'contact_phone': child.contact_phone,
                'address': child.address,
                'photo_url': request.build_absolute_uri(child.photo.url) if child.photo else None,
                'gallery_urls': [request.build_absolute_uri(photo.photo.url) for photo in child.photos.all()],
                'is_active': child.is_active,
                'enrollment_date': child.enrollment_date
            })

        attendance_qs = ChildAttendanceDetail.objects.filter(
            child_attendance__creche=creche
        ).select_related('child_attendance')

        total_present = attendance_qs.filter(attendance_status='PRESENT').count()
        total_absent = attendance_qs.filter(attendance_status='ABSENT').count()
        last_attendance = attendance_qs.order_by('-child_attendance__attendance_date').first()

        food_monitoring_count = FoodMonitoring.objects.filter(creche=creche).count()
        last_food_monitor = FoodMonitoring.objects.filter(creche=creche).order_by('-monitoring_date').first()

        return Response({
            'tea_garden_id': tea_garden.id,
            'tea_garden_name': tea_garden.tea_garden_name,
            'creche_id': creche.id,
            'creche_name': creche.creche_name,
            'location_name': creche.location_name,
            'latitude': creche.latitude,
            'longitude': creche.longitude,
            'geo_radius_meters': creche.geo_radius_meters,
            'is_active': creche.is_active,
            'attendants_count': attendants.count(),
            'attendants': attendant_data,
            'children_count': children.count(),
            'children': child_data,
            'attendance_summary': {
                'total_present': total_present,
                'total_absent': total_absent,
                'total_records': total_present + total_absent,
                'latest_attendance_date': last_attendance.child_attendance.attendance_date if last_attendance else None,
                'latest_attendance_status': last_attendance.attendance_status if last_attendance else None
            },
            'food_monitoring': {
                'total_records': food_monitoring_count,
                'latest_monitoring_date': last_food_monitor.monitoring_date if last_food_monitor else None
            }
        }, status=status.HTTP_200_OK)
    
class Healthcenterlist(APIView):
     def post(self, request):
         
        tea_garden_id = request.data.get('tea_garden_id') 
        
        if not all([tea_garden_id]):
            return Response(
                {"error": "tea_garden_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        health_centers = HealthCenter.objects.filter(tea_garden_id=tea_garden_id)
        data = []
        for hc in health_centers:
            data.append({
                
                "id": hc.id,
                "code": hc.code,
                "name": hc.name
            })
        return Response({
            "status_code": 200,
            "message": "success",
            "data": data
        }, status=status.HTTP_200_OK)    
        #return Response(data, status=status.HTTP_200_OK)    
    
    
class CrecheChildDetailsAPI(APIView):
    def post(self, request):
        creche_id = request.data.get('creche_id')
        child_id = request.data.get('child_id')

        if not creche_id or not child_id:
            return Response({
                "error": "Both creche_id and child_id are required"
            }, status=400)

        try:
            creche = Creche.objects.get(id=creche_id)
        except Creche.DoesNotExist:
            return Response({
                "error": "Creche not found"
            }, status=404)

        try:
            child = Child.objects.get(id=child_id, creche=creche)
        except Child.DoesNotExist:
            return Response({
                "error": "Child not found for the given creche"
            }, status=404)

        photo_url = request.build_absolute_uri(child.photo.url) if child.photo else None
        gallery_urls = [request.build_absolute_uri(photo.photo.url) for photo in child.photos.all()]

        attendance_qs = ChildAttendanceDetail.objects.filter(
            child=child,
            child_attendance__creche=creche
        ).select_related('child_attendance')

        total_present = attendance_qs.filter(attendance_status='PRESENT').count()
        total_absent = attendance_qs.filter(attendance_status='ABSENT').count()
        latest_attendance = attendance_qs.order_by('-child_attendance__attendance_date').first()

        child_detail = {
            'id': child.id,
            'name': child.name,
            'age_years': child.age_years,
            'gender': child.gender,
            'height_cm': child.height_cm,
            'weight_kg': child.weight_kg,
            'guardian_name': child.guardian_name,
            'contact_person_name': child.contact_person_name,
            'contact_phone': child.contact_phone,
            'address': child.address,
            'photo_url': photo_url,
            'gallery_urls': gallery_urls,
            'is_active': child.is_active,
            'enrollment_date': child.enrollment_date,
            'created_by': child.created_by.username if child.created_by else None,
            'created_at': child.created_at,
            'updated_at': child.updated_at,
            'attendance_summary': {
                'total_present': total_present,
                'total_absent': total_absent,
                'total_records': total_present + total_absent,
                'latest_attendance_date': latest_attendance.child_attendance.attendance_date if latest_attendance else None,
                'latest_attendance_status': latest_attendance.attendance_status if latest_attendance else None
            }
        }

        return Response({
            'creche_id': creche.id,
            'creche_name': creche.creche_name,
            'tea_garden_id': creche.tea_garden.id,
            'tea_garden_name': creche.tea_garden.tea_garden_name,
            'child': child_detail
        }, status=200)


class AttendantDetailsAPI(APIView):
    def post(self, request):
        creche_id = request.data.get('creche_id')
        attendant_id = request.data.get('attendant_id')

        if not creche_id or not attendant_id:
            return Response({
                'error': 'Both creche_id and attendant_id are required'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            creche = Creche.objects.get(id=creche_id)
        except Creche.DoesNotExist:
            return Response({
                'error': 'Creche not found'
            }, status=status.HTTP_404_NOT_FOUND)

        try:
            attendant = CrecheAttendant.objects.select_related('user', 'creche__tea_garden').get(
                id=attendant_id,
                creche=creche
            )
        except CrecheAttendant.DoesNotExist:
            return Response({
                'error': 'Attendant not found for the given creche'
            }, status=status.HTTP_404_NOT_FOUND)

        photo_url = request.build_absolute_uri(attendant.photo.url) if attendant.photo else None

        attendance_qs = AttendantAttendance.objects.filter(
            attendant=attendant,
            creche=creche
        ).order_by('-attendance_date')

        total_attendance = attendance_qs.count()
        latest_attendance = attendance_qs.first()

        attendance_records = []
        for att in attendance_qs[:30]:
            attendance_records.append({
                'id': att.id,
                'attendance_date': att.attendance_date,
                'check_in_time': att.check_in_time,
                'latitude': att.latitude,
                'longitude': att.longitude,
                'geo_verified': att.geo_verified,
                'remarks': att.remarks
            })

        return Response({
            'creche_id': creche.id,
            'creche_name': creche.creche_name,
            'tea_garden_id': creche.tea_garden.id,
            'tea_garden_name': creche.tea_garden.tea_garden_name,
            'attendant': {
                'id': attendant.id,
                'username': attendant.user.username,
                'role': attendant.role,
                'attendant_name': attendant.attendant_name,
                'mobile_no': attendant.mobile_no,
                'address': attendant.address,
                'photo_url': photo_url,
                'is_active': attendant.is_active,
                'created_at': attendant.created_at,
                'updated_at': attendant.updated_at
            },
            'attendance_summary': {
                'total_attendance_days': total_attendance,
                'latest_attendance_date': latest_attendance.attendance_date if latest_attendance else None,
                'latest_check_in_time': latest_attendance.check_in_time if latest_attendance else None,
                'latest_remarks': latest_attendance.remarks if latest_attendance else None
            },
            'attendance_records': attendance_records
        }, status=status.HTTP_200_OK)


class HealthCenterDetailsAPI(APIView):
    
    def post(self, request):
        teagarden_id = request.data.get('teagarden_id')
        healthcenter_id = request.data.get('healthcenter_id')

        if not teagarden_id or not healthcenter_id:
            return Response({
                "error": "Both teagarden_id and healthcenter_id are required"
            }, status=400)

        try:
            # Validate tea garden existsh
            tea_garden = TeaGarden.objects.get(id=teagarden_id)
        except TeaGarden.DoesNotExist:
            return Response({
                "error": "Tea garden not found"
            }, status=404)

        try:
            # Validate health center exists and belongs to the tea garden
            health_center = HealthCenter.objects.get(
                id=healthcenter_id,
                tea_garden=tea_garden
            )
        except HealthCenter.DoesNotExist:
            return Response({
                "error": "Health center not found or does not belong to the specified tea garden"
            }, status=404)

        # Get doctors
        doctors = Doctor.objects.filter(health_center=health_center).select_related('user')
        doctors_data = []
        for doctor in doctors:
            doctors_data.append({
                'id': doctor.id,
                'username': doctor.user.username,
                'name': doctor.name,
                'specialization': doctor.specialization,
                'qualification': doctor.qualification,
                'mobile_no': doctor.mobile_no,
                'photo_url': request.build_absolute_uri(doctor.photo.url) if doctor.photo else None,
                'is_active': doctor.is_active
            })

        # Get nurses (including head nurses)
        nurses = Nurse.objects.filter(health_center=health_center).select_related('user')
        nurses_data = []
        head_nurses_data = []

        for nurse in nurses:
            nurse_info = {
                'id': nurse.id,
                'username': nurse.user.username,
                'nurse_name': nurse.nurse_name,
                'role': nurse.role,
                'qualification': nurse.qualification,
                'mobile_no': nurse.mobile_no,
                'photo_url': request.build_absolute_uri(nurse.photo.url) if nurse.photo else None,
                'is_active': nurse.is_active
            }

            if nurse.role == 'head_nurse':
                head_nurses_data.append(nurse_info)
            else:
                nurses_data.append(nurse_info)

        # Get patients (recent treatments)
        patients = PatientTreatment.objects.filter(
            health_center=health_center
        ).order_by('-treatment_date')[:50]  # Last 50 patients

        patients_data = []
        for patient in patients:
            patients_data.append({
                'id': patient.id,
                'patient_name': patient.patient_name,
                'age': patient.age,
                'contact_number': patient.contact_number,
                'treatment_date': patient.treatment_date,
                'whatsapp_sent': patient.whatsapp_sent,
                'remarks': patient.remarks
            })

        # Get medicine stock
        medicine_stocks = HealthCenterMedicineStock.objects.filter(
            health_center=health_center
        ).select_related('medicine')

        medicine_stock_data = []
        for stock in medicine_stocks:
            medicine_stock_data.append({
                'id': stock.id,
                'medicine_name': stock.medicine.medicine_name,
                'medicine_code': stock.medicine.medicine_code,
                'current_stock_qty': stock.current_stock_qty,
                'last_updated_at': stock.last_updated_at
            })

        # Get recent doctor attendance (last 30 days)
        from django.utils import timezone
        from datetime import timedelta

        thirty_days_ago = timezone.now().date() - timedelta(days=30)
        doctor_attendances = DoctorAttendance.objects.filter(
            health_center=health_center,
            attendance_date__gte=thirty_days_ago
        ).select_related('doctor__user').order_by('-attendance_date')[:20]

        doctor_attendance_data = []
        for attendance in doctor_attendances:
            doctor_attendance_data.append({
                'id': attendance.id,
                'doctor_id': attendance.doctor.id,
                'doctor_name': attendance.doctor.name or attendance.doctor.user.username,
                'attendance_date': attendance.attendance_date,
                'check_in_time': attendance.check_in_time,
                'exit_time': attendance.exit_time,
                'patients_visited_today': attendance.patients_visited_today,
                'nurse_present': attendance.nurse_present,
                'hygiene_maintained': attendance.hygiene_maintained,
                'remarks': attendance.remarks
            })

        # Get recent nurse attendance (last 30 days)
        nurse_attendances = NurseAttendance.objects.filter(
            health_center=health_center,
            attendance_date__gte=thirty_days_ago
        ).select_related('nurse__user').order_by('-attendance_date')[:20]

        nurse_attendance_data = []
        for attendance in nurse_attendances:
            nurse_attendance_data.append({
                'id': attendance.id,
                'nurse_id': attendance.nurse.id,
                'nurse_name': attendance.nurse.nurse_name or attendance.nurse.user.username,
                'role': attendance.nurse.role,
                'attendance_date': attendance.attendance_date,
                'check_in_time': attendance.check_in_time,
                'remarks': attendance.remarks
            })

        return Response({
            'health_center': {
                'id': health_center.id,
                'code': health_center.code,
                'name': health_center.name,
                'location_name': health_center.location_name,
                'latitude': health_center.latitude,
                'longitude': health_center.longitude,
                'geo_radius_meters': health_center.geo_radius_meters,
                'is_active': health_center.is_active,
                'tea_garden_name': tea_garden.tea_garden_name
            },
            'doctors': {
                'count': len(doctors_data),
                'list': doctors_data
            },
            'nurses': {
                'count': len(nurses_data),
                'list': nurses_data
            },
            'head_nurses': {
                'count': len(head_nurses_data),
                'list': head_nurses_data
            },
            'patients': {
                'count': len(patients_data),
                'recent_list': patients_data
            },
            'medicine_stock': {
                'count': len(medicine_stock_data),
                'list': medicine_stock_data
            },
            'doctor_attendance': {
                'count': len(doctor_attendance_data),
                'recent_list': doctor_attendance_data
            },
            'nurse_attendance': {
                'count': len(nurse_attendance_data),
                'recent_list': nurse_attendance_data
            },
            'medicine_reports': {
                'low_stock_alerts': self._get_low_stock_alerts(health_center),
                'medicine_usage': self._get_medicine_usage_report(health_center),
                'medicine_transactions': self._get_medicine_transactions(health_center),
                'medicine_requisitions': self._get_medicine_requisitions(health_center),
                'medicine_statistics': self._get_medicine_statistics(health_center)
            }
        }, status=200)

    def _get_low_stock_alerts(self, health_center):
        """Get medicines that are below minimum stock level"""
        low_stock_medicines = HealthCenterMedicineStock.objects.filter(
            health_center=health_center,
            current_stock_qty__lte=models.F('medicine__min_stock_level')
        ).select_related('medicine')

        alerts = []
        for stock in low_stock_medicines:
            alerts.append({
                'medicine_id': stock.medicine.id,
                'medicine_name': stock.medicine.medicine_name,
                'medicine_code': stock.medicine.medicine_code,
                'current_stock': stock.current_stock_qty,
                'minimum_level': stock.medicine.min_stock_level,
                'shortage': stock.medicine.min_stock_level - stock.current_stock_qty,
                'last_updated': stock.last_updated_at
            })

        return {
            'count': len(alerts),
            'alerts': alerts
        }

    def _get_medicine_usage_report(self, health_center):
        """Get medicine usage from patient treatments (last 30 days)"""
        from django.utils import timezone
        from datetime import timedelta

        thirty_days_ago = timezone.now().date() - timedelta(days=30)

        # Get medicine usage from treatments
        usage_data = PatientTreatmentMedicine.objects.filter(
            treatment__health_center=health_center,
            treatment__treatment_date__gte=thirty_days_ago
        ).select_related('medicine', 'treatment').order_by('-treatment__treatment_date')[:50]

        usage_report = []
        for usage in usage_data:
            usage_report.append({
                'id': usage.id,
                'medicine_name': usage.medicine.medicine_name,
                'medicine_code': usage.medicine.medicine_code,
                'patient_name': usage.treatment.patient_name,
                'treatment_date': usage.treatment.treatment_date,
                'prescribed_qty': usage.prescribed_qty,
                'issued_qty': usage.issued_qty,
                'notes': usage.notes
            })

        return {
            'count': len(usage_report),
            'recent_usage': usage_report
        }

    def _get_medicine_transactions(self, health_center):
        """Get recent medicine stock transactions (last 30 days)"""
        from django.utils import timezone
        from datetime import timedelta

        thirty_days_ago = timezone.now() - timedelta(days=30)

        transactions = MedicineStockTransaction.objects.filter(
            health_center=health_center,
            transaction_at__gte=thirty_days_ago
        ).select_related('medicine').order_by('-transaction_at')[:30]

        transaction_data = []
        for transaction in transactions:
            transaction_data.append({
                'id': transaction.id,
                'medicine_name': transaction.medicine.medicine_name,
                'medicine_code': transaction.medicine.medicine_code,
                'transaction_type': transaction.transaction_type,
                'quantity': transaction.quantity,
                'reference_type': transaction.reference_type,
                'reference_id': transaction.reference_id,
                'transaction_at': transaction.transaction_at,
                'remarks': transaction.remarks
            })

        return {
            'count': len(transaction_data),
            'recent_transactions': transaction_data
        }

    def _get_medicine_requisitions(self, health_center):
        """Get medicine requisitions for the health center"""
        requisitions = WeeklyMedicineRequisition.objects.filter(
            health_center=health_center
        ).select_related('nurse__user').order_by('-created_at')[:10]

        requisition_data = []
        for req in requisitions:
            details = WeeklyMedicineRequisitionDetail.objects.filter(
                requisition=req
            ).select_related('medicine')

            detail_data = []
            for detail in details:
                detail_data.append({
                    'medicine_name': detail.medicine.medicine_name,
                    'medicine_code': detail.medicine.medicine_code,
                    'available_stock_qty': detail.available_stock_qty,
                    'requested_qty': detail.requested_qty,
                    'auto_low_stock_flag': detail.auto_low_stock_flag,
                    'remarks': detail.remarks
                })

            requisition_data.append({
                'id': req.id,
                'requisition_week_start': req.requisition_week_start,
                'requisition_week_end': req.requisition_week_end,
                'requisition_date': req.requisition_date,
                'status': req.status,
                'nurse_name': req.nurse.nurse_name if req.nurse else None,
                'remarks': req.remarks,
                'medicines_count': len(detail_data),
                'medicines': detail_data
            })

        return {
            'count': len(requisition_data),
            'recent_requisitions': requisition_data
        }

    def _get_medicine_statistics(self, health_center):
        """Get medicine-wise statistics"""
        from django.db.models import Sum, Count
        from django.utils import timezone
        from datetime import timedelta

        thirty_days_ago = timezone.now().date() - timedelta(days=30)

        # Get statistics for each medicine
        stats_data = []
        medicine_stocks = HealthCenterMedicineStock.objects.filter(
            health_center=health_center
        ).select_related('medicine')

        for stock in medicine_stocks:
            # Get usage in last 30 days
            recent_usage = PatientTreatmentMedicine.objects.filter(
                medicine=stock.medicine,
                treatment__health_center=health_center,
                treatment__treatment_date__gte=thirty_days_ago
            ).aggregate(
                total_prescribed=Sum('prescribed_qty'),
                total_issued=Sum('issued_qty'),
                usage_count=Count('id')
            )

            # Get transaction summary
            transactions = MedicineStockTransaction.objects.filter(
                medicine=stock.medicine,
                health_center=health_center
            ).aggregate(
                total_in=Sum('quantity', filter=models.Q(transaction_type='IN')),
                total_out=Sum('quantity', filter=models.Q(transaction_type='OUT')),
                total_adjustment=Sum('quantity', filter=models.Q(transaction_type='ADJUSTMENT'))
            )

            stats_data.append({
                'medicine_id': stock.medicine.id,
                'medicine_name': stock.medicine.medicine_name,
                'medicine_code': stock.medicine.medicine_code,
                'current_stock': stock.current_stock_qty,
                'min_stock_level': stock.medicine.min_stock_level,
                'unit_name': stock.medicine.unit_name,
                'recent_usage': {
                    'total_prescribed': recent_usage['total_prescribed'] or 0,
                    'total_issued': recent_usage['total_issued'] or 0,
                    'usage_count': recent_usage['usage_count'] or 0
                },
                'transaction_summary': {
                    'total_in': transactions['total_in'] or 0,
                    'total_out': transactions['total_out'] or 0,
                    'total_adjustment': transactions['total_adjustment'] or 0
                }
            })

        return {
            'count': len(stats_data),
            'statistics': stats_data
        }
        

class StoreFoodMonitoringAPI(APIView):
    """
    API to store food monitoring data by calling external API and saving to database.
    Required params: food_image, creche_id
    Optional params: meal_type, entered_by_id
    External API: http://45.64.107.97:5011/api/v1/food_monitoring
    """
    
    parser_classes = (MultiPartParser, FormParser)
    
    def post(self, request):
        from datetime import date
        
        # --- Extract request parameters ---
        food_image = (
            request.FILES.get('food_image') or
            request.FILES.get('file') or
            request.FILES.get('image')
        )
        creche_id = request.data.get('creche_id')
        meal_type = request.data.get('meal_type', 'Lunch')
        entered_by_id = request.data.get('entered_by_id')

        # --- Validation ---
        if not food_image:
            return Response({
                "status_code": 400,
                "message": "food_image is required"
            }, status=status.HTTP_200_OK)

        if not creche_id:
            return Response({
                "status_code": 400,
                "message": "creche_id is required"
            }, status=status.HTTP_200_OK)

        # --- Verify creche exists ---
        try:
            creche = Creche.objects.get(id=creche_id)
        except Creche.DoesNotExist:
            return Response({
                "status_code": 404,
                "message": "Creche not found"
            }, status=status.HTTP_200_OK)

        # --- Call external API ---
        try:
            files = {'food_image': (food_image.name, food_image.read(), food_image.content_type)}
            response = requests.post(
                'http://45.64.107.97:5011/api/v1/food_monitoring',
                files=files,
                timeout=60
            )

            if response.status_code != 200:
                return Response({
                    "status_code": response.status_code,
                    "message": "External API error",
                    "external_response": response.text
                }, status=status.HTTP_200_OK)

            ext_data = response.json()

        except requests.exceptions.Timeout:
            return Response({
                "status_code": 408,
                "message": "External API timed out"
            }, status=status.HTTP_200_OK)
        except requests.exceptions.ConnectionError as e:
            return Response({
                "status_code": 503,
                "message": f"Cannot connect to external API: {str(e)}"
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                "status_code": 500,
                "message": f"Error calling external API: {str(e)}"
            }, status=status.HTTP_200_OK)

        # --- Parse external API response ---
        try:
            image_save_path = ext_data.get('image_save_path', '')
            image_url = ext_data.get('image_url', '')
            llm_response = ext_data.get('llm_response', {})
            
            # Extract food items
            food_items = llm_response.get('food_items', [])
            health_score = llm_response.get('health_score', 0)
            dietary_tags = llm_response.get('dietary_tags', [])
            recommendations = llm_response.get('recommendations', '')

            # --- Calculate totals from food items ---
            total_calories = 0
            total_protein = 0
            total_carbs = 0
            total_fiber = 0

            food_description_parts = []

            for item in food_items:
                item_name = item.get('name', '')
                nutrition = item.get('nutrition', {})
                
                food_description_parts.append(f"- {item_name}")
                
                # Handle None values by converting them to 0
                calories = nutrition.get('calories') or 0
                protein = nutrition.get('protein') or 0
                carbs = nutrition.get('carbs') or 0
                fiber = nutrition.get('fiber') or 0
                
                total_calories += calories
                total_protein += protein
                total_carbs += carbs
                total_fiber += fiber

            # Build food description
            food_description = f"Food Items:\n" + "\n".join(food_description_parts)
            # food_description += f"\n\nHealth Score: {health_score}/10"
            # food_description += f"\nDietary Tags: {', '.join(dietary_tags)}"
            # food_description += f"\n\nRecommendations:\n{recommendations}"

            # Get entered_by attendant (try CrecheAttendant ID first, then user_id)
            entered_by = None
            if entered_by_id:
                try:
                    entered_by = CrecheAttendant.objects.get(id=entered_by_id)
                except CrecheAttendant.DoesNotExist:
                    # Try lookup by user_id (in case they passed a user ID instead)
                    from django.contrib.auth import get_user_model
                    User = get_user_model()
                    try:
                        user = User.objects.get(id=entered_by_id)
                        entered_by = CrecheAttendant.objects.filter(
                            user=user, creche=creche
                        ).first()
                    except User.DoesNotExist:
                        pass

            # --- Store in database ---
            food_monitoring = FoodMonitoring.objects.create(
                creche=creche,
                monitoring_date=date.today(),
                meal_type=meal_type,
                food_description=food_description,
                estimated_calories=total_calories,
                estimated_protein_g=total_protein,
                estimated_carbs_g=total_carbs,
                estimated_fibre_g=total_fiber,
                remarks=f"External API Image: {image_save_path}",
                entered_by=entered_by
            )

            # --- Build response ---
            return Response({
                "status_code": 200,
                "message": "Food monitoring data stored successfully",
                "data": {
                    "id": food_monitoring.id,
                    "creche_id": creche.id,
                    "creche_name": creche.creche_name,
                    "monitoring_date": date.today(),
                    "meal_type": meal_type,
                    "food_items_count": len(food_items),
                    "health_score": health_score,
                    "nutrition": {
                        "total_calories": float(total_calories),
                        "total_protein_g": float(total_protein),
                        "total_carbs_g": float(total_carbs),
                        "total_fibre_g": float(total_fiber)
                    },
                    "external_image_url": image_url,
                    "external_image_path": image_save_path,
                    "food_items": food_items,
                    "entered_by_id": entered_by.id if entered_by else None,
                    "entered_by_name": entered_by.attendant_name if entered_by else None
                }
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "status_code": 500,
                "message": f"Error processing response: {str(e)}"
            }, status=status.HTTP_200_OK)
    
    