"""JSON API for the Android field-technician companion app. Separate from views.py (which
renders the server-side HTML app) so the request/response shape for mobile clients stays in
one place. Auth is a per-user bearer token (UserProfile.api_token), the same pattern already
used for device ingestion (Device.api_token) rather than session cookies -- native apps don't
carry browser cookies, and this reuses a convention already proven in this codebase instead of
pulling in Django REST Framework for a handful of endpoints.
"""
import functools
import json

from django.contrib.auth import authenticate
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .inspection_checklist import CHECKLIST as INSPECTION_CHECKLIST, CRITICAL_ITEMS as INSPECTION_CRITICAL_ITEMS
from .models import Equipment, UserProfile
from .views import (
    _compute_lifecycle_signals,
    _compute_maintenance_forecast,
    _compute_utilization_pct,
    _create_inspection,
    _create_issue,
)

STATUS_RANK = {"ok": 0, "unknown": 1, "due_soon": 2, "overdue": 3}


def token_required(view_func):
    """Reads 'Authorization: Bearer <token>' and resolves it to a UserProfile, mirroring
    ingest_view's device-token check but for human users instead of hardware."""
    @functools.wraps(view_func)
    def wrapped(request, *args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        token = auth_header.removeprefix("Bearer ").strip()
        if not token:
            return JsonResponse({"error": "missing bearer token"}, status=401)
        profile = UserProfile.objects.filter(api_token=token).select_related("user").first()
        if profile is None or not profile.user.is_active:
            return JsonResponse({"error": "invalid token"}, status=401)
        request.user = profile.user
        request.profile = profile
        return view_func(request, *args, **kwargs)
    return wrapped


def _parse_json_body(request):
    if not request.body:
        return {}
    return json.loads(request.body)


def _user_json(user, profile=None):
    profile = profile or getattr(user, "profile", None)
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.get_full_name() or user.username,
        "role": profile.role if profile else "technician",
    }


def _equipment_summary_json(equipment, forecasts=None):
    forecasts = _compute_maintenance_forecast(equipment) if forecasts is None else forecasts
    status = max((f["status"] for f in forecasts), key=STATUS_RANK.get) if forecasts else "unknown"
    latest = equipment.hour_readings.first()
    return {
        "id": equipment.pk,
        "label": equipment.label,
        "customer": equipment.customer.name,
        "site": equipment.site.name if equipment.site else None,
        "status": status,
        "latest_hours": float(latest.engine_hours) if latest else None,
        "open_fault_count": equipment.fault_events.filter(cleared_at__isnull=True).count(),
        "open_issue_count": equipment.issues.filter(resolved_at__isnull=True).count(),
    }


@csrf_exempt
@require_POST
def api_login_view(request):
    try:
        payload = _parse_json_body(request)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "body must be valid JSON"}, status=400)

    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""
    if not username or not password:
        return JsonResponse({"error": "username and password are required"}, status=400)

    user = authenticate(request, username=username, password=password)
    if user is None or not user.is_active:
        return JsonResponse({"error": "invalid credentials"}, status=401)

    profile, _ = UserProfile.objects.get_or_create(user=user)
    return JsonResponse({"token": profile.api_token, "user": _user_json(user, profile)})


@token_required
@require_GET
def api_me_view(request):
    return JsonResponse({"user": _user_json(request.user, request.profile)})


@token_required
@require_GET
def api_checklist_view(request):
    items = [
        {"key": key, "label": label, "critical": key in INSPECTION_CRITICAL_ITEMS}
        for key, label in INSPECTION_CHECKLIST
    ]
    return JsonResponse({"items": items})


@token_required
@require_GET
def api_equipment_list_view(request):
    equipment_qs = Equipment.objects.select_related("customer", "site").order_by("label")
    return JsonResponse({"equipment": [_equipment_summary_json(e) for e in equipment_qs]})


@token_required
@require_GET
def api_equipment_detail_view(request, pk):
    equipment = get_object_or_404(Equipment.objects.select_related("customer", "site"), pk=pk)
    forecasts = _compute_maintenance_forecast(equipment)
    has_active_fault = equipment.fault_events.filter(cleared_at__isnull=True).exists()
    is_down = equipment.work_orders.filter(equipment_down=True).exclude(
        status__in=["completed", "cancelled"]
    ).exists()
    maintenance_status = max((f["status"] for f in forecasts), key=STATUS_RANK.get) if forecasts else "unknown"
    overall_status = "overdue" if (has_active_fault or is_down) else maintenance_status

    data = _equipment_summary_json(equipment, forecasts)
    data.update({
        "overall_status": overall_status,
        "is_down": is_down,
        "utilization_pct": _compute_utilization_pct(equipment, timezone.now()),
        "lifecycle_signals": _compute_lifecycle_signals(equipment),
        "forecast": [
            {
                "task_name": f["schedule"].task_name,
                "status": f["status"],
                "hours_remaining": f["hours_remaining"],
                "forecast_date": f["forecast_date"].isoformat() if f["forecast_date"] else None,
            }
            for f in forecasts
        ],
        "open_issues": [
            {
                "id": i.pk,
                "severity": i.severity,
                "description": i.description,
                "reported_by": i.reported_by,
                "reported_at": i.reported_at.isoformat(),
            }
            for i in equipment.issues.filter(resolved_at__isnull=True)
        ],
    })
    return JsonResponse(data)


@csrf_exempt
@token_required
@require_POST
def api_create_inspection_view(request, pk):
    equipment = get_object_or_404(Equipment, pk=pk)
    try:
        payload = _parse_json_body(request)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "body must be valid JSON"}, status=400)

    inspection = _create_inspection(
        equipment,
        request.user.get_username(),
        payload.get("responses") or {},
        (payload.get("notes") or "").strip(),
    )
    return JsonResponse({"id": inspection.pk, "has_issues": inspection.has_issues}, status=201)


@csrf_exempt
@token_required
@require_POST
def api_report_issue_view(request, pk):
    equipment = get_object_or_404(Equipment, pk=pk)
    description = request.POST.get("description", "").strip()
    if not description:
        return JsonResponse({"error": "description is required"}, status=400)

    issue = _create_issue(
        equipment,
        request.user.get_username(),
        request.POST.get("severity", "medium"),
        description,
        request.FILES.getlist("photos"),
    )
    return JsonResponse({"id": issue.pk}, status=201)
