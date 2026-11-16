from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase
from django.utils import timezone

from requests_app.models import Category, ServiceRequest, WorkOrder


class ServiceRequestModelTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.requester = user_model.objects.create_user(username="requester")
        self.technician = user_model.objects.create_user(username="technician")
        self.category = Category.objects.create(name="Electrical")

    def make_request(self, **overrides):
        values = {
            "requester": self.requester,
            "category": self.category,
            "title": "Faulty socket",
            "description": "Socket does not supply power.",
            "location": "Software Engineering Lab",
            "priority": 2,
        }
        values.update(overrides)
        return ServiceRequest.objects.create(**values)

    def test_default_status_is_open(self):
        item = self.make_request()
        self.assertEqual(item.status, ServiceRequest.Status.OPEN)

    def test_priority_validator_rejects_zero(self):
        item = ServiceRequest(
            requester=self.requester,
            category=self.category,
            title="Invalid",
            description="Invalid priority.",
            location="Lab",
            priority=0,
        )
        with self.assertRaises(ValidationError):
            item.full_clean()

    def test_database_constraint_rejects_priority_six(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.make_request(priority=6)

    def test_category_in_use_is_protected(self):
        self.make_request()
        with self.assertRaises(ProtectedError):
            self.category.delete()

    def test_request_accepts_only_one_work_order(self):
        item = self.make_request()
        WorkOrder.objects.create(
            service_request=item,
            technician=self.technician,
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                WorkOrder.objects.create(
                    service_request=item,
                    technician=self.technician,
                )


class ServiceLevelAndResolutionTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.requester = user_model.objects.create_user(username="requester")
        self.category = Category.objects.create(name="ICT Support")

    def make_request(self, **overrides):
        values = {
            "requester": self.requester,
            "category": self.category,
            "title": "Network port dead",
            "description": "Port gives no link light.",
            "location": "Software Engineering Lab",
            "priority": 3,
        }
        values.update(overrides)
        return ServiceRequest.objects.create(**values)

    def test_due_before_query_returns_only_earlier_requests(self):
        now = timezone.now()
        early = self.make_request(title="Due yesterday", due_at=now - timedelta(days=1))
        self.make_request(title="Due in three days", due_at=now + timedelta(days=3))
        self.make_request(title="No due date")
        due_soon = ServiceRequest.objects.filter(due_at__lt=now + timedelta(days=1))
        self.assertQuerySetEqual(due_soon, [early])

    def test_resolved_without_date_or_summary_fails(self):
        item = self.make_request()
        item.status = ServiceRequest.Status.RESOLVED
        with self.assertRaises(ValidationError) as context:
            item.full_clean()
        self.assertIn("resolved_at", context.exception.message_dict)
        self.assertIn("resolution_summary", context.exception.message_dict)

    def test_closed_with_blank_summary_fails(self):
        item = self.make_request()
        item.status = ServiceRequest.Status.CLOSED
        item.resolved_at = timezone.now()
        item.resolution_summary = "   "
        with self.assertRaises(ValidationError) as context:
            item.full_clean()
        self.assertIn("resolution_summary", context.exception.message_dict)

    def test_resolved_with_date_and_summary_passes(self):
        item = self.make_request()
        item.status = ServiceRequest.Status.RESOLVED
        item.resolved_at = timezone.now()
        item.resolution_summary = "Replaced faulty patch cable."
        item.full_clean()