from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from esg_app.models import Client, LocationMapping, AirportCode, EmissionFactor
from decimal import Decimal

class Command(BaseCommand):
    help = 'Seeds initial default data for ESG App'

    def handle(self, *args, **options):
        self.stdout.write("Seeding data...")

        # 1. Create Default Users (Analyst and Auditor)
        admin_user, created = User.objects.get_or_create(username='admin', email='admin@breatheesg.com')
        if created:
            admin_user.set_password('admin123')
            admin_user.is_superuser = True
            admin_user.is_staff = True
            admin_user.save()
            self.stdout.write("Created superuser 'admin' (password: admin123)")

        analyst, created = User.objects.get_or_create(username='analyst', email='analyst@breatheesg.com')
        if created:
            analyst.set_password('analyst123')
            analyst.save()
            self.stdout.write("Created analyst user 'analyst' (password: analyst123)")

        auditor, created = User.objects.get_or_create(username='auditor', email='auditor@breatheesg.com')
        if created:
            auditor.set_password('auditor123')
            auditor.save()
            self.stdout.write("Created auditor user 'auditor' (password: auditor123)")

        # 2. Create Clients
        acme, _ = Client.objects.get_or_create(name="Acme Corporation")
        globex, _ = Client.objects.get_or_create(name="Globex Industries")
        self.stdout.write("Created Clients: Acme Corporation, Globex Industries")

        # 3. Create Location Mappings for Acme Corp
        LocationMapping.objects.get_or_create(
            client=acme,
            code="1000",
            defaults={"name": "Acme Berlin Refinery", "region": "DE", "grid_emission_factor": Decimal("0.352000")}
        )
        LocationMapping.objects.get_or_create(
            client=acme,
            code="1100",
            defaults={"name": "Acme Detroit Assembly", "region": "US-MI", "grid_emission_factor": Decimal("0.455000")}
        )
        LocationMapping.objects.get_or_create(
            client=acme,
            code="2000",
            defaults={"name": "Acme Chennai Foundry", "region": "IN", "grid_emission_factor": Decimal("0.718000")}
        )
        LocationMapping.objects.get_or_create(
            client=acme,
            code="FAC-01",
            defaults={"name": "Acme HQ (New York)", "region": "US-NY", "grid_emission_factor": Decimal("0.285000")}
        )
        LocationMapping.objects.get_or_create(
            client=acme,
            code="FAC-02",
            defaults={"name": "Acme London Office", "region": "GB", "grid_emission_factor": Decimal("0.212000")}
        )
        
        # Location mappings for Globex Corp
        LocationMapping.objects.get_or_create(
            client=globex,
            code="1000",
            defaults={"name": "Globex Munich Warehouse", "region": "DE", "grid_emission_factor": Decimal("0.352000")}
        )
        LocationMapping.objects.get_or_create(
            client=globex,
            code="FAC-01",
            defaults={"name": "Globex SF HQ", "region": "US-CA", "grid_emission_factor": Decimal("0.224000")}
        )
        self.stdout.write("Created Location Mappings")

        # 4. Create Airport Coordinates
        airports = [
            ("JFK", "New York", "US", Decimal("40.641300"), Decimal("-73.778100")),
            ("LHR", "London", "GB", Decimal("51.470000"), Decimal("-0.454300")),
            ("CDG", "Paris", "FR", Decimal("49.009700"), Decimal("2.547900")),
            ("FRA", "Frankfurt", "DE", Decimal("50.037900"), Decimal("8.562200")),
            ("BLR", "Bengaluru", "IN", Decimal("13.198600"), Decimal("77.706600")),
            ("SIN", "Singapore", "SG", Decimal("1.364400"), Decimal("103.991500")),
            ("DXB", "Dubai", "AE", Decimal("25.253200"), Decimal("55.365700")),
            ("SFO", "San Francisco", "US", Decimal("37.621300"), Decimal("-122.379000")),
        ]
        for code, city, country, lat, lon in airports:
            AirportCode.objects.get_or_create(
                code=code,
                defaults={"city": city, "country": country, "latitude": lat, "longitude": lon}
            )
        self.stdout.write("Created Airport Codes")

        # 5. Create Emission Factors
        factors = [
            # Fuel / Procurement (Scope 1)
            ("Fuel", "Diesel", Decimal("2.68"), "kg CO2e/L", "GLOBAL", 2026, "EPA 2026"),
            ("Fuel", "Natural Gas", Decimal("2.03"), "kg CO2e/M3", "GLOBAL", 2026, "EPA 2026"),
            ("Fuel", "Heating Oil", Decimal("2.96"), "kg CO2e/L", "GLOBAL", 2026, "DEFRA 2026"),
            # Default Grid Factor (Scope 2 backup)
            ("Electricity", "Grid Factor", Decimal("0.40"), "kg CO2e/kWh", "GLOBAL", 2026, "IEA 2026"),
            # Flights (Scope 3) - short haul (<1600km) vs long haul (>1600km)
            ("Flights", "Economy Short-haul", Decimal("0.15"), "kg CO2e/pkm", "GLOBAL", 2026, "DEFRA 2026"),
            ("Flights", "Business Short-haul", Decimal("0.23"), "kg CO2e/pkm", "GLOBAL", 2026, "DEFRA 2026"),
            ("Flights", "Economy Long-haul", Decimal("0.10"), "kg CO2e/pkm", "GLOBAL", 2026, "DEFRA 2026"),
            ("Flights", "Business Long-haul", Decimal("0.29"), "kg CO2e/pkm", "GLOBAL", 2026, "DEFRA 2026"),
            # Hotels (Scope 3)
            ("Hotels", "Hotel Stay DE", Decimal("15.4"), "kg CO2e/room-night", "DE", 2026, "DEFRA 2026"),
            ("Hotels", "Hotel Stay US", Decimal("20.2"), "kg CO2e/room-night", "US", 2026, "DEFRA 2026"),
            ("Hotels", "Hotel Stay GB", Decimal("10.8"), "kg CO2e/room-night", "GB", 2026, "DEFRA 2026"),
            ("Hotels", "Hotel Stay IN", Decimal("35.1"), "kg CO2e/room-night", "IN", 2026, "DEFRA 2026"),
            ("Hotels", "Hotel Stay FR", Decimal("6.2"), "kg CO2e/room-night", "FR", 2026, "DEFRA 2026"),
            # Ground (Scope 3)
            ("Ground Transport", "Taxi", Decimal("0.18"), "kg CO2e/pkm", "GLOBAL", 2026, "DEFRA 2026"),
            ("Ground Transport", "Train", Decimal("0.04"), "kg CO2e/pkm", "GLOBAL", 2026, "DEFRA 2026"),
        ]
        for cat, subcat, val, unit, loc, yr, ref in factors:
            EmissionFactor.objects.get_or_create(
                category=cat, subcategory=subcat, location=loc, year=yr,
                defaults={"value": val, "unit": unit, "source_reference": ref}
            )
        self.stdout.write("Created Emission Factors")
        self.stdout.write("Seeding completed successfully!")
