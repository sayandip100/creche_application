from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from healthcenter.models import MedicineUnit
from healthcenter.serializers import MedicineUnitSerializer

import logging
logger = logging.getLogger(__name__)


class MedicineUnitListCreateAPI(APIView):
    """
    API to list all medicine units and create new ones.
    
    GET  /medicine/units/     → List all medicine units
    POST /medicine/units/     → Create a new medicine unit
    
    POST Request Body: {
        "unit_name": "Syrup"
    }
    
    Response: {
        "id": 1,
        "unit_name": "Syrup"
    }
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        units = MedicineUnit.objects.all().order_by('unit_name')
        serializer = MedicineUnitSerializer(units, many=True)
        return Response({
            'status_code': 200,
            'message': 'Medicine units retrieved successfully',
            'data': serializer.data
        }, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = MedicineUnitSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({
                'status_code': 201,
                'message': 'Medicine unit created successfully',
                'data': serializer.data
            }, status=status.HTTP_201_CREATED)
        return Response({
            'status_code': 400,
            'message': 'Validation error',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class MedicineUnitDetailAPI(APIView):
    """
    API to get, update, or delete a specific medicine unit.
    
    GET    /medicine/units/<id>/  → Get unit details
    PUT    /medicine/units/<id>/  → Update unit
    DELETE /medicine/units/<id>/  → Delete unit
    """
    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        try:
            return MedicineUnit.objects.get(pk=pk)
        except MedicineUnit.DoesNotExist:
            return None

    def get(self, request, unit_id):
        unit = self.get_object(unit_id)
        if not unit:
            return Response({
                'status_code': 404,
                'message': 'Medicine unit not found'
            }, status=status.HTTP_404_NOT_FOUND)
        serializer = MedicineUnitSerializer(unit)
        return Response({
            'status_code': 200,
            'message': 'Medicine unit retrieved successfully',
            'data': serializer.data
        }, status=status.HTTP_200_OK)

    def put(self, request, unit_id):
        unit = self.get_object(unit_id)
        if not unit:
            return Response({
                'status_code': 404,
                'message': 'Medicine unit not found'
            }, status=status.HTTP_404_NOT_FOUND)
        serializer = MedicineUnitSerializer(unit, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({
                'status_code': 200,
                'message': 'Medicine unit updated successfully',
                'data': serializer.data
            }, status=status.HTTP_200_OK)
        return Response({
            'status_code': 400,
            'message': 'Validation error',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, unit_id):
        unit = self.get_object(unit_id)
        if not unit:
            return Response({
                'status_code': 404,
                'message': 'Medicine unit not found'
            }, status=status.HTTP_404_NOT_FOUND)
        unit.delete()
        return Response({
            'status_code': 200,
            'message': 'Medicine unit deleted successfully'
        }, status=status.HTTP_200_OK)