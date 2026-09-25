from django.db import migrations, models

import tracker.models


def backfill_api_tokens(apps, schema_editor):
    UserProfile = apps.get_model("tracker", "UserProfile")
    for profile in UserProfile.objects.all():
        profile.api_token = tracker.models.generate_api_token()
        profile.save(update_fields=["api_token"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("tracker", "0013_photo"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="api_token",
            field=models.CharField(
                default=tracker.models.generate_api_token,
                help_text="Bearer token this user's mobile app sends to authenticate to the API",
                max_length=64,
                null=True,
                unique=True,
            ),
        ),
        migrations.RunPython(backfill_api_tokens, noop),
        migrations.AlterField(
            model_name="userprofile",
            name="api_token",
            field=models.CharField(
                default=tracker.models.generate_api_token,
                help_text="Bearer token this user's mobile app sends to authenticate to the API",
                max_length=64,
                unique=True,
            ),
        ),
    ]
