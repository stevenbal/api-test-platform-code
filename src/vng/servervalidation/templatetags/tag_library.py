from django import template

register = template.Library()


@register.filter
def to_int(value):
    return int(value)


@register.filter
def index(l, i):
    return l[int(i)]
