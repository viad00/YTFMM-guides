# Generated by Django 2.1.7 on 2019-03-17 21:21

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('YTFMM', '0009_auto_20190317_1729'),
    ]

    operations = [
        migrations.AlterField(
            model_name='order',
            name='payment_type',
            field=models.CharField(choices=[('YA', 'Яндекс Деньги'), ('QI', 'Qiwi')], max_length=2),
        ),
    ]
