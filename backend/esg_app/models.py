from django.db import models
from django.contrib.auth.models import User

class Client(models.Model):
    name = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class LocationMapping(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='locations')
    code = models.CharField(max_length=50, help_text="Plant code (WERKS) or facility ID")
    name = models.CharField(max_length=255, help_text="Human-readable facility name")
    region = models.CharField(max_length=100, help_text="Country or Grid region code (e.g. DE, US-NE, IN)")
    grid_emission_factor = models.DecimalField(max_digits=10, decimal_places=6, help_text="kg CO2e / kWh")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('client', 'code')

    def __str__(self):
        return f"{self.client.name} - {self.code} ({self.name})"

class AirportCode(models.Model):
    code = models.CharField(max_length=10, unique=True, help_text="IATA Airport Code (e.g. JFK, LHR)")
    city = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)

    def __str__(self):
        return f"{self.code} - {self.city}, {self.country}"

class IngestionSource(models.Model):
    SOURCE_TYPES = [
        ('SAP', 'SAP ERP (Fuel & Procurement)'),
        ('UTILITY', 'Utility Portal (Electricity)'),
        ('TRAVEL', 'Corporate Travel API/CSV (Flights, Hotels, Ground)'),
    ]
    STATUS_CHOICES = [
        ('PENDING', 'Pending Processing'),
        ('PROCESSED', 'Processed'),
        ('FAILED', 'Failed Ingestion'),
    ]

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='ingestion_sources')
    name = models.CharField(max_length=255, help_text="Descriptive ingestion process label")
    source_type = models.CharField(max_length=15, choices=SOURCE_TYPES)
    file_name = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='PENDING')
    ingested_at = models.DateTimeField(auto_now_add=True)
    raw_payload = models.TextField(blank=True, null=True, help_text="Original raw text / API JSON file content")

    def __str__(self):
        return f"{self.client.name} - {self.source_type} ({self.ingested_at.strftime('%Y-%m-%d %H:%M')})"

class RawRecord(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PROCESSED', 'Processed'),
        ('FAILED', 'Failed Validation'),
    ]

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='raw_records')
    source = models.ForeignKey(IngestionSource, on_delete=models.CASCADE, related_name='raw_records')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='PENDING')
    raw_data = models.JSONField(help_text="Stores the exact raw row fields as key-value pairs")
    validation_errors = models.TextField(blank=True, null=True, help_text="JSON or text logs of validation anomalies")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"RawRecord {self.id} ({self.source.source_type})"

class NormalizedRecord(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending Approval'),
        ('FLAGGED', 'Flagged (Suspicious)'),
        ('APPROVED', 'Approved (Auditable)'),
        ('REJECTED', 'Rejected'),
    ]

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='normalized_records')
    raw_record = models.ForeignKey(RawRecord, on_delete=models.SET_NULL, null=True, blank=True, related_name='normalized_records')
    scope = models.IntegerField(choices=[(1, 'Scope 1'), (2, 'Scope 2'), (3, 'Scope 3')])
    category = models.CharField(max_length=100, help_text="e.g. Fuel, Electricity, Flights, Hotels, Ground Transport")
    description = models.CharField(max_length=255, blank=True, null=True)
    
    # Normalized energy or travel metric values
    activity_value = models.DecimalField(max_digits=15, decimal_places=4, help_text="Quantity in standardized units")
    activity_unit = models.CharField(max_length=50, help_text="Standardized unit (e.g. L, kWh, pkm, room-night)")
    
    # Calculated greenhouse emissions in Metric Tonnes of CO2 equivalent
    co2e_emissions_t = models.DecimalField(max_digits=15, decimal_places=6, help_text="t CO2e calculated")
    
    location = models.CharField(max_length=255, help_text="Location code, facility or region name")
    date_start = models.DateField(help_text="Activity period start date")
    date_end = models.DateField(help_text="Activity period end date")
    
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='PENDING')
    flag_reason = models.TextField(blank=True, null=True, help_text="Why the anomaly checker flagged this row")
    
    is_locked = models.BooleanField(default=False, help_text="Locks the record against modifications during audit periods")
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_records')
    approved_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.category} Scope {self.scope} - {self.co2e_emissions_t:.3f} tCO2e ({self.status})"

class AuditTrail(models.Model):
    ACTION_CHOICES = [
        ('INGEST', 'Ingested & Normalized'),
        ('EDIT', 'Data Overridden / Corrected'),
        ('APPROVE', 'Record Approved'),
        ('REJECT', 'Record Rejected'),
        ('LOCK', 'Reporting Period Locked'),
    ]

    normalized_record = models.ForeignKey(NormalizedRecord, on_delete=models.CASCADE, related_name='audit_trails')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action_type = models.CharField(max_length=15, choices=ACTION_CHOICES)
    changed_fields = models.JSONField(blank=True, null=True, help_text="Audit logs of edits: {'field': {'old': x, 'new': y}}")
    comment = models.TextField(help_text="Auditable explanation for override, rejection, or sign-off")
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        user_name = self.user.username if self.user else "System"
        return f"{self.action_type} by {user_name} on {self.timestamp.strftime('%Y-%m-%d %H:%M')}"

class EmissionFactor(models.Model):
    category = models.CharField(max_length=100, help_text="e.g. Fuel, Electricity, Flights, Hotels, Ground Transport")
    subcategory = models.CharField(max_length=100, help_text="e.g. Diesel, Natural Gas, Short-haul Business, Hotel-DE")
    value = models.DecimalField(max_digits=12, decimal_places=6, help_text="Factor rate")
    unit = models.CharField(max_length=50, help_text="Emission factor unit denominator (e.g. kg CO2e/L, kg CO2e/pkm, kg CO2e/room-night)")
    location = models.CharField(max_length=100, default='GLOBAL', help_text="Target geographic region (e.g. DE, US, IN, GLOBAL)")
    year = models.IntegerField(default=2026)
    source_reference = models.CharField(max_length=255, blank=True, null=True, help_text="e.g. GHG Protocol, EPA 2026, DEFRA 2026")

    class Meta:
        unique_together = ('category', 'subcategory', 'location', 'year')

    def __str__(self):
        return f"{self.subcategory} ({self.location}, {self.year}): {self.value} {self.unit}"
