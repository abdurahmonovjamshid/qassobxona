from apps.sales.services import sale_service


def due_sales_notifications(request):
    """Har bir sahifada navbar bildirishnoma qo'ng'iroqchasi uchun
    to'lov muddati kelgan sotuvlar sonini beradi."""
    if not request.user.is_authenticated:
        return {}
    return {'due_sales_count': sale_service.get_due_sales().count()}
