import calendar
import json
import re
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import (
    Customer, Site, Equipment, Issue, WorkOrder, WorkOrderLaborLine, WorkOrderPartLine,
    MaintenanceRecord, Device, TelemetryPing, HourReading, FaultEvent,
)


@login_required
def equipment_list(request):
    equipment = Equipment.objects.select_related("customer").annotate(
        open_fault_count=Count(
            "fault_events", filter=Q(fault_events__cleared_at__isnull=True), distinct=True
        ),
        open_issue_count=Count(
            "issues", filter=Q(issues__resolved_at__isnull=True), distinct=True
        ),
    )
    return render(request, "tracker/equipment_list.html", {"equipment": equipment})


def _compute_maintenance_forecast(equipment):
    """For each recurring task, project when it'll next be due using the equipment's own hours-per-day rate."""
    hour_readings = list(equipment.hour_readings.order_by("recorded_at"))
    if not hour_readings:
        return []

    current_hours = float(hour_readings[-1].engine_hours)
    earliest, latest = hour_readings[0], hour_readings[-1]
    elapsed_days = (latest.recorded_at - earliest.recorded_at).total_seconds() / 86400
    hours_per_day = (
        (float(latest.engine_hours) - float(earliest.engine_hours)) / elapsed_days
        if elapsed_days > 0
        else 0
    )

    forecasts = []
    for schedule in equipment.maintenance_schedules.all():
        last_record = schedule.records.order_by("-performed_at").first()
        if not schedule.interval_hours or not last_record or last_record.hours_at_service is None:
            forecasts.append(
                {
                    "schedule": schedule,
                    "status": "unknown",
                    "hours_remaining": None,
                    "forecast_date": None,
                    "last_record": last_record,
                }
            )
            continue

        hours_since = current_hours - float(last_record.hours_at_service)
        hours_remaining = float(schedule.interval_hours) - hours_since
        forecast_date = None
        if hours_per_day > 0:
            forecast_date = timezone.now() + timedelta(days=hours_remaining / hours_per_day)

        if hours_remaining < 0:
            status = "overdue"
        elif hours_remaining < float(schedule.interval_hours) * 0.1:
            status = "due_soon"
        else:
            status = "ok"

        forecasts.append(
            {
                "schedule": schedule,
                "status": status,
                "hours_remaining": round(hours_remaining, 1),
                "forecast_date": forecast_date,
                "last_record": last_record,
            }
        )
    return forecasts


@login_required
def equipment_detail(request, pk):
    equipment = get_object_or_404(Equipment, pk=pk)

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "report_issue":
            description = request.POST.get("description", "").strip()
            if description:
                Issue.objects.create(
                    equipment=equipment,
                    reported_by=request.user.get_username(),
                    severity=request.POST.get("severity", "medium"),
                    description=description,
                )

        elif action == "create_workorder":
            title = request.POST.get("title", "").strip()
            if title:
                wo = WorkOrder.objects.create(
                    equipment=equipment,
                    title=title,
                    assigned_to=request.POST.get("assigned_to", "").strip(),
                    equipment_down=bool(request.POST.get("equipment_down")),
                )
                return redirect("work_order_detail", pk=wo.pk)

        return redirect("equipment_detail", pk=pk)

    hour_readings = equipment.hour_readings.order_by("recorded_at")
    fault_events = equipment.fault_events.all()
    maintenance_records = equipment.maintenance_records.all()
    oil_samples = equipment.oil_samples.order_by("sampled_at")
    telemetry_pings = equipment.telemetry_pings.order_by("recorded_at")

    hours_chart = {
        "labels": [hr.recorded_at.strftime("%Y-%m-%d") for hr in hour_readings],
        "hours": [float(hr.engine_hours) for hr in hour_readings],
    }
    oil_chart = {
        "labels": [s.sampled_at.strftime("%Y-%m-%d") for s in oil_samples],
        "iron": [s.wear_metals.get("iron") for s in oil_samples],
        "copper": [s.wear_metals.get("copper") for s in oil_samples],
        "silicon": [s.wear_metals.get("silicon") for s in oil_samples],
    }
    map_data = {
        "path": [[float(p.latitude), float(p.longitude)] for p in telemetry_pings],
        "current": (
            [float(telemetry_pings.last().latitude), float(telemetry_pings.last().longitude)]
            if telemetry_pings.exists()
            else None
        ),
        "pm25": [
            [float(p.latitude), float(p.longitude), float(p.pm25 or 0)] for p in telemetry_pings
        ],
        "vibration": [
            [float(p.latitude), float(p.longitude), float(p.vibration_magnitude or 0)]
            for p in telemetry_pings
        ],
        "speed": [
            [float(p.latitude), float(p.longitude), float(p.speed_kph or 0)] for p in telemetry_pings
        ],
    }

    context = {
        "equipment": equipment,
        "fault_events": fault_events,
        "maintenance_records": maintenance_records,
        "oil_samples": oil_samples,
        "issues": equipment.issues.all(),
        "work_orders": equipment.work_orders.all(),
        "hours_chart": hours_chart,
        "oil_chart": oil_chart,
        "map_data": map_data,
        "has_telemetry": telemetry_pings.exists(),
        "maintenance_forecast": _compute_maintenance_forecast(equipment),
    }
    return render(request, "tracker/equipment_detail.html", context)


@login_required
def manage_view(request):
    """Fleet administration: add/edit machines and sites. Deliberately no delete here --
    equipment and sites have too much history hanging off them (readings, faults, work
    orders) to make that a one-click action; use Django admin for that if it's ever needed."""
    if request.method == "POST":
        action = request.POST.get("action")

        if action == "create_equipment":
            label = request.POST.get("label", "").strip()
            customer_id = request.POST.get("customer_id")
            if label and customer_id:
                equipment = Equipment.objects.create(
                    label=label,
                    customer_id=customer_id,
                    site_id=request.POST.get("site_id") or None,
                    make=request.POST.get("make", "").strip(),
                    model=request.POST.get("model", "").strip(),
                    serial_number=request.POST.get("serial_number", "").strip(),
                )
                return redirect("manage_equipment_edit", pk=equipment.pk)

        elif action == "create_site":
            name = request.POST.get("name", "").strip()
            customer_id = request.POST.get("customer_id")
            if name and customer_id:
                site, _ = Site.objects.get_or_create(name=name, customer_id=customer_id)
                return redirect("manage_site_edit", pk=site.pk)

        return redirect("manage_view")

    context = {
        "equipment_list": Equipment.objects.select_related("customer", "site"),
        "sites": Site.objects.select_related("customer").annotate(equipment_count=Count("equipment")),
        "customers": Customer.objects.all(),
    }
    return render(request, "tracker/manage.html", context)


@login_required
def manage_equipment_edit_view(request, pk):
    equipment = get_object_or_404(Equipment, pk=pk)

    if request.method == "POST":
        equipment.label = request.POST.get("label", "").strip()
        equipment.customer_id = request.POST.get("customer_id") or equipment.customer_id
        equipment.site_id = request.POST.get("site_id") or None
        equipment.make = request.POST.get("make", "").strip()
        equipment.model = request.POST.get("model", "").strip()
        equipment.serial_number = request.POST.get("serial_number", "").strip()
        equipment.save()
        return redirect("manage_view")

    context = {
        "equipment": equipment,
        "customers": Customer.objects.all(),
        "sites": Site.objects.select_related("customer"),
    }
    return render(request, "tracker/manage_equipment_edit.html", context)


@login_required
def manage_site_edit_view(request, pk):
    site = get_object_or_404(Site, pk=pk)

    if request.method == "POST":
        site.name = request.POST.get("name", "").strip()
        site.customer_id = request.POST.get("customer_id") or site.customer_id
        site.save()
        return redirect("manage_view")

    context = {
        "site": site,
        "customers": Customer.objects.all(),
        "equipment_at_site": site.equipment.all(),
    }
    return render(request, "tracker/manage_site_edit.html", context)


@login_required
def schedule_view(request):
    today = timezone.now().date()
    year = int(request.GET.get("year", today.year))
    month = int(request.GET.get("month", today.month))

    overdue = []
    by_date = defaultdict(list)
    for equipment in Equipment.objects.select_related("customer"):
        for f in _compute_maintenance_forecast(equipment):
            if f["status"] == "unknown":
                continue
            entry = {"equipment": equipment, **f}
            if f["status"] == "overdue":
                overdue.append(entry)
            elif f["forecast_date"]:
                by_date[f["forecast_date"].date()].append(entry)
    overdue.sort(key=lambda e: e["hours_remaining"])

    cal = calendar.Calendar(firstweekday=6)  # weeks start Sunday
    weeks = []
    for week in cal.monthdatescalendar(year, month):
        weeks.append(
            [
                {
                    "date": day,
                    "in_month": day.month == month,
                    "is_today": day == today,
                    "items": by_date.get(day, []),
                }
                for day in week
            ]
        )

    prev_month, prev_year = (12, year - 1) if month == 1 else (month - 1, year)
    next_month, next_year = (1, year + 1) if month == 12 else (month + 1, year)

    context = {
        "weeks": weeks,
        "overdue": overdue,
        "month_label": f"{calendar.month_name[month]} {year}",
        "prev_year": prev_year,
        "prev_month": prev_month,
        "next_year": next_year,
        "next_month": next_month,
    }
    return render(request, "tracker/schedule.html", context)


@login_required
def fleet_map_view(request):
    range_key = request.GET.get("range", "all")
    now = timezone.now()
    cutoffs = {"24h": now - timedelta(hours=24), "1w": now - timedelta(days=7), "1m": now - timedelta(days=30)}
    cutoff = cutoffs.get(range_key)

    machines = []
    for equipment in Equipment.objects.select_related("customer"):
        pings = equipment.telemetry_pings.order_by("recorded_at")
        if cutoff:
            pings = pings.filter(recorded_at__gte=cutoff)
        pings = list(pings)
        machines.append(
            {
                "id": equipment.pk,
                "label": equipment.label,
                "path": [[float(p.latitude), float(p.longitude)] for p in pings],
                "current": [float(pings[-1].latitude), float(pings[-1].longitude)] if pings else None,
                "pm25": [[float(p.latitude), float(p.longitude), float(p.pm25 or 0)] for p in pings],
                "vibration": [
                    [float(p.latitude), float(p.longitude), float(p.vibration_magnitude or 0)] for p in pings
                ],
                "speed": [[float(p.latitude), float(p.longitude), float(p.speed_kph or 0)] for p in pings],
            }
        )

    context = {
        "machines_data": machines,
        "range_key": range_key,
        "has_any_telemetry": any(m["path"] for m in machines),
    }
    return render(request, "tracker/fleet_map.html", context)


def _equipment_type(label):
    """Derive a grouping type from a label like 'Excavator 4' -> 'Excavator'."""
    match = re.match(r"^(.*?)\s*\d+\s*$", label)
    return match.group(1) if match else label


@login_required
def fleet_tree_view(request):
    equipment_qs = Equipment.objects.select_related("customer", "site").annotate(
        open_fault_count=Count("fault_events", filter=Q(fault_events__cleared_at__isnull=True), distinct=True),
        open_issue_count=Count("issues", filter=Q(issues__resolved_at__isnull=True), distinct=True),
    )

    status_rank = {"ok": 0, "unknown": 1, "due_soon": 2, "overdue": 3}
    raw_tree = {}
    customer_ids = {}
    for equipment in equipment_qs:
        forecasts = _compute_maintenance_forecast(equipment)
        status = max((f["status"] for f in forecasts), key=status_rank.get) if forecasts else "unknown"
        latest = equipment.hour_readings.first()

        unit = {
            "id": equipment.pk,
            "name": equipment.label,
            "level": "unit",
            "status": status,
            "hours": float(latest.engine_hours) if latest else None,
            "open_faults": equipment.open_fault_count,
            "open_issues": equipment.open_issue_count,
            "url": reverse("equipment_detail", args=[equipment.pk]),
        }
        site = equipment.site.name if equipment.site else "Unassigned site"
        eq_type = _equipment_type(equipment.label)
        customer_ids[equipment.customer.name] = equipment.customer_id
        (
            raw_tree.setdefault(equipment.customer.name, {})
            .setdefault(site, {})
            .setdefault(eq_type, [])
            .append(unit)
        )

    def rollup(units):
        return {
            "count": len(units),
            "status": max((u["status"] for u in units), key=status_rank.get) if units else "unknown",
            "open_faults": sum(u["open_faults"] for u in units),
            "open_issues": sum(u["open_issues"] for u in units),
        }

    customer_nodes = []
    all_units = []
    for customer_name, sites in sorted(raw_tree.items()):
        customer_units = []
        site_nodes = []
        for site_name, types in sorted(sites.items()):
            site_units = []
            type_nodes = []
            for type_name, units in sorted(types.items()):
                type_nodes.append({"name": type_name, "level": "type", "children": units, **rollup(units)})
                site_units.extend(units)
            site_nodes.append(
                {"name": site_name, "level": "location", "children": type_nodes, **rollup(site_units)}
            )
            customer_units.extend(site_units)
        customer_nodes.append(
            {
                "name": customer_name,
                "level": "site",
                "customer_id": customer_ids[customer_name],
                "children": site_nodes,
                **rollup(customer_units),
            }
        )
        all_units.extend(customer_units)

    fleet_tree = {
        "name": "Fleet",
        "level": "root",
        "children": customer_nodes,
        **rollup(all_units),
    }

    return render(request, "tracker/fleet_tree.html", {"fleet_tree": fleet_tree})


@login_required
@require_POST
def reassign_equipment_view(request, pk):
    equipment = get_object_or_404(Equipment, pk=pk)
    customer_id = request.POST.get("customer_id", "").strip()
    site_name = request.POST.get("site_name", "").strip()

    if not customer_id:
        return JsonResponse({"error": "customer_id is required"}, status=400)
    customer = Customer.objects.filter(pk=customer_id).first()
    if not customer:
        return JsonResponse({"error": "Unknown customer"}, status=400)

    equipment.customer = customer
    if site_name:
        site, _ = Site.objects.get_or_create(customer=customer, name=site_name)
        equipment.site = site
    else:
        equipment.site = None
    equipment.save(update_fields=["customer", "site"])
    return JsonResponse({"ok": True})


def _compute_uptime_rows(all_equipment, now=None):
    """Per-equipment uptime %, based on time spent under an open equipment_down work order."""
    now = now or timezone.now()
    uptime_rows = []
    for equipment in all_equipment:
        open_orders = equipment.work_orders.exclude(status__in=["completed", "cancelled"])

        downtime = timedelta()
        for wo in equipment.work_orders.filter(equipment_down=True).exclude(status="cancelled"):
            downtime += (wo.completed_at or now) - wo.created_at

        earliest_reading = equipment.hour_readings.order_by("recorded_at").first()
        period_start = earliest_reading.recorded_at if earliest_reading else now
        period_hours = max((now - period_start).total_seconds() / 3600, 1)
        downtime_hours = downtime.total_seconds() / 3600
        uptime_pct = max(0.0, min(100.0, 100 * (1 - downtime_hours / period_hours)))

        uptime_rows.append(
            {
                "equipment": equipment,
                "downtime_hours": round(downtime_hours, 1),
                "uptime_pct": round(uptime_pct, 1),
                "open_work_orders": open_orders.count(),
            }
        )
    return uptime_rows


@login_required
def dashboard_view(request):
    now = timezone.now()
    all_equipment = list(
        Equipment.objects.select_related("customer").annotate(
            open_fault_count=Count(
                "fault_events", filter=Q(fault_events__cleared_at__isnull=True), distinct=True
            ),
            open_issue_count=Count(
                "issues", filter=Q(issues__resolved_at__isnull=True), distinct=True
            ),
        )
    )

    attention_items = []
    overdue_count = 0
    due_soon_count = 0
    for equipment in all_equipment:
        for f in _compute_maintenance_forecast(equipment):
            if f["status"] == "overdue":
                overdue_count += 1
                attention_items.append(
                    {
                        "severity": 3,
                        "equipment": equipment,
                        "text": f"{f['schedule'].task_name} — {abs(f['hours_remaining'])} hrs overdue",
                    }
                )
            elif f["status"] == "due_soon":
                due_soon_count += 1
                attention_items.append(
                    {
                        "severity": 2,
                        "equipment": equipment,
                        "text": f"{f['schedule'].task_name} — {f['hours_remaining']} hrs remaining",
                    }
                )
        if equipment.open_fault_count:
            attention_items.append(
                {
                    "severity": 3,
                    "equipment": equipment,
                    "text": f"{equipment.open_fault_count} active fault"
                    f"{'s' if equipment.open_fault_count != 1 else ''}",
                }
            )
        if equipment.open_issue_count:
            attention_items.append(
                {
                    "severity": 2,
                    "equipment": equipment,
                    "text": f"{equipment.open_issue_count} open issue"
                    f"{'s' if equipment.open_issue_count != 1 else ''}",
                }
            )
    attention_items.sort(key=lambda i: -i["severity"])

    equipment_down_count = (
        WorkOrder.objects.filter(equipment_down=True)
        .exclude(status__in=["completed", "cancelled"])
        .values("equipment_id")
        .distinct()
        .count()
    )
    open_work_order_count = WorkOrder.objects.exclude(status__in=["completed", "cancelled"]).count()

    uptime_rows = _compute_uptime_rows(all_equipment, now)
    fleet_uptime_pct = (
        round(sum(r["uptime_pct"] for r in uptime_rows) / len(uptime_rows), 1) if uptime_rows else None
    )

    context = {
        "total_equipment": len(all_equipment),
        "overdue_count": overdue_count,
        "due_soon_count": due_soon_count,
        "active_fault_count": sum(e.open_fault_count for e in all_equipment),
        "open_issue_count": sum(e.open_issue_count for e in all_equipment),
        "equipment_down_count": equipment_down_count,
        "open_work_order_count": open_work_order_count,
        "fleet_uptime_pct": fleet_uptime_pct,
        "attention_items": attention_items[:10],
    }
    return render(request, "tracker/dashboard.html", context)


@login_required
def work_orders_view(request):
    """Fleet-wide work order triage -- the supervisor view. Defaults to open/in-progress only."""
    show_all = request.GET.get("show") == "all"
    work_orders = WorkOrder.objects.select_related("equipment", "equipment__customer").prefetch_related(
        "labor_lines", "part_lines"
    )
    if not show_all:
        work_orders = work_orders.exclude(status__in=["completed", "cancelled"])

    return render(
        request,
        "tracker/work_orders.html",
        {"work_orders": work_orders, "show_all": show_all},
    )


def _complete_work_order(wo, performed_by):
    wo.status = "completed"
    wo.completed_at = timezone.now()
    latest = wo.equipment.hour_readings.order_by("-recorded_at").first()
    MaintenanceRecord.objects.create(
        equipment=wo.equipment,
        schedule=wo.schedule,
        performed_at=wo.completed_at,
        performed_by=wo.assigned_to or performed_by,
        description=wo.title,
        cost=wo.total_cost,
        hours_at_service=latest.engine_hours if latest else None,
    )
    wo.save()


@login_required
def work_order_detail_view(request, pk):
    """The technician view -- one job, its itemized labor/parts, and status control."""
    wo = get_object_or_404(WorkOrder.objects.select_related("equipment", "equipment__customer"), pk=pk)

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "add_labor_line":
            technician = request.POST.get("technician", "").strip() or request.user.get_username()
            hours = request.POST.get("hours", "").strip()
            if hours:
                WorkOrderLaborLine.objects.create(
                    work_order=wo,
                    technician=technician,
                    hours=hours,
                    rate=request.POST.get("rate") or 120,
                    note=request.POST.get("note", "").strip(),
                )

        elif action == "remove_labor_line":
            WorkOrderLaborLine.objects.filter(pk=request.POST.get("line_id"), work_order=wo).delete()

        elif action == "add_part_line":
            part_name = request.POST.get("part_name", "").strip()
            if part_name:
                WorkOrderPartLine.objects.create(
                    work_order=wo,
                    part_name=part_name,
                    quantity=request.POST.get("quantity") or 1,
                    unit_cost=request.POST.get("unit_cost") or 0,
                )

        elif action == "remove_part_line":
            WorkOrderPartLine.objects.filter(pk=request.POST.get("line_id"), work_order=wo).delete()

        elif action == "update_notes":
            wo.assigned_to = request.POST.get("assigned_to", "").strip()
            wo.description = request.POST.get("description", "").strip()
            wo.save()

        elif action == "advance_status":
            new_status = request.POST.get("status")
            if new_status in dict(WorkOrder.STATUS_CHOICES):
                if new_status == "completed":
                    _complete_work_order(wo, request.user.get_username())
                else:
                    wo.status = new_status
                    wo.save()

        return redirect("work_order_detail", pk=pk)

    return render(request, "tracker/work_order_detail.html", {"wo": wo})


@login_required
def reports_view(request):
    all_equipment = Equipment.objects.select_related("customer").all()
    now = timezone.now()

    cost_by_equipment = []
    cost_by_customer = defaultdict(float)
    total_cost = 0.0

    for equipment in all_equipment:
        eq_cost = float(sum((r.cost or 0) for r in equipment.maintenance_records.all()))
        cost_by_equipment.append({"label": equipment.label, "cost": eq_cost})
        cost_by_customer[equipment.customer.name] += eq_cost
        total_cost += eq_cost

    completed_orders = WorkOrder.objects.filter(status="completed").prefetch_related(
        "labor_lines", "part_lines"
    )
    total_labor_cost = float(sum((wo.labor_total for wo in completed_orders), Decimal("0")))
    total_parts_cost = float(sum((wo.parts_total for wo in completed_orders), Decimal("0")))

    uptime_rows = _compute_uptime_rows(all_equipment, now)
    total_open_work_orders = sum(r["open_work_orders"] for r in uptime_rows)
    fleet_uptime_pct = (
        round(sum(r["uptime_pct"] for r in uptime_rows) / len(uptime_rows), 1) if uptime_rows else None
    )

    context = {
        "total_cost": total_cost,
        "total_labor_cost": total_labor_cost,
        "total_parts_cost": total_parts_cost,
        "total_open_work_orders": total_open_work_orders,
        "fleet_uptime_pct": fleet_uptime_pct,
        "cost_chart": {
            "labels": [c["label"] for c in cost_by_equipment],
            "costs": [c["cost"] for c in cost_by_equipment],
        },
        "cost_by_customer": dict(cost_by_customer),
        "uptime_rows": uptime_rows,
    }
    return render(request, "tracker/reports.html", context)


@csrf_exempt
@require_POST
def ingest_view(request):
    """Machine-to-machine endpoint the device/gateway posts readings to. Auth is a per-device
    bearer token (Device.api_token), not the human session login used everywhere else."""
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.removeprefix("Bearer ").strip()
    if not token:
        return JsonResponse({"error": "missing bearer token"}, status=401)

    device = Device.objects.filter(api_token=token).select_related("equipment").first()
    if device is None:
        return JsonResponse({"error": "invalid token"}, status=401)
    if device.equipment is None:
        return JsonResponse({"error": "device is not assigned to any equipment"}, status=400)

    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "body must be valid JSON"}, status=400)

    equipment = device.equipment
    now = timezone.now()
    device.last_seen_at = now
    device.save(update_fields=["last_seen_at"])

    # Device's own clock, if it sent one (e.g. from GPS time); falls back to receipt time.
    # A live bench/WiFi test has no meaningful gap between the two -- this distinction starts
    # to matter once the SD-card-buffer + mesh relay path can deliver readings hours late.
    recorded_at = parse_datetime(payload.get("recorded_at") or "") or now

    created = {"hour_reading": False, "telemetry_ping": False, "faults": 0}

    if payload.get("engine_hours") is not None:
        HourReading.objects.create(
            equipment=equipment, recorded_at=recorded_at, engine_hours=payload["engine_hours"]
        )
        created["hour_reading"] = True

    if payload.get("latitude") is not None and payload.get("longitude") is not None:
        TelemetryPing.objects.create(
            equipment=equipment,
            recorded_at=recorded_at,
            latitude=payload["latitude"],
            longitude=payload["longitude"],
            speed_kph=payload.get("speed_kph"),
            pm25=payload.get("pm25"),
            vibration_magnitude=payload.get("vibration_magnitude"),
        )
        created["telemetry_ping"] = True

    for fault in payload.get("faults", []):
        spn, fmi = fault.get("spn"), fault.get("fmi")
        if spn is None or fmi is None:
            continue
        active = fault.get("active", True)
        existing = FaultEvent.objects.filter(
            equipment=equipment, spn=spn, fmi=fmi, cleared_at__isnull=True
        ).first()
        if active and existing:
            existing.occurrence_count += 1
            existing.save(update_fields=["occurrence_count"])
        elif active and not existing:
            FaultEvent.objects.create(equipment=equipment, spn=spn, fmi=fmi, first_seen_at=recorded_at)
        elif not active and existing:
            existing.cleared_at = recorded_at
            existing.save(update_fields=["cleared_at"])
        created["faults"] += 1

    return JsonResponse({"status": "ok", "equipment": equipment.label, "created": created})
