import json
import re
import logging
import requests

from urllib import parse
from subdomains.utils import reverse as reverse_sub
from django.shortcuts import get_object_or_404
from django.views import View
from django.utils import timezone
from django.db.models import Count
from django.core.exceptions import PermissionDenied
from django.http import (
    Http404, HttpResponse, HttpResponseForbidden, JsonResponse
)

from rest_framework import generics, permissions, viewsets, views, mixins
from rest_framework.authentication import (
    SessionAuthentication, TokenAuthentication
)
from .models import (
    ScenarioCase, Session, SessionLog, SessionType, ExposedUrl, Report,
    QueryParamsScenario, InjectHeader
)

from ..utils import choices
from ..utils.views import CSRFExemptMixin, get_jwt

from .permission import IsOwner
from .serializers import (
    SessionSerializer, SessionTypesSerializer, ExposedUrlSerializer, ScenarioCaseSerializer,
    SessionStatusSerializer
)
from .views import bootstrap_session
from .task import run_tests, stop_session

logger = logging.getLogger(__name__)


class SessionViewStatusSet(
        mixins.RetrieveModelMixin,
        viewsets.GenericViewSet):
    serializer_class = SessionStatusSerializer
    authentication_classes = (TokenAuthentication, SessionAuthentication)
    permission_classes = (permissions.IsAuthenticated, IsOwner)
    queryset = Session.objects.all()


class SessionViewSet(
        mixins.CreateModelMixin,
        mixins.ListModelMixin,
        mixins.RetrieveModelMixin,
        viewsets.GenericViewSet):
    """
    retrieve:
    Session detail.

    Return the given session's detail.

    list:
    Session list

    Return the list of all the sessions created by the user.

    create:
    Session create.

    Create a new session instance.
    """
    serializer_class = SessionSerializer
    authentication_classes = (TokenAuthentication, SessionAuthentication)
    permission_classes = (permissions.IsAuthenticated, IsOwner)

    def get_queryset(self):
        return Session.objects.all().prefetch_related('exposedurl_set').filter(user=self.request.user)

    def perform_create(self, serializer):
        session = serializer.save(
            user=self.request.user,
            pk=None,
            status=choices.StatusChoices.starting,
            name=Session.assign_name(self.request.user.id),
            started=timezone.now()
        )
        try:
            bootstrap_session(session.id)
        except Exception as e:
            logger.exception(e)
            session.delete()


class StopSessionView(generics.ListAPIView):
    """
    Stop Session

    Stop the session and retrieve all the scenario cases related to it.
    """
    authentication_classes = (TokenAuthentication, SessionAuthentication)
    permission_classes = (permissions.IsAuthenticated, IsOwner)
    serializer_class = ScenarioCaseSerializer

    def perform_operations(self, session):
        if session.status == choices.StatusChoices.stopped or session.status == choices.StatusChoices.shutting_down:
            return
        stop_session.delay(session.pk)
        session.status = choices.StatusChoices.shutting_down
        session.save()
        run_tests.delay(session.pk)

    def get_queryset(self):
        scenarios = ScenarioCase.objects.filter(vng_endpoint__session_type__session=self.kwargs['pk'])
        session = get_object_or_404(Session, id=self.kwargs['pk'])
        if session.user != self.request.user:
            return HttpResponseForbidden()
        self.perform_operations(session)
        return scenarios


class ResultSessionView(views.APIView):
    """
    Result of a Session

    Return for each scenario case related to the session, if that call has been performed and the global outcome.
    """
    authentication_classes = (TokenAuthentication, SessionAuthentication)
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, pk, *args, **kwargs):
        res = None
        session = self.get_object()
        if session.user != request.user:
            raise PermissionDenied
        scenario_cases = ScenarioCase.objects.filter(vng_endpoint__session_type=session.session_type)
        report = list(Report.objects.filter(session_log__session=session))

        def check(scenario_cases, report):
            if len(report) == 0:
                return {'result': 'Geen oproep uitgevoerd'}
            for rp in report:
                if rp.result == choices.HTTPCallChoices.failed:
                    return {'result': 'mislukt'}
            if len(report) < len(scenario_cases):
                return {'result': 'Gedeeltelijk succesvol'}
            else:
                return {'result': 'Succesvol'}

        if len(scenario_cases) == 0:
            res = {'result': 'No scenario cases available'}
        else:
            res = check(scenario_cases, report)

        res['report'] = []
        for case in scenario_cases:
            is_in = False
            for rp in report:
                if rp.scenario_case == case:
                    is_in = True
                    break
            if not is_in:
                report.append(Report(scenario_case=case))

        for rp in report:
            call = {
                'scenario_case': ScenarioCaseSerializer(rp.scenario_case).data
            }
            call['result'] = rp.result
            res['report'].append(call)

        res['test_session_url'] = session.get_absolute_request_url(request)
        response = HttpResponse(json.dumps(res))
        response['Content-Type'] = 'application/json'
        return response

    def get_object(self):
        self.session = get_object_or_404(Session, pk=self.kwargs['pk'])
        return self.session


class SessionTypesViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """
    Session types

    Return all the session types
    """
    authentication_classes = (TokenAuthentication, SessionAuthentication)
    permission_classes = (permissions.IsAuthenticated, )
    serializer_class = SessionTypesSerializer

    def get_queryset(self):
        return SessionType.objects.all()


class ExposedUrlView(mixins.ListModelMixin, viewsets.GenericViewSet):
    """
    Exposed url

    Return a list of all the exposed url of a certain session.
    """
    authentication_classes = (TokenAuthentication, SessionAuthentication)
    permission_classes = (permissions.IsAuthenticated, IsOwner)
    serializer_class = ExposedUrlSerializer
    user_path = ['session']

    def get_queryset(self):
        qs = ExposedUrl.objects.filter(session=self.kwargs['pk'])
        self.check_object_permissions(self.request, qs)
        return qs


class RunTest(CSRFExemptMixin, View):
    """ Proxy-view between clients and servers """
    error_codes = [(400, 599)]  # boundaries considered as errors

    def get_queryset(self):
        return get_object_or_404(ExposedUrl, subdomain=self.request.subdomain).session

    def match_url(self, url, compare, query_params):
        '''
        Return True if the url matches the compare url.
        The compare url contains the parameter matching group {param}
        '''
        # casting of the reference url into a regex
        param_pattern = '{[^/]+}'
        any_c = '[^/]+'
        parsed_url = '( |/)*' + re.sub(param_pattern, any_c, compare)
        if len(query_params) == 0:
            parsed_url += '$'
        else:
            parsed_url += '?'
        check_url = url.replace('/api/v1//', '/api/v1/')
        logger.info("Parsed: %s", parsed_url)
        logger.info("URL: %s", check_url)
        if re.search(parsed_url, check_url) is not None:
            if self.request.method == 'POST':
                params = self.request.POST
            else:
                params = self.request.GET
            for qp in query_params:
                par = params.get(qp.name)
                if par is None or (qp.expected_value != '*' and qp.expected_value != par):
                    return False
            return True

    def get_http_header(self, request, endpoint, session):
        '''
        Extracts the http header from the request and add the authorization header for
        gemma platform
        '''
        whitelist = ['host', 'cookie', 'content-length']
        request_headers = {}
        for header, value in request.headers.items():
            if header.lower() not in whitelist:
                request_headers[header] = value

        if session.session_type.authentication == choices.AuthenticationChoices.jwt:
            jwt_auth = get_jwt(session.session_type).credentials()
            for k, i in jwt_auth.items():
                if k not in request_headers:
                    request_headers[k] = i
        elif session.session_type.authentication == choices.AuthenticationChoices.header:
            request_headers['authorization'] = session.session_type.header

        # inject the eventual headers
        to_inject = InjectHeader.objects.filter(session_type=session.session_type)
        for header in to_inject:
            request_headers[header.key] = header.value

        return request_headers

    def save_call(self, request, request_method_name, url, relative_url, session, status_code, session_log):
        '''
        Find the matching scenario case with the same url and method, if one match is found,
        the result of the call is overrided
        '''
        logger.info("Saving call")
        logger.info(request_method_name)
        logger.info(url)
        logger.info(relative_url)
        scenario_cases = ScenarioCase.objects.filter(vng_endpoint__session_type=session.session_type).annotate(count=Count('queryparamsscenario')).order_by('-count')
        for case in scenario_cases:
            logger.info(case)
            if case.http_method.lower() == request_method_name.lower():
                if self.match_url(request.build_absolute_uri(), case.url, QueryParamsScenario.objects.filter(scenario_case=case)):
                    pre_exist = Report.objects.filter(scenario_case=case).filter(session_log__session=session)
                    if len(pre_exist) == 0:
                        report = Report(scenario_case=case, session_log=session_log)
                    else:
                        report = pre_exist[0]
                    is_failed = False
                    for a, b in self.error_codes:
                        if status_code >= a and status_code <= b:
                            report.result = choices.HTTPCallChoices.failed
                            report.session_log = session_log
                            is_failed = True
                            break
                    if not is_failed and not report.is_failed() or (session.sandbox and not is_failed):
                        report.session_log = session_log
                        report.result = choices.HTTPCallChoices.success
                    logger.info("Saving report: %s", report.result)
                    report.save()
                    break

    def sub_url_response(self, content, host, endpoint):
        '''
        Replace the url of the response body

        Arguments:
            content Str -- Body of the response
            host Str -- Host of the webservice
            endpoint ExposedUrl -- ExposedUrl corresponding the call

        Returns:
            Str -- The body after the rewrite
        '''

        sub = host
        if endpoint.vng_endpoint.url is not None:
            if not endpoint.vng_endpoint.url.endswith('/'):
                if sub.endswith('/'):
                    sub = sub[:-1]
            else:
                if not sub.endswith('/'):
                    sub = sub + '/'
            return re.sub(endpoint.vng_endpoint.url, sub, content)
        else:
            query = parse.urlparse(sub)
            if not sub.endswith('/'):
                sub = sub + '/'
            return re.sub(
                '{}://{}:{}/'.format(query.scheme, endpoint.docker_url, endpoint.port),
                sub,
                content
            )

    def sub_url_request(self, content, host, endpoint):
        '''
        Replace the url of the request body

        Arguments:
            content Str -- Body of the request
            host Str -- Host of the webservice
            endpoint ExposedUrl -- ExposedUrl corresponding the call

        Returns:
            Str -- The body after the rewrite
        '''
        sub = host
        if endpoint.vng_endpoint.url is not None:
            if not endpoint.vng_endpoint.url.endswith('/'):
                if sub.endswith('/'):
                    sub = sub[:-1]
            else:
                if not sub.endswith('/'):
                    sub = sub + '/'
            return re.sub(sub, endpoint.vng_endpoint.url, content)
        else:
            query = parse.urlparse(sub)
            if not sub.endswith('/'):
                sub = sub + '/'
            return re.sub(
                sub,
                '{}://{}:{}/'.format(query.scheme, endpoint.docker_url, endpoint.port),
                content
            )

    def parse_response(self, response, request, base_url, endpoints):
        """
        Rewrites the VNG Reference responses to make use of ATV URL endpoints:
        https://ref.tst.vng.cloud/zrc/api/v1/zaken/123
        ->
        https://testplatform/runtest/XXXX/api/v1/zaken/123
        """
        parsed = response.text
        for ep in endpoints:
            host = reverse_sub('run_test', ep.subdomain, kwargs={
                'relative_url': ''
            })
            parsed = self.sub_url_response(parsed, host, ep)
            logger.info("Rewriting response body: {}".format(parsed))
        return parsed

    def parse_response_text(self, text, endpoints):
        for ep in endpoints:
            host = reverse_sub('run_test', ep.subdomain, kwargs={
                'relative_url': ''
            })
            parsed = self.sub_url_response(text, host, ep)
        return parsed

    def rewrite_request_body(self, request, exposed):
        """
        Rewrites the request body's to replace the ATV URL endpoints to the VNG Reference endpoints
        https://testplatform/runtest/XXXX/api/v1/zaken/123
        ->
        https://ref.tst.vng.cloud/zrc/api/v1/zaken/123
        """
        parsed = request.body.decode('utf-8')
        for eu in exposed:
            host = reverse_sub('run_test', eu.subdomain, kwargs={
                'relative_url': ''
            })
            parsed = self.sub_url_request(parsed, host, eu)
        logger.info("Rewriting request body:{}".format(parsed))
        return parsed

    def build_url(self, eu, arguments):
        self.kwargs['relative_url']
        if eu.vng_endpoint.url is not None:
            request_url = '{}/{}?{}'.format(eu.vng_endpoint.url, self.kwargs['relative_url'], arguments)
        else:
            request_url = 'http://{}:{}/{}?{}'.format(eu.docker_url, eu.port, self.kwargs['relative_url'], arguments)
        if arguments == '':
            request_url = request_url[:-1]
        return request_url

    def build_method(self, request_method_name, request, body=False):
        self.session = self.get_queryset()
        eu = get_object_or_404(ExposedUrl, session=self.session, subdomain=request.subdomain)
        request_header = self.get_http_header(request, eu.vng_endpoint, self.session)
        session_log, session = self.build_session_log(request, request_header)
        if session.is_stopped():
            raise Http404()
        endpoints = ExposedUrl.objects.filter(session=session)
        arguments = request.META['QUERY_STRING']

        request_url = self.build_url(eu, arguments)
        logger.info('Requesting the url:{}'.format(request_url))
        method = getattr(requests, request_method_name)

        def make_call():
            if body:
                rewritten_body = self.rewrite_request_body(request, endpoints)
                logger.info("Request body after rewrite: %s", rewritten_body)
                response = method(request_url, data=rewritten_body, headers=request_header, allow_redirects=False)
            else:
                response = method(request_url, headers=request_header, allow_redirects=False)
            return response
        try:
            response = make_call()
        except Exception as e:
            try:
                request_header['Host'] = '{}:{}'.format(eu.docker_url, eu.port)
                response = make_call()
            except Exception as e:
                logger.exception(e)
                raise Http404()

        self.add_response(response, session_log, request_url, request)

        self.save_call(request, request_method_name, request.subdomain,
                       self.kwargs['relative_url'], session, response.status_code, session_log)
        reply = HttpResponse(self.parse_response(response, request, eu.vng_endpoint.url, endpoints), status=response.status_code)
        white_headers = ['Content-type', 'location']
        for h in white_headers:
            if h in response.headers:
                reply[h] = self.parse_response_text(response.headers[h], endpoints)

        return reply

    def build_method_handler(self, request_method_name, request, body=False):
        try:
            return self.build_method(request_method_name, request, body)
        except Http404:
            return JsonResponse({
                'info': 'The requested resource has been already turned off.'
            })

    def get(self, request, *args, **kwargs):
        return self.build_method_handler('get', request)

    def post(self, request, *args, **kwargs):
        return self.build_method_handler('post', request, body=True)

    def put(self, request, *args, **kwargs):
        return self.build_method_handler('put', request, body=True)

    def delete(self, request, *args, **kwargs):
        return self.build_method_handler('delete', request)

    def patch(self, request, *args, **kwargs):
        return self.build_method_handler('patch', request, body=True)

    def build_session_log(self, request, header):
        session = self.session
        session_log = SessionLog(session=session)
        if 'host' in header:
            if type(header['host']) != str:
                header['host'] = header['host'].decode('utf-8')

        request_dict = {
            "request": {
                "path": "{} {}".format(request.method, request.build_absolute_uri()),
                "body": request.body.decode('utf-8'),
                "header": header
            }
        }
        session_log.request = json.dumps(request_dict)

        return session_log, session

    def add_response(self, response, session_log, request_url, request):
        response_dict = {
            "response": {
                "status_code": response.status_code,
                "body": response.text,
                "path": "{} {}".format(request.method, request_url),
            }
        }
        session_log.response_status = response.status_code
        session_log.response = json.dumps(response_dict)
        session_log.save()


class ResultTestsessionViewShield(views.APIView):

    def get(self, request, uuid=None):
        session = get_object_or_404(Session, uuid=uuid)
        scenario_case = ScenarioCase.objects.filter(vng_endpoint__session_type=session.session_type)
        report = list(Report.objects.filter(session_log__session=session))
        report_ordered = []
        is_error = False
        not_full = False

        for case in scenario_case:
            missing = False
            for rp in report:
                if rp.result == choices.HTTPCallChoices.failed:
                    is_error = True
                if rp.scenario_case == case and rp.result != choices.HTTPCallChoices.not_called:
                    report_ordered.append(rp)
                    missing = True
                    break
            if not missing:
                not_full = True

        if not scenario_case:
            message = 'No results'
            color = 'inactive'
        elif is_error:
            message = 'Failed'
            color = 'red'
        elif not_full:
            message = 'Not completed'
            color = 'orange'
        else:
            message = 'Success'
            color = 'green'
            is_error = False

        result = {
            'schemaVersion': 1,
            'label': 'API Test Platform',
            'message': message,
            'color': color,
            'isError': is_error,
        }

        return JsonResponse(result)
