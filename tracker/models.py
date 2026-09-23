import secrets
from decimal import Decimal

from django.db import models

from .j1939_codes import describe_fault


def generate_api_token():
    return secrets.token_hex(20)


class Customer(models.Model):
    name = models.CharField(max_length=200)
    contact_info = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Site(models.Model):
    """A job site a customer's equipment can be deployed to. Separate from Customer because
    one customer can have several active sites at once, and equipment moves between them."""

    name = models.CharField(max_length=200, help_text='e.g. "Site 12 – Downtown Interchange"')
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="sites")

    class Meta:
        ordering = ["customer__name", "name"]
        unique_together = [["customer", "name"]]

    def __str__(self):
        return f"{self.name} ({self.customer.name})"


class Equipment(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="equipment")
    label = models.CharField(max_length=100, help_text='e.g. "Excavator 4"')
    site = models.ForeignKey(
        Site, on_delete=models.SET_NULL, null=True, blank=True, related_name="equipment",
        help_text="Job site this unit is currently deployed to",
    )
    make = models.CharField(max_length=100, blank=True)
    model = models.CharField(max_length=100, blank=True)
    serial_number = models.CharField(max_length=100, blank=True)

    class Meta:
        verbose_name_plural = "equipment"

    def __str__(self):
        return self.label


class Device(models.Model):
    equipment = models.OneToOneField(
        Equipment, on_delete=models.SET_NULL, null=True, blank=True, related_name="device"
    )
    hardware_id = models.CharField(max_length=100, unique=True, help_text="ESP32 chip ID")
    api_token = models.CharField(
        max_length=64, unique=True, default=generate_api_token,
        help_text="Bearer token the device sends to authenticate to /api/ingest/",
    )
    last_seen_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.hardware_id


class HourReading(models.Model):
    equipment = models.ForeignKey(Equipment, on_delete=models.CASCADE, related_name="hour_readings")
    engine_hours = models.DecimalField(max_digits=10, decimal_places=1)
    recorded_at = models.DateTimeField(help_text="Device's own clock, not server receipt time")
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-recorded_at"]

    def __str__(self):
        return f"{self.equipment} - {self.engine_hours}h"


class FaultEvent(models.Model):
    equipment = models.ForeignKey(Equipment, on_delete=models.CASCADE, related_name="fault_events")
    spn = models.IntegerField(verbose_name="SPN")
    fmi = models.IntegerField(verbose_name="FMI")
    occurrence_count = models.IntegerField(default=1)
    first_seen_at = models.DateTimeField()
    cleared_at = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-first_seen_at"]

    def __str__(self):
        return f"{self.equipment} - SPN {self.spn} FMI {self.fmi}"

    @property
    def description(self):
        return describe_fault(self.spn, self.fmi)


class Issue(models.Model):
    """A human-reported problem — distinct from FaultEvent, which is device-detected."""

    SEVERITY_CHOICES = [("low", "Low"), ("medium", "Medium"), ("high", "High")]

    equipment = models.ForeignKey(Equipment, on_delete=models.CASCADE, related_name="issues")
    reported_by = models.CharField(max_length=200)
    reported_at = models.DateTimeField(auto_now_add=True)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default="medium")
    description = models.TextField()
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-reported_at"]

    def __str__(self):
        return f"{self.equipment} - {self.description[:40]}"


class MaintenanceSchedule(models.Model):
    equipment = models.ForeignKey(Equipment, on_delete=models.CASCADE, related_name="maintenance_schedules")
    task_name = models.CharField(max_length=200, help_text='e.g. "Oil and filter change"')
    interval_hours = models.DecimalField(
        max_digits=10, decimal_places=1, null=True, blank=True,
        help_text="Recurs every N engine hours, if hour-based",
    )
    interval_days = models.IntegerField(
        null=True, blank=True, help_text="Recurs every N calendar days, if time-based instead"
    )

    def __str__(self):
        return f"{self.equipment} - {self.task_name}"


class WorkOrder(models.Model):
    """Planned/in-progress work — the stateful layer above MaintenanceRecord, which stays
    the historical ledger of completed service. Completing a work order creates the
    matching MaintenanceRecord automatically, so the maintenance forecast stays accurate."""

    STATUS_CHOICES = [
        ("open", "Open"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    equipment = models.ForeignKey(Equipment, on_delete=models.CASCADE, related_name="work_orders")
    schedule = models.ForeignKey(
        MaintenanceSchedule, on_delete=models.SET_NULL, null=True, blank=True, related_name="work_orders"
    )
    issue = models.ForeignKey(
        Issue, on_delete=models.SET_NULL, null=True, blank=True, related_name="work_orders"
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open")
    assigned_to = models.CharField(max_length=200, blank=True)
    equipment_down = models.BooleanField(
        default=True, help_text="Was the machine out of service while this was open?"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.equipment} - {self.title}"

    @property
    def labor_total(self):
        return sum((line.line_total for line in self.labor_lines.all()), Decimal("0"))

    @property
    def parts_total(self):
        return sum((line.line_total for line in self.part_lines.all()), Decimal("0"))

    @property
    def total_cost(self):
        return self.labor_total + self.parts_total


class WorkOrderLaborLine(models.Model):
    """One technician's time on a work order -- itemized so cost analysis can break
    labor out from parts instead of relying on a single guessed total."""

    work_order = models.ForeignKey(WorkOrder, on_delete=models.CASCADE, related_name="labor_lines")
    technician = models.CharField(max_length=200)
    hours = models.DecimalField(max_digits=6, decimal_places=2)
    rate = models.DecimalField(max_digits=8, decimal_places=2, default=120, help_text="$/hour")
    note = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.technician} - {self.hours}h on {self.work_order}"

    @property
    def line_total(self):
        return self.hours * self.rate


class WorkOrderPartLine(models.Model):
    """One line item of parts/materials used on a work order."""

    work_order = models.ForeignKey(WorkOrder, on_delete=models.CASCADE, related_name="part_lines")
    part_name = models.CharField(max_length=200)
    quantity = models.DecimalField(max_digits=8, decimal_places=2, default=1)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.quantity}x {self.part_name} on {self.work_order}"

    @property
    def line_total(self):
        return self.quantity * self.unit_cost


class MaintenanceRecord(models.Model):
    equipment = models.ForeignKey(Equipment, on_delete=models.CASCADE, related_name="maintenance_records")
    schedule = models.ForeignKey(
        MaintenanceSchedule, on_delete=models.SET_NULL, null=True, blank=True, related_name="records"
    )
    performed_at = models.DateTimeField()
    performed_by = models.CharField(max_length=200, blank=True)
    description = models.TextField()
    parts_used = models.TextField(blank=True)
    cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    hours_at_service = models.DecimalField(max_digits=10, decimal_places=1, null=True, blank=True)

    class Meta:
        ordering = ["-performed_at"]

    def __str__(self):
        return f"{self.equipment} - {self.performed_at:%Y-%m-%d}"


class TelemetryPing(models.Model):
    """One bundled sensor snapshot: GPS + speed + PM + vibration, as the device logs them together."""

    equipment = models.ForeignKey(Equipment, on_delete=models.CASCADE, related_name="telemetry_pings")
    recorded_at = models.DateTimeField(help_text="Device's own clock, not server receipt time")
    received_at = models.DateTimeField(auto_now_add=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    speed_kph = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    pm25 = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True, verbose_name="PM2.5 (µg/m³)")
    vibration_magnitude = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        help_text="Relative intensity, not calibrated g-force",
    )
    is_impact_event = models.BooleanField(default=False)

    class Meta:
        ordering = ["-recorded_at"]

    def __str__(self):
        return f"{self.equipment} @ {self.recorded_at:%Y-%m-%d %H:%M}"


class OilSample(models.Model):
    equipment = models.ForeignKey(Equipment, on_delete=models.CASCADE, related_name="oil_samples")
    sampled_at = models.DateTimeField()
    hours_at_sample = models.DecimalField(max_digits=10, decimal_places=1, null=True, blank=True)
    wear_metals = models.JSONField(blank=True, default=dict, help_text="e.g. iron/copper/silicon in ppm")
    viscosity = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    contamination_flags = models.CharField(max_length=300, blank=True)
    lab_recommendation = models.TextField(blank=True)

    class Meta:
        ordering = ["-sampled_at"]

    def __str__(self):
        return f"{self.equipment} - sample {self.sampled_at:%Y-%m-%d}"
