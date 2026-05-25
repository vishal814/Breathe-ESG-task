import csv
import json
import math
from datetime import datetime, date
from decimal import Decimal
from django.db import transaction, models
from django.utils import timezone
from esg_app.models import (
    Client, IngestionSource, RawRecord, NormalizedRecord, 
    AuditTrail, LocationMapping, AirportCode, EmissionFactor
)

def calculate_haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great-circle distance between two points on the Earth 
    in kilometers using the Haversine formula.
    """
    # Convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [float(lat1), float(lon1), float(lat2), float(lon2)])
    
    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    r = 6371.0 # Radius of earth in kilometers
    return r * c

def parse_date(date_str):
    """
    Tries to parse date string in multiple standard formats.
    """
    if not date_str:
        return None
    date_str = str(date_str).strip()
    
    # Formats: 'YYYYMMDD', 'DD.MM.YYYY', 'YYYY-MM-DD', 'MM/DD/YYYY'
    formats = ['%Y%m%d', '%d.%m.%Y', '%Y-%m-%d', '%m/%d/%Y']
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unable to parse date: {date_str}")

def normalize_unit(unit_str):
    """
    Maps varying units into standardized ESG units.
    """
    if not unit_str:
        return ""
    u = str(unit_str).strip().upper()
    
    # Liters
    if u in ['L', 'LIT', 'LITER', 'LITERS', 'LITRE', 'LITRES']:
        return 'L'
    # Kilograms
    elif u in ['KG', 'KILOGRAM', 'KILOGRAMS', 'KILO', 'KILOGRAMM']:
        return 'KG'
    # Cubic meters
    elif u in ['M3', 'CUBIC METER', 'CUBIC METERS', 'KUBIKMETER']:
        return 'M3'
    # Kilowatt-hours
    elif u in ['KWH', 'KILOWATT HOUR', 'KILOWATT HOURS', 'KILOWATTHOUR']:
        return 'kWh'
    # Megawatt-hours
    elif u in ['MWH', 'MEGAWATT HOUR', 'MEGAWATT HOURS']:
        return 'MWh'
    # Passenger-kilometers
    elif u in ['PKM', 'PASSENGER-KM', 'PASSENGER-KILOMETERS']:
        return 'pkm'
    # Room-nights
    elif u in ['ROOM-NIGHT', 'ROOM-NIGHTS', 'ROOM NIGHT', 'ROOM NIGHTS', 'NIGHTS']:
        return 'room-night'
    return u

@transaction.atomic
def ingest_and_process_sap(client_id, file_name, file_content):
    """
    Ingests a raw SAP CSV file, creates RawRecords, and runs normalization rules.
    """
    client = Client.objects.get(id=client_id)
    
    # Create Ingestion Source
    source = IngestionSource.objects.create(
        client=client,
        name=f"SAP Ingestion: {file_name}",
        source_type='SAP',
        file_name=file_name,
        raw_payload=file_content
    )
    
    # Read CSV
    lines = file_content.strip().split('\n')
    reader = csv.DictReader(lines)
    
    # Clean headers (strip spaces and convert to uppercase)
    reader.fieldnames = [f.strip().upper() if f else '' for f in reader.fieldnames]
    
    # SAP column headers lookups
    # Can be German (WERKS, BUDAT, MENGE, MEINS, DMBTR, WAERS, MAKTX) or English equivalents
    werks_col = next((col for col in ['WERKS', 'PLANT', 'PLANT_CODE'] if col in reader.fieldnames), None)
    budat_col = next((col for col in ['BUDAT', 'POSTING_DATE', 'DATE'] if col in reader.fieldnames), None)
    menge_col = next((col for col in ['MENGE', 'QUANTITY', 'QTY'] if col in reader.fieldnames), None)
    meins_col = next((col for col in ['MEINS', 'UNIT', 'UOM'] if col in reader.fieldnames), None)
    dmbtr_col = next((col for col in ['DMBTR', 'AMOUNT', 'COST'] if col in reader.fieldnames), None)
    waers_col = next((col for col in ['WAERS', 'CURRENCY'] if col in reader.fieldnames), None)
    maktx_col = next((col for col in ['MAKTX', 'MATERIAL_DESC', 'DESCRIPTION'] if col in reader.fieldnames), None)
    ebeln_col = next((col for col in ['EBELN', 'PO_NUMBER'] if col in reader.fieldnames), None)
    
    if not all([werks_col, budat_col, menge_col, maktx_col]):
        source.status = 'FAILED'
        source.save()
        raise ValueError(f"SAP CSV is missing required columns. Headers found: {reader.fieldnames}")
        
    records_processed = 0
    
    for row in reader:
        # Create raw record
        raw_rec = RawRecord.objects.create(
            client=client,
            source=source,
            raw_data=row
        )
        
        # Parse fields
        werks = row.get(werks_col, '').strip()
        budat_str = row.get(budat_col, '').strip()
        menge_str = row.get(menge_col, '').strip()
        meins = row.get(meins_col, '').strip() if meins_col else 'L'
        dmbtr_str = row.get(dmbtr_col, '0').strip() if dmbtr_col else '0'
        waers = row.get(waers_col, 'EUR').strip() if waers_col else 'EUR'
        maktx = row.get(maktx_col, '').strip()
        ebeln = row.get(ebeln_col, '').strip() if ebeln_col else ''
        
        errors = []
        status = 'PENDING'
        
        # 1. Parse Date
        parsed_date = None
        try:
            parsed_date = parse_date(budat_str)
        except Exception as e:
            errors.append(f"Invalid Date: {budat_str}. Error: {str(e)}")
            
        # 2. Parse Numeric values
        qty = Decimal('0')
        try:
            qty = Decimal(menge_str)
            if qty <= 0:
                errors.append(f"Zero or negative quantity: {menge_str}")
        except Exception:
            errors.append(f"Non-numeric quantity: {menge_str}")
            
        cost = Decimal('0')
        try:
            cost = Decimal(dmbtr_str)
            if cost < 0:
                errors.append(f"Negative cost/amount: {dmbtr_str}")
        except Exception:
            errors.append(f"Non-numeric cost: {dmbtr_str}")
            
        # 3. Lookup plant mapping
        location = None
        location_obj = None
        if werks:
            location_obj = LocationMapping.objects.filter(client=client, code=werks).first()
            if not location_obj:
                errors.append(f"Plant code '{werks}' not found in location mappings")
            else:
                location = location_obj.name
        else:
            errors.append("Plant code is empty")
            
        # 4. Standardize Unit
        std_unit = normalize_unit(meins)
        
        # 5. Look up emission factor for material description
        # We search category='Fuel'
        material_search = maktx.lower()
        ef_subcategory = None
        if 'diesel' in material_search or 'kraftstoff' in material_search:
            ef_subcategory = 'Diesel'
        elif 'gas' in material_search or 'erdgas' in material_search:
            ef_subcategory = 'Natural Gas'
        elif 'oil' in material_search or 'heiz' in material_search:
            ef_subcategory = 'Heating Oil'
        else:
            errors.append(f"No emission factor mapped for material description: '{maktx}'")
            
        ef_value = Decimal('0')
        if ef_subcategory:
            # Get emission factor
            ef_obj = EmissionFactor.objects.filter(category='Fuel', subcategory=ef_subcategory, year=2026).first()
            if not ef_obj:
                errors.append(f"Emission factor for {ef_subcategory} not found in database for 2026")
            else:
                ef_value = ef_obj.value
                # Unit conversion if needed (e.g. if SAP reports in different unit than EF)
                if std_unit != ef_obj.unit.split('/')[-1].strip().upper():
                    # Handle basic conversion or flag mismatch
                    pass
        
        # Calculate carbon emissions: Value * Factor / 1000 (tonnes CO2e)
        co2e = (qty * ef_value) / Decimal('1000')
        
        if errors:
            status = 'FLAGGED'
            raw_rec.status = 'FAILED'
            raw_rec.validation_errors = "\n".join(errors)
        else:
            raw_rec.status = 'PROCESSED'
            
        raw_rec.save()
        
        # Save normalized record
        norm_rec = NormalizedRecord.objects.create(
            client=client,
            raw_record=raw_rec,
            scope=1, # SAP Fuel procurement is Scope 1
            category="Fuel",
            description=f"SAP Procurement - PO {ebeln} - {maktx}",
            activity_value=qty,
            activity_unit=std_unit,
            co2e_emissions_t=co2e,
            location=location or f"Plant {werks}",
            date_start=parsed_date or date.today(),
            date_end=parsed_date or date.today(),
            status=status,
            flag_reason="\n".join(errors) if errors else None
        )
        
        # Write initial Audit Trail
        AuditTrail.objects.create(
            normalized_record=norm_rec,
            action_type='INGEST',
            comment=f"Ingested from SAP CSV row. Status: {status}." + (f" Anomalies: {'; '.join(errors)}" if errors else "")
        )
        
        records_processed += 1
        
    source.status = 'PROCESSED'
    source.save()
    return records_processed

@transaction.atomic
def ingest_and_process_utility(client_id, file_name, file_content):
    """
    Ingests a raw electricity utility CSV, verifies meter math, and pro-rates usage.
    """
    client = Client.objects.get(id=client_id)
    
    source = IngestionSource.objects.create(
        client=client,
        name=f"Utility Ingestion: {file_name}",
        source_type='UTILITY',
        file_name=file_name,
        raw_payload=file_content
    )
    
    lines = file_content.strip().split('\n')
    reader = csv.DictReader(lines)
    
    # Strip spaces and standardize headers
    reader.fieldnames = [f.strip() if f else '' for f in reader.fieldnames]
    
    required_cols = ['Facility ID', 'Billing Period Start', 'Billing Period End', 'Consumption (kWh)']
    if not all(col in reader.fieldnames for col in required_cols):
        source.status = 'FAILED'
        source.save()
        raise ValueError(f"Utility CSV is missing required columns. Headers: {reader.fieldnames}")
        
    records_processed = 0
    
    for row in reader:
        raw_rec = RawRecord.objects.create(
            client=client,
            source=source,
            raw_data=row
        )
        
        facility_id = row.get('Facility ID', '').strip()
        start_str = row.get('Billing Period Start', '').strip()
        end_str = row.get('Billing Period End', '').strip()
        consumption_str = row.get('Consumption (kWh)', '').strip()
        
        prev_reading_str = row.get('Previous Reading', '').strip()
        curr_reading_str = row.get('Current Reading', '').strip()
        multiplier_str = row.get('Multiplier', '1').strip()
        
        errors = []
        status = 'PENDING'
        
        # 1. Parse Dates
        start_date = None
        end_date = None
        try:
            start_date = parse_date(start_str)
            end_date = parse_date(end_str)
            if start_date and end_date:
                if end_date < start_date:
                    errors.append(f"End date ({end_str}) is before start date ({start_str})")
                else:
                    duration_days = (end_date - start_date).days + 1
                    if duration_days < 25 or duration_days > 45:
                        errors.append(f"Irregular billing period duration: {duration_days} days (expected 25-45)")
        except Exception as e:
            errors.append(f"Invalid date format in period: {start_str} to {end_str}. Error: {str(e)}")
            
        # 2. Parse Consumption
        consumption = Decimal('0')
        try:
            consumption = Decimal(consumption_str)
            if consumption <= 0:
                errors.append(f"Zero or negative consumption: {consumption_str}")
        except Exception:
            errors.append(f"Non-numeric consumption: {consumption_str}")
            
        # 3. Verify Reading Math if available
        if prev_reading_str and curr_reading_str:
            try:
                prev_read = Decimal(prev_reading_str)
                curr_read = Decimal(curr_reading_str)
                mult = Decimal(multiplier_str or '1')
                
                calculated_cons = (curr_read - prev_read) * mult
                if abs(calculated_cons - consumption) > (consumption * Decimal('0.01')):
                    errors.append(f"Meter reading math mismatch. Current ({curr_read}) - Previous ({prev_read}) * Multiplier ({mult}) = {calculated_cons} kWh, but reported consumption is {consumption} kWh")
            except Exception as e:
                errors.append(f"Error validating meter reading values: {str(e)}")
                
        # 4. Lookup facility
        location_obj = None
        grid_factor = Decimal('0.40') # Global default fallback
        if facility_id:
            location_obj = LocationMapping.objects.filter(client=client, code=facility_id).first()
            if not location_obj:
                errors.append(f"Facility ID '{facility_id}' not found in location mapping")
            else:
                grid_factor = location_obj.grid_emission_factor
        else:
            errors.append("Facility ID is empty")
            
        # 5. Outlier Detection
        # Check if this consumption is an outlier compared to the facility's average historical approved values
        if location_obj and consumption > 0:
            approved_avg = NormalizedRecord.objects.filter(
                client=client,
                location=location_obj.name,
                category="Electricity",
                status="APPROVED"
            ).aggregate(avg_cons=models.Avg('activity_value'))['avg_cons']
            
            if approved_avg and consumption > (Decimal(approved_avg) * Decimal('3.0')):
                errors.append(f"High consumption anomaly. Ingested {consumption} kWh is > 3x average approved monthly consumption ({approved_avg:.1f} kWh)")
                
        # Calculate carbon emissions
        co2e = (consumption * grid_factor) / Decimal('1000') # tCO2e
        
        if errors:
            status = 'FLAGGED'
            raw_rec.status = 'FAILED'
            raw_rec.validation_errors = "\n".join(errors)
        else:
            raw_rec.status = 'PROCESSED'
        raw_rec.save()
        
        # 6. Time Pro-rating splitting across calendar months
        # If dates are valid, let's split this record by calendar months
        if start_date and end_date and not errors:
            # We will split consumption proportionally into the months
            months_distribution = []
            curr = start_date
            total_days = (end_date - start_date).days + 1
            
            while curr <= end_date:
                # Find end of current month or billing period end
                year = curr.year
                month = curr.month
                
                # End of current month
                if month == 12:
                    next_month = date(year + 1, 1, 1)
                else:
                    next_month = date(year, month + 1, 1)
                    
                month_end = min(next_month - timezone.timedelta(days=1), end_date)
                days_in_month = (month_end - curr).days + 1
                
                months_distribution.append({
                    'month_start': curr,
                    'month_end': month_end,
                    'days': days_in_month,
                    'month_label': curr.strftime('%B %Y')
                })
                curr = month_end + timezone.timedelta(days=1)
                
            # Create sub-records for each month
            for dist in months_distribution:
                share = Decimal(dist['days']) / Decimal(total_days)
                sub_consumption = consumption * share
                sub_co2e = co2e * share
                
                norm_rec = NormalizedRecord.objects.create(
                    client=client,
                    raw_record=raw_rec,
                    scope=2, # Electricity is Scope 2
                    category="Electricity",
                    description=f"Electricity Utility - Meter {row.get('Meter Number','')} ({dist['month_label']})",
                    activity_value=sub_consumption,
                    activity_unit="kWh",
                    co2e_emissions_t=sub_co2e,
                    location=location_obj.name if location_obj else f"Facility {facility_id}",
                    date_start=dist['month_start'],
                    date_end=dist['month_end'],
                    status='PENDING',
                )
                
                AuditTrail.objects.create(
                    normalized_record=norm_rec,
                    action_type='INGEST',
                    comment=f"Ingested and pro-rated for calendar month {dist['month_label']}. Shared {dist['days']}/{total_days} days."
                )
        else:
            # If flagged or dates are invalid, we create a single non-split pending/flagged record
            norm_rec = NormalizedRecord.objects.create(
                client=client,
                raw_record=raw_rec,
                scope=2,
                category="Electricity",
                description=f"Electricity Utility - Meter {row.get('Meter Number','')}",
                activity_value=consumption,
                activity_unit="kWh",
                co2e_emissions_t=co2e,
                location=location_obj.name if location_obj else f"Facility {facility_id}",
                date_start=start_date or date.today(),
                date_end=end_date or date.today(),
                status=status,
                flag_reason="\n".join(errors) if errors else None
            )
            
            AuditTrail.objects.create(
                normalized_record=norm_rec,
                action_type='INGEST',
                comment=f"Ingested from Utility CSV. Status: {status}." + (f" Anomalies: {'; '.join(errors)}" if errors else "")
            )
            
        records_processed += 1
        
    source.status = 'PROCESSED'
    source.save()
    return records_processed

@transaction.atomic
def ingest_and_process_travel(client_id, source_name, travel_records):
    """
    Ingests travel bookings (JSON array format), resolves airport codes, 
    calculates great-circle distance (Haversine), and maps emission factors.
    """
    client = Client.objects.get(id=client_id)
    
    # Store raw json payload as a string
    raw_payload_str = json.dumps(travel_records, indent=2)
    source = IngestionSource.objects.create(
        client=client,
        name=source_name,
        source_type='TRAVEL',
        file_name=None,
        raw_payload=raw_payload_str
    )
    
    records_processed = 0
    
    for row in travel_records:
        raw_rec = RawRecord.objects.create(
            client=client,
            source=source,
            raw_data=row
        )
        
        booking_id = row.get('booking_id', '').strip()
        trip_type = row.get('trip_type', '').strip().upper() # FLIGHT, HOTEL, GROUND
        booking_date_str = row.get('booking_date', '').strip()
        cost_str = str(row.get('cost', '0')).strip()
        currency = row.get('currency', 'USD').strip()
        details = row.get('details', {})
        
        errors = []
        status = 'PENDING'
        
        # 1. Parse Date
        parsed_date = None
        try:
            parsed_date = parse_date(booking_date_str)
        except Exception as e:
            errors.append(f"Invalid Date: {booking_date_str}. Error: {str(e)}")
            
        # 2. Parse Cost
        cost = Decimal('0')
        try:
            cost = Decimal(cost_str)
            if cost < 0:
                errors.append(f"Negative cost/amount: {cost_str}")
        except Exception:
            errors.append(f"Non-numeric cost: {cost_str}")
            
        # Variables to compute
        scope = 3 # Travel is Scope 3
        category = "Travel"
        description = f"Travel Booking {booking_id} - {trip_type}"
        activity_val = Decimal('0')
        activity_unit = ""
        co2e = Decimal('0')
        location = ""
        
        if trip_type == 'FLIGHT':
            category = "Flights"
            origin = details.get('origin', '').strip().upper()
            destination = details.get('destination', '').strip().upper()
            cabin = details.get('cabin_class', 'Economy').strip()
            
            if not origin or not destination:
                errors.append("Flight booking is missing origin or destination airport codes")
            else:
                location = f"{origin} to {destination}"
                # Get airport coordinates
                ap_orig = AirportCode.objects.filter(code=origin).first()
                ap_dest = AirportCode.objects.filter(code=destination).first()
                
                if not ap_orig:
                    errors.append(f"Airport code '{origin}' not found in airport coordinate database")
                if not ap_dest:
                    errors.append(f"Airport code '{destination}' not found in airport coordinate database")
                    
                if ap_orig and ap_dest:
                    # Calculate distance
                    dist_km = calculate_haversine_distance(
                        ap_orig.latitude, ap_orig.longitude, 
                        ap_dest.latitude, ap_dest.longitude
                    )
                    
                    # Convert to passenger-kilometers (pkm)
                    activity_val = Decimal(f"{dist_km:.2f}")
                    activity_unit = "pkm"
                    
                    # Flight category: short-haul (<1600km) vs long-haul
                    is_short_haul = dist_km < 1600.0
                    haul_label = "Short-haul" if is_short_haul else "Long-haul"
                    
                    # Find EF subcategory: e.g. "Economy Long-haul"
                    cabin_label = "Economy" if "ECON" in cabin.upper() else "Business"
                    ef_subcategory = f"{cabin_label} {haul_label}"
                    
                    ef_obj = EmissionFactor.objects.filter(category='Flights', subcategory=ef_subcategory, year=2026).first()
                    if not ef_obj:
                        errors.append(f"Emission factor for '{ef_subcategory}' not found in database for 2026")
                    else:
                        co2e = (activity_val * ef_obj.value) / Decimal('1000') # tCO2e
                        
        elif trip_type == 'HOTEL':
            category = "Hotels"
            hotel_name = details.get('hotel_name', '').strip()
            city = details.get('city', '').strip()
            country = details.get('country', '').strip().upper()
            room_nights_str = str(details.get('room_nights', '0')).strip()
            
            location = f"{hotel_name}, {city} ({country})"
            
            room_nights = Decimal('0')
            try:
                room_nights = Decimal(room_nights_str)
                if room_nights <= 0:
                    errors.append(f"Zero or negative room nights: {room_nights_str}")
            except Exception:
                errors.append(f"Non-numeric room nights: {room_nights_str}")
                
            activity_val = room_nights
            activity_unit = "room-night"
            
            # Lookup country-specific hotel factor, default to GLOBAL or US if not found
            ef_subcategory = f"Hotel Stay {country}"
            ef_obj = EmissionFactor.objects.filter(category='Hotels', subcategory=ef_subcategory, year=2026).first()
            if not ef_obj:
                # Fall back to US stay as default or first stay factor
                ef_obj = EmissionFactor.objects.filter(category='Hotels', subcategory__contains='US', year=2026).first()
                
            if not ef_obj:
                errors.append("Hotel Stay emission factors not found in database")
            else:
                co2e = (activity_val * ef_obj.value) / Decimal('1000') # tCO2e
                
        elif trip_type == 'GROUND':
            category = "Ground Transport"
            vehicle = details.get('vehicle_type', 'Taxi').strip()
            dist_km_str = str(details.get('distance_km', '0')).strip()
            
            location = f"Ground - {vehicle}"
            
            dist_km = Decimal('0')
            try:
                dist_km = Decimal(dist_km_str)
                if dist_km <= 0:
                    errors.append(f"Zero or negative distance: {dist_km_str}")
            except Exception:
                errors.append(f"Non-numeric distance: {dist_km_str}")
                
            activity_val = dist_km
            activity_unit = "pkm"
            
            # Lookup ground factor
            ef_subcategory = vehicle.capitalize() # Taxi, Train etc.
            ef_obj = EmissionFactor.objects.filter(category='Ground Transport', subcategory=ef_subcategory, year=2026).first()
            if not ef_obj:
                errors.append(f"Ground factor for '{ef_subcategory}' not found in database")
            else:
                co2e = (activity_val * ef_obj.value) / Decimal('1000')
                
        else:
            errors.append(f"Unknown trip type: {trip_type}")
            
        if errors:
            status = 'FLAGGED'
            raw_rec.status = 'FAILED'
            raw_rec.validation_errors = "\n".join(errors)
        else:
            raw_rec.status = 'PROCESSED'
        raw_rec.save()
        
        # Save normalized record
        norm_rec = NormalizedRecord.objects.create(
            client=client,
            raw_record=raw_rec,
            scope=scope,
            category=category,
            description=description,
            activity_value=activity_val,
            activity_unit=activity_unit,
            co2e_emissions_t=co2e,
            location=location or "Corporate Travel",
            date_start=parsed_date or date.today(),
            date_end=parsed_date or date.today(),
            status=status,
            flag_reason="\n".join(errors) if errors else None
        )
        
        AuditTrail.objects.create(
            normalized_record=norm_rec,
            action_type='INGEST',
            comment=f"Ingested from Corporate Travel data. Status: {status}." + (f" Anomalies: {'; '.join(errors)}" if errors else "")
        )
        
        records_processed += 1
        
    source.status = 'PROCESSED'
    source.save()
    return records_processed
