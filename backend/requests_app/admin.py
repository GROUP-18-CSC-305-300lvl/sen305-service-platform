from django.contrib import admin
from django.utils import timezone

from .models import Category, Comment, ServiceRequest, WorkOrder

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "description")

class CommentInline(admin.TabularInline):
    model = Comment
    extra = 0
    fields = ("author", "body", "is_internal", "created_at")
    readonly_fields = ("created_at",)

@admin.register(WorkOrder)
class WorkOrderAdmin(admin.ModelAdmin):
    list_display = ("service_request", "technician", "started_at", "completed_at")
    search_fields = ("service_request__title", "technician__username")
    autocomplete_fields = ("service_request", "technician")
    
@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("service_request", "author", "is_internal", "created_at")
    list_filter = ("is_internal", "created_at")
    search_fields = ("body", "service_request__title", "author__username")

class OverdueFilter(admin.SimpleListFilter):
    title = "overdue"
    parameter_name = "overdue"

    def lookups(self, request, model_admin):
        return [
            ("yes", "Overdue"),
            ("upcoming", "Not yet due"),
            ("none", "No due date"),
        ]

    def queryset(self, request, queryset):
        now = timezone.now()
        active = [
            ServiceRequest.Status.OPEN,
            ServiceRequest.Status.ASSIGNED,
            ServiceRequest.Status.IN_PROGRESS,
        ]
        if self.value() == "yes":
            return queryset.filter(due_at__lt=now, status__in=active)
        if self.value() == "upcoming":
            return queryset.filter(due_at__gte=now)
        if self.value() == "none":
            return queryset.filter(due_at__isnull=True)
        return queryset

@admin.register(ServiceRequest)
class ServiceRequestAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "status", "priority", "due_at", "resolved_at")
    list_filter = ("status", "category", OverdueFilter)
    search_fields = ("title", "description", "resolution_summary")       
