import requests
from PIL import Image
from io import BytesIO
import random
import time
import threading
import os
import psutil

from flask import Flask, jsonify, render_template_string

app = Flask(__name__)

# ==== CONFIG ====
TEST_IMAGE = "https://picsum.photos/400/300"

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

# ==== IMAGE FUNCTION (OPTIMIZED) ====
def add_goku_to_image(image_url):
    if not GOKU_FOUND:
        return None

    r = requests.get(image_url, timeout=5)
    base = Image.open(BytesIO(r.content)).convert("RGBA")

    # Resize for performance
    base.thumbnail((800, 800))

    # Resize Goku (25px height)
    aspect = GOKU.width / GOKU.height
    goku_resized = GOKU.resize((int(25 * aspect), 25))

    # === FAST DARK AREA DETECTION ===
    small = base.resize((100, 100)).convert("L")
    pixels = small.load()

    best_x, best_y = 0, 0
    darkest = 255

    for _ in range(8):  # low sample count for speed
        sx = random.randint(0, 99)
        sy = random.randint(0, 99)

        brightness = pixels[sx, sy]

        if brightness < darkest:
            darkest = brightness
            best_x = int(sx / 100 * base.width)
            best_y = int(sy / 100 * base.height)

    # Clamp position
    best_x = min(best_x, base.width - goku_resized.width)
    best_y = min(best_y, base.height - goku_resized.height)

    # Paste
    base.paste(goku_resized, (best_x, best_y), goku_resized)

    # Save
    os.makedirs("static", exist_ok=True)
    filename = f"output_{int(time.time())}.png"
    path = os.path.join("static", filename)
    base.save(path)

    return "/static/" + filename

# ==== MOCK POSTS ====
def get_mock_posts():
    return [{"id": str(time.time()), "image": "https://picsum.photos/800/600"}]

# ==== PROCESS POSTS ====
def process_posts():
    new_posts = get_mock_posts()

    for post in new_posts:
        task = {"id": post["id"], "status": "processing", "image": post["image"]}
        with lock:
            tasks.append(task)

        try:
            result = add_goku_to_image(post["image"])
            task["status"] = "done"
            task["result"] = result
        except Exception as e:
            task["status"] = "error"
            task["error"] = str(e)

# ==== BACKGROUND LOOP ====
def background_loop():
    while True:
        process_posts()
        time.sleep(15)

threading.Thread(target=background_loop, daemon=True).start()

# ==== ROUTES ====

@app.route("/")
def dashboard():
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
<title>Goku Bot Dashboard</title>
<style>
body { font-family: Arial; background:#111; color:#eee; margin:0; }
header { background:#222; padding:10px; }
#stats { display:flex; gap:20px; padding:10px; flex-wrap:wrap; }
#tasks {
    display:grid;
    grid-template-columns: repeat(auto-fill,minmax(220px,1fr));
    gap:10px;
    padding:10px;
}
.task {
    background:#1a1a1a;
    border:1px solid #333;
    padding:10px;
    border-radius:6px;
}
.done { border-color:lime; }
.processing { border-color:orange; }
.error { border-color:red; }
img { max-width:100%; border-radius:4px; margin-top:5px; }
button { padding:6px 10px; cursor:pointer; }
</style>
</head>
<body>

<header>
<h2>🔥 Goku Bot Dashboard</h2>
</header>

<div id="stats">
<p>CPU: <span id="cpu"></span>%</p>
<p>RAM: <span id="ram"></span>%</p>
<p>Net Sent: <span id="nets"></span></p>
<p>Net Recv: <span id="netr"></span></p>
<p>Goku.webp: {{goku}}</p>
</div>

<div style="padding:10px;">
<button onclick="addGoku()">Add Goku (Test)</button>
<div id="manual"></div>
</div>

<div id="tasks"></div>

<script>
async function loadTasks(){
    const res = await fetch('/tasks');
    const data = await res.json();
    const container = document.getElementById('tasks');
    container.innerHTML = "";

    data.reverse().forEach(t=>{
        const div = document.createElement('div');
        div.className = "task " + t.status;

        div.innerHTML = `
            <b>ID:</b> ${t.id}<br>
            <b>Status:</b> ${t.status}<br>
            <a href="${t.image}" target="_blank">Original</a>
            ${t.result ? `<img src="${t.result}">` : ""}
        `;

        container.appendChild(div);
    });
}

async function loadStats(){
    const res = await fetch('/system');
    const s = await res.json();

    document.getElementById('cpu').innerText = s.cpu.toFixed(1);
    document.getElementById('ram').innerText = s.ram.toFixed(1);
    document.getElementById('nets').innerText = s.net_sent;
    document.getElementById('netr').innerText = s.net_recv;
}

async function addGoku(){
    const res = await fetch('/add');
    const j = await res.json();
    const div = document.getElementById('manual');

    if(j.result){
        div.innerHTML = `<img src="${j.result}">`;
    } else {
        div.innerHTML = `<p style="color:red">${j.error}</p>`;
    }
}

setInterval(loadTasks,1000);
setInterval(loadStats,1000);
loadTasks();
loadStats();
</script>

</body>
</html>
""", goku=GOKU_FOUND)

@app.route("/tasks")
def get_tasks():
    with lock:
        return jsonify(tasks[-50:])

@app.route("/add")
def add_manual():
    result = add_goku_to_image(TEST_IMAGE)
    if result:
        return jsonify({"result": result})
    return jsonify({"error": "Goku not found"})

@app.route("/system")
def system():
    net = psutil.net_io_counters()
    return jsonify({
        "cpu": psutil.cpu_percent(),
        "ram": psutil.virtual_memory().percent,
        "net_sent": net.bytes_sent,
        "net_recv": net.bytes_recv
    })

@app.route("/ping")
def ping():
    return "pong 🔥"

# ==== START ====
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
