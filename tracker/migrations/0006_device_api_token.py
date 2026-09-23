from django.db import migrations, models

import tracker.models


class Migration(migrations.Migration):

    dependencies = [
        ("tracker", "0005_workorder"),
    ]

    operations = [
        migrations.AddField(
            model_name="device",
            name="api_token",
            field=models.CharField(
                default=tracker.models.generate_api_token,
                help_text="Bearer token the device sends to authenticate to /api/ingest/",
                max_length=64,
                unique=True,
            ),
        ),
    ]
