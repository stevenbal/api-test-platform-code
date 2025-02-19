from rest_framework import routers

from django.urls import path, re_path

from . import api_views, apps
from ..utils.schema import schema_view


app_name = apps.AppConfig.__name__


router = routers.SimpleRouter()
router.register('testsessions', api_views.SessionViewSet, 'test_session')
router.register('sessiontypes', api_views.SessionTypesViewSet, 'session_types')
router.register('exposed_url', api_views.ExposedUrlView, 'exposed_url')
router.register('status', api_views.SessionViewStatusSet, 'test_session-status')


urlpatterns = router.urls


urlpatterns += [
    re_path(r'schema/openapi(?P<format>\.json|\.yaml)$', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('schema/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    path('testsession-run-shield/<uuid:uuid>/', api_views.ResultTestsessionViewShield.as_view(), name='testsession-shield'),
    path('testsessions/<int:pk>/stop/', api_views.StopSessionView.as_view(), name='stop_session'),
    path('testsessions/<int:pk>/result/', api_views.ResultSessionView.as_view(), name='result_session'),
    path('testsessions/<int:pk>/stop/', api_views.StopSessionView.as_view(), name='stop_session'),
    path('testsessions/<int:pk>/result/', api_views.ResultSessionView.as_view(), name='result_session'),
]
