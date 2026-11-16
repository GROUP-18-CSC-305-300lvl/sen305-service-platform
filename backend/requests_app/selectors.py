from django.db.models import Count, Q

from .models import ServiceRequest


def _visible_requests(*, user):
    queryset = ServiceRequest.objects.all()
    if user.is_staff:
        return queryset
    return queryset.filter(Q(requester=user) | Q(work_order__technician=user))


def service_request_list(*, user):
    return (
        _visible_requests(user=user)
        .select_related("requester", "category")
        .annotate(comment_count=Count("comments"))
        .order_by("-created_at")
    )


def service_request_filter(*, user, status="", query=""):
    queryset = service_request_list(user=user)
    if status:
        queryset = queryset.filter(status=status)
    if query:
        queryset = queryset.filter(
            Q(title__icontains=query)
            | Q(description__icontains=query)
            | Q(location__icontains=query)
        )
    return queryset


def service_request_get(*, user, request_id):
    return service_request_list(user=user).get(id=request_id)


def service_request_status_counts(*, user):
    status = ServiceRequest.Status
    return _visible_requests(user=user).aggregate(
        open=Count("id", filter=Q(status=status.OPEN)),
        assigned=Count("id", filter=Q(status=status.ASSIGNED)),
        resolved=Count("id", filter=Q(status=status.RESOLVED)),
    )