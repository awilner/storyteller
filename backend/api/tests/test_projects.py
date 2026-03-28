from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from api.models import Project


class ProjectListTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="alice", password="pw")
        self.other = User.objects.create_user(username="bob", password="pw")
        self.client.force_login(self.user)

    def test_list_own_projects(self):
        Project.objects.create(owner=self.user, title="My Novel")
        Project.objects.create(owner=self.other, title="Bob's Novel")
        resp = self.client.get("/api/projects/")
        self.assertEqual(resp.status_code, 200)
        titles = [p["title"] for p in resp.json()]
        self.assertIn("My Novel", titles)
        self.assertNotIn("Bob's Novel", titles)

    def test_list_empty(self):
        resp = self.client.get("/api/projects/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    def test_list_unauthenticated(self):
        self.client.logout()
        resp = self.client.get("/api/projects/")
        self.assertEqual(resp.status_code, 403)


class ProjectCreateTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="alice", password="pw")
        self.client.force_login(self.user)

    def test_create_project(self):
        resp = self.client.post("/api/projects/", {
            "title": "New Novel",
            "description": "A great story",
        })
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["title"], "New Novel")
        self.assertEqual(data["description"], "A great story")
        self.assertTrue(Project.objects.filter(title="New Novel", owner=self.user).exists())

    def test_create_project_minimal(self):
        resp = self.client.post("/api/projects/", {"title": "Minimal"})
        self.assertEqual(resp.status_code, 201)

    def test_create_project_no_title(self):
        resp = self.client.post("/api/projects/", {"description": "no title"})
        self.assertEqual(resp.status_code, 400)

    def test_create_project_unauthenticated(self):
        self.client.logout()
        resp = self.client.post("/api/projects/", {"title": "Nope"})
        self.assertEqual(resp.status_code, 403)


class ProjectDeleteTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(username="alice", password="pw")
        self.other = User.objects.create_user(username="bob", password="pw")
        self.project = Project.objects.create(owner=self.owner, title="Novel")

    def test_delete_own_project(self):
        self.client.force_login(self.owner)
        resp = self.client.delete(f"/api/projects/{self.project.pk}/")
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(Project.objects.filter(pk=self.project.pk).exists())

    def test_delete_other_user_project(self):
        self.client.force_login(self.other)
        resp = self.client.delete(f"/api/projects/{self.project.pk}/")
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(Project.objects.filter(pk=self.project.pk).exists())

    def test_delete_nonexistent_project(self):
        self.client.force_login(self.owner)
        resp = self.client.delete("/api/projects/99999/")
        self.assertEqual(resp.status_code, 403)

    def test_delete_unauthenticated(self):
        resp = self.client.delete(f"/api/projects/{self.project.pk}/")
        self.assertEqual(resp.status_code, 403)
