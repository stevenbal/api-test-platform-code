# -*- coding: utf-8 -*-
# Generated by Django 1.11.16 on 2018-12-17 11:08
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('testsession', '0031_auto_20181217_1159'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='scenariocase',
            name='scenario',
        ),
        migrations.RemoveField(
            model_name='session',
            name='scenario',
        ),
        migrations.AddField(
            model_name='scenariocase',
            name='session_type',
            field=models.ForeignKey(default=None, null=True, on_delete=django.db.models.deletion.SET_NULL, to='testsession.SessionType'),
        ),
        migrations.AddField(
            model_name='sessiontype',
            name='application',
            field=models.CharField(max_length=200, null=True),
        ),
        migrations.AddField(
            model_name='sessiontype',
            name='role',
            field=models.CharField(max_length=200, null=True),
        ),
        migrations.AddField(
            model_name='sessiontype',
            name='standard',
            field=models.CharField(max_length=200, null=True),
        ),
        migrations.AddField(
            model_name='sessiontype',
            name='version',
            field=models.CharField(max_length=200, null=True),
        ),
        migrations.AlterField(
            model_name='session',
            name='session_type',
            field=models.ForeignKey(blank=True, default=None, null=True, on_delete=django.db.models.deletion.CASCADE, to='testsession.SessionType'),
        ),
        migrations.DeleteModel(
            name='Scenario',
        ),
    ]
