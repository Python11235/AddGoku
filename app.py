import praw
import requests
from PIL import Image
from io import BytesIO
import random
import time
import threading

from flask import Flask, jsonify, render_template_string

app = Flask(__name__)

# ==== CONFIG ====
BOT_NAME = "u/YOUR_BOT_NAME"

# Reddit placeholder (fill later)
reddit = None

# ==== GLOBAL TASK STATE ====
tasks = []
lock = threading.Lock()

# ==== LOAD GOKU ====
GOKU = Image.open("goku.webp").convert("RGBA")

# ==== IMAGE FUNCTION ====
def add_goku(image_url):
    r = requests.get(image_url, timeout=10)
    base = Image.open(BytesIO(r.content)).convert("RGBA")

    # Resize large images for performance
    base.thumbnail((1024, 1024))

    # Maintain aspect ratio, set height = 50px
    aspect = GOKU.width / GOKU.height
    goku_resized = GOKU.resize((int(50 * aspect), 50))

    # Random position
    x = random.randint(0, max(1, base.width - goku_resized.width))
    y = random.randint(0, max(1, base.height - goku_resized.height))

    base.paste(goku_resized, (x, y), goku_resized)

    output = "output.png"
    base.save(output)

    return output


# ==== MOCK REDDIT FETCH ====
def get_mock_posts():
    # Placeholder for now
    return [
        {
            "id": str(time.time()),
            "image": "https://picsum.photos/800/600"
        }
    ]


# ==== BOT LOGIC ====
def process_posts():
    new_tasks = get_mock_posts()

    for post in new_tasks:
        task = {
            "id": post["id"],
            "status": "processing",
            "image": post["image"]
        }

        with lock:
            tasks.append(task)

        try:
            output = add_goku(post["image"])

            # Placeholder for repost logic
            task["status"] = "done"
            task["result"] = output

        except Exception as e:
            task["status"] = "error"
            task["error"] = str(e)


# ==== BACKGROUND LOOP ====
def background_loop():
    while True:
        process_posts()
        time.sleep(15)  # every 15 sec


threading.Thread(target=background_loop, daemon=True).start()

# ==== ROUTES ====

# Ping endpoint (keep alive)
@app.route("/ping")
def ping():
    return "pong 🔥"


# Trigger manually
@app.route("/run")
def run():
    process_posts()
    return "ran bot"


# Task API
@app.route("/tasks")
def get_tasks():
    with lock:
        return jsonify(tasks[-50:])  # last 50


# Frontend (live dashboard)
@app.route("/")
def dashboard():
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Goku Bot Dashboard</title>
        <style>
            body { font-family: Arial; background: #111; color: #eee; }
            .task { padding: 10px; border-bottom: 1px solid #333; }
            .done { color: lime; }
            .processing { color: orange; }
            .error { color: red; }
        </style>
    </head>
    <body>
        <h1>🔥 Goku Bot Task Manager</h1>
        <div id="tasks"></div>

        <script>
            async function loadTasks() {
                const res = await fetch('/tasks');
                const data = await res.json();

                const container = document.getElementById('tasks');
                container.innerHTML = "";

                data.reverse().forEach(t => {
                    const div = document.createElement('div');
                    div.className = "task " + t.status;

                    div.innerHTML = `
                        <b>ID:</b> ${t.id}<br>
                        <b>Status:</b> ${t.status}<br>
                        <b>Image:</b> <a href="${t.image}" target="_blank">open</a>
                    `;

                    container.appendChild(div);
                });
            }

            setInterval(loadTasks, 1000);
            loadTasks();
        </script>
    </body>
    </html>
    """)


# ==== START ====
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
