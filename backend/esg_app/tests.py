from django.test import TestCase
from decimal import Decimal
from datetime import date
from esg_app.models import Client, LocationMapping, AirportCode, EmissionFactor, NormalizedRecord, RawRecord
from esg_app.normalization_engine import (
    calculate_haversine_distance, 
    ingest_and_process_sap, 
    ingest_and_process_utility, 
    ingest_and_process_travel
)

class ESGNormalizationEngineTests(TestCase):
    def setUp(self):
        # 1. Create client
        self.client_obj = Client.objects.create(name="Acme Test Corp")
        
        # 2. Create Location Mappings
        self.loc_berlin = LocationMapping.objects.create(
            client=self.client_obj,
            code="1000",
            name="Berlin Facility",
            region="DE",
            grid_emission_factor=Decimal("0.350")
        )
        self.loc_hq = LocationMapping.objects.create(
            client=self.client_obj,
            code="FAC-01",
            name="New York HQ",
            region="US-NY",
            grid_emission_factor=Decimal("0.280")
        )
        
        # 3. Create Airport Coordinates
        self.jfk = AirportCode.objects.create(
            code="JFK", city="New York", country="US",
            latitude=Decimal("40.6413"), longitude=Decimal("-73.7781")
        )
        self.lhr = AirportCode.objects.create(
            code="LHR", city="London", country="GB",
            latitude=Decimal("51.4700"), longitude=Decimal("-0.4543")
        )
        
        # 4. Create Emission Factors
        self.ef_diesel = EmissionFactor.objects.create(
            category="Fuel", subcategory="Diesel", value=Decimal("2.68"),
            unit="kg CO2e/L", location="GLOBAL", year=2026, source_reference="EPA"
        )
        self.ef_flight_biz = EmissionFactor.objects.create(
            category="Flights", subcategory="Business Long-haul", value=Decimal("0.29"),
            unit="kg CO2e/pkm", location="GLOBAL", year=2026, source_reference="DEFRA"
        )
        self.ef_hotel_de = EmissionFactor.objects.create(
            category="Hotels", subcategory="Hotel Stay DE", value=Decimal("15.4"),
            unit="kg CO2e/room-night", location="DE", year=2026, source_reference="DEFRA"
        )

    def test_haversine_distance(self):
        # Distance from JFK to LHR should be roughly 5570 km
        dist = calculate_haversine_distance(
            self.jfk.latitude, self.jfk.longitude,
            self.lhr.latitude, self.lhr.longitude
        )
        self.assertGreater(dist, 5500)
        self.assertLess(dist, 5600)

    def test_sap_ingestion_success(self):
        # German headers: WERKS, BUDAT, MENGE, MEINS, DMBTR, WAERS, MAKTX, EBELN
        sap_csv = (
            "WERKS,BUDAT,MENGE,MEINS,DMBTR,WAERS,MAKTX,EBELN\n"
            "1000,20260515,1000,L,2500,EUR,Diesel Kraftstoff,PO-001\n"
        )
        
        rows = ingest_and_process_sap(self.client_obj.id, "sap_test.csv", sap_csv)
        self.assertEqual(rows, 1)
        
        # Check raw record
        raw_rec = RawRecord.objects.first()
        self.assertEqual(raw_rec.status, "PROCESSED")
        
        # Check normalized record
        norm_rec = NormalizedRecord.objects.first()
        self.assertEqual(norm_rec.status, "PENDING")
        self.assertEqual(norm_rec.scope, 1)
        self.assertEqual(norm_rec.category, "Fuel")
        self.assertEqual(norm_rec.location, "Berlin Facility")
        self.assertEqual(norm_rec.activity_value, Decimal("1000.0000"))
        self.assertEqual(norm_rec.activity_unit, "L")
        # CO2e calculation: 1000 * 2.68 / 1000 = 2.68 tonnes
        self.assertEqual(norm_rec.co2e_emissions_t, Decimal("2.680000"))
        self.assertEqual(norm_rec.date_start, date(2026, 5, 15))

    def test_sap_ingestion_flagging(self):
        # 1. Invalid plant code
        # 2. Negative quantity
        sap_csv = (
            "WERKS,BUDAT,MENGE,MEINS,DMBTR,WAERS,MAKTX,EBELN\n"
            "9999,20260515,-500,L,2500,EUR,Diesel Kraftstoff,PO-002\n"
        )
        
        ingest_and_process_sap(self.client_obj.id, "sap_flagged.csv", sap_csv)
        
        raw_rec = RawRecord.objects.first()
        self.assertEqual(raw_rec.status, "FAILED")
        self.assertIn("Plant code '9999' not found in location mappings", raw_rec.validation_errors)
        self.assertIn("Zero or negative quantity: -500", raw_rec.validation_errors)
        
        norm_rec = NormalizedRecord.objects.first()
        self.assertEqual(norm_rec.status, "FLAGGED")
        self.assertIn("Plant code '9999' not found", norm_rec.flag_reason)

    def test_utility_prorating_split(self):
        # Spans April 15 to May 14 (30 days total: 16 days in April, 14 days in May)
        # Total consumption = 3000 kWh
        # April share: 3000 * 16 / 30 = 1600 kWh
        # May share: 3000 * 14 / 30 = 1400 kWh
        utility_csv = (
            "Facility ID,Billing Period Start,Billing Period End,Previous Reading,Current Reading,Multiplier,Consumption (kWh),Total Amount Due,Currency\n"
            "FAC-01,2026-04-15,2026-05-14,10000,13000,1.0,3000,600,USD\n"
        )
        
        rows = ingest_and_process_utility(self.client_obj.id, "utility_test.csv", utility_csv)
        self.assertEqual(rows, 1)
        
        # Check raw record
        raw_rec = RawRecord.objects.first()
        self.assertEqual(raw_rec.status, "PROCESSED")
        
        # Because of calendar month splitting, it should create 2 normalized records
        norm_recs = NormalizedRecord.objects.filter(raw_record=raw_rec).order_by('date_start')
        self.assertEqual(norm_recs.count(), 2)
        
        # April Record
        rec_april = norm_recs[0]
        self.assertEqual(rec_april.date_start, date(2026, 4, 15))
        self.assertEqual(rec_april.date_end, date(2026, 4, 30))
        self.assertEqual(rec_april.activity_value, Decimal("1600.0000")) # 3000 * 16 / 30
        # Emissions: 1600 * 0.28 (grid factor) / 1000 = 0.448 tonnes
        self.assertEqual(rec_april.co2e_emissions_t, Decimal("0.448000"))
        
        # May Record
        rec_may = norm_recs[1]
        self.assertEqual(rec_may.date_start, date(2026, 5, 1))
        self.assertEqual(rec_may.date_end, date(2026, 5, 14))
        self.assertEqual(rec_may.activity_value, Decimal("1400.0000")) # 3000 * 14 / 30
        # Emissions: 1400 * 0.28 / 1000 = 0.392 tonnes
        self.assertEqual(rec_may.co2e_emissions_t, Decimal("0.392000"))

    def test_utility_meter_math_flagging(self):
        # Meter reading math: (12000 - 10000) * 1.0 = 2000 kWh. But reported consumption is 5000 kWh. This should be flagged!
        utility_csv = (
            "Facility ID,Billing Period Start,Billing Period End,Previous Reading,Current Reading,Multiplier,Consumption (kWh),Total Amount Due,Currency\n"
            "FAC-01,2026-05-01,2026-05-30,10000,12000,1.0,5000,1000,USD\n"
        )
        
        ingest_and_process_utility(self.client_obj.id, "utility_bad_math.csv", utility_csv)
        
        raw_rec = RawRecord.objects.first()
        self.assertEqual(raw_rec.status, "FAILED")
        self.assertIn("Meter reading math mismatch", raw_rec.validation_errors)
        
        norm_rec = NormalizedRecord.objects.first()
        self.assertEqual(norm_rec.status, "FLAGGED")

    def test_travel_ingestion_flight(self):
        travel_records = [
            {
                "booking_id": "TRV-001",
                "trip_type": "FLIGHT",
                "booking_date": "2026-05-20",
                "cost": 1500,
                "currency": "USD",
                "details": {
                    "origin": "JFK",
                    "destination": "LHR",
                    "cabin_class": "Business"
                }
            }
        ]
        
        rows = ingest_and_process_travel(self.client_obj.id, "Travel API Call", travel_records)
        self.assertEqual(rows, 1)
        
        raw_rec = RawRecord.objects.first()
        self.assertEqual(raw_rec.status, "PROCESSED")
        
        norm_rec = NormalizedRecord.objects.first()
        self.assertEqual(norm_rec.status, "PENDING")
        self.assertEqual(norm_rec.scope, 3)
        self.assertEqual(norm_rec.category, "Flights")
        self.assertEqual(norm_rec.activity_unit, "pkm")
        
        # Verify emissions are calculated based on ~5570 km distance and Business Long-haul EF (0.29)
        self.assertGreater(norm_rec.co2e_emissions_t, Decimal("1.6")) # 5570 * 0.29 / 1000 ~ 1.61 tonnes
        self.assertLess(norm_rec.co2e_emissions_t, Decimal("1.7"))
