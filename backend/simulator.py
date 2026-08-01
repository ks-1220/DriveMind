import numpy as np
import pandas as pd
from datetime import datetime, timedelta

def generate_fleet_data(num_vehicles=10, num_days=30, points_per_day=3):
    """
    Generates high-fidelity synthetic fleet data including:
    - Vehicle metadata
    - Sensor telemetry (OBD-II, CAN Bus, GPS) with normal and injected anomaly patterns
    - Maintenance history records
    - Warranty claims
    - Unstructured repair manuals and warranty policies
    """
    np.random.seed(42)
    
    # 1. Vehicles Metadata
    manufacturers = ["Volvo", "Freightliner", "Kenworth", "Peterbilt", "Mack"]
    models = {
        "Volvo": "VNL 860",
        "Freightliner": "Cascadia",
        "Kenworth": "T680",
        "Peterbilt": "Model 579",
        "Mack": "Anthem"
    }
    
    vehicles = []
    for i in range(num_vehicles):
        v_id = f"TRK-{400 + i * 27}"
        mfr = manufacturers[i % len(manufacturers)]
        model = models[mfr]
        year = int(np.random.choice([2020, 2021, 2022, 2023, 2024]))
        
        # Initial status (will update after telemetry assessment)
        status = "Healthy"
        if v_id in ["TRK-427", "TRK-454", "TRK-481"]: # Target anomaly vehicles
            status = "Warning"
            
        vehicles.append({
            "id": v_id,
            "manufacturer": mfr,
            "model": model,
            "year": year,
            "initial_status": status
        })
    
    df_vehicles = pd.DataFrame(vehicles)
    
    # 2. Telemetry Stream Simulation
    telemetry_records = []
    start_date = datetime.now() - timedelta(days=num_days)
    
    for idx, v in enumerate(vehicles):
        v_id = v["id"]
        mfr = v["manufacturer"]
        
        # Base sensor baselines
        base_temp = 190.0   # Coolant Temp in °F
        base_rpm = 1200.0   # Engine RPM
        base_oil = 50.0     # Oil Pressure in PSI
        base_load = 55.0    # Engine Load in %
        base_vib = 0.25     # Vibration in g
        base_volt = 13.9    # Battery/Alternator Voltage in V
        base_exh = 750.0    # Exhaust Gas Temperature (EGT) in °F
        
        for day in range(num_days):
            for p in range(points_per_day):
                timestamp = start_date + timedelta(days=day, hours=(p * (24 // points_per_day)))
                
                # Default normal behavior with noise
                temp = base_temp + np.random.normal(0, 3)
                rpm = base_rpm + np.random.normal(0, 100)
                oil = base_oil + np.random.normal(0, 2)
                load = base_load + np.random.uniform(-20, 20)
                vib = base_vib + np.random.uniform(-0.05, 0.05)
                volt = base_volt + np.random.normal(0, 0.05)
                exh = base_exh + load * 3 + np.random.normal(0, 15)  # EGT correlates with load
                
                # Injected anomalies for specific vehicles
                
                # A. TRK-427: Volvo - EGR Coolant leak leading to engine overheat
                # Starts around day 15, gets progressively worse, coolant temp rises under load, oil pressure drops
                if v_id == "TRK-427" and day >= 15:
                    severity = (day - 15) / (num_days - 15) # 0 to 1
                    temp += severity * 35.0  # Up to 225-235°F
                    exh += severity * 250.0  # EGT spikes
                    oil -= severity * 12.0   # Oil pressure drops as engine thins oil
                    # Anomaly trigger on load
                    if load > 65:
                        temp += 15.0  # Overheating spike
                
                # B. TRK-454: Freightliner - Turbocharger underboost
                # Starts day 18, vibration spikes, RPM fluctuates, exhaust temp rises due to rich fuel/air mix
                elif v_id == "TRK-454" and day >= 18:
                    severity = (day - 18) / (num_days - 18)
                    vib += severity * 1.2    # Severe vibration
                    exh += severity * 180.0  # EGT increase
                    oil -= severity * 5.0
                    load = min(95.0, load + severity * 15)  # Engine works harder for same output
                
                # C. TRK-481: Kenworth - Electrical system / Alternator decay
                # Rapid intermittent voltage drop
                elif v_id == "TRK-481" and day >= 20:
                    if day % 2 == 0 or day > 27:
                        volt -= np.random.uniform(1.2, 2.8) # Dips down to 11V-12V range
                        vib += np.random.uniform(0.1, 0.3)  # Alternator bearing issues
                
                telemetry_records.append({
                    "vehicle_id": v_id,
                    "timestamp": timestamp.isoformat(),
                    "coolant_temp": round(float(temp), 2),
                    "engine_rpm": round(float(rpm), 2),
                    "oil_pressure": round(float(oil), 2),
                    "engine_load": round(float(load), 2),
                    "vibration": round(float(vib), 3),
                    "voltage": round(float(volt), 2),
                    "exhaust_temp": round(float(exh), 2)
                })
                
    df_telemetry = pd.DataFrame(telemetry_records)
    
    # 3. Maintenance History
    maintenance_records = []
    m_id = 1
    
    # Seed standard preventative maintenance for all trucks
    for idx, v in enumerate(vehicles):
        v_id = v["id"]
        
        # Standard maintenance 3 months ago (not shown in current 30 day telemetry but in history)
        maintenance_records.append({
            "id": f"MNT-{m_id:04d}",
            "vehicle_id": v_id,
            "date": (start_date - timedelta(days=90)).strftime("%Y-%m-%d"),
            "component": "Engine Oil & Filter",
            "description": "Standard PM-A fleet service. Oil changed, filters replaced, fluid levels adjusted.",
            "cost": 350.00
        })
        m_id += 1
        
        # Brake pads
        if idx % 2 == 0:
            maintenance_records.append({
                "id": f"MNT-{m_id:04d}",
                "vehicle_id": v_id,
                "date": (start_date - timedelta(days=60)).strftime("%Y-%m-%d"),
                "component": "Brakes",
                "description": "Replaced front axle brake pads and inspected brake drums.",
                "cost": 650.00
            })
            m_id += 1
            
        # Recent maintenance within the 30-day window
        # TRK-427 had standard PM servicing, but it did not fix the internal EGR micro-leak
        if v_id == "TRK-427":
            maintenance_records.append({
                "id": f"MNT-{m_id:04d}",
                "vehicle_id": v_id,
                "date": (start_date + timedelta(days=10)).strftime("%Y-%m-%d"),
                "component": "Cooling System",
                "description": "Preventive maintenance. Flushed cooling system, pressure tested radiator cap. Checked OK.",
                "cost": 420.00
            })
            m_id += 1
            maintenance_records.append({
                "id": f"MNT-{m_id:04d}",
                "vehicle_id": v_id,
                "date": (start_date + timedelta(days=22)).strftime("%Y-%m-%d"),
                "component": "Cooling System",
                "description": "Driver reported minor coolant warning. Topped off coolant reservoir (1.5 gal). Visual check did not reveal leaks.",
                "cost": 150.00
            })
            m_id += 1
            
        # TRK-454 (Freightliner)
        if v_id == "TRK-454":
            maintenance_records.append({
                "id": f"MNT-{m_id:04d}",
                "vehicle_id": v_id,
                "date": (start_date + timedelta(days=5)).strftime("%Y-%m-%d"),
                "component": "Turbocharger",
                "description": "Routine intake system inspection. Cleaned charge air cooler hoses.",
                "cost": 180.00
            })
            m_id += 1
            
        # TRK-481 (Kenworth)
        if v_id == "TRK-481":
            maintenance_records.append({
                "id": f"MNT-{m_id:04d}",
                "vehicle_id": v_id,
                "date": (start_date + timedelta(days=12)).strftime("%Y-%m-%d"),
                "component": "Electrical",
                "description": "Standard battery state-of-health test. Batteries passed conductance test. Cleaned terminals.",
                "cost": 110.00
            })
            m_id += 1

    df_maintenance = pd.DataFrame(maintenance_records)
    
    # 4. Warranty Claims
    warranty_records = []
    w_id = 1
    for idx, v in enumerate(vehicles):
        v_id = v["id"]
        # Seed some historical claims
        if idx % 3 == 0:
            warranty_records.append({
                "id": f"WRN-{w_id:04d}",
                "vehicle_id": v_id,
                "component": "Drivetrain",
                "claim_date": (start_date - timedelta(days=120)).strftime("%Y-%m-%d"),
                "cost": 2450.00,
                "status": "Approved"
            })
            w_id += 1
            
        # Add an active/recently denied or pending claim for Volvo fuel injectors
        if v["manufacturer"] == "Volvo" and idx % 2 == 1:
            warranty_records.append({
                "id": f"WRN-{w_id:04d}",
                "vehicle_id": v_id,
                "component": "Fuel Injector",
                "claim_date": (start_date + timedelta(days=5)).strftime("%Y-%m-%d"),
                "cost": 1800.00,
                "status": "Pending Review"
            })
            w_id += 1
            
    df_warranty = pd.DataFrame(warranty_records)
    
    # 5. Unstructured Knowledge Documents (Manuals, Warranty policies, Case histories)
    documents = [
        {
            "id": "DOC-001",
            "title": "EGR Cooler Leak Diagnostic & Troubleshooting Manual (Volvo D13 Engine)",
            "category": "Repair Manual",
            "tags": "EGR, coolant leak, overheat, D13, Volvo",
            "content": """
## Diagnostic Procedure for Volvo D13 Engine - Exhaust Gas Recirculation (EGR) Cooler Micro-Leaks

### Issue Description
EGR cooler leakage occurs when internal thermal fatigue cracks develop in the cooler core tubes. This allows pressurized engine coolant to seep into the exhaust gas stream. Because coolant is boiled off in the exhaust, visual external leaks are rarely present.

### Key Symptoms
1. Intermittent high coolant temperature warning (coolant temp > 220°F) under high engine load (engine load > 70%).
2. Gradual loss of coolant from the reservoir without any visible external dripping or puddles.
3. Elevated exhaust gas temperature (EGT) and white smoke under high load.
4. Loss of oil pressure as engine coolant contamination dilutes the motor oil, reducing viscosity.

### Root Cause Verification Steps
- **Pressure Test**: Pressurize the cooling system to 20 PSI. Monitor for pressure drop. If pressure drops but no external leak is visible, remove the EGR mixer tube.
- **Visual Inspection**: Look for wetness, sticky black carbon residue, or green/orange crusty deposits inside the EGR mixer pipe.
- **Exhaust Test**: Run the engine at operating temperature. Block off the EGR outlet and check for exhaust moisture condensation.

### Action Plan
If internal cracking is confirmed, replace the EGR cooler core immediately. Drain engine oil and check for glycol contamination. If contaminated, perform an engine oil flush and replace filters before returning the vehicle to service.
            """
        },
        {
            "id": "DOC-002",
            "title": "Turbocharger Underboost Diagnostics (Code P0299 - Cummins/Freightliner)",
            "category": "Repair Manual",
            "tags": "turbo, P0299, underboost, boost pressure, Freightliner",
            "content": """
## Diagnostic Manual: Cummins ISX15 Turbocharger Underboost (Diagnostic Trouble Code P0299)

### Issue Description
Diagnostic Trouble Code (DTC) P0299 triggers when the Engine Control Module (ECM) detects that the actual boost pressure is significantly below the commanded boost pressure for more than 5 seconds.

### Diagnostic Symptoms
- Engine feels sluggish and lacks power during hill climbs.
- High-frequency whistling or whining noise coming from the engine bay.
- High exhaust gas temperatures (EGT) due to fuel-rich running conditions.
- Severe turbocharger housing vibration (exceeding 1.0 g) indicating bearing wear or compressor blade damage.

### Common Failure Points
1. **Actuator Failure**: The Variable Geometry Turbocharger (VGT) electronic actuator fails internally or binds.
2. **Compressor Wheel Damage**: Dirt ingestion causes compressor blade pitting, resulting in unbalanced rotation and high vibration.
3. **Boost Leak**: Cracks in the charge air cooler (CAC) or loose clamps on the intake piping.

### Recommended Fix
Inspect intake ducting for leaks. Perform a VGT actuator self-test via diagnostic software. If the actuator binds, replace the actuator. If the turbine shaft has radial play or high vibration is verified, replace the complete turbocharger assembly.
            """
        },
        {
            "id": "DOC-003",
            "title": "Volvo D13 Engine Warranty Policy & Claim Guidelines",
            "category": "Warranty Policy",
            "tags": "warranty, Volvo, coverage, fuel injector, engine components",
            "content": """
## Volvo Heavy Truck Warranty Coverage Policy - Engine Drivetrain & Fuel Systems

### Coverage Period
Standard Volvo D13 engine warranty covers 2 years or 250,000 miles, whichever comes first. This includes major engine blocks, cylinder heads, camshafts, and the EGR assembly.

### Fuel System & Injectors
- Fuel injectors and fuel pumps are covered for 1 year or 100,000 miles.
- **Special Notice**: Warranty claims for fuel injector replacement will be automatically rejected if fuel quality analysis reveals contamination (water in fuel, rust particles) or if unauthorized aftermarket fuel filters were used.
- Claims submitted under "Pending Review" status require fuel samples and ECM freeze frame data to verify clean operating conditions.

### Cooling System Exclusions
Radiator hoses, belts, and coolant fluids are considered wear items and are not covered under warranty after 90 days. EGR cooler cores are covered if structural cracking occurs due to material defect, but are excluded if failure was caused by lack of coolant level maintenance or freeze damage.
            """
        },
        {
            "id": "DOC-004",
            "title": "Heavy Duty Alternator and Electrical Malfunction Protocols",
            "category": "Repair Manual",
            "tags": "electrical, alternator, battery, voltage drop, Kenworth",
            "content": """
## Diagnostic Procedure: Alternator Charging Anomaly & Battery Voltage Fluctuations

### Symptoms
1. Dashboard voltage display fluctuates rapidly between 11.5V and 14.2V.
2. Anomaly alarms trigger under accessories load (headlights, sleeper heater).
3. Minor voltage drops (below 12.0 V) recorded in ECU history logs.

### Root Cause Analysis
Alternator voltage drop is usually caused by alternator internal brush wear, a failing voltage regulator, or a slipping drive belt. A worn alternator bearing can also induce high-frequency mechanical vibration that registers on engine block sensors.

### Test Protocol
- Measure voltage directly at the alternator output terminal while engine is running. It should register 13.8V - 14.4V.
- Conduct a voltage drop test between the alternator case and the battery negative terminal to identify bad grounding.
- If output voltage is below 13.2V under load, replace the alternator assembly.
            """
        },
        {
            "id": "DOC-005",
            "title": "Thermostat Malfunction and Radiator Heat Dissipation",
            "category": "Repair Manual",
            "tags": "cooling, thermostat, overheat, radiator, Peterbilt",
            "content": """
## Diagnostic Standard: Thermostat Stuck Closed (Peterbilt/Kenworth Cooling Systems)

### Symptoms
- Engine coolant temperature rapidly climbs to critical levels (coolant temp > 230°F) within 5-10 minutes of operation.
- The lower radiator hose remains cold to the touch while the upper radiator hose is extremely hot, indicating lack of coolant circulation.
- Severe radiator pressure and expansion tank boil-over.

### Action Plan
Remove the thermostat housing and inspect the thermostat. Test thermostat operation in a container of boiling water. If it does not fully open at 180°F (82°C), replace the thermostat assembly. Do not operate the vehicle with a stuck thermostat, as this can crack cylinder heads or blow head gaskets.
            """
        },
        {
            "id": "DOC-006",
            "title": "Case Study: Volvo D13 Intermittent Coolant Leak Repair Case #9983",
            "category": "Case History",
            "tags": "case study, Volvo, coolant leak, EGR, overheating",
            "content": """
## Case History: Intermittent Overheating under Load - Volvo VNL (Engine #427)

### Customer Complaint
Operator reports that the truck warning light for engine coolant temperature triggers on steep climbs, but returns to normal when driving on flat terrain. No fluid is leaking on the ground.

### Diagnostic Diagnostics
Technician performed standard system pressure test; system held 18 PSI pressure for 30 minutes. However, a chemical block test revealed trace combustion gas elements in the coolant reservoir.

### Solution & Repair
The EGR cooler was removed. A hot pressure test (submerging the EGR cooler in 180°F water and applying 30 PSI air) revealed a hairline fracture in the internal tubes that only opened up at high temperature. Replaced the EGR cooler core (Part #22384210) and performed oil flush. The vehicle was road-tested under load; coolant temperatures remained steady at 192°F.
            """
        }
    ]
    
    return df_vehicles, df_telemetry, df_maintenance, df_warranty, documents
