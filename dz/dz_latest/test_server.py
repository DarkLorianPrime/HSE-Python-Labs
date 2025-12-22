import unittest
import json
import threading
import time
import os
from http.client import HTTPConnection
from main_latest import run, TASKS_FILE


class TestTodoServer(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # перед стартом удаляем файл, чтобы тесты были чистыми
        if os.path.exists(TASKS_FILE):
            os.remove(TASKS_FILE)

        cls.server_thread = threading.Thread(target=run, daemon=True)
        cls.server_thread.start()
        time.sleep(1)

    def setUp(self):
        self.conn = HTTPConnection("localhost", 8000)

    def tearDown(self):
        self.conn.close()

    # ---------- helpers ----------

    def _post(self, path, body=None):
        self.conn.request(
            "POST",
            path,
            body=json.dumps(body) if body else None,
            headers={"Content-Type": "application/json"}
        )
        return self.conn.getresponse()

    def _get(self, path):
        self.conn.request("GET", path)
        return self.conn.getresponse()

    def _delete(self, path):
        self.conn.request("DELETE", path)
        return self.conn.getresponse()

    # ---------- tests ----------

    def test_create_task_success(self):
        response = self._post("/tasks", {
            "title": "Write tests",
            "priority": "high"
        })

        data = json.loads(response.read())
        self.assertEqual(response.status, 201)
        self.assertEqual(data["title"], "Write tests")
        self.assertEqual(data["priority"], "high")
        self.assertFalse(data["isDone"])
        self.assertIn("id", data)

    def test_create_task_invalid_priority(self):
        response = self._post("/tasks", {
            "title": "Bad task",
            "priority": "urgent"
        })

        self.assertEqual(response.status, 400)

    def test_get_all_tasks(self):
        response = self._get("/tasks")
        data = json.loads(response.read())

        self.assertEqual(response.status, 200)
        self.assertIsInstance(data, list)
        self.assertGreaterEqual(len(data), 1)

    def test_get_task_by_id(self):
        response = self._post("/tasks", {
            "title": "Get by id",
            "priority": "normal"
        })
        task = json.loads(response.read())

        response = self._get(f"/tasks/{task['id']}")
        fetched = json.loads(response.read())

        self.assertEqual(response.status, 200)
        self.assertEqual(fetched["id"], task["id"])

    def test_get_task_not_found(self):
        response = self._get("/tasks/99999")
        self.assertEqual(response.status, 404)

    def test_complete_task(self):
        response = self._post("/tasks", {
            "title": "Complete me",
            "priority": "low"
        })
        task = json.loads(response.read())

        response = self._post(f"/tasks/{task['id']}/complete")
        self.assertEqual(response.status, 200)

        response = self._get(f"/tasks/{task['id']}")
        task = json.loads(response.read())
        self.assertTrue(task["isDone"])

    def test_complete_task_not_found(self):
        response = self._post("/tasks/99999/complete")
        self.assertEqual(response.status, 404)

    def test_delete_task(self):
        response = self._post("/tasks", {
            "title": "Delete me",
            "priority": "normal"
        })
        task = json.loads(response.read())

        response = self._delete(f"/tasks/{task['id']}")
        self.assertEqual(response.status, 200)

        response = self._get(f"/tasks/{task['id']}")
        self.assertEqual(response.status, 404)


if __name__ == "__main__":
    unittest.main()