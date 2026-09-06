from django.contrib import admin, messages
from django.core.exceptions import ValidationError

from .models import (
    Butchering, ButcheringExpense, ButcheringOutput,
    ButcheringSpecification, ButcheringSpecificationItem,
)
from .services import butchering_service


class ButcheringSpecificationItemInline(admin.TabularInline):
    model = ButcheringSpecificationItem
    extra = 1
    autocomplete_fields = ('child_product',)


@admin.register(ButcheringSpecification)
class ButcheringSpecificationAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent_product', 'active')
    list_filter = ('active',)
    search_fields = ('name', 'parent_product__name')
    autocomplete_fields = ('parent_product',)
    inlines = (ButcheringSpecificationItemInline,)


class ButcheringOutputInline(admin.TabularInline):
    model = ButcheringOutput
    extra = 1
    autocomplete_fields = ('product',)
    readonly_fields = ('unit_cost',)


class ButcheringExpenseInline(admin.TabularInline):
    model = ButcheringExpense
    extra = 1


@admin.register(Butchering)
class ButcheringAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'purchase', 'input_product', 'input_weight', 'output_weight',
        'difference', 'yield_percentage', 'date', 'status',
    )
    list_filter = ('status', 'date')
    search_fields = ('purchase__purchase_number', 'input_product__name', 'notes')
    autocomplete_fields = ('purchase', 'input_product', 'created_by')
    readonly_fields = (
        'output_weight', 'difference', 'yield_percentage', 'status',
        'created_at', 'updated_at',
    )
    date_hierarchy = 'date'
    ordering = ('-date', '-id')
    inlines = (ButcheringOutputInline, ButcheringExpenseInline)
    actions = ('confirm_butcherings', 'cancel_butcherings')

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    @admin.action(description="✅ Tanlangan bo'laklashlarni tasdiqlash (ombor yangilanadi)")
    def confirm_butcherings(self, request, queryset):
        ok, failed = 0, 0
        for butchering in queryset:
            try:
                butchering_service.confirm_butchering(butchering, user=request.user)
                ok += 1
            except ValidationError as exc:
                failed += 1
                self.message_user(request, f'{butchering}: {"; ".join(exc.messages)}', level=messages.ERROR)
        if ok:
            self.message_user(request, f'{ok} ta bolaklash tasdiqlandi.', level=messages.SUCCESS)
        if failed:
            self.message_user(request, f'{failed} tasida xatolik yuz berdi.', level=messages.WARNING)

    @admin.action(description="❌ Tanlangan bo'laklashlarni bekor qilish")
    def cancel_butcherings(self, request, queryset):
        ok, failed = 0, 0
        for butchering in queryset:
            try:
                butchering_service.cancel_butchering(butchering, user=request.user)
                ok += 1
            except ValidationError as exc:
                failed += 1
                self.message_user(request, f'{butchering}: {"; ".join(exc.messages)}', level=messages.ERROR)
        if ok:
            self.message_user(request, f'{ok} ta bolaklash bekor qilindi.', level=messages.SUCCESS)
        if failed:
            self.message_user(request, f'{failed} tasida xatolik yuz berdi.', level=messages.WARNING)


@admin.register(ButcheringOutput)
class ButcheringOutputAdmin(admin.ModelAdmin):
    list_display = ('butchering', 'product', 'quantity', 'unit_cost')
    search_fields = ('product__name', 'product__code')
    autocomplete_fields = ('butchering', 'product')
