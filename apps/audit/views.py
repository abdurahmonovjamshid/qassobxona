from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import render

from apps.audit.models import AuditLog, section_label
from apps.common.date_filters import get_date_range


def can_view_audit(user):
    """Rollar tizimi bo'lsa (Mezon) — "audit" bo'limiga ruxsat; aks holda faqat superuser."""
    try:
        from apps.accounts.roles import can_access
    except ImportError:
        return user.is_superuser
    return can_access(user, 'audit')


@login_required
def audit_list(request):
    if not can_view_audit(request.user):
        raise PermissionDenied
    logs = AuditLog.objects.select_related('user', 'content_type')
    date_from, date_to = get_date_range(request)
    if date_from:
        logs = logs.filter(created_at__date__gte=date_from)
    if date_to:
        logs = logs.filter(created_at__date__lte=date_to)
    for key in ('user', 'content_type', 'action', 'source'):
        value = request.GET.get(key)
        if value:
            logs = logs.filter(**{f'{key}_id' if key in ('user', 'content_type') else key: value})

    page = Paginator(logs, 50).get_page(request.GET.get('page'))
    query = request.GET.copy()
    query.pop('page', None)
    used_types = AuditLog.objects.values_list('content_type', flat=True).distinct()
    used_users = AuditLog.objects.exclude(user=None).values_list('user', flat=True).distinct()
    return render(request, 'audit/list.html', {
        'page': page,
        'query': query.urlencode(),
        'date_from': date_from,
        'date_to': date_to,
        'users': get_user_model().objects.filter(pk__in=used_users).order_by('username'),
        'content_types': sorted(((ct.id, section_label(ct)) for ct in ContentType.objects.filter(pk__in=used_types)),
                                key=lambda item: item[1]),
        'actions': AuditLog.Action.choices,
        'sources': AuditLog.Source.choices,
    })
