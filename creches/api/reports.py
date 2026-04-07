from datetime import datetime

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from creches.models import Creche, Child, ChildAttendanceDetail , FoodMonitoring , AttendantAttendance , CrecheAttendant

class ChildAttendanceReportAPI(APIView):
   

    def post(self, request):
        tea_garden_id = request.data.get('tea_garden_id')
        creche_id = request.data.get('creche_id')
        start_date = request.data.get('start_date')
        end_date = request.data.get('end_date')

        # -----------------------------
        # VALIDATION (ALL REQUIRED)
        # -----------------------------
        if not all([tea_garden_id, creche_id, start_date, end_date]):
            return Response(
                {"error": "tea_garden_id, creche_id, start_date, end_date are required"},
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

        # -----------------------------
        # REPORT BUILD
        # -----------------------------
        children_data = []
        total_present = 0
        total_absent = 0

        for child in creche.children.all():

            attendance_qs = ChildAttendanceDetail.objects.filter(
                child=child,
                child_attendance__creche=creche,
                child_attendance__attendance_date__range=[start_date, end_date]
            ).select_related('child_attendance')

            attendance_list = []

            for detail in attendance_qs.order_by('child_attendance__attendance_date'):
                attendance_list.append({
                    'attendance_date': detail.child_attendance.attendance_date,
                    'status': detail.attendance_status
                })

                if detail.attendance_status == 'PRESENT':
                    total_present += 1
                else:
                    total_absent += 1

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

        total_records = total_present + total_absent

        attendance_percentage = (
            (total_present / total_records) * 100
            if total_records > 0 else 0
        )

        # -----------------------------
        # FINAL RESPONSE
        # -----------------------------
        return Response({
            "tea_garden_id": tea_garden_id,
            "creche_id": creche.id,
            "creche_name": creche.creche_name,

            "summary": {
                "total_records": total_records,
                "total_present": total_present,
                "total_absent": total_absent,
                "attendance_percentage": round(attendance_percentage, 2)
            },

            "children": children_data

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

        # -----------------------------
        # VALIDATION
        # -----------------------------
        if not all([tea_garden_id, creche_id, start_date, end_date]):
            return Response(
                {"error": "tea_garden_id, creche_id, start_date, end_date are required"},
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
        food_qs = FoodMonitoring.objects.filter(
            creche=creche,
            monitoring_date__range=[start_date, end_date]
        ).order_by('monitoring_date')

        total_meals = food_qs.count()

        total_calories = 0
        total_protein = 0
        total_carbs = 0
        total_fiber = 0

        food_records = []
        chart_data = []

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
                "monitoring_date": fm.monitoring_date,
                "meal_type": fm.meal_type,
                "food_description": fm.food_description,
                "estimated_calories": calories,
                "estimated_protein_g": protein,
                "estimated_carbs_g": carbs,
                "estimated_fibre_g": fiber,
            })

            # Chart data
            chart_data.append({
                "date": str(fm.monitoring_date),
                "calories": calories,
                "protein": protein,
                "carbs": carbs,
                "fiber": fiber
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
            "creche_id": creche.id,
            "creche_name": creche.creche_name,
            "tea_garden": creche.tea_garden.tea_garden_name,

            "total_meals_logged": total_meals,

            "average_calories": round(avg_calories, 2),
            "average_protein_g": round(avg_protein, 2),
            "average_carbs_g": round(avg_carbs, 2),
            "average_fibre_g": round(avg_fiber, 2),

            "nutrition_grade": nutrition_grade,
            "insights": insights,

            "chart_data": chart_data,
            "food_records": food_records

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