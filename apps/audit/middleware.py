from apps.audit.context import audit_actor


class AuditMiddleware:
    """Har bir sayt so'rovi davomida qilingan o'zgarishlarni shu foydalanuvchiga yozadi."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        source = 'admin' if request.path.startswith('/admin/') else 'web'
        with audit_actor(lambda: getattr(request, 'user', None), source):
            return self.get_response(request)
