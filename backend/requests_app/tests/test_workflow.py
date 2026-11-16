from django.contrib.auth import get_user_model
from django.http import QueryDict
from django.test import TestCase
from django.urls import reverse

from requests_app.models import Category, ServiceRequest, WorkOrder
from requests_app.services import service_request_assign


class WorkflowTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user("owner", password="pass12345")
        self.staff = User.objects.create_user("staff", password="pass12345", is_staff=True)
        self.technician = User.objects.create_user("tech", password="pass12345", is_staff=True)
        self.category = Category.objects.create(name="Facilities")
        self.item = ServiceRequest.objects.create(
            requester=self.owner,
            category=self.category,
            title="Projector does not display",
            description="The projector reports no HDMI signal.",
            location="Room B12",
            priority=3,
        )

    def test_non_staff_assignment_returns_403_and_creates_no_work_order(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("requests:assign", args=[self.item.id]),
            {"technician": self.technician.id},
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(WorkOrder.objects.filter(service_request=self.item).exists())
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, ServiceRequest.Status.OPEN)

    def test_staff_assignment_creates_work_order_and_sets_assigned(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("requests:assign", args=[self.item.id]),
            {"technician": self.technician.id},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(WorkOrder.objects.filter(service_request=self.item).count(), 1)
        self.assertEqual(WorkOrder.objects.get(service_request=self.item).technician, self.technician)
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, ServiceRequest.Status.ASSIGNED)

    def test_resolution_without_assignment_leaves_request_unchanged(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("requests:resolve", args=[self.item.id]),
            {"work_notes": "Tried to resolve without a technician."},
        )
        self.assertEqual(response.status_code, 302)
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, ServiceRequest.Status.OPEN)
        self.assertIsNone(self.item.resolved_at)
        self.assertFalse(WorkOrder.objects.filter(service_request=self.item).exists())

    def test_assigned_technician_resolution_changes_both_models(self):
        service_request_assign(item=self.item, technician=self.technician, actor=self.staff)
        self.client.force_login(self.technician)
        response = self.client.post(
            reverse("requests:resolve", args=[self.item.id]),
            {"work_notes": "Replaced the HDMI cable."},
        )
        self.assertEqual(response.status_code, 302)

        self.item.refresh_from_db()
        self.assertEqual(self.item.status, ServiceRequest.Status.RESOLVED)
        self.assertIsNotNone(self.item.resolved_at)
        self.assertEqual(self.item.resolution_summary, "Replaced the HDMI cable.")

        work_order = WorkOrder.objects.get(service_request=self.item)
        self.assertEqual(work_order.work_notes, "Replaced the HDMI cable.")
        self.assertIsNotNone(work_order.completed_at)

    def test_filtered_pagination_preserves_q_and_status(self):
        for n in range(1, 13):
            ServiceRequest.objects.create(
                requester=self.owner,
                category=self.category,
                title=f"Synthetic request {n}",
                description="Synthetic pagination data.",
                location="Test Room",
                priority=3,
            )
        self.client.force_login(self.owner)

        page_one = self.client.get(reverse("requests:list"), {"q": "Synthetic", "status": "open"})
        self.assertEqual(page_one.status_code, 200)
        self.assertTrue(page_one.context["page_obj"].has_next())
        kept = QueryDict(page_one.context["filter_query"])
        self.assertEqual(kept["q"], "Synthetic")
        self.assertEqual(kept["status"], "open")
        self.assertNotIn("page", kept)

        page_two = self.client.get(
            reverse("requests:list"),
            {"q": "Synthetic", "status": "open", "page": 2},
        )
        self.assertEqual(page_two.context["page_obj"].number, 2)
        self.assertEqual(page_two.context["query"], "Synthetic")
        self.assertEqual(page_two.context["selected_status"], "open")
        kept_two = QueryDict(page_two.context["filter_query"])
        self.assertEqual(kept_two["q"], "Synthetic")
        self.assertEqual(kept_two["status"], "open")