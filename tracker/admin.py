from django.contrib import admin

from .models import (
    Customer,
    Site,
    Equipment,
    Device,
    HourReading,
    FaultEvent,
    Issue,
    MaintenanceSchedule,
    WorkOrder,
    WorkOrderLaborLine,
    WorkOrderPartLine,
    MaintenanceRecord,
    TelemetryPing,
    OilSample,
)


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ["name"]


@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ["name", "customer"]
    list_filter = ["customer"]


@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
    list_display = ["label", "customer", "site", "make", "model", "serial_number"]
    list_filter = ["customer"]


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ["hardware_id", "equipment", "api_token", "last_seen_at"]


@admin.register(HourReading)
class HourReadingAdmin(admin.ModelAdmin):
    list_display = ["equipment", "engine_hours", "recorded_at", "received_at"]
    list_filter = ["equipment"]


@admin.register(FaultEvent)
class FaultEventAdmin(admin.ModelAdmin):
    list_display = ["equipment", "spn", "fmi", "occurrence_count", "first_seen_at", "cleared_at"]
    list_filter = ["equipment"]


@admin.register(Issue)
class IssueAdmin(admin.ModelAdmin):
    list_display = ["equipment", "severity", "description", "reported_by", "reported_at", "resolved_at"]
    list_filter = ["equipment", "severity"]


@admin.register(MaintenanceSchedule)
class MaintenanceScheduleAdmin(admin.ModelAdmin):
    list_display = ["equipment", "task_name", "interval_hours", "interval_days"]
    list_filter = ["equipment"]


class WorkOrderLaborLineInline(admin.TabularInline):
    model = WorkOrderLaborLine
    extra = 0


class WorkOrderPartLineInline(admin.TabularInline):
    model = WorkOrderPartLine
    extra = 0


@admin.register(WorkOrder)
class WorkOrderAdmin(admin.ModelAdmin):
    list_display = ["equipment", "title", "status", "assigned_to", "total_cost", "equipment_down", "created_at", "completed_at"]
    list_filter = ["equipment", "status"]
    inlines = [WorkOrderLaborLineInline, WorkOrderPartLineInline]


@admin.register(MaintenanceRecord)
class MaintenanceRecordAdmin(admin.ModelAdmin):
    list_display = ["equipment", "performed_at", "performed_by", "cost", "hours_at_service", "schedule"]
    list_filter = ["equipment"]


@admin.register(TelemetryPing)
class TelemetryPingAdmin(admin.ModelAdmin):
    list_display = ["equipment", "recorded_at", "latitude", "longitude", "speed_kph", "pm25", "vibration_magnitude"]
    list_filter = ["equipment"]


@admin.register(OilSample)
class OilSampleAdmin(admin.ModelAdmin):
    list_display = ["equipment", "sampled_at", "hours_at_sample", "viscosity"]
    list_filter = ["equipment"]
