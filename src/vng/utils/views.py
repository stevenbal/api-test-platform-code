import functools
from collections.abc import Iterable
from zds_client import ClientAuth

from weasyprint import HTML

from django import http
from django.http import Http404, HttpResponse
from django.template import loader, TemplateDoesNotExist
from django.shortcuts import get_object_or_404
from django.views.defaults import ERROR_500_TEMPLATE_NAME
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.csrf import csrf_exempt, requires_csrf_token
from django.core.exceptions import PermissionDenied
from django.views.generic.edit import ModelFormMixin, ProcessFormView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic.list import MultipleObjectMixin, MultipleObjectTemplateResponseMixin, ListView
from django.views.generic.detail import DetailView


def rsetattr(obj, attr, val):
    pre, _, post = attr.rpartition('.')
    return setattr(rgetattr(obj, pre) if pre else obj, post, val)


def rgetattr(obj, attr, *args):
    def _getattr(obj, attr):
        return getattr(obj, attr, *args)
    return functools.reduce(_getattr, [obj] + attr.split('.'))


def get_jwt(session):

    return ClientAuth(
        client_id=session.client_id,
        secret=session.secret
    )


@requires_csrf_token
def server_error(request, template_name=ERROR_500_TEMPLATE_NAME):
    """
    500 error handler.

    Templates: :template:`500.html`
    Context: None
    """
    try:
        template = loader.get_template(template_name)
    except TemplateDoesNotExist:
        if template_name != ERROR_500_TEMPLATE_NAME:
            # Reraise if it's a missing custom template.
            raise
        return http.HttpResponseServerError('<h1>Server Error (500)</h1>', content_type='text/html')
    context = {'request': request}
    return http.HttpResponseServerError(template.render(context))


class ObjectOwner(LoginRequiredMixin):
    field_name = None
    user_field = 'user'

    def check_object(self, obj):
        if self.field_name is None:
            return self.request.user == rgetattr(obj, self.user_field)
        return self.request.user == rgetattr(obj, self.field_name)

    def check_ownership(self, queryset):
        if not isinstance(queryset, Iterable):
            return self.check_object(queryset)
        if len(queryset) == 0:
            return queryset
        if self.field_name is None:
            params = {
                self.user_field: self.request.user
            }
        else:
            params = {
                self.field_name: self.request.user
            }
        qs = queryset.filter(**params).distinct()
        if len(qs) == 0:
            raise PermissionDenied
        else:
            return qs


class CSRFExemptMixin(object):
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super(CSRFExemptMixin, self).dispatch(*args, **kwargs)


class OwnerSingleObject(ObjectOwner, DetailView):

    pk_name = 'pk'
    slug_pk_name = 'pk'

    def get_queryset(self, object):
        return object.__class__.objects.filter(
            **{
                self.slug_pk_name: getattr(object, self.slug_pk_name)
            }
        )

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.check_ownership(self.get_queryset(self.object))
        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)

    def get_object(self):
        if not hasattr(self, 'pk_name'):
            raise Exception('Field "pk_name" in subclasses has not been defined')

        pk = self.kwargs.get(self.pk_name)
        if not pk:
            raise Exception('Primary key param name not defined in the URLs')
        obj = get_object_or_404(self.model, **{
            self.slug_pk_name: pk
        })

        return obj


class PDFGenerator():

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs).render().content.decode('utf-8')
        pdf = HTML(string=response, base_url=request.build_absolute_uri('/')).write_pdf()
        response = HttpResponse(pdf, content_type='application/pdf')
        if hasattr(self, 'filename'):
            response['Content-Disposition'] = 'attachment; filename="{}"'.format(self.filename)
        return response
