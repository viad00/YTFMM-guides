from django import forms
from django.conf import settings as s


class OrderForm(forms.Form):
    name_id = forms.IntegerField(label="UserID", required=True)
    sum_to_get = forms.FloatField(label="Sum of robux to get", required=True)
    pay_type = forms.ChoiceField(choices=s.PAY_CHOICES, required=True, widget=forms.RadioSelect(attrs={'class': 'form-check-input'}))
