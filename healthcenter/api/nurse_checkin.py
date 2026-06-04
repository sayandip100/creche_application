from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db import transaction
import requests

from healthcenter.models import Nurse, NurseAttendance, HealthCenter


class NurseCheckInAPI(APIView):
    """
    Nurse & Head Nurse Check-In API
    Allows nurses and head nurses to check in with:
    - Photo verification (face recognition via external API)
    - GPS location

    Endpoint: POST /nurse/check-in/

    Request Parameters:
    - photo (required): Image file for face verification
    - latitude (required): GPS latitude
    - longitude (required): GPS longitude
    - health_center_id (required): Health center ID

    Optional:
    - nurse_id: If not provided, uses the authenticated user's nurse profile

    Response: {
        "status_code": 200,
        "message": "Check-in successful",
        "data": {
            "attendance_id": 123,
            "nurse_name": "Nurse Name",
            "nurse_id": 7,
            "role": "nurse",
            "check_in_time": "2025-05-27T10:30:00Z",
            "face_verified": true,
            "geo_verified": true
        }
    }
    """

    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser)

    # External API configuration (same endpoint used for doctors/attendants)
    FACE_API_URL = "http://45.64.107.97:5010/api/v1/attendance/doctor"

    @transaction.atomic
    def post(self, request):
        try:
            # --- Validate user is a nurse or head nurse ---
            if request.user.role not in ['nurse', 'head_nurse']:
                return Response({
                    'status_code': 403,
                    'message': 'Only nurses and head nurses can check in',
                    'data': {}
                }, status=status.HTTP_403_FORBIDDEN)

            # --- Extract request parameters ---
            photo = (request.FILES.get('photo') or request.FILES.get('file') or request.FILES.get('image'))
            latitude = request.data.get('latitude')
            longitude = request.data.get('longitude')
            health_center_id = request.data.get('health_center_id')
            nurse_id = request.data.get('nurse_id')

            # --- Validation ---
            if not all([photo, latitude, longitude, health_center_id]):
                return Response({
                    'status_code': 400,
                    'message': 'photo, latitude, longitude, and health_center_id are required',
                    'data': {}
                }, status=status.HTTP_400_BAD_REQUEST)

            # Validate health center exists
            try:
                health_center = HealthCenter.objects.get(id=health_center_id)
            except HealthCenter.DoesNotExist:
                return Response({
                    'status_code': 404,
                    'message': 'Health center not found',
                    'data': {}
                }, status=status.HTTP_404_NOT_FOUND)

            # Determine nurse - use provided nurse_id or try authenticated user
            nurse = None
            if nurse_id:
                try:
                    nurse = Nurse.objects.get(id=nurse_id, health_center=health_center)
                except Nurse.DoesNotExist:
                    return Response({
                        'status_code': 404,
                        'message': 'Nurse not found for this health center',
                        'data': {}
                    }, status=status.HTTP_404_NOT_FOUND)
            else:
                try:
                    nurse = Nurse.objects.get(user=request.user, health_center=health_center)
                except Nurse.DoesNotExist:
                    return Response({
                        'status_code': 404,
                        'message': 'Nurse profile not found for this health center',
                        'data': {}
                    }, status=status.HTTP_404_NOT_FOUND)

            # Check if already checked in today
            today = timezone.now().date()
            existing_checkin = NurseAttendance.objects.filter(
                nurse=nurse,
                attendance_date=today
            ).first()

            if existing_checkin:
                return Response({
                    'status_code': 409,
                    'message': 'Nurse already checked in today',
                    'data': {
                        'attendance_id': existing_checkin.id,
                        'check_in_time': existing_checkin.check_in_time,
                        'face_verified': True,
                        'geo_verified': existing_checkin.geo_verified
                    }
                }, status=status.HTTP_409_CONFLICT)

            # ============================================
            # FACE VERIFICATION via External API
            # ============================================
            face_verified = False
            face_api_response = None
            face_error = None

            try:
                # Prepare multipart form data for external API
                files = {'file': photo}
                data = {'health_center_id': health_center_id}

                # Call external face recognition API
                api_response = requests.post(
                    self.FACE_API_URL,
                    files=files,
                    data=data,
                    timeout=30
                )

                if api_response.status_code == 200:
                    face_api_response = api_response.json()

                    # Check if nurse was detected in the image
                    if 'present' in face_api_response and face_api_response['present']:
                        detected_persons = face_api_response['present']

                        # Look for current nurse in detected faces
                        for detected_person in detected_persons:
                            if detected_person.get('id') == nurse.id:
                                face_verified = True
                                break

                        # If current nurse not found but others are detected
                        if not face_verified and detected_persons:
                            face_error = f"Another person detected: {detected_persons[0].get('name', 'Unknown')}. Expected: {nurse.nurse_name or nurse.user.username}"

                    # Check for spoof faces
                    if face_api_response.get('spoof_faces', 0) > 0:
                        face_error = "Spoof face detected. Please try again with a real face."
                        face_verified = False

                    # Check for unknown faces
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

            # Check if location is within health center radius
            hc_latitude = float(health_center.latitude) if health_center.latitude else None
            hc_longitude = float(health_center.longitude) if health_center.longitude else None

            geo_verified = False
            if hc_latitude and hc_longitude:
                distance = self._calculate_distance(
                    latitude, longitude, hc_latitude, hc_longitude
                )
                radius_meters = float(health_center.geo_radius_meters)
                geo_verified = distance <= radius_meters

            # ============================================
            # If face not verified, return error
            # ============================================
            if not face_verified:
                return Response({
                    'status_code': 401,
                    'message': face_error or 'Face verification failed',
                    'data': {
                        'face_api_response': face_api_response
                    }
                }, status=status.HTTP_401_UNAUTHORIZED)

            # ============================================
            # CREATE ATTENDANCE RECORD
            # ============================================
            attendance = NurseAttendance.objects.create(
                nurse=nurse,
                health_center=health_center,
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
                    'nurse_id': nurse.id,
                    'nurse_name': nurse.nurse_name or nurse.user.username,
                    'role': nurse.role,
                    'health_center_id': health_center.id,
                    'health_center_name': health_center.name,
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