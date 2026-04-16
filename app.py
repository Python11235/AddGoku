import os
import time
import random
import threading
import requests
import psutil
from io import BytesIO
from flask import Flask, jsonify, render_template_string
from PIL import Image
import praw

app = Flask(__name__)

# =============================
# LOAD GOKU (png preferred)
# =============================
GOKU = None
GOKU_FOUND = False
GOKU_FILE = None

for path in ["goku.png", "goku.webp"]:
    if os.path.exists(path):
        GOKU = Image.open(path).convert("RGBA")
        GOKU_FOUND = True
        GOKU_FILE = path
        print(f"Loaded {path}")
        break

# =============================
# TASK STORAGE
# =============================
tasks = []
network_start = psutil.net_io_counters()

# =============================
# IMAGE PROCESSING
# =============================
def add_goku_to_image(image_url):
    if not GOKU_FOUND:
        return None

    try:
        r = requests.get(image_url, timeout=5)
        base = Image.open(BytesIO(r.content)).convert("RGBA")

        base.thumbnail((800, 800))

        # Resize Goku (25px height)
        aspect = GOKU.width / GOKU.height
        goku_resized = GOKU.resize((int(25 * aspect), 25))

        # Fast dark area detection
        small = base.resize((100, 100)).convert("L")
        pixels = small.load()

        best_x, best_y = 0, 0
        darkest = 255

        for _ in range(8):
            sx = random.randint(0, 99)
            sy = random.randint(0, 99)

            brightness = pixels[sx, sy]
            if brightness < darkest:
                darkest = brightness
                best_x = int(sx / 100 * base.width)
                best_y = int(sy / 100 * base.height)

        best_x = min(best_x, base.width - goku_resized.width)
        best_y = min(best_y, base.height - goku_resized.height)

        base.paste(goku_resized, (best_x, best_y), goku_resized)

        os.makedirs("static", exist_ok=True)
        filename = f"output_{int(time.time())}.png"
        path = os.path.join("static", filename)
        base.save(path)

        return "/static/" + filename

    except Exception as e:
        print("Image error:", e)
        return None

# =============================
# REDDIT BOT
# =============================
def start_reddit_bot():
    if not all([
        os.getenv("REDDIT_CLIENT_ID"),
        os.getenv("REDDIT_CLIENT_SECRET"),
        os.getenv("REDDIT_USERNAME"),
        os.getenv("REDDIT_PASSWORD")
    ]):
        print("Reddit credentials missing.")
        return

    reddit = praw.Reddit(
        client_id=os.getenv("REDDIT_CLIENT_ID"),
        client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
        username=os.getenv("REDDIT_USERNAME"),
        password=os.getenv("REDDIT_PASSWORD"),
        user_agent=os.getenv("REDDIT_USER_AGENT")
    )

    print("Reddit bot started.")

    for mention in reddit.inbox.stream(skip_existing=True):
        try:
            print("Mention from:", mention.author)

            submission = mention.submission
            image_url = submission.url

            if not any(image_url.lower().endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp"]):
                continue

            task = {"id": len(tasks), "status": "processing", "result": None}
            tasks.append(task)

            result = add_goku_to_image(image_url)

            if result:
                full_url = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}{result}"
                mention.reply(f"Goku has been added 🔥\n\n![Goku]({full_url})")
                task["status"] = "done"
                task["result"] = result
            else:
                task["status"] = "failed"

            mention.mark_read()

        except Exception as e:
            print("Reddit error:", e)

# =============================
# SYSTEM STATS
# =============================
@app.route("/stats")
def stats():
    net = psutil.net_io_counters()
    return jsonify({
        "cpu": psutil.cpu_percent(),
        "ram": psutil.virtual_memory().percent,
        "sent": net.bytes_sent - network_start.bytes_sent,
        "recv": net.bytes_recv - network_start.bytes_recv,
        "goku": GOKU_FOUND,
        "file": GOKU_FILE
    })

@app.route("/tasks")
def get_tasks():
    return jsonify(tasks)

# =============================
# MANUAL TEST
# =============================
@app.route("/test")
def test():
    test_url = "https://i.imgur.com/ExdKOOz.png"
    result = add_goku_to_image(test_url)

    task = {"id": len(tasks), "status": "done", "result": result}
    tasks.append(task)

    return jsonify(task)

# =============================
# KEEP ALIVE
# =============================
@app.route("/ping")
def ping():
    return "alive"

# =============================
# DASHBOARD
# =============================
@app.route("/")
def dashboard():
    return render_template_string("""
    <html>
    <head>
    <script>
    async function update(){
        let stats = await fetch('/stats').then(r=>r.json());
        document.getElementById('cpu').innerText = stats.cpu;
        document.getElementById('ram').innerText = stats.ram;
        document.getElementById('sent').innerText = stats.sent;
        document.getElementById('recv').innerText = stats.recv;
        document.getElementById('goku').innerText = stats.file + " | " + stats.goku;

        let tasks = await fetch('/tasks').then(r=>r.json());
        let html = "";
        tasks.slice().reverse().forEach(t=>{
            html += `<div class="card">
                <b>Task ${t.id}</b><br>
                Status: ${t.status}<br>
                ${t.result ? `<img src="${t.result}?t=${Date.now()}">` : ""}
            </div>`;
        });
        document.getElementById('tasks').innerHTML = html;
    }

    setInterval(update, 1000);
    </script>

    <style>
    body { font-family: Arial; background:#111; color:#eee; }
    .grid { display:grid; grid-template-columns:repeat(auto-fill,200px); gap:10px; }
    .card { background:#222; padding:10px; border-radius:10px; }
    img { width:100%; }
    </style>
    </head>

    <body onload="update()">
    <h2>Goku Bot Dashboard</h2>

    CPU: <span id="cpu"></span>%<br>
    RAM: <span id="ram"></span>%<br>
    Net Sent: <span id="sent"></span><br>
    Net Recv: <span id="recv"></span><br>
    Goku: <span id="goku"></span><br><br>

    <button onclick="fetch('/test')">Test Goku</button>

    <div id="tasks" class="grid"></div>
    </body>
    </html>
    """)

# =============================
# START THREAD
# =============================
threading.Thread(target=start_reddit_bot, daemon=True).start()

# =============================
# RUN
# =============================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
