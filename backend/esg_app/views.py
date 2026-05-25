from rest_framework import viewsets, status, views
from rest_framework.response import Response
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.contrib.auth.models import User
from decimal import Decimal
import json

from esg_app.models import (
    Client, IngestionSource, RawRecord, NormalizedRecord, 
    AuditTrail, LocationMapping, AirportCode, EmissionFactor
)
from esg_app.serializers import (
    ClientSerializer, IngestionSourceSerializer, RawRecordSerializer, 
    NormalizedRecordSerializer, AuditTrailSerializer, LocationMappingSerializer,
    EmissionFactorSerializer
)
from esg_app.normalization_engine import (
    ingest_and_process_sap, ingest_and_process_utility, ingest_and_process_travel
)

# Helper to get simulated acting user from request parameters or headers
def get_acting_user(request):
    username = request.query_params.get('acting_user') or request.data.get('acting_user') or 'analyst'
    user = User.objects.filter(username=username).first()
    if not user:
        user = User.objects.filter(username='admin').first()
    return user

class ClientViewSet(viewsets.ModelViewSet):
    queryset = Client.objects.all().order_by('name')
    serializer_class = ClientSerializer

class LocationMappingViewSet(viewsets.ModelViewSet):
    queryset = LocationMapping.objects.all().order_by('code')
    serializer_class = LocationMappingSerializer
    
    def get_queryset(self):
        queryset = self.queryset
        client_id = self.request.query_params.get('client')
        if client_id:
            queryset = queryset.filter(client_id=client_id)
        return queryset

class EmissionFactorViewSet(viewsets.ModelViewSet):
    queryset = EmissionFactor.objects.all().order_by('category', 'subcategory')
    serializer_class = EmissionFactorSerializer

class IngestionSourceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = IngestionSource.objects.all().order_by('-ingested_at')
    serializer_class = IngestionSourceSerializer
    
    def get_queryset(self):
        queryset = self.queryset
        client_id = self.request.query_params.get('client')
        if client_id:
            queryset = queryset.filter(client_id=client_id)
        return queryset

class NormalizedRecordViewSet(viewsets.ModelViewSet):
    queryset = NormalizedRecord.objects.all().order_by('-date_start', '-id')
    serializer_class = NormalizedRecordSerializer
    
    def get_queryset(self):
        queryset = self.queryset
        
        client_id = self.request.query_params.get('client')
        if client_id:
            queryset = queryset.filter(client_id=client_id)
            
        scope = self.request.query_params.get('scope')
        if scope:
            queryset = queryset.filter(scope=scope)
            
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category=category)
            
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
            
        return queryset

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        record = self.get_object_or_404(pk)
        
        if record.is_locked:
            return Response({'error': 'Record is locked for audit and cannot be approved.'}, status=status.HTTP_400_BAD_REQUEST)
            
        user = get_acting_user(request)
        
        # Update record
        record.status = 'APPROVED'
        record.approved_by = user
        record.approved_at = timezone.now()
        record.save()
        
        # Audit Trail
        AuditTrail.objects.create(
            normalized_record=record,
            user=user,
            action_type='APPROVE',
            comment=request.data.get('comment', 'Record approved.')
        )
        
        return Response(NormalizedRecordSerializer(record).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        record = self.get_object_or_404(pk)
        
        if record.is_locked:
            return Response({'error': 'Record is locked for audit and cannot be rejected.'}, status=status.HTTP_400_BAD_REQUEST)
            
        comment = request.data.get('comment', '').strip()
        if not comment:
            return Response({'error': 'A rejection comment is mandatory.'}, status=status.HTTP_400_BAD_REQUEST)
            
        user = get_acting_user(request)
        
        # Update record
        record.status = 'REJECTED'
        record.save()
        
        # Audit Trail
        AuditTrail.objects.create(
            normalized_record=record,
            user=user,
            action_type='REJECT',
            comment=comment
        )
        
        return Response(NormalizedRecordSerializer(record).data)

    @action(detail=False, methods=['post'])
    def bulk_approve(self, request):
        record_ids = request.data.get('record_ids', [])
        user = get_acting_user(request)
        
        records = NormalizedRecord.objects.filter(id__in=record_ids, is_locked=False)
        updated_count = 0
        
        for record in records:
            record.status = 'APPROVED'
            record.approved_by = user
            record.approved_at = timezone.now()
            record.save()
            
            AuditTrail.objects.create(
                normalized_record=record,
                user=user,
                action_type='APPROVE',
                comment="Bulk approved."
            )
            updated_count += 1
            
        return Response({'message': f'Successfully approved {updated_count} records.'})

    @action(detail=False, methods=['post'])
    def bulk_reject(self, request):
        record_ids = request.data.get('record_ids', [])
        comment = request.data.get('comment', '').strip()
        if not comment:
            return Response({'error': 'A comment is required for bulk rejection.'}, status=status.HTTP_400_BAD_REQUEST)
            
        user = get_acting_user(request)
        records = NormalizedRecord.objects.filter(id__in=record_ids, is_locked=False)
        updated_count = 0
        
        for record in records:
            record.status = 'REJECTED'
            record.save()
            
            AuditTrail.objects.create(
                normalized_record=record,
                user=user,
                action_type='REJECT',
                comment=comment
            )
            updated_count += 1
            
        return Response({'message': f'Successfully rejected {updated_count} records.'})

    @action(detail=True, methods=['post'])
    def edit_record(self, request, pk=None):
        record = self.get_object_or_404(pk)
        
        if record.is_locked:
            return Response({'error': 'Record is locked for audit and cannot be edited.'}, status=status.HTTP_400_BAD_REQUEST)
            
        comment = request.data.get('comment', '').strip()
        if not comment:
            return Response({'error': 'A reason/comment is mandatory for overrides.'}, status=status.HTTP_400_BAD_REQUEST)
            
        user = get_acting_user(request)
        
        new_activity_val_str = request.data.get('activity_value')
        new_date_start_str = request.data.get('date_start')
        new_date_end_str = request.data.get('date_end')
        
        diff = {}
        
        # 1. Update activity value & recalculate emissions
        if new_activity_val_str is not None:
            try:
                new_val = Decimal(str(new_activity_val_str))
                old_val = record.activity_value
                if old_val != new_val:
                    diff['activity_value'] = {'old': float(old_val), 'new': float(new_val)}
                    record.activity_value = new_val
                    
                    # Recompute emissions using active emission factor
                    # Determine EF subcategory
                    ef_subcategory = None
                    category = record.category
                    
                    if category == "Fuel":
                        if "diesel" in record.description.lower():
                            ef_subcategory = "Diesel"
                        elif "gas" in record.description.lower():
                            ef_subcategory = "Natural Gas"
                        elif "oil" in record.description.lower():
                            ef_subcategory = "Heating Oil"
                    elif category == "Flights":
                        # Match subcategory in record description (e.g. "Business Long-haul")
                        for sub in ["Economy Short-haul", "Business Short-haul", "Economy Long-haul", "Business Long-haul"]:
                            if sub.lower() in record.description.lower():
                                ef_subcategory = sub
                                break
                    elif category == "Hotels":
                        # Look for "Hotel Stay DE", etc.
                        if "de" in record.location.lower() or "germany" in record.location.lower():
                            ef_subcategory = "Hotel Stay DE"
                        elif "gb" in record.location.lower() or "london" in record.location.lower():
                            ef_subcategory = "Hotel Stay GB"
                        elif "in" in record.location.lower() or "india" in record.location.lower():
                            ef_subcategory = "Hotel Stay IN"
                        else:
                            ef_subcategory = "Hotel Stay US"
                    elif category == "Ground Transport":
                        if "taxi" in record.description.lower():
                            ef_subcategory = "Taxi"
                        elif "train" in record.description.lower():
                            ef_subcategory = "Train"
                            
                    # Get factor
                    ef_value = Decimal('0.0')
                    if category == "Electricity":
                        # Electricity factor is facility grid intensity
                        loc_mapping = LocationMapping.objects.filter(client=record.client, name=record.location).first()
                        if loc_mapping:
                            ef_value = loc_mapping.grid_emission_factor
                        else:
                            ef_value = Decimal('0.40')
                    else:
                        ef_obj = EmissionFactor.objects.filter(category=category, subcategory=ef_subcategory, year=2026).first()
                        if ef_obj:
                            ef_value = ef_obj.value
                        else:
                            ef_value = Decimal('0.0')
                            
                    old_emissions = record.co2e_emissions_t
                    new_emissions = (new_val * ef_value) / Decimal('1000')
                    record.co2e_emissions_t = new_emissions
                    diff['co2e_emissions_t'] = {'old': float(old_emissions), 'new': float(new_emissions)}
            except Exception as e:
                return Response({'error': f'Invalid activity value: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)
                
        # 2. Update dates
        if new_date_start_str:
            old_start = record.date_start.strftime('%Y-%m-%d')
            if old_start != new_date_start_str:
                record.date_start = timezone.datetime.strptime(new_date_start_str, '%Y-%m-%d').date()
                diff['date_start'] = {'old': old_start, 'new': new_date_start_str}
                
        if new_date_end_str:
            old_end = record.date_end.strftime('%Y-%m-%d')
            if old_end != new_date_end_str:
                record.date_end = timezone.datetime.strptime(new_date_end_str, '%Y-%m-%d').date()
                diff['date_end'] = {'old': old_end, 'new': new_date_end_str}

        if not diff:
            return Response({'message': 'No changes detected.'})
            
        # Reset flag if edited, transition status to PENDING for review
        record.status = 'PENDING'
        record.flag_reason = None
        record.save()
        
        # Audit Trail
        AuditTrail.objects.create(
            normalized_record=record,
            user=user,
            action_type='EDIT',
            changed_fields=diff,
            comment=comment
        )
        
        return Response(NormalizedRecordSerializer(record).data)

    @action(detail=False, methods=['post'])
    def lock_period(self, request):
        client_id = request.data.get('client_id')
        date_start_str = request.data.get('date_start')
        date_end_str = request.data.get('date_end')
        
        if not client_id or not date_start_str or not date_end_str:
            return Response({'error': 'client_id, date_start, and date_end are required fields.'}, status=status.HTTP_400_BAD_REQUEST)
            
        user = get_acting_user(request)
        
        date_start = timezone.datetime.strptime(date_start_str, '%Y-%m-%d').date()
        date_end = timezone.datetime.strptime(date_end_str, '%Y-%m-%d').date()
        
        # Only lock APPROVED records
        records = NormalizedRecord.objects.filter(
            client_id=client_id,
            status='APPROVED',
            date_start__gte=date_start,
            date_end__lte=date_end,
            is_locked=False
        )
        
        updated_count = 0
        for record in records:
            record.is_locked = True
            record.save()
            
            AuditTrail.objects.create(
                normalized_record=record,
                user=user,
                action_type='LOCK',
                comment="Locked for audit sign-off."
            )
            updated_count += 1
            
        return Response({'message': f'Successfully locked {updated_count} approved records for audit.'})

    def get_object_or_404(self, pk):
        return get_object_or_404(NormalizedRecord, pk=pk)

# Upload/Ingestion API Views
class UploadSAPView(views.APIView):
    def post(self, request):
        client_id = request.data.get('client_id')
        file_obj = request.FILES.get('file')
        
        if not client_id or not file_obj:
            return Response({'error': 'client_id and file are required.'}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            file_content = file_obj.read().decode('utf-8')
            records_count = ingest_and_process_sap(client_id, file_obj.name, file_content)
            return Response({'message': f'Successfully ingested {records_count} raw records from SAP CSV.'}, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': f'Failed to process SAP CSV: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

class UploadUtilityView(views.APIView):
    def post(self, request):
        client_id = request.data.get('client_id')
        file_obj = request.FILES.get('file')
        
        if not client_id or not file_obj:
            return Response({'error': 'client_id and file are required.'}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            file_content = file_obj.read().decode('utf-8')
            records_count = ingest_and_process_utility(client_id, file_obj.name, file_content)
            return Response({'message': f'Successfully ingested {records_count} utility records (splits applied).'}, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': f'Failed to process Utility CSV: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

class PullTravelView(views.APIView):
    def post(self, request):
        client_id = request.data.get('client_id')
        if not client_id:
            return Response({'error': 'client_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
            
        MOCK_TRAVEL_API_DATA = [
            {
                "booking_id": "CONC-82194",
                "employee_id": "EMP-382",
                "trip_type": "FLIGHT",
                "booking_date": "2026-05-12",
                "cost": 1820.00,
                "currency": "USD",
                "details": {
                    "origin": "JFK",
                    "destination": "LHR",
                    "cabin_class": "Business"
                }
            },
            {
                "booking_id": "CONC-82195",
                "employee_id": "EMP-382",
                "trip_type": "HOTEL",
                "booking_date": "2026-05-13",
                "cost": 940.00,
                "currency": "GBP",
                "details": {
                    "hotel_name": "Hilton Munich Park",
                    "city": "Munich",
                    "country": "DE",
                    "room_nights": 4
                }
            },
            {
                "booking_id": "CONC-82196",
                "employee_id": "EMP-102",
                "trip_type": "FLIGHT",
                "booking_date": "2026-05-14",
                "cost": 310.00,
                "currency": "EUR",
                "details": {
                    "origin": "FRA",
                    "destination": "CDG",
                    "cabin_class": "Economy"
                }
            },
            {
                "booking_id": "CONC-82197",
                "employee_id": "EMP-102",
                "trip_type": "GROUND",
                "booking_date": "2026-05-16",
                "cost": 45.00,
                "currency": "EUR",
                "details": {
                    "vehicle_type": "Taxi",
                    "distance_km": 18.5
                }
            },
            {
                "booking_id": "CONC-82198",
                "employee_id": "EMP-204",
                "trip_type": "FLIGHT",
                "booking_date": "2026-05-18",
                "cost": 2100.00,
                "currency": "USD",
                "details": {
                    "origin": "JFK",
                    "destination": "BLR",
                    "cabin_class": "First"
                }
            },
            {
                "booking_id": "CONC-82199",
                "employee_id": "EMP-204",
                "trip_type": "HOTEL",
                "booking_date": "2026-05-19",
                "cost": 150.00,
                "currency": "INR",
                "details": {
                    "hotel_name": "Taj Coromandel",
                    "city": "Chennai",
                    "country": "IN",
                    "room_nights": -2
                }
            }
        ]
        
        try:
            records_count = ingest_and_process_travel(client_id, "Concur API Pull (Simulated)", MOCK_TRAVEL_API_DATA)
            return Response({
                'message': f'Successfully pulled and processed {records_count} records from Concur API.',
                'records': MOCK_TRAVEL_API_DATA
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': f'Failed to pull from Concur API: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)
