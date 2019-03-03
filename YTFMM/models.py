from django.db import models

# Create your models here.


class Setting(models.Model):
    name=models.CharField(max_length=50, unique=True)
    value=models.CharField(max_length=200)
