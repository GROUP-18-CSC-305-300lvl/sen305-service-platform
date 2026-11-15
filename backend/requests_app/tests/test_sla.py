from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from requests_app.models import Category, ServiceRequest


class ResolutionRuleTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user("owner", password="pass12345")
        self.category = Category.objects.create(name="Facilities")

    def make(self, **kwargs):
        return ServiceRequest(
            requester=self.owner, category=self.category,
            title="Projector does not display",
            description="No HDMI signal.", location="Room B12", priority=3,
            **kwargs,
        )

    def test_resolved_without_summary_fails(self):
        item = self.make(status=ServiceRequest.Status.RESOLVED, resolved_at=timezone.now())
        with self.assertRaises(ValidationError) as ctx:
            item.full_clean()
        self.assertIn("resolution_summary", ctx.exception.message_dict)

    def test_whitespace_summary_fails(self):
        item = self.make(status=ServiceRequest.Status.RESOLVED,
                         resolved_at=timezone.now(), resolution_summary="   ")
        with self.assertRaises(ValidationError):
            item.full_clean()

    def test_resolved_without_resolved_at_fails(self):
        item = self.make(status=ServiceRequest.Status.RESOLVED, resolution_summary="Fixed cable.")
        with self.assertRaises(ValidationError) as ctx:
            item.full_clean()
        self.assertIn("resolved_at", ctx.exception.message_dict)

    def test_closed_without_summary_fails(self):
        item = self.make(status=ServiceRequest.Status.CLOSED, resolved_at=timezone.now())
        with self.assertRaises(ValidationError):
            item.full_clean()

    def test_valid_resolved_request_passes(self):
        item = self.make(status=ServiceRequest.Status.RESOLVED,
                         resolved_at=timezone.now(), resolution_summary="Fixed cable.")
        item.full_clean()

    def test_open_request_needs_no_summary(self):
        self.make(status=ServiceRequest.Status.OPEN).full_clean()


class DueDateTests(TestCase):
    def test_due_before_cutoff_query(self):
        owner = get_user_model().objects.create_user("owner", password="pass12345")
        category = Category.objects.create(name="Facilities")
        now = timezone.now()
        for title, delta in (("Soon", timedelta(hours=2)), ("Later", timedelta(days=5))):
            ServiceRequest.objects.create(
                requester=owner, category=category, title=title,
                description="x", location="Lab", priority=3, due_at=now + delta)
        due = ServiceRequest.objects.filter(due_at__lt=now + timedelta(days=1))
        self.assertEqual([r.title for r in due], ["Soon"])