from django.contrib import admin
from .models import Order, Setting, Log

# Register your models here.


class SettingAdmin(admin.ModelAdmin):
    list_display = ('name', 'value')


admin.site.register(Setting, SettingAdmin)


class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'name_id', 'value_to_pay', 'payment_type', 'paid', 'created')


admin.site.register(Order, OrderAdmin)


class LogAdmin(admin.ModelAdmin):
    list_display = ('message')


admin.site.register(Log, LogAdmin)
