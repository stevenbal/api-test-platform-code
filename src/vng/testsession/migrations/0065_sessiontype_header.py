# Generated by Django 2.2a1 on 2019-03-25 14:56

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('testsession', '0064_auto_20190325_1435'),
    ]

    operations = [
        migrations.AddField(
            model_name='sessiontype',
            name='header',
            field=models.TextField(blank=True, default=None, null=True),
        ),
    ]
