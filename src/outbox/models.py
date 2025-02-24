from django.db import models


class EventOutbox(models.Model):
    event_type = models.CharField(max_length=255)
    event_date_time = models.DateTimeField(auto_now_add=True)
    environment = models.CharField(max_length=255)
    event_context = models.JSONField()
    metadata_version = models.BigIntegerField(default=1)
    processed = models.BooleanField(default=False)
