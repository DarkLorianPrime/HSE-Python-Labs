import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse
from typing import List, Optional

TASKS_FILE = "tasks.txt"


class Task:
    """Модель задачи"""

    def __init__(self, task_id: int, title: str, priority: str, is_done: bool = False):
        self.id = task_id
        self.title = title
        self.priority = priority
        self.isDone = is_done

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "priority": self.priority,
            "isDone": self.isDone
        }

    @staticmethod
    def from_dict(data: dict) -> "Task":
        return Task(
            task_id=data["id"],
            title=data["title"],
            priority=data["priority"],
            is_done=data["isDone"]
        )


class TaskRepository:
    """Хранилище задач + работа с файлом"""

    def __init__(self, filename: str):
        self.filename = filename
        self.lock = threading.Lock()
        self.tasks: List[Task] = []
        self.next_id = 1
        self._load()

    def _load(self):
        if os.path.exists(self.filename):
            with open(self.filename, "r", encoding="utf-8") as f:
                raw_tasks = json.load(f)
                self.tasks = [Task.from_dict(t) for t in raw_tasks]
                if self.tasks:
                    self.next_id = max(t.id for t in self.tasks) + 1

    def _save(self):
        with open(self.filename, "w", encoding="utf-8") as f:
            json.dump([t.to_dict() for t in self.tasks], f, ensure_ascii=False, indent=2)

    def get_all(self) -> List[Task]:
        return self.tasks

    def get_by_id(self, task_id: int) -> Optional[Task]:
        return next((t for t in self.tasks if t.id == task_id), None)

    def add(self, title: str, priority: str) -> Task:
        with self.lock:
            task = Task(self.next_id, title, priority)
            self.tasks.append(task)
            self.next_id += 1
            self._save()
            return task

    def complete(self, task_id: int) -> bool:
        with self.lock:
            task = self.get_by_id(task_id)
            if not task:
                return False
            task.isDone = True
            self._save()
            return True

    def delete(self, task_id: int) -> bool:
        with self.lock:
            task = self.get_by_id(task_id)
            if not task:
                return False
            self.tasks.remove(task)
            self._save()
            return True


class TaskService:
    """Бизнес-логика"""

    VALID_PRIORITIES = {"low", "normal", "high"}

    def __init__(self, repo: TaskRepository):
        self.repo = repo

    def create_task(self, title: str, priority: str) -> Task:
        if not title or not isinstance(title, str):
            raise ValueError("Invalid title")
        if priority not in self.VALID_PRIORITIES:
            raise ValueError("Invalid priority")
        return self.repo.add(title, priority)


repository = TaskRepository(TASKS_FILE)
service = TaskService(repository)


class TodoHTTPHandler(BaseHTTPRequestHandler):

    def _json_response(self, data=None, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        if data is not None:
            self.wfile.write(json.dumps(data).encode())

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length)) if length else {}

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/tasks":
            tasks = [t.to_dict() for t in repository.get_all()]
            self._json_response(tasks)

        elif path.startswith("/tasks/"):
            try:
                task_id = int(path.split("/")[2])
                task = repository.get_by_id(task_id)
                if not task:
                    self._json_response(status=404)
                else:
                    self._json_response(task.to_dict())
            except Exception:
                self._json_response(status=400)

        else:
            self._json_response(status=404)

    def do_POST(self):
        path = urlparse(self.path).path

        if path == "/tasks":
            try:
                body = self._read_body()
                task = service.create_task(body["title"], body["priority"])
                self._json_response(task.to_dict(), status=201)
            except Exception:
                self._json_response({"error": "Bad request"}, status=400)

        elif path.startswith("/tasks/") and path.endswith("/complete"):
            try:
                task_id = int(path.split("/")[2])
                if repository.complete(task_id):
                    self._json_response(status=200)
                else:
                    self._json_response(status=404)
            except Exception:
                self._json_response(status=400)

        else:
            self._json_response(status=404)

    def do_DELETE(self):
        path = urlparse(self.path).path
        if path.startswith("/tasks/"):
            try:
                task_id = int(path.split("/")[2])
                if repository.delete(task_id):
                    self._json_response(status=200)
                else:
                    self._json_response(status=404)
            except Exception:
                self._json_response(status=400)
        else:
            self._json_response(status=404)


def run():
    server = HTTPServer(("localhost", 8000), TodoHTTPHandler)
    print("🚀 Todo server running on http://localhost:8000")
    server.serve_forever()


if __name__ == "__main__":
    run()