import math
import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from tracker.models import (
    Customer,
    Site,
    Equipment,
    Device,
    HourReading,
    FaultEvent,
    MaintenanceSchedule,
    WorkOrder,
    WorkOrderLaborLine,
    WorkOrderPartLine,
    MaintenanceRecord,
    TelemetryPing,
    OilSample,
)


# ---- Path shapes, one movement style per equipment type, so the fleet doesn't look like one
# path stamped in four places. Each returns a list of (lat, lon).

def spiral_points(n, base_lat, base_lon, radius=0.0017):
    """An excavator working a contained area: tightening/loosening loops around one spot."""
    pts = []
    for i in range(n):
        angle = i * 0.35
        r = radius * 0.6 + radius * 0.4 * math.sin(i * 0.2)
        pts.append((base_lat + r * math.sin(angle), base_lon + r * math.cos(angle)))
    return pts


def shuttle_points(n, point_a, point_b, cycles=6):
    """A loader running back and forth between a stockpile and a load-out point."""
    pts = []
    for i in range(n):
        t = i / (n - 1) if n > 1 else 0
        frac = abs(((t * cycles) % 2) - 1)  # triangle wave 0->1->0...
        pts.append(
            (point_a[0] + (point_b[0] - point_a[0]) * frac, point_a[1] + (point_b[1] - point_a[1]) * frac)
        )
    return pts


def sweep_points(n, base_lat, base_lon, rows=7, row_spacing=0.0004, row_width=0.0026):
    """A dozer grading in parallel passes, like mowing a lawn."""
    pts = []
    per_row = max(2, n // rows)
    for i in range(n):
        row = i // per_row
        pos_in_row = (i % per_row) / max(1, per_row - 1)
        direction = 1 if row % 2 == 0 else -1
        lon = base_lon + direction * (pos_in_row - 0.5) * row_width
        lat = base_lat + row * row_spacing
        pts.append((lat, lon))
    return pts


def figure8_points(n, base_lat, base_lon, radius=0.0011):
    """A smaller excavator working a tighter double-loop area."""
    pts = []
    for i in range(n):
        t = (i / (n - 1) if n > 1 else 0) * 4 * math.pi
        pts.append((base_lat + radius * math.sin(t), base_lon + radius * math.sin(t) * math.cos(t)))
    return pts


def transit_points(n, point_a, point_b, bow=0.0006):
    """A haul/relocation move between two sites -- a gentle bowed line, not a straight ruler-line."""
    pts = []
    dlat, dlon = point_b[0] - point_a[0], point_b[1] - point_a[1]
    perp_lat, perp_lon = -dlon, dlat
    norm = math.hypot(perp_lat, perp_lon) or 1
    for i in range(n):
        t = i / (n - 1) if n > 1 else 0
        bow_offset = bow * math.sin(t * math.pi)
        pts.append(
            (
                point_a[0] + dlat * t + (perp_lat / norm) * bow_offset,
                point_a[1] + dlon * t + (perp_lon / norm) * bow_offset,
            )
        )
    return pts


def seed_telemetry(equipment, start, end, points, hotspots=None, recent_points=None, fast_range=None):
    """points cover the full [start, end] historical span; recent_points (if given) get densely
    packed into the last ~20 hours from right now, so 24h/1-week filters have something to show.
    fast_range=(lo, hi) marks a slice of `points` (e.g. a haul-road relocation) as highway-speed
    instead of typical slow on-site travel."""
    hotspots = hotspots or []

    def make_ping(lat, lon, t, fast=False):
        pm25 = round(random.uniform(8, 18), 1)
        vibration = round(random.uniform(0.5, 1.8), 2)
        impact = False
        for zlat, zlon, metric in hotspots:
            if math.hypot(lat - zlat, lon - zlon) < 0.0009:
                if metric == "pm25":
                    pm25 = round(random.uniform(60, 140), 1)
                elif metric == "vibration":
                    vibration = round(random.uniform(4.5, 8.0), 2)
                    impact = vibration > 6.5
        if fast:
            speed = round(random.uniform(35, 70), 1)
        else:
            speed = 0.0 if random.random() < 0.6 else round(random.uniform(2, 6), 1)
        return TelemetryPing(
            equipment=equipment, recorded_at=t, latitude=round(lat, 6), longitude=round(lon, 6),
            speed_kph=speed, pm25=pm25, vibration_magnitude=vibration, is_impact_event=impact,
        )

    pings = []
    span = end - start
    n = len(points)
    for i, (lat, lon) in enumerate(points):
        t = start + span * (i / (n - 1)) if n > 1 else end
        fast = fast_range is not None and fast_range[0] <= i < fast_range[1]
        pings.append(make_ping(lat, lon, t, fast=fast))

    if recent_points:
        now = timezone.now()
        recent_span = timedelta(hours=20)
        recent_start = now - recent_span
        m = len(recent_points)
        for i, (lat, lon) in enumerate(recent_points):
            t = recent_start + recent_span * (i / (m - 1)) if m > 1 else now
            pings.append(make_ping(lat, lon, t))

    TelemetryPing.objects.bulk_create(pings)


class Command(BaseCommand):
    help = "Populates the database with a small demo fleet. Safe to re-run: wipes and rebuilds each time."

    def handle(self, *args, **options):
        Equipment.objects.filter(
            label__in=["Excavator 4", "Loader 1", "Dozer 2", "Excavator 7"]
        ).delete()

        acme, _ = Customer.objects.get_or_create(
            name="Acme Site Services", defaults={"contact_info": "ops@acmesiteservices.example"}
        )
        northgate, _ = Customer.objects.get_or_create(
            name="Northgate Excavation", defaults={"contact_info": "dispatch@northgateexcavation.example"}
        )
        ridgeline, _ = Customer.objects.get_or_create(
            name="Ridgeline Contractors", defaults={"contact_info": "office@ridgelinecontractors.example"}
        )

        site_12, _ = Site.objects.get_or_create(customer=acme, name="Site 12 – Downtown Interchange")
        ridgeview_quarry, _ = Site.objects.get_or_create(customer=northgate, name="Ridgeview Quarry – Phase 2")
        elm_street, _ = Site.objects.get_or_create(customer=ridgeline, name="Elm Street Reconstruction")

        today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        start = today - timedelta(days=100)

        # ---- Excavator 4: flagship story — overdue oil change, active fault, rising oil-wear trend ----
        excavator4 = Equipment.objects.create(
            label="Excavator 4", customer=acme, site=site_12,
            make="Caterpillar", model="336", serial_number="CAT0336DEMO0001"
        )
        Device.objects.update_or_create(
            hardware_id="ESP32-DEMO-001", defaults={"equipment": excavator4, "last_seen_at": timezone.now()}
        )
        for i, hrs in enumerate([1180, 1205, 1248, 1290, 1335, 1378, 1415, 1453]):
            HourReading.objects.create(equipment=excavator4, recorded_at=start + timedelta(days=i * 14), engine_hours=hrs)
        FaultEvent.objects.create(
            equipment=excavator4, spn=110, fmi=16,
            first_seen_at=start + timedelta(days=40), cleared_at=start + timedelta(days=43), occurrence_count=6,
        )
        FaultEvent.objects.create(
            equipment=excavator4, spn=168, fmi=18, first_seen_at=start + timedelta(days=92), occurrence_count=2
        )
        oil_sched_4 = MaintenanceSchedule.objects.create(equipment=excavator4, task_name="Oil and filter change", interval_hours=250)
        air_sched_4 = MaintenanceSchedule.objects.create(equipment=excavator4, task_name="Air filter inspection", interval_hours=500)
        MaintenanceRecord.objects.create(
            equipment=excavator4, schedule=oil_sched_4, performed_at=start + timedelta(days=2),
            performed_by="J. Smith", description="Oil and filter change", cost=340.00, hours_at_service=1195,
        )
        MaintenanceRecord.objects.create(
            equipment=excavator4, schedule=air_sched_4, performed_at=start + timedelta(days=5),
            performed_by="J. Smith", description="Air filter inspection", hours_at_service=1200,
        )
        for day_offset, hrs, metals, note in [
            (2, 1195, {"iron": 15, "copper": 8, "silicon": 5}, "Normal wear, no action needed."),
            (48, 1310, {"iron": 22, "copper": 10, "silicon": 9}, "Slight upward trend, continue monitoring."),
            (95, 1415, {"iron": 38, "copper": 14, "silicon": 18}, "Silicon trending upward — inspect air intake seal/filter for dust ingress."),
        ]:
            OilSample.objects.create(
                equipment=excavator4, sampled_at=start + timedelta(days=day_offset),
                hours_at_sample=hrs, wear_metals=metals, viscosity=14.2, lab_recommendation=note,
            )
        seed_telemetry(
            excavator4, start, today,
            spiral_points(220, 39.7392, -104.9903),
            hotspots=[(39.7405, -104.9895, "pm25"), (39.7382, -104.9915, "vibration")],
            recent_points=spiral_points(24, 39.7392, -104.9903),
        )
        # Left in-progress on purpose: completing it in the UI shows the forecast above flip from Overdue to OK.
        wo_excavator4_oil = WorkOrder.objects.create(
            equipment=excavator4, schedule=oil_sched_4, title="Oil and filter change",
            status="in_progress", assigned_to="J. Smith", equipment_down=True,
        )
        WorkOrderLaborLine.objects.create(
            work_order=wo_excavator4_oil, technician="J. Smith", hours=1.5, rate=100,
            note="Drain, filter swap, refill",
        )
        WorkOrderPartLine.objects.create(
            work_order=wo_excavator4_oil, part_name="Engine oil (15W-40), 20L", quantity=1, unit_cost=140,
        )
        WorkOrderPartLine.objects.create(
            work_order=wo_excavator4_oil, part_name="Oil filter", quantity=1, unit_cost=50,
        )
        WorkOrder.objects.create(
            equipment=excavator4, title="Diagnose low battery voltage fault",
            status="open", equipment_down=False,
        )

        # ---- Loader 1: maintenance due soon, one old cleared fault, flat oil trend ----
        loader1 = Equipment.objects.create(
            label="Loader 1", customer=acme, site=site_12,
            make="Caterpillar", model="950M", serial_number="CAT0950DEMO0002"
        )
        Device.objects.update_or_create(
            hardware_id="ESP32-DEMO-002", defaults={"equipment": loader1, "last_seen_at": timezone.now()}
        )
        for i, hrs in enumerate([820, 850, 875, 900, 930, 955, 980, 1005]):
            HourReading.objects.create(equipment=loader1, recorded_at=start + timedelta(days=i * 14), engine_hours=hrs)
        FaultEvent.objects.create(
            equipment=loader1, spn=100, fmi=1,
            first_seen_at=start + timedelta(days=30), cleared_at=start + timedelta(days=32), occurrence_count=3,
        )
        oil_sched_l1 = MaintenanceSchedule.objects.create(equipment=loader1, task_name="Oil and filter change", interval_hours=250)
        MaintenanceRecord.objects.create(
            equipment=loader1, schedule=oil_sched_l1, performed_at=start - timedelta(days=15),
            performed_by="R. Alvarez", description="Oil and filter change", cost=310.00, hours_at_service=775,
        )
        # A completed work order with a real itemized breakdown, so Reports' Labor vs. Parts
        # split and the Work Orders list both have a finished example to show, not just open ones.
        wo_loader1_hose = WorkOrder.objects.create(
            equipment=loader1, title="Replace hydraulic hose", status="completed",
            assigned_to="R. Alvarez", equipment_down=True,
            completed_at=start + timedelta(days=33),
        )
        # created_at is auto_now_add, so .create() always stamps "now" no matter what's passed --
        # backdate it via .update() (bypasses the pre_save override) so it lands before completed_at.
        WorkOrder.objects.filter(pk=wo_loader1_hose.pk).update(created_at=start + timedelta(days=32))
        WorkOrderLaborLine.objects.create(
            work_order=wo_loader1_hose, technician="R. Alvarez", hours=3, rate=110,
            note="Diagnose leak, replace hose, bleed system",
        )
        WorkOrderPartLine.objects.create(
            work_order=wo_loader1_hose, part_name="Hydraulic hose assembly", quantity=1, unit_cost=185,
        )
        WorkOrderPartLine.objects.create(
            work_order=wo_loader1_hose, part_name="Hydraulic fluid, 5L", quantity=2, unit_cost=42,
        )
        MaintenanceRecord.objects.create(
            equipment=loader1, performed_at=wo_loader1_hose.completed_at,
            performed_by="R. Alvarez", description="Replace hydraulic hose",
            cost=wo_loader1_hose.total_cost, hours_at_service=865,
        )
        for day_offset, hrs, metals, note in [
            (10, 830, {"iron": 10, "copper": 6, "silicon": 4}, "Normal wear, no action needed."),
            (70, 970, {"iron": 12, "copper": 7, "silicon": 5}, "Normal wear, no action needed."),
        ]:
            OilSample.objects.create(
                equipment=loader1, sampled_at=start + timedelta(days=day_offset),
                hours_at_sample=hrs, wear_metals=metals, viscosity=13.8, lab_recommendation=note,
            )
        loader_a, loader_b = (39.735, -104.995), (39.7368, -104.9905)
        seed_telemetry(
            loader1, start, today,
            shuttle_points(220, loader_a, loader_b, cycles=30),
            recent_points=shuttle_points(24, loader_a, loader_b, cycles=4),
        )

        # ---- Dozer 2: healthy across the board, different customer ----
        dozer2 = Equipment.objects.create(
            label="Dozer 2", customer=northgate, site=ridgeview_quarry,
            make="Caterpillar", model="D6T", serial_number="CATD6TDEMO0003"
        )
        Device.objects.update_or_create(
            hardware_id="ESP32-DEMO-003", defaults={"equipment": dozer2, "last_seen_at": timezone.now()}
        )
        for i, hrs in enumerate([2100, 2130, 2158, 2185, 2212, 2242, 2268, 2295]):
            HourReading.objects.create(equipment=dozer2, recorded_at=start + timedelta(days=i * 14), engine_hours=hrs)
        oil_sched_d2 = MaintenanceSchedule.objects.create(equipment=dozer2, task_name="Oil and filter change", interval_hours=250)
        air_sched_d2 = MaintenanceSchedule.objects.create(equipment=dozer2, task_name="Air filter inspection", interval_hours=500)
        MaintenanceRecord.objects.create(
            equipment=dozer2, schedule=oil_sched_d2, performed_at=start + timedelta(days=60),
            performed_by="R. Alvarez", description="Oil and filter change", cost=355.00, hours_at_service=2240,
        )
        MaintenanceRecord.objects.create(
            equipment=dozer2, schedule=air_sched_d2, performed_at=start + timedelta(days=60),
            performed_by="R. Alvarez", description="Air filter inspection", hours_at_service=2240,
        )
        for day_offset, hrs, metals, note in [
            (20, 2140, {"iron": 8, "copper": 5, "silicon": 3}, "Normal wear, no action needed."),
            (80, 2270, {"iron": 9, "copper": 5, "silicon": 4}, "Normal wear, no action needed."),
        ]:
            OilSample.objects.create(
                equipment=dozer2, sampled_at=start + timedelta(days=day_offset),
                hours_at_sample=hrs, wear_metals=metals, viscosity=14.0, lab_recommendation=note,
            )
        # Relocated partway through the window -- previous quarry phase, then hauled ~4km to its
        # current site, so the longer time ranges show a real haul in addition to on-site work.
        dozer2_old_site = (39.7695, -104.9558)
        dozer2_current_site = (39.7445, -104.9858)
        dozer2_old_pts = sweep_points(70, *dozer2_old_site, rows=5)
        dozer2_transit_pts = transit_points(20, dozer2_old_site, dozer2_current_site)
        dozer2_current_pts = sweep_points(130, *dozer2_current_site)
        seed_telemetry(
            dozer2, start, today,
            dozer2_old_pts + dozer2_transit_pts + dozer2_current_pts,
            hotspots=[(39.757, -104.9708, "vibration")],  # a rough stretch along the haul route
            recent_points=sweep_points(24, *dozer2_current_site, rows=3),
            fast_range=(len(dozer2_old_pts), len(dozer2_old_pts) + len(dozer2_transit_pts)),
        )

        # ---- Excavator 7: active fault is the headline issue, maintenance itself is fine, third customer ----
        excavator7 = Equipment.objects.create(
            label="Excavator 7", customer=ridgeline, site=elm_street,
            make="Caterpillar", model="320", serial_number="CAT0320DEMO0004"
        )
        Device.objects.update_or_create(
            hardware_id="ESP32-DEMO-004", defaults={"equipment": excavator7, "last_seen_at": timezone.now()}
        )
        for i, hrs in enumerate([500, 525, 545, 570, 590, 615, 635, 660]):
            HourReading.objects.create(equipment=excavator7, recorded_at=start + timedelta(days=i * 14), engine_hours=hrs)
        FaultEvent.objects.create(
            equipment=excavator7, spn=100, fmi=1, first_seen_at=start + timedelta(days=95), occurrence_count=4
        )
        oil_sched_7 = MaintenanceSchedule.objects.create(equipment=excavator7, task_name="Oil and filter change", interval_hours=250)
        MaintenanceRecord.objects.create(
            equipment=excavator7, schedule=oil_sched_7, performed_at=start + timedelta(days=3),
            performed_by="J. Smith", description="Oil and filter change", cost=300.00, hours_at_service=505,
        )
        OilSample.objects.create(
            equipment=excavator7, sampled_at=start + timedelta(days=10),
            hours_at_sample=515, wear_metals={"iron": 11, "copper": 6, "silicon": 4},
            viscosity=14.1, lab_recommendation="Normal wear, no action needed.",
        )
        WorkOrder.objects.create(
            equipment=excavator7, title="Investigate oil pressure fault (SPN 100)",
            status="open", assigned_to="J. Smith", equipment_down=True,
        )
        # Also relocated partway through the window -- a different previous site, ~3.6km out,
        # hauled over to Elm Street Reconstruction (its current, dusty demolition/road-rebuild site).
        excavator7_old_site = (39.7020, -105.0210)
        excavator7_current_site = (39.7305, -104.9975)
        excavator7_old_pts = figure8_points(70, *excavator7_old_site)
        excavator7_transit_pts = transit_points(20, excavator7_old_site, excavator7_current_site)
        excavator7_current_pts = figure8_points(130, *excavator7_current_site)
        seed_telemetry(
            excavator7, start, today,
            excavator7_old_pts + excavator7_transit_pts + excavator7_current_pts,
            hotspots=[(39.7312, -104.9968, "pm25")],
            recent_points=figure8_points(24, *excavator7_current_site),
            fast_range=(len(excavator7_old_pts), len(excavator7_old_pts) + len(excavator7_transit_pts)),
        )

        self.stdout.write(self.style.SUCCESS("Seeded demo fleet: Excavator 4, Loader 1, Dozer 2, Excavator 7"))
