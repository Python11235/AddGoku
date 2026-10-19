import os
import time
import uuid
import threading
import requests
import psutil
from io import BytesIO
from urllib.parse import urlparse
from flask import Flask, jsonify, render_template_string
from PIL import Image, ImageFilter
import praw

# Resolve files next to this script, not the current working directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)

USER_AGENT = "AddGoku bot (github.com/python11235/AddGoku)"
TEST_IMAGE = "https://picsum.photos/800/600"
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp")

# =============================
# LOAD GOKU (png preferred)
# =============================
GOKU = None
GOKU_FOUND = False
GOKU_FILE = None

for name in ["goku.png", "goku.webp"]:
    path = os.path.join(BASE_DIR, name)
    if os.path.exists(path):
        GOKU = Image.open(path).convert("RGBA")
        GOKU_FOUND = True
        GOKU_FILE = name
        print(f"Loaded {name}", flush=True)
        break

# =============================
# TASK STORAGE
# =============================
tasks = []
tasks_lock = threading.Lock()
network_start = psutil.net_io_counters()

def new_task(status, result=None):
    with tasks_lock:
        task = {"id": len(tasks), "status": status, "result": result}
        tasks.append(task)
    return task

# =============================
# IMAGE PROCESSING
# =============================
def add_goku_to_image(image_url):
    if not GOKU_FOUND:
        return None

    try:
        r = requests.get(image_url, timeout=10, headers={"User-Agent": USER_AGENT})
        r.raise_for_status()
        base = Image.open(BytesIO(r.content)).convert("RGBA")

        base.thumbnail((800, 800))

        # Resize Goku (25px height)
        aspect = GOKU.width / GOKU.height
        goku_resized = GOKU.resize((max(1, int(25 * aspect)), 25))

        # Fast dark area detection (a 100x100 copy is cheap to scan fully,
        # the blur makes the darkest pixel the middle of a dark area)
        small = base.resize((100, 100)).convert("L").filter(ImageFilter.BoxBlur(2))
        pixels = small.load()
        sx, sy = min(((x, y) for x in range(100) for y in range(100)), key=lambda p: pixels[p])

        # Center Goku on the darkest spot, keeping him inside the image
        best_x = int(sx / 100 * base.width) - goku_resized.width // 2
        best_y = int(sy / 100 * base.height) - goku_resized.height // 2
        best_x = max(0, min(best_x, base.width - goku_resized.width))
        best_y = max(0, min(best_y, base.height - goku_resized.height))

        base.paste(goku_resized, (best_x, best_y), goku_resized)

        os.makedirs(app.static_folder, exist_ok=True)
        filename = f"output_{int(time.time())}_{uuid.uuid4().hex[:8]}.png"
        base.save(os.path.join(app.static_folder, filename))

        return "/static/" + filename

    except Exception as e:
        print("Image error:", e, flush=True)
        return None

# =============================
# REDDIT BOT
# =============================
def find_image_url(submission):
    url = submission.url
    if urlparse(url).path.lower().endswith(IMAGE_EXTS):
        return url

    # Gallery posts: use the first image
    if getattr(submission, "is_gallery", False):
        try:
            first = submission.gallery_data["items"][0]["media_id"]
            return submission.media_metadata[first]["s"]["u"]
        except (KeyError, IndexError, TypeError):
            pass

    # Anything else Reddit made a preview image for (imgur pages, etc.)
    try:
        return submission.preview["images"][0]["source"]["url"]
    except (AttributeError, KeyError, IndexError):
        return None

def handle_mention(item, bot_mention, public_url):
    try:
        # The inbox also holds DMs and replies to the bot's own comments,
        # only comments that actually mention the bot get a Goku
        if not isinstance(item, praw.models.Comment) or bot_mention not in item.body.lower():
            return

        print("Mention from:", item.author, flush=True)

        image_url = find_image_url(item.submission)
        if not image_url:
            print("No image found on post.", flush=True)
            return

        task = new_task("processing")

        result = add_goku_to_image(image_url)

        if result:
            item.reply(f"[Goku has been added 🔥]({public_url}{result})")
            task["status"] = "done"
            task["result"] = result
        else:
            task["status"] = "failed"

    except Exception as e:
        print("Reddit error:", e, flush=True)

    finally:
        # Always mark as read, so the same mention is never handled twice
        item.mark_read()

def start_reddit_bot():
    if not all([
        os.getenv("REDDIT_CLIENT_ID"),
        os.getenv("REDDIT_CLIENT_SECRET"),
        os.getenv("REDDIT_USERNAME"),
        os.getenv("REDDIT_PASSWORD")
    ]):
        print("Reddit credentials missing.", flush=True)
        return

    if os.getenv("PUBLIC_URL"):
        public_url = os.getenv("PUBLIC_URL").rstrip("/")
    elif os.getenv("RENDER_EXTERNAL_HOSTNAME"):
        public_url = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}"
    else:
        print("PUBLIC_URL (or RENDER_EXTERNAL_HOSTNAME) missing.", flush=True)
        return

    reddit = praw.Reddit(
        client_id=os.getenv("REDDIT_CLIENT_ID"),
        client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
        username=os.getenv("REDDIT_USERNAME"),
        password=os.getenv("REDDIT_PASSWORD"),
        user_agent=os.getenv("REDDIT_USER_AGENT") or USER_AGENT
    )
    bot_mention = "u/" + os.getenv("REDDIT_USERNAME").lower()

    print("Reddit bot started.", flush=True)

    # The stream yields unread inbox items, so mentions that came in while
    # the app was asleep still get handled. If Reddit or the network
    # hiccups, restart the stream instead of letting the thread die.
    while True:
        try:
            for item in reddit.inbox.stream():
                handle_mention(item, bot_mention, public_url)
        except Exception as e:
            print("Reddit stream error:", e, flush=True)
            time.sleep(30)

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
    with tasks_lock:
        return jsonify(tasks[-50:])

# =============================
# MANUAL TEST
# =============================
@app.route("/test")
def test():
    result = add_goku_to_image(TEST_IMAGE)

    task = new_task("done" if result else "failed", result)

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
                ${t.result ? `<a href="${t.result}" target="_blank"><img src="${t.result}"></a>` : ""}
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

    <button onclick="fetch('/test').then(update)">Test Goku</button>

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
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
