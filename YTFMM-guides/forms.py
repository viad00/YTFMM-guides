from django import forms
from django.conf import settings as s


class OrderForm(forms.Form):
    guide_id = forms.IntegerField(label="Guide ID", required=True)
    pay_type = forms.ChoiceField(choices=s.PAY_CHOICES, required=True, widget=forms.RadioSelect(attrs={'class': 'form-check-input'}))
