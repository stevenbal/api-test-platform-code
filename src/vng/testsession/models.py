import json
import uuid
import re
import time

from tinymce.models import HTMLField

from django.conf import settings
from django.core.validators import RegexValidator
from django.core.files import File
from django.db import models
from django.utils import timezone
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _

from ordered_model.models import OrderedModel

from filer.fields.file import FilerFileField

import vng.postman.utils as postman

from vng.accounts.models import User
from vng.postman.choices import ResultChoices

from ..utils import choices


class SessionType(models.Model):

    name = models.CharField(_('Name'), max_length=200, unique=True)
    standard = models.CharField(_('Standard'), max_length=200, null=True)
    role = models.CharField(_('Role'), max_length=200, null=True)
    application = models.CharField(_('Application'), max_length=200, null=True)
    version = models.CharField(_('Version'), max_length=200, null=True)
    authentication = models.CharField(max_length=20, default=choices.AuthenticationChoices.no_auth, choices=choices.AuthenticationChoices.choices)
    description = HTMLField()
    client_id = models.TextField(default=None, null=True, blank=True)
    secret = models.TextField(default=None, null=True, blank=True)
    header = models.TextField(default=None, null=True, blank=True)
    database = models.BooleanField(help_text='Check if the a postgres db is needed in the Kubernetes cluster', default=False)
    db_data = models.TextField(default=None, null=True, blank=True)
    ZGW_images = models.BooleanField(default=False, blank=True)
    active = models.BooleanField(blank=True, default=True)

    class Meta:
        verbose_name = _('Session Type')
        verbose_name_plural = _('Sessions type')
        ordering = ('name',)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.ZGW_images:
            VNGEndpoint(name='ZRC', session_type=self).save()
            VNGEndpoint(name='NRC', session_type=self).save()
            VNGEndpoint(name='ZTC', session_type=self).save()
            VNGEndpoint(name='BRC', session_type=self).save()
            VNGEndpoint(name='DRC', session_type=self).save()
            VNGEndpoint(name='AC', session_type=self).save()


class InjectHeader(models.Model):

    session_type = models.ForeignKey(SessionType, on_delete=models.CASCADE)
    key = models.CharField(max_length=200)
    value = models.TextField()

    class Meta:
        unique_together = ('session_type', 'key')


class TestSession(models.Model):

    test_result = models.FileField(settings.MEDIA_FOLDER_FILES['testsession_log'], blank=True, null=True, default=None)
    json_result = models.TextField(blank=True, null=True, default=None)

    class Meta:
        verbose_name = _('Test Session')
        verbose_name_plural = _('Test Sessions')

    def save_test(self, file):
        name_file = str(uuid.uuid4())
        django_file = File(file)
        self.test_result.save(name_file, django_file)

    def save_test_json(self, file):
        text = file.read().replace('\n', '')
        self.json_result = text

    def display_test_result(self):
        if self.test_result:
            with open(self.test_result.path) as fp:
                return fp.read().replace('\n', '<br>')

    def is_success_test(self):
        if self.json_result is not None:
            return postman.get_outcome_json(self.json_result) == ResultChoices.success

    def get_json_obj(self):
        return postman.get_json_obj(self.json_result)


class VNGEndpoint(models.Model):

    port = models.PositiveIntegerField(default=8080, blank=True)
    url = models.URLField(
        max_length=200,
        blank=True,
        null=True,
        default=None,
        validators=[
            RegexValidator(
                regex='/$',
                message=_('The url must not contain a final slash'),
                code='Invalid_url',
                inverse_match=True
            )
        ],
        help_text=_('Base url (host of the service). E.g. http://ref.tst.vng.cloud, without the ending slash.')
    )
    path = models.CharField(
        max_length=200,
        default='',
        validators=[
            RegexValidator(
                regex='^/',
                message=_('The path must start with a slash'),
                code='Invalid_path',
            )
        ],
        help_text=_('Path url that is appended in the front end page. The path must contain the slash at \
                            the beginning. E.g. /zrc/api/v1/'),
        blank=True
    )
    name = models.CharField(
        max_length=200,
        validators=[
            RegexValidator(
                regex='^[^ ]*$',
                message=_('The name cannot contain spaces'),
                code='Invalid_name'
            )
        ]
    )
    docker_image = models.CharField(max_length=200, blank=True, null=True, default=None)
    session_type = models.ForeignKey(SessionType, on_delete=models.PROTECT)
    test_file = FilerFileField(null=True, blank=True, default=None, on_delete=models.SET_NULL)

    def __str__(self):
        # To show the session type when adding a scenario case
        return self.name + " ({})".format(self.session_type)


class EnvironmentalVariables(models.Model):

    vng_endpoint = models.ForeignKey(VNGEndpoint, on_delete=models.CASCADE)
    key = models.CharField(max_length=50)
    value = models.CharField(max_length=100)


class ScenarioCase(OrderedModel):

    url = models.CharField(max_length=200, help_text='''
    URL pattern that will be compared
    with the request and eventually matched.
    Wildcards can be added, e.g. '/test/{uuid}/stop'
    will match the URL '/test/c5429dcc-6955-4e22-9832-08d52205f633/stop'.
    ''')
    http_method = models.CharField(max_length=20, choices=choices.HTTPMethodChoices.choices, default=choices.HTTPMethodChoices.GET)
    vng_endpoint = models.ForeignKey(VNGEndpoint, on_delete=models.PROTECT)
    order_with_respect_to = 'vng_endpoint__session_type'

    class Meta(OrderedModel.Meta):
        pass

    def __str__(self):
        return '{} - {}'.format(self.http_method, self.url)

    def query_params(self):
        return [qp.name for qp in self.queryparamsscenario_set.all()]


class QueryParamsScenario(models.Model):

    scenario_case = models.ForeignKey(ScenarioCase, on_delete=models.PROTECT)
    name = models.CharField(max_length=50)
    expected_value = models.CharField(max_length=50, default='*')

    def __str__(self):
        if self.expected_value:
            return '{} - {}: {}'.format(self.scenario_case, self.name, self.expected_value)
        else:
            return '{} {}'.format(self.scenario_case, self.name)


class Session(models.Model):

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    name = models.CharField(_('Name'), max_length=30, unique=True, null=True)
    session_type = models.ForeignKey(SessionType, verbose_name=_('Session type'), on_delete=models.PROTECT)
    started = models.DateTimeField(_('Started at'), default=timezone.now)
    stopped = models.DateTimeField(_('Stopped at'), null=True, blank=True)
    status = models.CharField(max_length=20, choices=choices.StatusChoices.choices, default=choices.StatusChoices.starting)
    user = models.ForeignKey(User, verbose_name=_('User'), on_delete=models.SET_NULL, null=True)
    build_version = models.TextField(blank=True, null=True, default=None)
    error_message = models.TextField(blank=True, null=True, default=None)
    deploy_status = models.TextField(blank=True, null=True, default=None)
    deploy_percentage = models.IntegerField(default=None, null=True, blank=True)
    sandbox = models.BooleanField(default=False)
    supplier_name = models.CharField(max_length=100, blank=True, null=True)
    software_product = models.CharField(max_length=100, blank=True, null=True)
    product_role = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        verbose_name = _('Session')
        verbose_name_plural = _('Sessions')

    @staticmethod
    def assign_name(id):
        return "s{}{}".format(str(id), str(time.time()).replace('.', '-'))

    def __str__(self):
        if self.user:
            return "{} - {} - #{}".format(self.session_type, self.user.username, str(self.id))
        else:
            return "{} - #{}".format(self.session_type, str(self.id))

    def get_absolute_request_url(self, request):
        test_session_url = 'https://{}{}'.format(request.get_host(),
                                                 reverse('testsession:session_log', args=[self.uuid]))
        return test_session_url

    def is_stopped(self):
        return self.status == choices.StatusChoices.stopped

    def is_running(self):
        return self.status == choices.StatusChoices.running

    def is_starting(self):
        return self.status == choices.StatusChoices.starting

    def is_shutting_down(self):
        return self.status == choices.StatusChoices.shutting_down

    def get_report_stats(self):
        success, failed, not_called = 0, 0, 0
        reports = Report.objects.filter(session_log__in=self.sessionlog_set.all())
        for report in reports:
            if report.is_success():
                success += 1
            elif report.is_failed():
                failed += 1
            elif report.is_not_called():
                not_called += 1
        return success, failed, not_called + (ScenarioCase.objects.filter(vng_endpoint__session_type=self.session_type).count() - reports.count())


class ExposedUrl(models.Model):

    port = models.PositiveIntegerField(default=8080)
    subdomain = models.CharField(max_length=200, unique=True, null=True)
    session = models.ForeignKey(Session, on_delete=models.CASCADE)
    vng_endpoint = models.ForeignKey(VNGEndpoint, on_delete=models.CASCADE)
    test_session = models.ForeignKey(TestSession, blank=True, null=True, default=None, on_delete=models.CASCADE)
    docker_url = models.CharField(max_length=200, blank=True, null=True, default=None)

    def __str__(self):
        return '{} {}'.format(self.session, self.vng_endpoint)


class SessionLog(models.Model):

    uuid = models.UUIDField(default=uuid.uuid4, editable=False)
    date = models.DateTimeField(default=timezone.now)
    session = models.ForeignKey(Session, on_delete=models.SET_NULL, null=True)
    request = models.TextField(blank=True, null=True, default=None)
    response = models.TextField(blank=True, null=True, default=None)
    response_status = models.PositiveIntegerField(blank=True, null=True, default=None)

    def __str__(self):
        return '{} - {} - {}'.format(str(self.date), str(self.session),
                                     str(self.response_status))

    def request_path(self):
        return json.loads(self.request)['request']['path']

    def request_headers(self):
        return json.loads(self.request)['request']['header']

    def request_body(self):
        try:
            return json.loads(self.request)['request']['body']
        except:
            return ""

    def response_body(self):
        try:
            return json.loads(self.response)['response']['body']
        except:
            return ""


class Report(models.Model):

    class Meta:
        unique_together = ('scenario_case', 'session_log')

    scenario_case = models.ForeignKey(ScenarioCase, on_delete=models.CASCADE)
    session_log = models.ForeignKey(SessionLog, on_delete=models.CASCADE)
    result = models.CharField(max_length=20, choices=choices.HTTPCallChoices.choices, default=choices.HTTPCallChoices.not_called)

    def is_success(self):
        return self.result == choices.HTTPCallChoices.success

    def is_failed(self):
        return self.result == choices.HTTPCallChoices.failed

    def is_not_called(self):
        return self.result == choices.HTTPCallChoices.not_called

    def __str__(self):
        return 'Case: {} - Log: {} - Result: {}'.format(self.scenario_case, self.session_log, self.result)
