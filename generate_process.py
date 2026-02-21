# This file looks for new folders inside user uploads and converts them to reel if they are not already converted
import os
import time
import subprocess
from text_to_audio import text_to_speech_file, generate_music

def text_to_audio(folder):
    print("TTA - ", folder)

    with open(f"user_uploads/{folder}/desc.txt", "r", encoding="utf-8") as f:
        text = f.read().strip()

    voice_path = f"user_uploads/{folder}/voice.txt"
    voice_id = "JBFqnCBsd6RMkjVDRZzb"
    if os.path.exists(voice_path):
        with open(voice_path, "r", encoding="utf-8") as f:
            voice_id = f.read().strip() or voice_id

    print(text, folder, "| voice:", voice_id)
    text_to_speech_file(text, folder, voice_id)
    try:
        generate_music(folder)
    except Exception as e:
        print(f"Music generation failed (will continue without music): {e}")


def get_audio_duration(audio_path: str) -> float:
    """
    Get duration of audio in seconds using ffprobe.
    ffprobe comes with ffmpeg, make sure it's in PATH.
    """
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        audio_path
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {r.stderr}")
    return float(r.stdout.strip())


def make_timed_concat(folder: str, per_item_duration: float) -> str:
    """
    Creates a new concat file that assigns duration to each item,
    so total video ~= audio duration. Also repeats last file (required by ffmpeg concat for durations).
    """
    src = f"user_uploads/{folder}/input.txt"
    timed = f"user_uploads/{folder}/input_timed.txt"

    file_lines = []
    with open(src, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("file "):
                file_lines.append(line)

    if not file_lines:
        raise RuntimeError(f"No 'file' lines found in {src}")

    with open(timed, "w", encoding="utf-8") as f:
        for fl in file_lines:
            f.write(fl + "\n")
            f.write(f"duration {per_item_duration}\n")
        # IMPORTANT: repeat last file so the last duration is applied
        f.write(file_lines[-1] + "\n")

    return timed


def get_media_duration(path: str) -> float:
    """Duration in seconds (works for gif/video)."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        path
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffprobe failed for {path}: {r.stderr}")
    raw = r.stdout.strip()
    if not raw or raw == "N/A":
        return 0.0
    return float(raw)

def create_reel(folder: str):
    os.makedirs("static/reels", exist_ok=True)

    user_dir   = os.path.join("user_uploads", folder)
    audio_path = os.path.join(user_dir, "audio.mp3")
    input_txt  = os.path.join(user_dir, "input.txt")

    A = get_audio_duration(audio_path)  # total target duration
    if A <= 0:
        raise RuntimeError("Audio duration is 0. Check audio.mp3")

    # ---- read ordered inputs from input.txt ----
    files = []
    with open(input_txt, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("file "):
                # line: file 'name.ext'
                name = line.split("file", 1)[1].strip().strip("'").strip('"')
                files.append(name)

    if not files:
        raise RuntimeError("No files found in input.txt")

    # ---- classify files ----
    def ext(p): return os.path.splitext(p)[1].lower()

    gifs   = []
    stills = []
    videos = []

    for name in files:
        e = ext(name)
        if e == ".gif":
            gifs.append(name)
        elif e in [".png", ".jpg", ".jpeg", ".webp", ".jfif", ".bmp", ".tiff", ".tif", ".avif"]:
            stills.append(name)
        else:
            # treat everything else as "video" (mp4/mov/webm etc)
            videos.append(name)

    # We'll build clips in the ORIGINAL order, but duration depends on type
    # First pass: compute gif/video durations (trim later), and count stills
    timeline = []  # list of dicts: {name, kind, dur}
    t_used = 0.0

    # Precompute gif/video durations
    dur_map = {}
    for name in gifs + videos:
        full_path = os.path.join(user_dir, name)
        dur_map[name] = max(0.0, get_media_duration(full_path))

    # Decide fixed durations for gifs/videos first (trim to remaining audio)
    # For stills, we decide after we know remaining time.
    for name in files:
        if t_used >= A:
            break

        e = ext(name)

        if e == ".gif":
            raw = dur_map.get(name, 0.0) or 0.0
            dur = min(raw, A - t_used)
            if dur > 0:
                timeline.append({"name": name, "kind": "gif", "dur": dur})
                t_used += dur

        elif e in [".png", ".jpg", ".jpeg", ".webp", ".jfif", ".bmp", ".tiff", ".tif", ".avif"]:
            timeline.append({"name": name, "kind": "still", "dur": None})

        else:
            # video: use its real duration but trim if it would exceed audio
            raw = dur_map.get(name, 0.0) or 0.0
            if raw <= 0:
                # fallback: if ffprobe fails, give it 1s
                raw = 1.0
            dur = min(raw, A - t_used)
            if dur > 0:
                timeline.append({"name": name, "kind": "video", "dur": dur})
                t_used += dur

    # Remaining time for stills
    remaining = max(0.0, A - t_used)
    still_count = sum(1 for x in timeline if x["kind"] == "still")
    per_still = (remaining / still_count) if still_count > 0 else 0.0
    per_still = max(1.0, per_still) if still_count > 0 else 0.0

    # Assign still durations, but don't exceed audio total
    t = 0.0
    for item in timeline:
        if t >= A:
            item["dur"] = 0.0
            continue

        if item["kind"] == "still":
            dur = min(per_still, A - t)
            item["dur"] = dur
        # gif/video already have dur
        t += item["dur"]

    # Remove any zero-duration items
    timeline = [x for x in timeline if x["dur"] and x["dur"] > 0]

    # Debug: print timeline
    print(f"[DEBUG] Audio duration (A): {A}s, t_used by gifs/videos: {t_used}s, remaining for stills: {remaining}s")
    print(f"[DEBUG] still_count: {still_count}, per_still: {per_still}s")
    for item in timeline:
        print(f"[DEBUG]   {item['kind']:6s} {item['name']:30s} dur={item['dur']:.2f}s")

    # ---- create per-item mp4 clips ----
    clips_dir = os.path.join(user_dir, "_clips")
    os.makedirs(clips_dir, exist_ok=True)

    clips_list_path = os.path.join(clips_dir, "clips.txt")

    clip_paths = []
    for i, item in enumerate(timeline, start=1):
        src = os.path.join(user_dir, item["name"])
        out = os.path.join(clips_dir, f"clip_{i:03d}.mp4")
        dur = item["dur"]

        # unified scaling to 1080x1920 portrait
        vf = (
            "scale=1080:1920:force_original_aspect_ratio=decrease,"
            "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black,"
            "fps=30"
        )

        if item["kind"] == "still":
            cmd = [
                "ffmpeg", "-y",
                "-loop", "1", "-i", src,
                "-t", str(dur),
                "-vf", vf,
                "-an",
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                out
            ]

        elif item["kind"] == "gif":
            # play gif fully; trim via -t dur
            cmd = [
                "ffmpeg", "-y",
                "-ignore_loop", "0", "-i", src,
                "-t", str(dur),
                "-vf", vf,
                "-an",
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                out
            ]

        else:  # video
            cmd = [
                "ffmpeg", "-y",
                "-i", src,
                "-t", str(dur),
                "-vf", vf,
                "-an",
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                out
            ]

        subprocess.run(cmd, check=True)
        clip_paths.append(out)

    # write clips.txt for concat
    if not clip_paths:
        raise RuntimeError("No clips were generated (clip_paths is empty).")

    with open(clips_list_path, "w", encoding="utf-8") as f:
        for p in clip_paths:
            abs_p = os.path.abspath(p).replace("\\", "/")
            f.write(f"file '{abs_p}'\n")
    
    # ---- concat clips into one mp4 ----
    merged_video = os.path.join(clips_dir, "merged.mp4")
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", clips_list_path,
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-r", "30",
        merged_video
    ], check=True)
    
    # ---- mux audio, make final output exactly audio length ----
    out_final = os.path.join("static", "reels", f"{folder}.mp4")
    music_path = os.path.join(user_dir, "music.mp3")

    if os.path.exists(music_path):
        # Mix TTS voice + background music
        subprocess.run([
            "ffmpeg", "-y",
            "-i", merged_video,
            "-i", audio_path,
            "-i", music_path,
            "-filter_complex",
            f"[0:v]tpad=stop_mode=clone:stop_duration=10,trim=duration={A},setpts=PTS-STARTPTS[v];"
            f"[1:a]atrim=duration={A},asetpts=PTS-STARTPTS[voice];"
            f"[2:a]aloop=loop=-1:size=2e+09,atrim=duration={A},asetpts=PTS-STARTPTS,volume=0.25,afade=t=out:st={max(0,A-0.5)}:d=0.5[music];"
            f"[voice][music]amix=inputs=2:duration=first:dropout_transition=2:normalize=0[a]",
            "-map", "[v]",
            "-map", "[a]",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-movflags", "+faststart",
            out_final
        ], check=True)
    else:
        # Voice only (no background music)
        subprocess.run([
            "ffmpeg", "-y",
            "-i", merged_video,
            "-i", audio_path,
            "-filter_complex",
            f"[0:v]tpad=stop_mode=clone:stop_duration=10,trim=duration={A},setpts=PTS-STARTPTS[v];"
            f"[1:a]atrim=duration={A},asetpts=PTS-STARTPTS[a]",
            "-map", "[v]",
            "-map", "[a]",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-movflags", "+faststart",
            out_final
        ], check=True)


    print("CR -", folder, "=>", out_final)


if __name__ == "__main__":
    while True:
        try:
            print("Processing queue...")

            # if done.txt doesn't exist, create it
            if not os.path.exists("done.txt"):
                with open("done.txt", "w", encoding="utf-8") as f:
                    pass

            with open("done.txt", "r", encoding="utf-8") as f:
                done_folders = [x.strip() for x in f.readlines() if x.strip()]

            folders = os.listdir("user_uploads")

            for folder in folders:
                if folder not in done_folders:
                    text_to_audio(folder)   # Generate audio from desc.txt
                    create_reel(folder)     # Create reel mp4

                    with open("done.txt", "a", encoding="utf-8") as f:
                        f.write(folder + "\n")

        except Exception as e:
            print("ERROR:", repr(e))
            import traceback
            traceback.print_exc()
            input("\nPress Enter to continue...")

        time.sleep(3)
