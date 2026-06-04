from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from creches.models import CrecheAttendant, Creche, TeaGarden
from healthcenter.models import Nurse, HealthCenter


class AttendantListByTeaGardenAPI(APIView):
    """
    API to list attendants/super_attendants filtered by tea_garden and optionally creche.
    Admin only.

    GET /attendants/list/

    Request Parameters:
    - tea_garden_id (required): Tea Garden ID
    - creche_id (optional): Creche ID to filter by specific creche

    Response: {
        "status_code": 200,
        "message": "success",
        "data": [
            {
                "id": 1,
                "username": "john",
                "name": "John Doe",
                "role": "attendant",
                "mobile_no": "1234567890",
                "creche_id": 1,
                "creche_name": "Creche A"
            },
            ...
        ]
    }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Only superadmin or tea_garden_head can access
        if request.user.role not in ['superadmin', 'teagarden_head']:
            return Response({
                'status_code': 403,
                'message': 'Access denied. Only admin users can view attendant list.',
                'data': []
            }, status=status.HTTP_403_FORBIDDEN)

        tea_garden_id = request.data.get('tea_garden_id')
        creche_id = request.data.get('creche_id')

        if not tea_garden_id:
            return Response({
                'status_code': 400,
                'message': 'tea_garden_id is required',
                'data': []
            }, status=status.HTTP_400_BAD_REQUEST)

        # Verify tea garden exists
        try:
            tea_garden = TeaGarden.objects.get(id=tea_garden_id)
        except TeaGarden.DoesNotExist:
            return Response({
                'status_code': 404,
                'message': 'Tea garden not found',
                'data': []
            }, status=status.HTTP_404_NOT_FOUND)

        # Build query for creches in this tea garden
        creche_qs = Creche.objects.filter(tea_garden=tea_garden)
        if creche_id:
            creche_qs = creche_qs.filter(id=creche_id)
            if not creche_qs.exists():
                return Response({
                    'status_code': 404,
                    'message': 'Creche not found in this tea garden',
                    'data': []
                }, status=status.HTTP_404_NOT_FOUND)

        # Get all attendants in these creches
        attendants = CrecheAttendant.objects.filter(
            creche__in=creche_qs,
            is_active=True
        ).select_related('user', 'creche').order_by('creche__creche_name', 'attendant_name')

        data = []
        for att in attendants:
            data.append({
                'id': att.id,
                'user_id': att.user.id,
                'username': att.user.username,
                'name': att.attendant_name,
                'role': att.role,
                'mobile_no': att.mobile_no,
                'address': att.address,
                'creche_id': att.creche.id,
                'creche_name': att.creche.creche_name,
                'tea_garden_id': tea_garden.id,
                'tea_garden_name': tea_garden.tea_garden_name,
                'is_active': att.is_active
            })

        return Response({
            'status_code': 200,
            'message': 'success',
            'data': data
        }, status=status.HTTP_200_OK)


class PromotetoSuperAPI(APIView):
    """
    Unified API to promote an attendant to super_attendant or a nurse to head_nurse.
    Admin only (superadmin or teagarden_head).

    POST /promote-to-super/

    Request Parameters (provide one):
    - attendant_id (optional): ID of the attendant to promote to super_attendant
    - nurse_id (optional): ID of the nurse to promote to head_nurse

    Response examples:
    
    Attendant promoted:
    {
        "status_code": 200,
        "message": "Attendant promoted to Super Attendant successfully",
        "data": {
            "id": 1,
            "user_id": 5,
            "username": "john",
            "name": "John Doe",
            "old_role": "attendant",
            "new_role": "super_attendant",
            "type": "attendant",
            "creche_id": 1,
            "creche_name": "Creche A",
            "tea_garden_id": 285,
            "tea_garden_name": "Garden A"
        }
    }

    Nurse promoted:
    {
        "status_code": 200,
        "message": "Nurse promoted to Head Nurse successfully",
        "data": {
            "id": 1,
            "user_id": 6,
            "username": "jane",
            "name": "Jane Doe",
            "old_role": "nurse",
            "new_role": "head_nurse",
            "type": "nurse",
            "health_center_id": 1,
            "health_center_name": "Health Center A",
            "tea_garden_id": 285,
            "tea_garden_name": "Garden A"
        }
    }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Only superadmin or teagarden_head can promote
        if request.user.role not in ['superadmin', 'teagarden_head']:
            return Response({
                'status_code': 403,
                'message': 'Access denied. Only admin users can promote.',
                'data': {}
            }, status=status.HTTP_403_FORBIDDEN)

        attendant_id = request.data.get('attendant_id')
        nurse_id = request.data.get('nurse_id')

        # Must provide exactly one
        if not attendant_id and not nurse_id:
            return Response({
                'status_code': 400,
                'message': 'Either attendant_id or nurse_id is required',
                'data': {}
            }, status=status.HTTP_400_BAD_REQUEST)

        if attendant_id and nurse_id:
            return Response({
                'status_code': 400,
                'message': 'Provide only one: attendant_id OR nurse_id, not both',
                'data': {}
            }, status=status.HTTP_400_BAD_REQUEST)

        # ============================================
        # PROMOTE ATTENDANT -> SUPER_ATTENDANT
        # ============================================
        if attendant_id:
            try:
                attendant = CrecheAttendant.objects.select_related('user', 'creche__tea_garden').get(
                    id=attendant_id,
                    is_active=True
                )
            except CrecheAttendant.DoesNotExist:
                return Response({
                    'status_code': 404,
                    'message': 'Attendant not found',
                    'data': {}
                }, status=status.HTTP_404_NOT_FOUND)

            # Check if already super_attendant
            if attendant.role == 'super_attendant':
                return Response({
                    'status_code': 400,
                    'message': 'Attendant is already a Super Attendant',
                    'data': {
                        'id': attendant.id,
                        'username': attendant.user.username,
                        'name': attendant.attendant_name,
                        'role': attendant.role
                    }
                }, status=status.HTTP_400_BAD_REQUEST)

            old_role = attendant.role

            # Also update the user's role if needed
            user = attendant.user
            if user.role == 'attendant':
                user.role = 'super_attendant'
                user.save()

            # Update the attendant role
            attendant.role = 'super_attendant'
            attendant.save()

            return Response({
                'status_code': 200,
                'message': 'Attendant promoted to Super Attendant successfully',
                'data': {
                    'id': attendant.id,
                    'user_id': user.id,
                    'username': user.username,
                    'name': attendant.attendant_name,
                    'type': 'attendant',
                    'old_role': old_role,
                    'new_role': attendant.role,
                    'creche_id': attendant.creche.id,
                    'creche_name': attendant.creche.creche_name,
                    'tea_garden_id': attendant.creche.tea_garden.id,
                    'tea_garden_name': attendant.creche.tea_garden.tea_garden_name
                }
            }, status=status.HTTP_200_OK)

        # ============================================
        # PROMOTE NURSE -> HEAD_NURSE
        # ============================================
        else:
            try:
                nurse = Nurse.objects.select_related('user', 'health_center__tea_garden').get(
                    id=nurse_id,
                    is_active=True
                )
            except Nurse.DoesNotExist:
                return Response({
                    'status_code': 404,
                    'message': 'Nurse not found',
                    'data': {}
                }, status=status.HTTP_404_NOT_FOUND)

            # Check if already head_nurse
            if nurse.role == 'head_nurse':
                return Response({
                    'status_code': 400,
                    'message': 'Nurse is already a Head Nurse',
                    'data': {
                        'id': nurse.id,
                        'username': nurse.user.username,
                        'name': nurse.nurse_name,
                        'role': nurse.role
                    }
                }, status=status.HTTP_400_BAD_REQUEST)

            old_role = nurse.role

            # Also update the user's role if needed
            user = nurse.user
            if user.role == 'nurse':
                user.role = 'head_nurse'
                user.save()

            # Update the nurse role
            nurse.role = 'head_nurse'
            nurse.save()

            return Response({
                'status_code': 200,
                'message': 'Nurse promoted to Head Nurse successfully',
                'data': {
                    'id': nurse.id,
                    'user_id': user.id,
                    'username': user.username,
                    'name': nurse.nurse_name,
                    'type': 'nurse',
                    'old_role': old_role,
                    'new_role': nurse.role,
                    'health_center_id': nurse.health_center.id,
                    'health_center_name': nurse.health_center.name,
                    'tea_garden_id': nurse.health_center.tea_garden.id,
                    'tea_garden_name': nurse.health_center.tea_garden.tea_garden_name
                }
            }, status=status.HTTP_200_OK)


class NurseListByTeaGardenAPI(APIView):
    """
    API to list nurses filtered by tea_garden and optionally health_center.
    Admin only.

    POST /nurses/list/

    Request Parameters:
    - tea_garden_id (required): Tea Garden ID
    - health_center_id (optional): Health Center ID to filter by specific center

    Response: {
        "status_code": 200,
        "message": "success",
        "data": [
            {
                "id": 1,
                "username": "jane",
                "name": "Jane Doe",
                "role": "nurse",
                "mobile_no": "9876543210",
                "qualification": "GNM",
                "health_center_id": 1,
                "health_center_name": "Health Center A"
            },
            ...
        ]
    }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Only superadmin or tea_garden_head can access
        if request.user.role not in ['superadmin', 'teagarden_head']:
            return Response({
                'status_code': 403,
                'message': 'Access denied. Only admin users can view nurse list.',
                'data': []
            }, status=status.HTTP_403_FORBIDDEN)

        tea_garden_id = request.data.get('tea_garden_id')
        health_center_id = request.data.get('health_center_id')

        if not tea_garden_id:
            return Response({
                'status_code': 400,
                'message': 'tea_garden_id is required',
                'data': []
            }, status=status.HTTP_400_BAD_REQUEST)

        # Verify tea garden exists
        try:
            tea_garden = TeaGarden.objects.get(id=tea_garden_id)
        except TeaGarden.DoesNotExist:
            return Response({
                'status_code': 404,
                'message': 'Tea garden not found',
                'data': []
            }, status=status.HTTP_404_NOT_FOUND)

        # Build query for health centers in this tea garden
        hc_qs = HealthCenter.objects.filter(tea_garden=tea_garden)
        if health_center_id:
            hc_qs = hc_qs.filter(id=health_center_id)
            if not hc_qs.exists():
                return Response({
                    'status_code': 404,
                    'message': 'Health center not found in this tea garden',
                    'data': []
                }, status=status.HTTP_404_NOT_FOUND)

        # Get all nurses in these health centers
        nurses = Nurse.objects.filter(
            health_center__in=hc_qs,
            is_active=True
        ).select_related('user', 'health_center').order_by('health_center__name', 'nurse_name')

        data = []
        for n in nurses:
            data.append({
                'id': n.id,
                'user_id': n.user.id,
                'username': n.user.username,
                'name': n.nurse_name,
                'role': n.role,
                'mobile_no': n.mobile_no,
                'qualification': n.qualification,
                'health_center_id': n.health_center.id,
                'health_center_name': n.health_center.name,
                'tea_garden_id': tea_garden.id,
                'tea_garden_name': tea_garden.tea_garden_name,
                'is_active': n.is_active
            })

        return Response({
            'status_code': 200,
            'message': 'success',
            'data': data
        }, status=status.HTTP_200_OK)


