#!/usr/bin/env python3

import os
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests

YADISK_API = "https://cloud-api.yandex.net/v1/disk"


def get_ext_from_url(url: str) -> str:
    """
    Достаём расширение из пути URL (последняя часть после точки).
    Если не получается — вернём 'bin'.
    """
    try:
        path = urllib.parse.urlparse(url).path
    except Exception:
        return "bin"

    filename = path.rsplit("/", 1)[-1]
    if "." in filename and not filename.endswith("."):
        ext = filename.rsplit(".", 1)[-1].lower()
        
        if ext and all(ch.isalnum() for ch in ext) and len(ext) <= 10:
            return ext
    return "bin"


def upload_by_url(token: str, file_url: str, disk_path: str):
    """
    Запуск загрузки по URL на Яндекс.Диск.
    Возвращает (status_code, text_response).
    """
    endpoint = f"{YADISK_API}/resources/upload"
    headers = {"Authorization": f"OAuth {token}"}
    params = {"url": file_url, "path": disk_path}

    resp = requests.post(endpoint, headers=headers, params=params, timeout=20)
    return resp.status_code, resp.text


def get_uploaded_files(token: str):
    """
    Получает список загруженных файлов с Яндекс.Диска.
    Возвращает список путей файлов.
    """
    headers = {"Authorization": f"OAuth {token}"}
    params = {
        "path": "/Uploads",
        "fields": "_embedded.items.path",
        "limit": 1000  
    }

    resp = requests.get(f"{YADISK_API}/resources", headers=headers, params=params, timeout=20)
    if resp.status_code != 200:
        print(f"Error getting files: {resp.text}")
        return []

    try:
        data = resp.json()
        items = data.get("_embedded", {}).get("items", [])
        return [item["path"] for item in items]
    except Exception as e:
        print(f"Error parsing response: {e}")
        return []


class Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, body: str, content_type: str = "text/plain; charset=utf-8"):
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path != "/":
            self._send(404, "not found")
            return

        
        token = os.environ.get('YADISK_TOKEN', '')
        
        uploaded_files = []
        if token:
            uploaded_files = get_uploaded_files(token)

        html = """<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <title>Загрузка файлов на Яндекс.Диск</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }
        .uploaded {
            background-color: rgba(0, 200, 0, 0.25);
            padding: 10px;
            margin: 5px 0;
            border-radius: 5px;
            border-left: 4px solid green;
        }
        .file-item {
            padding: 10px;
            margin: 5px 0;
            border: 1px solid #ddd;
            border-radius: 5px;
            font-family: monospace;
        }
        button {
            background-color: #4CAF50;
            color: white;
            padding: 12px 24px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 16px;
            margin: 20px 0;
        }
        button:hover {
            background-color: #45a049;
        }
        h1 {
            color: #333;
        }
    </style>
</head>
<body>
    <h1>Загрузка файлов на Яндекс.Диск</h1>

    <button id="btn">Загрузить новый файл по URL</button>

    <h2>Уже загруженные файлы:</h2>
    <div id="file-list">"""

        
        if uploaded_files:
            for file_path in uploaded_files:
                html += f'<div class="uploaded file-item">{file_path}</div>\n'
        else:
            html += '<p>Нет загруженных файлов или не удалось получить список</p>'

        html += """    </div>

    <script>
        document.getElementById("btn").addEventListener("click", async () => {
            const url = prompt("Введите URL файла:");
            if (!url) return;

            try {
                const resp = await fetch("/download", {
                    method: "POST",
                    headers: { "Content-Type": "text/plain; charset=utf-8" },
                    body: url
                });

                const text = await resp.text();
                alert(text);

                // Перезагружаем страницу, чтобы обновить список
                if (resp.ok) {
                    setTimeout(() => location.reload(), 1000);
                }
            } catch (e) {
                alert("Ошибка: " + e);
            }
        });
    </script>
</body>
</html>"""

        self._send(200, html, "text/html; charset=utf-8")

    def do_POST(self):
        if self.path != "/download":
            self._send(404, "not found")
            return

        token = os.environ.get('YADISK_TOKEN', '')
        if not token:
            self._send(500, "YADISK_TOKEN is not set. Please set environment variable.")
            return

        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length)

        
        body_text = raw.decode("utf-8", errors="replace").strip()

        file_url = body_text

        if not file_url:
            self._send(400, "empty url")
            return
        if not (file_url.startswith("http://") or file_url.startswith("https://")):
            self._send(400, "url must start with http:// or https://")
            return

        ext = get_ext_from_url(file_url)
        ts = int(time.time())
        disk_path = f"/Uploads/{ts}.{ext}"

        status, yadisk_resp_text = upload_by_url(token, file_url, disk_path)

        
        self._send(
            status,
            f"disk_path={disk_path}\nstatus={status}\nresponse={yadisk_resp_text}\n",
        )

    def log_message(self, fmt, *args):
        return


def main():
    
    token = os.environ.get('YADISK_TOKEN')
    if not token:
        print("Введите токен Яндекс.Диска (или установите переменную окружения YADISK_TOKEN):")
        token = input().strip()
        if token:
            os.environ['YADISK_TOKEN'] = token
        else:
            print("Токен не введен. Некоторые функции могут не работать.")

    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8080"))
    httpd = HTTPServer((host, port), Handler)
    print(f"Open: http://{host}:{port}")
    print("Для остановки сервера нажмите Ctrl+C")
    httpd.serve_forever()


if __name__ == "__main__":
    main()