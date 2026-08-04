from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
import requests
import json

from healthcenter.models import Doctor, DoctorCheckIn, HealthCenter


class DoctorCheckInAPI(APIView):
    
    """
    Doctor Check-In API
    Allows doctors to check in with:
    - Photo verification (face recognition via external API)
    - GPS location
    
    Endpoint: POST /doctor/check-in/
    
    Request Parameters:
    - photo (required): Image file for face verification
    - latitude (required): GPS latitude
    - longitude (required): GPS longitude
    - health_center_id (required): Health center ID
    
    Response: {
        "status_code": 200,
        "message": "Check-in successful",
        "data": {
            "check_in_id": 123,
            "doctor_name": "Dr. John",
            "doctor_id": 7,
            "check_in_time": "2025-05-27T10:30:00Z",
            "face_verified": true,
            "timer_duration_minutes": 120
        }
    }
    """
    
    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser)
    
    # External API configuration
    FACE_API_URL = "http://45.64.107.97:5010/api/v1/attendance/doctor"
    
    @transaction.atomic
    def post(self, request):
        try:
            # Validate user is a doctor
            if request.user.role != 'doctor':
                return Response({
                    'status_code': 403,
                    'message': 'Only doctors can check in',
                    'data': {}
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Get doctor profile
            try:
                doctor = Doctor.objects.get(user=request.user)
            except Doctor.DoesNotExist:
                return Response({
                    'status_code': 404,
                    'message': 'Doctor profile not found',
                    'data': {}
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Validate required fields
            photo = request.FILES.get('photo')
            latitude = request.data.get('latitude')
            longitude = request.data.get('longitude')
            health_center_id = request.data.get('health_center_id')
            
            # Optional fields
            attendance_date = request.data.get('attendance_date')
            nurse_present = request.data.get('nurse_present', False)
            hygiene_maintained = request.data.get('hygiene_maintained', False)
            patients_visited_today = request.data.get('patients_visited_today', 0)
            
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
            
            # Check if already checked in today
            today = timezone.now().date()
            existing_checkin = DoctorCheckIn.objects.filter(
                doctor=doctor,
                check_in_date=today,
                status='CHECKED_IN'
            ).first()
            
            if existing_checkin:
                return Response({
                    'status_code': 409,
                    'message': 'Doctor already checked in today',
                    'data': {
                        'check_in_id': existing_checkin.id,
                        'check_in_time': existing_checkin.check_in_time,
                        'remaining_time_minutes': self._calculate_remaining_time(existing_checkin)
                    }
                }, status=status.HTTP_409_CONFLICT)
            
            # ============================================
            # FACE VERIFICATION via External API
            # ============================================
            face_verified = False
            detected_doctor_id = None
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
                    
                    # Check if doctor was detected in the image
                    if 'present' in face_api_response and face_api_response['present']:
                        detected_doctors = face_api_response['present']
                        
                        # Look for current doctor in detected faces
                        for detected_doctor in detected_doctors:
                            if detected_doctor['id'] == doctor.id:
                                face_verified = True
                                detected_doctor_id = detected_doctor['id']
                                break
                        
                        # If current doctor not found but others are detected
                        if not face_verified and detected_doctors:
                            face_error = f"Another doctor detected: {detected_doctors[0]['name']}. Expected: {doctor.name}"
                    
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
                # Calculate distance using Haversine formula (simplified)
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
            # CREATE CHECK-IN RECORD
            # ============================================
            # Parse optional fields
            try:
                nurse_present_bool = nurse_present in [True, 'true', 'True', '1', 1]
            except:
                nurse_present_bool = False
            
            try:
                hygiene_maintained_bool = hygiene_maintained in [True, 'true', 'True', '1', 1]
            except:
                hygiene_maintained_bool = False
            
            try:
                patients_count = int(patients_visited_today) if patients_visited_today else 0
            except:
                patients_count = 0
            
            check_in = DoctorCheckIn.objects.create(
                doctor=doctor,
                health_center=health_center,
                check_in_date=today,
                attendance_date=attendance_date if attendance_date else today,
                check_in_time=timezone.now(),
                check_in_photo=photo,
                check_in_latitude=latitude,
                check_in_longitude=longitude,
                check_in_geo_verified=geo_verified,
                face_match_score=1.0 if face_verified else 0.0,
                face_verified=face_verified,
                status='CHECKED_IN',
                nurse_present=nurse_present_bool,
                hygiene_maintained=hygiene_maintained_bool,
                patients_visited_today=patients_count,
                remarks=f"Face verified via external API. Geo verified: {geo_verified}"
            )
            
            return Response({
                'status_code': 200,
                'message': 'Check-in successful',
                'data': {
                    'check_in_id': check_in.id,
                    'doctor_id': doctor.id,
                    'doctor_name': doctor.name or doctor.user.username,
                    'check_in_date': check_in.check_in_date,
                    'attendance_date': check_in.attendance_date,
                    'check_in_time': check_in.check_in_time,
                    'face_verified': face_verified,
                    'geo_verified': geo_verified,
                    'health_center': health_center.name,
                    'nurse_present': check_in.nurse_present,
                    'hygiene_maintained': check_in.hygiene_maintained,
                    'patients_visited_today': check_in.patients_visited_today,
                    'timer_duration_minutes': 120,  # 2 hours
                    'timer_end_time': check_in.check_in_time + timedelta(minutes=120),
                    'image_url': face_api_response.get('image_url') if face_api_response else None
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'status_code': 500,
                'message': f'Check-in error: {str(e)}',
                'data': {}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _calculate_remaining_time(self, check_in):
        """Calculate remaining time until 2-hour timer expires"""
        timer_end = check_in.check_in_time + timedelta(minutes=120)
        remaining = (timer_end - timezone.now()).total_seconds() / 60
        return max(0, int(remaining))
    
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


class DoctorCheckOutAPI(APIView):
    """
    Doctor Check-Out API
    
    Endpoint: POST /doctor/check-out/
    
    Request Parameters:
    - check_in_id (required): ID of the check-in record
    - photo (required): Image file for exit verification
    - latitude (required): GPS latitude
    - longitude (required): GPS longitude
    
    Response: {
        "status_code": 200,
        "message": "Check-out successful",
        "data": {
            "check_in_id": 123,
            "check_in_time": "2025-05-27T10:30:00Z",
            "check_out_time": "2025-05-27T12:45:00Z",
            "duration_minutes": 135
        }
    }
    """
    
    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser)
    
    @transaction.atomic
    def post(self, request):
        try:
            # Validate user is a doctor
            if request.user.role != 'doctor':
                return Response({
                    'status_code': 403,
                    'message': 'Only doctors can check out',
                    'data': {}
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Validate required fields
            check_in_id = request.data.get('check_in_id')
            photo = request.FILES.get('photo')
            latitude = request.data.get('latitude')
            longitude = request.data.get('longitude')
            
            # Optional fields for checkout
            nurse_present = request.data.get('nurse_present')
            hygiene_maintained = request.data.get('hygiene_maintained')
            patients_visited_today = request.data.get('patients_visited_today')
            
            if not all([check_in_id, photo, latitude, longitude]):
                return Response({
                    'status_code': 400,
                    'message': 'check_in_id, photo, latitude, and longitude are required',
                    'data': {}
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get check-in record
            try:
                check_in = DoctorCheckIn.objects.get(id=check_in_id)
            except DoctorCheckIn.DoesNotExist:
                return Response({
                    'status_code': 404,
                    'message': 'Check-in record not found',
                    'data': {}
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Verify doctor ownership
            if check_in.doctor.user != request.user:
                return Response({
                    'status_code': 403,
                    'message': 'Unauthorized: This check-in belongs to another doctor',
                    'data': {}
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Check if already checked out
            if check_in.status == 'CHECKED_OUT':
                return Response({
                    'status_code': 409,
                    'message': 'Doctor already checked out',
                    'data': {
                        'check_in_id': check_in.id,
                        'check_out_time': check_in.check_out_time
                    }
                }, status=status.HTTP_409_CONFLICT)
            
            # Validate location format
            try:
                latitude = float(latitude)
                longitude = float(longitude)
            except (ValueError, TypeError):
                return Response({
                    'status_code': 400,
                    'message': 'Invalid latitude or longitude format',
                    'data': {}
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # GEO verification for checkout
            health_center = check_in.health_center
            hc_latitude = float(health_center.latitude) if health_center.latitude else None
            hc_longitude = float(health_center.longitude) if health_center.longitude else None
            
            geo_verified = False
            if hc_latitude and hc_longitude:
                distance = self._calculate_distance(
                    latitude, longitude, hc_latitude, hc_longitude
                )
                radius_meters = float(health_center.geo_radius_meters)
                geo_verified = distance <= radius_meters
            
            # Check if 2-hour + 30 minute timer has expired (total 150 mins for auto-checkout)
            timer_end = check_in.check_in_time + timedelta(minutes=150)
            timer_expired = timezone.now() >= timer_end
            
            # Check if user provided the optional fields
            user_provided_nurse = nurse_present is not None
            user_provided_hygiene = hygiene_maintained is not None
            user_provided_patients = patients_visited_today is not None
            user_provided_any = user_provided_nurse or user_provided_hygiene or user_provided_patients
            
            # Set checkout_remarks only if timer expired AND user did NOT provide optional fields
            checkout_remarks = None
            timer_auto_logout = False
            if timer_expired and not user_provided_any:
                timer_auto_logout = True
                checkout_remarks = "Doctor did not check out within the 2-hour 30-minute timer period - automatically marked as checked out"
            
            # Calculate duration
            check_out_time = timezone.now()
            duration = (check_out_time - check_in.check_in_time).total_seconds() / 60
            
            # Parse optional fields
            if timer_auto_logout:
                # Timer expired and user did NOT provide fields → set to None
                nurse_present_bool = None
                hygiene_maintained_bool = None
                patients_count = None
            elif timer_expired and user_provided_any:
                # Timer expired but user DID provide fields → use provided values, no remarks
                try:
                    nurse_present_bool = nurse_present in [True, 'true', 'True', '1', 1, 'Yes','yes'] if nurse_present else check_in.nurse_present
                except:
                    nurse_present_bool = check_in.nurse_present
                
                try:
                    hygiene_maintained_bool = hygiene_maintained in [True, 'true', 'True', '1', 1] if hygiene_maintained else check_in.hygiene_maintained
                except:
                    hygiene_maintained_bool = check_in.hygiene_maintained
                
                try:
                    patients_count = int(patients_visited_today) if patients_visited_today else check_in.patients_visited_today
                except:
                    patients_count = check_in.patients_visited_today
            else:
                # Timer NOT expired → normal behavior
                try:
                    nurse_present_bool = nurse_present in [True, 'true', 'True', '1', 1, 'Yes','yes'] if nurse_present else check_in.nurse_present
                except:
                    nurse_present_bool = check_in.nurse_present
                
                try:
                    hygiene_maintained_bool = hygiene_maintained in [True, 'true', 'True', '1', 1] if hygiene_maintained else check_in.hygiene_maintained
                except:
                    hygiene_maintained_bool = check_in.hygiene_maintained
                
                try:
                    patients_count = int(patients_visited_today) if patients_visited_today else check_in.patients_visited_today
                except:
                    patients_count = check_in.patients_visited_today
            
            # Update check-in record
            check_in.check_out_time = check_out_time
            check_in.check_out_photo = photo
            check_in.check_out_latitude = latitude
            check_in.check_out_longitude = longitude
            check_in.check_out_geo_verified = geo_verified
            check_in.status = 'CHECKED_OUT'
            check_in.duration_minutes = int(duration)
            check_in.nurse_present = nurse_present_bool
            check_in.hygiene_maintained = hygiene_maintained_bool
            check_in.patients_visited_today = patients_count
            check_in.checkout_remarks = checkout_remarks
            check_in.save()
            
            return Response({
                'status_code': 200,
                'message': 'Check-out successful',
                'data': {
                    'check_in_id': check_in.id,
                    'check_in_time': check_in.check_in_time,
                    'check_out_time': check_out_time,
                    'duration_minutes': int(duration),
                    'nurse_present': check_in.nurse_present,
                    'hygiene_maintained': check_in.hygiene_maintained,
                    'patients_visited_today': check_in.patients_visited_today
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'status_code': 500,
                'message': f'Check-out error: {str(e)}',
                'data': {}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _calculate_distance(self, lat1, lon1, lat2, lon2):
        """Calculate distance between two coordinates using Haversine formula"""
        from math import radians, cos, sin, asin, sqrt
        
        lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        r = 6371000  # Radius of earth in meters
        return c * r


class DoctorCheckInStatusAPI(APIView):
    """
    Get Doctor Current Check-In Status
    
    Endpoint: GET /doctor/check-in/status/
    
    Response: {
        "status_code": 200,
        "message": "success",
        "data": {
            "is_checked_in": true,
            "check_in_id": 123,
            "check_in_time": "2025-05-27T10:30:00Z",
            "remaining_time_minutes": 95,
            "health_center": "Health Center Name"
        }
    }
    """
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            # Validate user is a doctor
            if request.user.role != 'doctor':
                return Response({
                    'status_code': 403,
                    'message': 'Only doctors can access check-in status',
                    'data': {}
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Get doctor profile
            try:
                doctor = Doctor.objects.get(user=request.user)
            except Doctor.DoesNotExist:
                return Response({
                    'status_code': 404,
                    'message': 'Doctor profile not found',
                    'data': {}
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Get today's check-in
            today = timezone.now().date()
            check_in = DoctorCheckIn.objects.filter(
                doctor=doctor,
                check_in_date=today,
                status='CHECKED_IN'
            ).first()
            
            if not check_in:
                return Response({
                    'status_code': 200,
                    'message': 'No active check-in',
                    'data': {
                        'is_checked_in': False,
                        'check_in_id': None,
                        'remaining_time_minutes': 0
                    }
                }, status=status.HTTP_200_OK)
            
            # Calculate remaining time
            timer_end = check_in.check_in_time + timedelta(minutes=120)
            remaining = (timer_end - timezone.now()).total_seconds() / 60
            remaining_minutes = max(0, int(remaining))
            
            return Response({
                'status_code': 200,
                'message': 'success',
                'data': {
                    'is_checked_in': True,
                    'check_in_id': check_in.id,
                    'check_in_time': check_in.check_in_time,
                    'remaining_time_minutes': remaining_minutes,
                    'timer_expired': remaining_minutes == 0,
                    'health_center': check_in.health_center.name,
                    'face_verified': check_in.face_verified,
                    'geo_verified': check_in.check_in_geo_verified
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'status_code': 500,
                'message': f'Error: {str(e)}',
                'data': {}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
