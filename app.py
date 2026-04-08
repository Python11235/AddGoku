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
BOT_NAME = "u/YOUR_BOT_NAME"
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

    output = f"static/output_{int(time.time())}.png"
    os.makedirs("static", exist_ok=True)
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
        return jsonify({"result": output})
    else:
        return jsonify({"error": "Goku.webp not found 😢"})

# ==== DASHBOARD ====
@app.route("/")
def dashboard():
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
<title>Goku Bot Dashboard</title>
<style>
body { font-family: Arial; background: #111; color: #eee; margin:0; padding:0; }
header { padding:10px; background:#222; display:flex; justify-content:space-between; align-items:center; }
header h1 { margin:0; font-size:1.5em; }
button { padding:5px 10px; cursor:pointer; }
#stats { padding:10px; display:flex; gap:20px; flex-wrap:wrap; }
#tasks { display:grid; grid-template-columns: repeat(auto-fill,minmax(200px,1fr)); gap:10px; padding:10px; }
.task { padding:10px; border:1px solid #333; border-radius:5px; background:#1a1a1a; }
.done { border-color: lime; }
.processing { border-color: orange; }
.error { border-color: red; }
img { max-width: 100%; display:block; margin-top:5px; border-radius:3px; }
</style>
</head>
<body>
<header>
<h1>🔥 Goku Bot Dashboard</h1>
<button onclick="addGoku()">Add Goku to test image</button>
</header>
<div id="stats">
<p>CPU: <span id="cpu"></span>%</p>
<p>RAM: <span id="ram"></span>%</p>
<p>Network Sent: <span id="nets"></span> bytes</p>
<p>Network Recv: <span id="netr"></span> bytes</p>
<p>Goku.webp found: {{goku}}</p>
</div>
<div id="tasks"></div>

<script>
async function loadStats() {
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
            <b>Original:</b> <a href="${t.image}" target="_blank">open</a>
            ${t.result ? `<br><b>Goku Image:</b><br><img src="${t.result}">` : ""}
        `;
        container.appendChild(div);
    });
}

async function loadSystem() {
    const res = await fetch('/system_stats');
    const stats = await res.json();
    document.getElementById('cpu').innerText = stats.cpu;
    document.getElementById('ram').innerText = stats.ram;
    document.getElementById('nets').innerText = stats.net_sent;
    document.getElementById('netr').innerText = stats.net_recv;
}

async function addGoku() {
    const res = await fetch('/add_goku');
    const json = await res.json();
    if(json.result){
        alert("Goku added! Check below for image.");
    } else {
        alert(json.error);
    }
}

setInterval(loadStats, 1000);
setInterval(loadSystem, 1000);
loadStats();
loadSystem();
</script>
</body>
</html>
""", goku=GOKU_FOUND)

# ==== SYSTEM STATS API ====
@app.route("/system_stats")
def system_stats():
    net = psutil.net_io_counters()
    return jsonify({
        "cpu": psutil.cpu_percent(),
        "ram": psutil.virtual_memory().percent,
        "net_sent": net.bytes_sent,
        "net_recv": net.bytes_recv
    })

# ==== START ====
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
