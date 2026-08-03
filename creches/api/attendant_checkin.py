from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db import transaction
import requests

from creches.models import CrecheAttendant, Creche, AttendantAttendance
from healthcenter.models import Nurse, NurseAttendance, HealthCenter


class CheckInAPI(APIView):
    """
    Unified Check-In API for:
      - Attendant / Super Attendant (creches)
      - Nurse / Head Nurse (healthcenter)

    Role-based logic:
      - If user has a CrecheAttendant profile with role 'attendant' or 'super_attendant'
        → uses creche_id, Creche, AttendantAttendance
      - If user has a Nurse profile with role 'nurse' or 'head_nurse'
        → uses health_center_id, HealthCenter, NurseAttendance

    Endpoint: POST /check-in/

    Request Parameters (common):
    - file (required): Image file for face verification
    - latitude (required): GPS latitude
    - longitude (required): GPS longitude

    For Attendant / Super Attendant:
    - creche_id (required): Creche ID

    For Nurse / Head Nurse:
    - health_center_id (required): Health Center ID

    Response: {
        "status_code": 200,
        "message": "Check-in successful",
        "data": {
            "attendance_id": 123,
            "person_name": "...",
            "profile_id": 7,
            "role": "attendant|super_attendant|nurse|head_nurse",
            "check_in_time": "2025-05-27T10:30:00Z",
            "face_verified": true,
            "geo_verified": true
        }
    }
    """

    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser)

    # External API configuration (role-specific endpoints)
    FACE_API_URL_ATTENDANT = "http://45.64.107.97:5010/api/v1/attendance/attendant"
    FACE_API_URL_NURSE = "http://45.64.107.97:5010/api/v1/attendance/nurse"

    @transaction.atomic
    def post(self, request):
        try:
            # --- Extract common request parameters ---
            photo = request.FILES.get('photo')
            latitude = request.data.get('latitude')
            longitude = request.data.get('longitude')
            creche_id = request.data.get('creche_id')
            health_center_id = request.data.get('health_center_id')

            if not all([photo, latitude, longitude]):
                return Response({
                    'status_code': 400,
                    'message': 'file, latitude, and longitude are required',
                    'data': {}
                }, status=status.HTTP_400_BAD_REQUEST)

            # ============================================
            # DETERMINE ROLE & PROFILE
            # ============================================
            # Try to match user to CrecheAttendant profile
            attendant_profile = CrecheAttendant.objects.filter(
                user=request.user, is_active=True
            ).first()

            # Try to match user to Nurse profile
            nurse_profile = Nurse.objects.filter(
                user=request.user, is_active=True
            ).first()

            # Determine which role group the user belongs to
            is_attendant = attendant_profile is not None and attendant_profile.role in ['attendant', 'super_attendant']
            is_nurse = nurse_profile is not None and nurse_profile.role in ['nurse', 'head_nurse']

            if not is_attendant and not is_nurse:
                return Response({
                    'status_code': 403,
                    'message': 'Access denied. User must be an attendant, super attendant, nurse, or head nurse.',
                    'data': {}
                }, status=status.HTTP_403_FORBIDDEN)

            # ============================================
            # ATTENDANT / SUPER ATTENDANT PATH
            # ============================================
            if is_attendant:
                if not creche_id:
                    return Response({
                        'status_code': 400,
                        'message': 'creche_id is required for attendant check-in',
                        'data': {}
                    }, status=status.HTTP_400_BAD_REQUEST)

                try:
                    creche = Creche.objects.get(id=creche_id)
                except Creche.DoesNotExist:
                    return Response({
                        'status_code': 404,
                        'message': 'Creche not found',
                        'data': {}
                    }, status=status.HTTP_404_NOT_FOUND)

                # Verify attendant belongs to this creche
                if attendant_profile.creche_id != creche.id:
                    return Response({
                        'status_code': 403,
                        'message': 'Attendant is not assigned to this creche',
                        'data': {}
                    }, status=status.HTTP_403_FORBIDDEN)

                profile = attendant_profile
                location_id = creche_id
                location_obj = creche
                location_name_field = 'creche_name'
                location_name = creche.creche_name
                AttendanceModel = AttendantAttendance
                profile_name = profile.attendant_name or profile.user.username
                profile_id_field = 'attendant_id'
                profile_role = profile.role

            # ============================================
            # NURSE / HEAD NURSE PATH
            # ============================================
            else:  # is_nurse
                if not health_center_id:
                    return Response({
                        'status_code': 400,
                        'message': 'health_center_id is required for nurse check-in',
                        'data': {}
                    }, status=status.HTTP_400_BAD_REQUEST)

                try:
                    health_center = HealthCenter.objects.get(id=health_center_id)
                except HealthCenter.DoesNotExist:
                    return Response({
                        'status_code': 404,
                        'message': 'Health center not found',
                        'data': {}
                    }, status=status.HTTP_404_NOT_FOUND)

                # Verify nurse belongs to this health center
                if nurse_profile.health_center_id != health_center.id:
                    return Response({
                        'status_code': 403,
                        'message': 'Nurse is not assigned to this health center',
                        'data': {}
                    }, status=status.HTTP_403_FORBIDDEN)

                profile = nurse_profile
                location_id = health_center_id
                location_obj = health_center
                location_name_field = 'name'
                location_name = health_center.name
                AttendanceModel = NurseAttendance
                profile_name = profile.nurse_name or profile.user.username
                profile_id_field = 'nurse_id'
                profile_role = profile.role

            # ============================================
            # CHECK DUPLICATE CHECK-IN
            # ============================================
            today = timezone.now().date()
            if is_attendant:
                existing_checkin = AttendanceModel.objects.filter(
                    attendant=profile,
                    attendance_date=today
                ).first()
            else:
                existing_checkin = AttendanceModel.objects.filter(
                    nurse=profile,
                    attendance_date=today
                ).first()

            if existing_checkin:
                return Response({
                    'status_code': 409,
                    'message': f'{profile_role.replace("_", " ").title()} already checked in today',
                    'data': {
                        'attendance_id': existing_checkin.id,
                        'check_in_time': existing_checkin.check_in_time,
                        'face_verified': True,
                        'geo_verified': existing_checkin.geo_verified if hasattr(existing_checkin, 'geo_verified') else getattr(existing_checkin, 'check_in_geo_verified', False)
                    }
                }, status=status.HTTP_409_CONFLICT)

            # ============================================
            # FACE VERIFICATION via External API
            # ============================================
            face_verified = False
            face_api_response = None
            face_error = None

            # Choose API endpoint based on role
            if is_attendant:
                face_api_url = self.FACE_API_URL_ATTENDANT
            else:
                face_api_url = self.FACE_API_URL_NURSE

            try:
                # Read file data to ensure it's sent properly to external API
                photo_data = photo.read()
                files = {'file': ('image.jpg', photo_data, photo.content_type if hasattr(photo, 'content_type') else 'image/jpeg')}
                if is_attendant:
                    data = {'creche_id': location_id}
                else:
                    data = {'health_center_id': location_id}

                api_response = requests.post(
                    face_api_url,
                    files=files,
                    data=data,
                    timeout=30
                )

                # Restore file pointer for saving to DB
                if photo and hasattr(photo, 'seek'):
                    photo.seek(0)

                if api_response.status_code == 200:
                    face_api_response = api_response.json()

                    if 'present' in face_api_response and face_api_response['present']:
                        detected_persons = face_api_response['present']

                        for detected_person in detected_persons:
                            if detected_person.get('id') == profile.id:
                                face_verified = True
                                break

                        if not face_verified and detected_persons:
                            face_error = f"Another person detected: {detected_persons[0].get('name', 'Unknown')}. Expected: {profile_name}"

                    if face_api_response.get('spoof_faces', 0) > 0:
                        face_error = "Spoof face detected. Please try again with a real face."
                        face_verified = False

                    if not face_verified and face_api_response.get('unknown_faces', 0) > 0:
                        face_error = "Face not recognized. Please try again."
                else:
                    face_error = f"Face API error: {api_response.status_code}"

            except requests.exceptions.Timeout:
                face_error = "Face recognition service timeout"
            except requests.exceptions.ConnectionError:
                face_error = "Unable to connect to face recognition service"
            except Exception as e:
                face_error = f"Face recognition error: {str(e)}"

            # ============================================
            # GEO VERIFICATION
            # ============================================
            try:
                latitude = float(latitude)
                longitude = float(longitude)
            except (ValueError, TypeError):
                return Response({
                    'status_code': 400,
                    'message': 'Invalid latitude or longitude format',
                    'data': {}
                }, status=status.HTTP_400_BAD_REQUEST)

            loc_latitude = float(location_obj.latitude) if location_obj.latitude else None
            loc_longitude = float(location_obj.longitude) if location_obj.longitude else None

            geo_verified = False
            if loc_latitude and loc_longitude:
                distance = self._calculate_distance(
                    latitude, longitude, loc_latitude, loc_longitude
                )
                radius_meters = float(location_obj.geo_radius_meters)
                geo_verified = distance <= radius_meters

            # ============================================
            # If face not verified, return error
            # ============================================
            if not face_verified:
                return Response({
                    'status_code': 400,
                    'message': face_error or 'Face verification failed',
                    'data': {
                        'face_api_response': face_api_response
                    }
                }, status=status.HTTP_400_BAD_REQUEST)

            # ============================================
            # CREATE ATTENDANCE RECORD
            # ============================================
            if is_attendant:
                attendance = AttendantAttendance.objects.create(
                    attendant=profile,
                    creche=location_obj,
                    attendance_date=today,
                    check_in_time=timezone.now(),
                    attendance_photo=photo,
                    latitude=latitude,
                    longitude=longitude,
                    geo_verified=geo_verified,
                    remarks=f"Face verified via external API. Geo verified: {geo_verified}"
                )
            else:  # is_nurse
                attendance = NurseAttendance.objects.create(
                    nurse=profile,
                    health_center=location_obj,
                    attendance_date=today,
                    check_in_time=timezone.now(),
                    attendance_photo=photo,
                    latitude=latitude,
                    longitude=longitude,
                    geo_verified=geo_verified,
                    remarks=f"Face verified via external API. Geo verified: {geo_verified}"
                )

            return Response({
                'status_code': 200,
                'message': 'Check-in successful',
                'data': {
                    'attendance_id': attendance.id,
                    'profile_id': profile.id,
                    'person_name': profile_name,
                    'role': profile_role,
                    'location_id': location_obj.id,
                    'location_name': location_name,
                    'check_in_date': attendance.attendance_date,
                    'check_in_time': attendance.check_in_time,
                    'face_verified': face_verified,
                    'geo_verified': geo_verified,
                    'image_url': face_api_response.get('image_url') if face_api_response else None
                }
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'status_code': 500,
                'message': f'Check-in error: {str(e)}',
                'data': {}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            
            
    def _calculate_distance(self, lat1, lon1, lat2, lon2):
        """
        Calculate distance between two coordinates using Haversine formula
        Returns distance in meters
        """
        from math import radians, cos, sin, asin, sqrt

        lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        r = 6371000  # Radius of earth in meters
        return c * r        



class CheckInAPI_260626(APIView):
    """
    Unified Check-In API for:
      - Attendant / Super Attendant (creches)
      - Nurse / Head Nurse (healthcenter)

    Role-based logic:
      - If user has a CrecheAttendant profile with role 'attendant' or 'super_attendant'
        → uses creche_id, Creche, AttendantAttendance
      - If user has a Nurse profile with role 'nurse' or 'head_nurse'
        → uses health_center_id, HealthCenter, NurseAttendance

    Endpoint: POST /check-in/

    Request Parameters (common):
    - file (required): Image file for face verification
    - latitude (required): GPS latitude
    - longitude (required): GPS longitude

    For Attendant / Super Attendant:
    - creche_id (required): Creche ID

    For Nurse / Head Nurse:
    - health_center_id (required): Health Center ID

    Response: {
        "status_code": 200,
        "message": "Check-in successful",
        "data": {
            "attendance_id": 123,
            "person_name": "...",
            "profile_id": 7,
            "role": "attendant|super_attendant|nurse|head_nurse",
            "check_in_time": "2025-05-27T10:30:00Z",
            "face_verified": true,
            "geo_verified": true]
        }
    }
    """

    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser)

    # External API configuration (role-specific endpoints)
    FACE_API_URL_ATTENDANT = "http://45.64.107.97:5010/api/v1/attendance/attendant"
    FACE_API_URL_NURSE = "http://45.64.107.97:5010/api/v1/attendance/nurse"

    @transaction.atomic
    def post(self, request):
        try:
            # --- Extract common request parameters ---
            photo = request.FILES.get('photo')
            latitude = request.data.get('latitude')
            longitude = request.data.get('longitude')
            creche_id = request.data.get('creche_id')
            health_center_id = request.data.get('health_center_id')

            if not all([latitude, longitude]):
                return Response({
                    'status_code': 400,
                    'message': 'latitude and longitude are required',
                    'data': {}
                }, status=status.HTTP_400_BAD_REQUEST)
                
            if not all([photo]):
                    return Response({
                    'status_code': 400,
                    'message': 'photo is required',
                    'data': {}
                }, status=status.HTTP_400_BAD_REQUEST)  
    


            # ============================================
            # DETERMINE ROLE & PROFILE
            # ============================================
            # Try to match user to CrecheAttendant profile
            attendant_profile = CrecheAttendant.objects.filter(
                user=request.user, is_active=True
            ).first()

            # Try to match user to Nurse profile
            nurse_profile = Nurse.objects.filter(
                user=request.user, is_active=True
            ).first()

            # Determine which role group the user belongs to
            is_attendant = attendant_profile is not None and attendant_profile.role in ['attendant', 'super_attendant']
            is_nurse = nurse_profile is not None and nurse_profile.role in ['nurse', 'head_nurse']

            if not is_attendant and not is_nurse:
                return Response({
                    'status_code': 403,
                    'message': 'Access denied. User must be an attendant, super attendant, nurse, or head nurse.',
                    'data': {}
                }, status=status.HTTP_403_FORBIDDEN)

            # ============================================
            # ATTENDANT / SUPER ATTENDANT PATH
            # ============================================
            if is_attendant:
                if not creche_id:
                    return Response({
                        'status_code': 400,
                        'message': 'creche_id is required for attendant check-in',
                        'data': {}
                    }, status=status.HTTP_400_BAD_REQUEST)

                try:
                    creche = Creche.objects.get(id=creche_id)
                except Creche.DoesNotExist:
                    return Response({
                        'status_code': 404,
                        'message': 'Creche not found',
                        'data': {}
                    }, status=status.HTTP_404_NOT_FOUND)

                # Verify attendant belongs to this creche
                if attendant_profile.creche_id != creche.id:
                    return Response({
                        'status_code': 403,
                        'message': 'Attendant is not assigned to this creche',
                        'data': {}
                    }, status=status.HTTP_403_FORBIDDEN)

                profile = attendant_profile
                location_id = creche_id
                location_obj = creche
                location_name_field = 'creche_name'
                location_name = creche.creche_name
                AttendanceModel = AttendantAttendance
                profile_name = profile.attendant_name or profile.user.username
                profile_id_field = 'attendant_id'
                profile_role = profile.role

            # ============================================
            # NURSE / HEAD NURSE PATH
            # ============================================
            else:  # is_nurse
                if not health_center_id:
                    return Response({
                        'status_code': 400,
                        'message': 'health_center_id is required for nurse check-in',
                        'data': {}
                    }, status=status.HTTP_400_BAD_REQUEST)

                try:
                    health_center = HealthCenter.objects.get(id=health_center_id)
                except HealthCenter.DoesNotExist:
                    return Response({
                        'status_code': 404,
                        'message': 'Health center not found',
                        'data': {}
                    }, status=status.HTTP_404_NOT_FOUND)

                # Verify nurse belongs to this health center
                if nurse_profile.health_center_id != health_center.id:
                    return Response({
                        'status_code': 403,
                        'message': 'Nurse is not assigned to this health center',
                        'data': {}
                    }, status=status.HTTP_403_FORBIDDEN)

                profile = nurse_profile
                location_id = health_center_id
                location_obj = health_center
                location_name_field = 'name'
                location_name = health_center.name
                AttendanceModel = NurseAttendance
                profile_name = profile.nurse_name or profile.user.username
                profile_id_field = 'nurse_id'
                profile_role = profile.role

            # ============================================
            # CHECK DUPLICATE CHECK-IN
            # ============================================
            today = timezone.now().date()
            if is_attendant:
                existing_checkin = AttendanceModel.objects.filter(
                    attendant=profile,
                    attendance_date=today
                ).first()
            else:
                existing_checkin = AttendanceModel.objects.filter(
                    nurse=profile,
                    attendance_date=today
                ).first()

            if existing_checkin:
                return Response({
                    'status_code': 409,
                    'message': f'{profile_role.replace("_", " ").title()} already checked in today',
                    'data': {
                        'attendance_id': existing_checkin.id,
                        'check_in_time': existing_checkin.check_in_time,
                        'face_verified': True,
                        'geo_verified': existing_checkin.geo_verified if hasattr(existing_checkin, 'geo_verified') else getattr(existing_checkin, 'check_in_geo_verified', False)
                    }
                }, status=status.HTTP_409_CONFLICT)

            # ============================================
            # FACE VERIFICATION via External API
            # ============================================
            face_verified = False
            face_api_response = None
            face_error = None

            # Choose API endpoint based on role
            if is_attendant:
                face_api_url = self.FACE_API_URL_ATTENDANT
            else:
                face_api_url = self.FACE_API_URL_NURSE

            try:
                files = {'file': photo}
                if is_attendant:
                    data = {'creche_id': location_id}
                else:
                    data = {'health_center_id': location_id}

                api_response = requests.post(
                    face_api_url,
                    files=files,
                    data=data,
                    timeout=30
                )

                if api_response.status_code == 200:
                    face_api_response = api_response.json()

                    if 'present' in face_api_response and face_api_response['present']:
                        detected_persons = face_api_response['present']

                        for detected_person in detected_persons:
                            if detected_person.get('id') == profile.id:
                                face_verified = True
                                break

                        if not face_verified and detected_persons:
                            face_error = f"Another person detected: {detected_persons[0].get('name', 'Unknown')}. Expected: {profile_name}"

                    if face_api_response.get('spoof_faces', 0) > 0:
                        face_error = "Spoof face detected. Please try again with a real face."
                        face_verified = False

                    if not face_verified and face_api_response.get('unknown_faces', 0) > 0:
                        face_error = "Face not recognized. Please try again."
                else:
                    face_error = f"Face API error: {api_response.status_code}"

            except requests.exceptions.Timeout:
                face_error = "Face recognition service timeout"
            except requests.exceptions.ConnectionError:
                face_error = "Unable to connect to face recognition service"
            except Exception as e:
                face_error = f"Face recognition error: {str(e)}"

            # ============================================
            # GEO VERIFICATION
            # ============================================
            try:
                latitude = float(latitude)
                longitude = float(longitude)
            except (ValueError, TypeError):
                return Response({
                    'status_code': 400,
                    'message': 'Invalid latitude or longitude format',
                    'data': {}
                }, status=status.HTTP_400_BAD_REQUEST)

            loc_latitude = float(location_obj.latitude) if location_obj.latitude else None
            loc_longitude = float(location_obj.longitude) if location_obj.longitude else None

            geo_verified = False
            if loc_latitude and loc_longitude:
                distance = self._calculate_distance(
                    latitude, longitude, loc_latitude, loc_longitude
                )
                radius_meters = float(location_obj.geo_radius_meters)
                geo_verified = distance <= radius_meters

            # ============================================
            # If face not verified, return error
            # ============================================
            if not face_verified:
                return Response({
                    'status_code': 400,
                    'message': 'Mismatch Face ',
                    'data': {
                        'face_api_response': face_api_response
                    }
                }, status=status.HTTP_400_BAD_REQUEST)

            # ============================================
            # CREATE ATTENDANCE RECORD
            # ============================================
            if is_attendant:
                attendance = AttendantAttendance.objects.create(
                    attendant=profile,
                    creche=location_obj,
                    attendance_date=today,
                    check_in_time=timezone.now(),
                    attendance_photo=photo,
                    latitude=latitude,
                    longitude=longitude,
                    geo_verified=geo_verified,
                    remarks=f"Face verified via external API. Geo verified: {geo_verified}"
                )
            else:  # is_nurse
                attendance = NurseAttendance.objects.create(
                    nurse=profile,
                    health_center=location_obj,
                    attendance_date=today,
                    check_in_time=timezone.now(),
                    attendance_photo=photo,
                    latitude=latitude,
                    longitude=longitude,
                    geo_verified=geo_verified,
                    remarks=f"Face verified via external API. Geo verified: {geo_verified}"
                )

            return Response({
                'status_code': 200,
                'message': 'Check-in successful',
                'data': {
                    'attendance_id': attendance.id,
                    'profile_id': profile.id,
                    'person_name': profile_name,
                    'role': profile_role,
                    'location_id': location_obj.id,
                    'location_name': location_name,
                    'check_in_date': attendance.attendance_date,
                    'check_in_time': attendance.check_in_time,
                    'face_verified': face_verified,
                    'geo_verified': geo_verified,
                    'image_url': face_api_response.get('image_url') if face_api_response else None
                }
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'status_code': 500,
                'message': f'Check-in error: {str(e)}',
                'data': {}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _calculate_distance(self, lat1, lon1, lat2, lon2):
        """
        Calculate distance between two coordinates using Haversine formula
        Returns distance in meters
        """
        from math import radians, cos, sin, asin, sqrt

        lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        r = 6371000  # Radius of earth in meters
        return c * r
    
    

class CheckInStatusAPI(APIView):
    """
    Check-In Status API for:
      - Attendant / Super Attendant (creches)
      - Nurse / Head Nurse (healthcenter)

    Returns the current check-in status for the authenticated user.
    If checked in, returns the check-in details and remaining time.

    Endpoint: GET /check-in/status/

    No request parameters needed - identifies user from auth token.

    Response:
    {
        "status_code": 200,
        "message": "success",
        "data": {
            "is_checked_in": true,
            "role": "attendant|nurse",
            "attendance_id": 123,
            "person_name": "...",
            "location_name": "...",
            "check_in_time": "2025-05-27T10:30:00Z",
            "face_verified": true,
            "geo_verified": true
        }
    }
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            today = timezone.now().date()

            # Try to match user to CrecheAttendant profile
            attendant_profile = CrecheAttendant.objects.filter(
                user=request.user, is_active=True
            ).first()

            # Try to match user to Nurse profile
            nurse_profile = Nurse.objects.filter(
                user=request.user, is_active=True
            ).first()

            # Check attendant status
            if attendant_profile:
                attendance = AttendantAttendance.objects.filter(
                    attendant=attendant_profile,
                    attendance_date=today
                ).first()

                if attendance:
                    return Response({
                        "status_code": 200,
                        "message": "success",
                        "data": {
                            "is_checked_in": True,
                            "role": attendant_profile.role,
                            "attendance_id": attendance.id,
                            "person_name": attendant_profile.attendant_name or attendant_profile.user.username,
                            "profile_id": attendant_profile.id,
                            "location_name": attendance.creche.creche_name if attendance.creche else None,
                            "check_in_time": attendance.check_in_time,
                            "face_verified": True,
                            "geo_verified": attendance.geo_verified,
                            "remarks": attendance.remarks
                        }
                    }, status=status.HTTP_200_OK)

                return Response({
                    "status_code": 200,
                    "message": "No active check-in found"
                   
                }, status=status.HTTP_200_OK)

            # Check nurse status
            if nurse_profile:
                attendance = NurseAttendance.objects.filter(
                    nurse=nurse_profile,
                    attendance_date=today
                ).first()

                if attendance:
                    return Response({
                        "status_code": 200,
                        "message": "success",
                        "data": {
                            "is_checked_in": True,
                            "role": nurse_profile.role,
                            "attendance_id": attendance.id,
                            "person_name": nurse_profile.nurse_name or nurse_profile.user.username,
                            "profile_id": nurse_profile.id,
                            "location_name": attendance.health_center.name if attendance.health_center else None,
                            "check_in_time": attendance.check_in_time,
                            "face_verified": True,
                            "geo_verified": attendance.geo_verified,
                            "remarks": attendance.remarks
                        }
                    }, status=status.HTTP_200_OK)

                return Response({
                    "status_code": 200,
                    "message": "No active check-in found"
                    
                }, status=status.HTTP_200_OK)

            # No matching profile found
            return Response({
                "status_code": 403,
                "message": "Access denied. User must be an attendant, super attendant, nurse, or head nurse.",
                "data": {}
            }, status=status.HTTP_403_FORBIDDEN)

        except Exception as e:
            return Response({
                "status_code": 500,
                "message": f"Error: {str(e)}",
                "data": {}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    