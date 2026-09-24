from django.db import migrations


def backfill_profiles(apps, schema_editor):
    User = apps.get_model("auth", "User")
    UserProfile = apps.get_model("tracker", "UserProfile")
    for user in User.objects.all():
        if not UserProfile.objects.filter(user=user).exists():
            role = "admin" if user.is_superuser else "technician"
            UserProfile.objects.create(user=user, role=role)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("tracker", "0010_userprofile"),
    ]

    operations = [
        migrations.RunPython(backfill_profiles, noop),
    ]
