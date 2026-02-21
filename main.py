from flask import Flask, render_template, request, redirect, url_for, jsonify
import uuid
import requests as http_requests
from werkzeug.utils import secure_filename
from queue_config import q
from rq.job import Job
from queue_config import redis_conn
from tasks import generate_reel_job
from config import ELEVENLABS_API_KEY
import os
import shutil

UPLOAD_FOLDER = "user_uploads"
REELS_FOLDER = os.path.join("static", "reels")

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/create", methods=["GET", "POST"])
def create():
    myid = uuid.uuid1()

    if request.method == "POST":
        rec_id = request.form.get("uuid")
        desc = request.form.get("text", "")
        voice_id = request.form.get("voice_id", "JBFqnCBsd6RMkjVDRZzb")
        reel_name = request.form.get("reel_name", "").strip()
        created_by = request.form.get("created_by", "").strip()
        music_prompt = request.form.get("music_prompt", "").strip()

        user_dir = os.path.join(app.config['UPLOAD_FOLDER'], rec_id)
        os.makedirs(user_dir, exist_ok=True)

        # save desc/voice/meta
        with open(os.path.join(user_dir, "desc.txt"), "w", encoding="utf-8") as f:
            f.write(desc)

        with open(os.path.join(user_dir, "voice.txt"), "w", encoding="utf-8") as f:
            f.write(voice_id)

        with open(os.path.join(user_dir, "meta.txt"), "w", encoding="utf-8") as f:
            f.write(f"{reel_name}\n{created_by}\n")

        if music_prompt:
            with open(os.path.join(user_dir, "music.txt"), "w", encoding="utf-8") as f:
                f.write(music_prompt)

        # save uploads in order
        input_files = []
        for key in request.files:
            file = request.files[key]
            if file and file.filename:
                filename = secure_filename(file.filename)
                file.save(os.path.join(user_dir, filename))
                input_files.append(filename)

        with open(os.path.join(user_dir, "input.txt"), "w", encoding="utf-8") as f:
            for fl in input_files:
                f.write(f"file '{fl}'\n")

        # enqueue background job
        job = q.enqueue(generate_reel_job, rec_id)

        # send user to a “processing” page that polls status
        return redirect(url_for("processing", job_id=job.id))

    return render_template("create.html", myid=myid)

@app.route("/status/<job_id>")
def status(job_id):
    job = Job.fetch(job_id, connection=redis_conn)
    state = job.get_status()  # queued / started / finished / failed
    return {"status": state}

@app.route("/processing/<job_id>")
def processing(job_id):
    return render_template("processing.html", job_id=job_id)

@app.route("/gallery")
def gallery():
    os.makedirs(REELS_FOLDER, exist_ok=True)

    reels = []
    for filename in os.listdir(REELS_FOLDER):
        if not filename.lower().endswith(".mp4"):
            continue

        folder = filename[:-4]  # remove ".mp4"
        meta_path = os.path.join(app.config["UPLOAD_FOLDER"], folder, "meta.txt")

        title = folder
        created_by = "Unknown"

        if os.path.exists(meta_path):
            with open(meta_path, "r", encoding="utf-8") as f:
                lines = [x.strip() for x in f.readlines() if x.strip()]
                if len(lines) >= 1:
                    title = lines[0]
                if len(lines) >= 2:
                    created_by = lines[1]

        reels.append({"file": filename, "title": title, "created_by": created_by})

    reels.reverse()
    return render_template("gallery.html", reels=reels)

@app.route("/reel/<reel_id>/delete", methods=["POST"])
def delete_reel(reel_id):
    # reel_id is the folder name / uuid you used, e.g. "a1b2c3..."
    # mp4 file path
    mp4_path = os.path.join(REELS_FOLDER, f"{reel_id}.mp4")

    # user_uploads folder path (contains meta.txt, audio, inputs, clips)
    upload_dir = os.path.join(app.config["UPLOAD_FOLDER"], reel_id)

    # Delete the mp4 if it exists
    if os.path.exists(mp4_path):
        os.remove(mp4_path)

    # Delete the whole upload folder (optional but recommended to free space)
    if os.path.exists(upload_dir):
        shutil.rmtree(upload_dir, ignore_errors=True)

    return redirect(url_for("gallery"))

@app.route("/api/voice-preview/<voice_id>")
def voice_preview(voice_id):
    try:
        resp = http_requests.get(
            f"https://api.elevenlabs.io/v1/voices/{voice_id}",
            headers={"xi-api-key": ELEVENLABS_API_KEY},
            timeout=10,
        )
        if resp.ok:
            data = resp.json()
            preview_url = data.get("preview_url", "")
            if preview_url:
                return jsonify({"preview_url": preview_url})
    except Exception:
        pass
    return jsonify({"error": "Preview not available"}), 404

if __name__ == "__main__":
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(REELS_FOLDER, exist_ok=True)
    app.run(debug=True)
