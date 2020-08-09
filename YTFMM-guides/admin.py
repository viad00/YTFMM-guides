from django.contrib import admin
from django_summernote.admin import SummernoteModelAdmin
from .models import Order, Setting, Log, Guide

# Register your models here.


class SettingAdmin(admin.ModelAdmin):
    list_display = ('name', 'value')


admin.site.register(Setting, SettingAdmin)


class GuideAdmin(SummernoteModelAdmin):
    list_display = ('name','price')
    summernote_fields = ('abstract', 'text', 'paid')


admin.site.register(Guide, GuideAdmin)


class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'guide', 'value_to_pay', 'payment_type', 'paid', 'created')


admin.site.register(Order, OrderAdmin)


class LogAdmin(admin.ModelAdmin):
    list_display = ('message',)


admin.site.register(Log, LogAdmin)
