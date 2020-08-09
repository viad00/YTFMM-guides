from django.db import models
from django.conf import settings as s
import uuid

# Create your models here.


class Setting(models.Model):
    name=models.CharField(max_length=50, unique=True)
    value=models.TextField()


class Guide(models.Model):
    name=models.CharField(max_length=200, unique=True)
    img=models.ImageField()
    abstract=models.TextField()
    text=models.TextField()
    paid=models.TextField()
    price=models.PositiveIntegerField()


class Order(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    value_to_pay = models.PositiveIntegerField()
    guide = models.ForeignKey(Guide, models.SET_NULL, blank=True, null=True)
    payment_type = models.CharField(max_length=2, choices=s.PAY_CHOICES)
    created = models.DateTimeField(auto_now_add=True)
    paid = models.BooleanField(default=False)
    been_success = models.BooleanField(default=False)
    operation_id = models.CharField(max_length=255)
    visited_times = models.PositiveIntegerField(default=0)


class Log(models.Model):
    message = models.CharField(max_length=255)
