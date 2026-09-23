"""Daily PM alert digest.

Scans every piece of equipment's maintenance forecast and, if anything is OVERDUE
or DUE SOON, emails a plain-text summary to ALERT_RECIPIENTS (settings.py). Each
recipient can be a normal email address or a carrier email-to-SMS gateway address
(e.g. 5551234567@vtext.com) -- both just work, since it's plain email underneath.

Run manually:
    python manage.py check_pm_alerts

Schedule it (Windows Task Scheduler, daily):
    Program:   <path to>.venv\\Scripts\\python.exe
    Arguments: manage.py check_pm_alerts
    Start in:  <project root>

If ALERT_RECIPIENTS isn't set yet, this prints the digest to the console instead
of sending anything, so it's always safe to run.
"""

from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.utils import timezone

from tracker.models import Equipment
from tracker.views import _compute_maintenance_forecast


class Command(BaseCommand):
    help = "Email/print a digest of any maintenance that is overdue or due soon."

    def handle(self, *args, **options):
        alert_items = []
        for equipment in Equipment.objects.select_related("customer").all():
            for f in _compute_maintenance_forecast(equipment):
                if f["status"] in ("overdue", "due_soon"):
                    alert_items.append({"equipment": equipment, **f})

        if not alert_items:
            self.stdout.write(self.style.SUCCESS("Nothing overdue or due soon. No alert sent."))
            return

        overdue = [i for i in alert_items if i["status"] == "overdue"]
        due_soon = sorted(
            (i for i in alert_items if i["status"] == "due_soon"),
            key=lambda i: i["hours_remaining"],
        )
        overdue.sort(key=lambda i: i["hours_remaining"])  # most overdue first (most negative)

        lines = [f"PM alert digest -- {timezone.now():%Y-%m-%d %H:%M}", ""]

        if overdue:
            lines.append(f"OVERDUE ({len(overdue)}):")
            for i in overdue:
                lines.append(
                    f"  - {i['equipment'].label}: {i['schedule'].task_name} "
                    f"-- {abs(i['hours_remaining'])} hrs overdue"
                )
            lines.append("")

        if due_soon:
            lines.append(f"DUE SOON ({len(due_soon)}):")
            for i in due_soon:
                due_date = i["forecast_date"].strftime("%Y-%m-%d") if i["forecast_date"] else "unknown"
                lines.append(
                    f"  - {i['equipment'].label}: {i['schedule'].task_name} "
                    f"-- {i['hours_remaining']} hrs remaining, est. {due_date}"
                )
            lines.append("")

        lines.append("-- Fleet PM Tracker")
        body = "\n".join(lines)

        recipients = [r.strip() for r in getattr(settings, "ALERT_RECIPIENTS", []) if r.strip()]
        if not recipients:
            self.stdout.write(
                self.style.WARNING(
                    "No ALERT_RECIPIENTS configured (set the PM_ALERT_RECIPIENTS env var) "
                    "-- printing the digest instead of sending it:"
                )
            )
            self.stdout.write(body)
            return

        send_mail(
            subject=f"PM alerts: {len(overdue)} overdue, {len(due_soon)} due soon",
            message=body,
            from_email=getattr(settings, "ALERT_FROM_EMAIL", "pm-alerts@localhost"),
            recipient_list=recipients,
        )
        self.stdout.write(self.style.SUCCESS(f"Digest sent to {len(recipients)} recipient(s):"))
        self.stdout.write(body)
