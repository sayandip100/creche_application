from rest_framework import serializers
from healthcenter.models import PatientTreatment, HealthCenter, Nurse, Doctor


class DoctorSerializer(serializers.ModelSerializer):
    health_center_id = serializers.IntegerField(source='health_center.id', read_only=True)
    health_center_name = serializers.CharField(source='health_center.name', read_only=True)
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = Doctor
        fields = [
            'id',
            'user_id',
            'username',
            'health_center_id',
            'health_center_name',
            'name',
            'mobile_no',
            'qualification',
            'specialization',
            'photo',
            'is_active',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class PatientTreatmentSerializer(serializers.ModelSerializer):
    health_center_name = serializers.CharField(source='health_center.name', read_only=True)
    nurse_id = serializers.IntegerField(source='nurse.id', read_only=True)
    nurse_name = serializers.CharField(source='nurse.nurse_name', read_only=True)
    doctor_id = serializers.IntegerField(source='doctor.id', read_only=True)
    doctor_name = serializers.CharField(source='doctor.name', read_only=True)
    
    class Meta:
        model = PatientTreatment
        fields = [
            'id',
            'patient_name',
            'age',
            'contact_number',
            'health_center',
            'health_center_name',
            'nurse',
            'nurse_id',
            'nurse_name',
            'doctor',
            'doctor_id',
            'doctor_name',
            'prescription_image',
            'image',
            'status',
            'treatment_date',
            'whatsapp_sent',
            'whatsapp_sent_at',
            'remarks',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at', 'treatment_date']
    

class AddPatientSerializer(serializers.Serializer):
    patient_name = serializers.CharField(max_length=200)
    age = serializers.IntegerField(required=False, allow_null=True)
    contact_number = serializers.CharField(max_length=20, required=False, allow_null=True)
    health_center_id = serializers.IntegerField()
    nurse_id = serializers.IntegerField(required=False, allow_null=True)
    doctor_id = serializers.IntegerField(required=False, allow_null=True)
    status = serializers.IntegerField(default=1)
    remarks = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    
    def validate_health_center_id(self, value):
        try:
            HealthCenter.objects.get(id=value)
        except HealthCenter.DoesNotExist:
            raise serializers.ValidationError("Health center does not exist")
        return value
    
    def validate_nurse_id(self, value):
        if value is not None:
            try:
                Nurse.objects.get(id=value)
            except Nurse.DoesNotExist:
                raise serializers.ValidationError("Nurse does not exist")
        return value

    def validate_doctor_id(self, value):
        if value is not None:
            try:
                Doctor.objects.get(id=value)
            except Doctor.DoesNotExist:
                raise serializers.ValidationError("Doctor does not exist")
        return value
