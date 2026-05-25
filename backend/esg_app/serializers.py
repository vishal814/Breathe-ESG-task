from rest_framework import serializers
from django.contrib.auth.models import User
from esg_app.models import (
    Client, LocationMapping, AirportCode, IngestionSource,
    RawRecord, NormalizedRecord, AuditTrail, EmissionFactor
)

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email']

class ClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = '__all__'

class LocationMappingSerializer(serializers.ModelSerializer):
    class Meta:
        model = LocationMapping
        fields = '__all__'

class AirportCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = AirportCode
        fields = '__all__'

class EmissionFactorSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmissionFactor
        fields = '__all__'

class AuditTrailSerializer(serializers.ModelSerializer):
    user_detail = UserSerializer(source='user', read_only=True)
    
    class Meta:
        model = AuditTrail
        fields = ['id', 'normalized_record', 'user', 'user_detail', 'action_type', 'changed_fields', 'comment', 'timestamp']

class RawRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = RawRecord
        fields = ['id', 'source', 'status', 'raw_data', 'validation_errors', 'created_at']

class NormalizedRecordSerializer(serializers.ModelSerializer):
    audit_trails = AuditTrailSerializer(many=True, read_only=True)
    raw_record_detail = RawRecordSerializer(source='raw_record', read_only=True)
    approved_by_detail = UserSerializer(source='approved_by', read_only=True)
    
    class Meta:
        model = NormalizedRecord
        fields = [
            'id', 'client', 'raw_record', 'raw_record_detail', 'scope', 'category', 
            'description', 'activity_value', 'activity_unit', 'co2e_emissions_t', 
            'location', 'date_start', 'date_end', 'status', 'flag_reason', 
            'is_locked', 'approved_by', 'approved_by_detail', 'approved_at', 
            'created_at', 'updated_at', 'audit_trails'
        ]

class IngestionSourceSerializer(serializers.ModelSerializer):
    raw_records_count = serializers.SerializerMethodField()
    
    class Meta:
        model = IngestionSource
        fields = ['id', 'client', 'name', 'source_type', 'file_name', 'status', 'ingested_at', 'raw_payload', 'raw_records_count']
        
    def get_raw_records_count(self, obj):
        return obj.raw_records.count()
