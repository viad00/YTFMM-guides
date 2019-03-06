from django import forms


class OrderForm(forms.Form):
    name_id = forms.IntegerField(label="UserID", required=True)
    sum_to_get = forms.DecimalField(label="Sum of robux to get", required=True)
    PAY_CHOICES = (
        ('YA', 'Яндекс Деньги: Комиссия 0.5%'),
        ('KE', 'dadsdassdas'),
        ('23', 'asdsafsfdfd'),
    )
    pay_type = forms.ChoiceField(choices=PAY_CHOICES, required=True, widget=forms.RadioSelect(attrs={'class': 'form-check-input'}))
