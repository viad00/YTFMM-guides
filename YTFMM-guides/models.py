from django.db import models
from django.conf import settings as s
import uuid

# Create your models here.


class Setting(models.Model):
    name=models.CharField(max_length=50, unique=True)
    value=models.TextField(max_length=2000)


class Order(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name_id = models.PositiveIntegerField()
    value_to_pay = models.FloatField()
    sum_to_get = models.IntegerField()
    payment_type = models.CharField(max_length=2, choices=s.PAY_CHOICES)
    created = models.DateTimeField(auto_now_add=True)
    paid = models.BooleanField(default=False)
    been_success = models.BooleanField(default=False)
    operation_id = models.CharField(max_length=255)
    group_id=models.IntegerField()


class Log(models.Model):
    message = models.CharField(max_length=255)
