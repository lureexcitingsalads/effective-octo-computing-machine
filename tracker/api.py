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
from .models import Equipment, Part, UserProfile, WorkOrder, WorkOrderComment, WorkOrderLaborLine, WorkOrderPartLine
from .views import (
    INSPECTION_SIDES,
    _add_part_line,
    _attach_inspection_photos,
    _complete_work_order,
    _compute_lifecycle_signals,
    _compute_maintenance_forecast,
    _compute_utilization_pct,
    _create_inspection,
    _create_issue,
    scoped_equipment_qs,
    user_customer_scope,
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


def role_required(*roles):
    """Same gate as views.role_required, but for JSON endpoints -- 403 JSON instead of an
    HTML error page. Must sit below @token_required so request.profile is already set."""
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if request.profile.role not in roles:
                return JsonResponse({"error": "not permitted for this role"}, status=403)
            return view_func(request, *args, **kwargs)
        return wrapped
    return decorator


def _parse_json_body(request):
    if not request.body:
        return {}
    return json.loads(request.body)


def _user_json(user, profile=None):
    profile = profile or getattr(user, "profile", None)
    scope = user_customer_scope(user)
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.get_full_name() or user.username,
        "role": profile.role if profile else "technician",
        "customer": scope.name if scope else None,
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
    return JsonResponse({"items": items, "sides": INSPECTION_SIDES})


@token_required
@require_GET
def api_equipment_list_view(request):
    equipment_qs = scoped_equipment_qs(request.user).select_related("customer", "site").order_by("label")
    return JsonResponse({"equipment": [_equipment_summary_json(e) for e in equipment_qs]})


@token_required
@require_GET
def api_equipment_detail_view(request, pk):
    equipment = get_object_or_404(
        scoped_equipment_qs(request.user).select_related("customer", "site"), pk=pk
    )
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
    """Multipart, not JSON, since this can carry photos: per-item issue photos and the
    4-side walkaround. `responses`/`comments` travel as JSON-encoded text fields within the
    multipart body -- there's no clean way to nest structured data any other way alongside
    files in a single request."""
    equipment = get_object_or_404(scoped_equipment_qs(request.user), pk=pk)
    try:
        responses = json.loads(request.POST.get("responses") or "{}")
        comments = json.loads(request.POST.get("comments") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "responses/comments must be valid JSON"}, status=400)

    hours_raw = (request.POST.get("hours_at_inspection") or "").strip()
    performed_by = request.user.get_username()

    inspection = _create_inspection(
        equipment,
        performed_by,
        responses,
        (request.POST.get("notes") or "").strip(),
        comments=comments,
        hours_override=hours_raw or None,
    )
    _attach_inspection_photos(
        inspection,
        performed_by,
        item_photos={key: request.FILES.get(f"photo_{key}") for key, _ in INSPECTION_CHECKLIST},
        side_photos={side: request.FILES.get(f"side_{side}") for side in INSPECTION_SIDES},
    )
    return JsonResponse({"id": inspection.pk, "has_issues": inspection.has_issues}, status=201)


@csrf_exempt
@token_required
@require_POST
def api_report_issue_view(request, pk):
    if request.profile.role == "operator":
        return JsonResponse({"error": "operators can only submit inspections"}, status=403)
    equipment = get_object_or_404(scoped_equipment_qs(request.user), pk=pk)
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


def _work_order_summary_json(wo):
    return {
        "id": wo.pk,
        "title": wo.title,
        "status": wo.status,
        "equipment_id": wo.equipment_id,
        "equipment_label": wo.equipment.label,
        "assigned_to": wo.assigned_to,
        "equipment_down": wo.equipment_down,
        "total_cost": float(wo.total_cost),
        "created_at": wo.created_at.isoformat(),
    }


@token_required
@role_required("admin", "technician")
@require_GET
def api_work_orders_list_view(request):
    show_all = request.GET.get("show") == "all"
    work_orders = WorkOrder.objects.filter(equipment__in=scoped_equipment_qs(request.user)).select_related(
        "equipment"
    ).prefetch_related("labor_lines", "part_lines")
    if not show_all:
        work_orders = work_orders.exclude(status__in=["completed", "cancelled"])
    return JsonResponse({"work_orders": [_work_order_summary_json(wo) for wo in work_orders]})


@token_required
@role_required("admin", "technician")
@require_GET
def api_work_order_detail_view(request, pk):
    wo = get_object_or_404(
        WorkOrder.objects.filter(equipment__in=scoped_equipment_qs(request.user)).select_related(
            "equipment", "equipment__customer"
        ).prefetch_related("labor_lines", "part_lines"),
        pk=pk,
    )
    data = _work_order_summary_json(wo)
    data.update({
        "description": wo.description,
        "customer": wo.equipment.customer.name,
        "completed_at": wo.completed_at.isoformat() if wo.completed_at else None,
        "labor_total": float(wo.labor_total),
        "parts_total": float(wo.parts_total),
        "labor_lines": [
            {
                "id": line.pk,
                "technician": line.technician,
                "hours": float(line.hours),
                "rate": float(line.rate),
                "note": line.note,
                "line_total": float(line.line_total),
            }
            for line in wo.labor_lines.all()
        ],
        "part_lines": [
            {
                "id": line.pk,
                "part_id": line.part_id,
                "part_name": line.part_name,
                "quantity": float(line.quantity),
                "unit_cost": float(line.unit_cost),
                "line_total": float(line.line_total),
            }
            for line in wo.part_lines.all()
        ],
        "comments": [
            {"id": c.pk, "author": c.author, "text": c.text, "created_at": c.created_at.isoformat()}
            for c in wo.comments.all()
        ],
    })
    return JsonResponse(data)


@csrf_exempt
@token_required
@role_required("admin", "technician")
@require_POST
def api_add_work_order_comment_view(request, pk):
    wo = get_object_or_404(WorkOrder.objects.filter(equipment__in=scoped_equipment_qs(request.user)), pk=pk)
    try:
        payload = _parse_json_body(request)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "body must be valid JSON"}, status=400)

    text = (payload.get("text") or "").strip()
    if not text:
        return JsonResponse({"error": "text is required"}, status=400)

    comment = WorkOrderComment.objects.create(work_order=wo, author=request.user.get_username(), text=text)
    return JsonResponse(
        {"id": comment.pk, "author": comment.author, "text": comment.text, "created_at": comment.created_at.isoformat()},
        status=201,
    )


@csrf_exempt
@token_required
@role_required("admin", "technician")
@require_POST
def api_work_order_status_view(request, pk):
    wo = get_object_or_404(WorkOrder.objects.filter(equipment__in=scoped_equipment_qs(request.user)), pk=pk)
    try:
        payload = _parse_json_body(request)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "body must be valid JSON"}, status=400)

    new_status = payload.get("status")
    if new_status not in dict(WorkOrder.STATUS_CHOICES):
        return JsonResponse({"error": "invalid status"}, status=400)

    if new_status == "completed":
        _complete_work_order(wo, request.user.get_username())
    else:
        wo.status = new_status
        wo.save()
    return JsonResponse({"id": wo.pk, "status": wo.status})


@csrf_exempt
@token_required
@role_required("admin", "technician")
@require_POST
def api_add_labor_line_view(request, pk):
    wo = get_object_or_404(WorkOrder.objects.filter(equipment__in=scoped_equipment_qs(request.user)), pk=pk)
    try:
        payload = _parse_json_body(request)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "body must be valid JSON"}, status=400)

    hours = payload.get("hours")
    if not hours:
        return JsonResponse({"error": "hours is required"}, status=400)

    line = WorkOrderLaborLine.objects.create(
        work_order=wo,
        technician=(payload.get("technician") or "").strip() or request.user.get_username(),
        hours=hours,
        rate=payload.get("rate") or 120,
        note=(payload.get("note") or "").strip(),
    )
    return JsonResponse({"id": line.pk, "line_total": float(line.line_total)}, status=201)


@csrf_exempt
@token_required
@role_required("admin", "technician")
@require_POST
def api_add_part_line_view(request, pk):
    wo = get_object_or_404(WorkOrder.objects.filter(equipment__in=scoped_equipment_qs(request.user)), pk=pk)
    try:
        payload = _parse_json_body(request)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "body must be valid JSON"}, status=400)

    part_id = payload.get("part_id")
    part_name = (payload.get("part_name") or "").strip()
    if not part_id and not part_name:
        return JsonResponse({"error": "part_id or part_name is required"}, status=400)

    unit_cost = payload.get("unit_cost")
    line = _add_part_line(
        wo,
        part_id=part_id,
        part_name=part_name,
        quantity=payload.get("quantity") or 1,
        unit_cost=unit_cost if unit_cost is not None else None,
    )
    return JsonResponse({"id": line.pk, "line_total": float(line.line_total)}, status=201)


@token_required
@role_required("admin", "technician")
@require_GET
def api_parts_list_view(request):
    if user_customer_scope(request.user) is not None:
        return JsonResponse({"error": "inventory is internal-only"}, status=403)
    parts = Part.objects.all()
    return JsonResponse({
        "parts": [
            {
                "id": p.pk,
                "name": p.name,
                "part_number": p.part_number,
                "quantity_on_hand": float(p.quantity_on_hand),
                "unit_cost": float(p.unit_cost),
                "is_low_stock": p.is_low_stock,
            }
            for p in parts
        ],
    })
