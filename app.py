import praw
import requests
from PIL import Image
from io import BytesIO
import random
import time
import threading
import os
import psutil

from flask import Flask, jsonify, render_template_string, request

app = Flask(__name__)

# ==== CONFIG ====
BOT_NAME = "u/addgoku"
TEST_IMAGE = "https://picsum.photos/400/300"  # manual test image

# Reddit placeholder (fill later)
reddit = None

# ==== GLOBAL TASK STATE ====
tasks = []
lock = threading.Lock()

# ==== LOAD GOKU ====
GOKU_PATH = "goku.webp"
GOKU_FOUND = os.path.exists(GOKU_PATH)
if GOKU_FOUND:
    GOKU = Image.open(GOKU_PATH).convert("RGBA")
else:
    GOKU = None

# ==== IMAGE FUNCTION ====
def add_goku_to_image(image_url):
    if not GOKU_FOUND:
        return None

    r = requests.get(image_url, timeout=10)
    base = Image.open(BytesIO(r.content)).convert("RGBA")

    # Resize large images
    base.thumbnail((1024, 1024))

    # Maintain aspect ratio, set Goku height = 50px
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
    # Placeholder
    return [
        {"id": str(time.time()), "image": "https://picsum.photos/800/600"}
    ]

# ==== BOT LOGIC ====
def process_posts():
    new_tasks = get_mock_posts()

    for post in new_tasks:
        task = {"id": post["id"], "status": "processing", "image": post["image"]}
        with lock:
            tasks.append(task)
        try:
            output = add_goku_to_image(post["image"])
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

@app.route("/ping")
def ping():
    return "pong 🔥"

@app.route("/run")
def run():
    process_posts()
    return "Bot run triggered"

@app.route("/tasks")
def get_tasks():
    with lock:
        return jsonify(tasks[-50:])

# Manual Goku test
@app.route("/add_goku")
def add_goku_manual():
    output = add_goku_to_image(TEST_IMAGE)
    if output:
        return f"Goku added! <a href='{output}' target='_blank'>View</a>"
    else:
        return "Goku.webp not found 😢"

# ==== DASHBOARD ====
@app.route("/")
def dashboard():
    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory().percent
    net = psutil.net_io_counters()
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
button { padding:5px 10px; margin:5px; cursor:pointer; }
</style>
</head>
<body>
<h1>🔥 Goku Bot Task Manager</h1>
<p>CPU: {{cpu}}% | RAM: {{ram}}% | Network sent: {{net.bytes_sent}} bytes | received: {{net.bytes_recv}} bytes</p>
<p>Goku.webp found: {{goku}}</p>
<button onclick="fetch('/add_goku').then(r=>r.text().then(alert))">Add Goku to test image</button>
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
""", cpu=cpu, ram=ram, net=net, goku=GOKU_FOUND)

# ==== START ====
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
