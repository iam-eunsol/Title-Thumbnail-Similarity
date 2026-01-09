import streamlit as st
from st_click_detector import click_detector
import os
import json
import random
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
from collections import defaultdict
import base64
from pathlib import Path
import time

st.set_page_config(layout="wide", page_title="Video Selection Study")

# --- CUSTOM CSS (Main App Only) ---
st.markdown("""
<style>
    /* 1. HIDE STREAMLIT UI */
    [class="_container_1upux_1"], header[data-testid="stHeader"], .stAppDeployButton {
        display: none !important;
    }
    
    /* 2. MAIN CONTAINER */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 5rem;
        max-width: 1000px;
        margin: 0 auto;
    }

    /* 3. STYLES */
    .stProgress > div > div > div > div { background-color: #cc0000; }
    
    .stButton button {
        background-color: #cc0000; color: white; border: none;
        border-radius: 2px; font-weight: 500; padding: 0.5rem 1rem;
    }
    .stButton button:hover {
        background-color: #ff0000; color: white;
    }

    h1, h2, h3, p, div { font-family: 'Roboto', Arial, sans-serif; }
</style>
""", unsafe_allow_html=True)

# --- CONFIGURATION ---
GOOGLE_SHEET_URL = "https://script.google.com/macros/s/AKfycbzHUUlpdy7B4vZF7lTlBUyJBRScRN_j3PHvGSXH2n_yeTDOCKvBoV4SbLhqNl05yvEO/exec"

# --- LOAD DATA ---
try:
    with open("video_metadata.json", "r", encoding="utf-8") as f:
        all_videos = json.load(f)
except FileNotFoundError:
    st.error("video_metadata.json not found.")
    st.stop()

videos_by_page = defaultdict(list)
for v in all_videos:
    page = v.get("page", 1)
    videos_by_page[page].append(v)

pages = sorted(videos_by_page.keys())
MAX_PAGES = 10
pages = [p for p in pages if p >= 1][:MAX_PAGES]
total_pages = len(pages)

# --- GET PARTICIPANT ID ---
params = st.query_params
raw_pid = params.get("pid", None)
participant_id = raw_pid[0] if isinstance(raw_pid, list) else str(raw_pid) if raw_pid else "unknown"

# --- THUMBNAIL HANDLING ---
THUMBNAIL_DIR = Path("thumbnails")

def get_thumbnail_src(video, assignment):
    vid_id = video["vid_id"]
    is_control = (video["id"] == assignment.get("control_internal_id"))
    is_treated = (video["id"] == assignment.get("treated_internal_id"))

    filename = None
    if is_control:
        filename = f"{vid_id}_control.jpg"
    elif is_treated:
        img_c = assignment.get("image_congruency", "more")
        txt_c = assignment.get("text_congruency", "more")
        filename = f"{vid_id}_image_{img_c}_text_{txt_c}.jpg"

    if filename:
        path = THUMBNAIL_DIR / filename
        if path.exists():
            try:
                with open(path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("utf-8")
                return f"data:image/jpeg;base64,{b64}"
            except Exception:
                pass

    return f"https://img.youtube.com/vi/{vid_id}/hqdefault.jpg"

# --- LOGGING ---
def log_choice(pid, page, video):
    eastern_now = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M:%S")
    assignments = st.session_state.get("page_assignments", {})
    assign = assignments.get(page, {})

    control_internal_id = assign.get("control_internal_id", "")
    treated_internal_id = assign.get("treated_internal_id", "")
    
    page_videos_full = videos_by_page.get(page, [])
    by_internal = {v["id"]: v for v in page_videos_full}
    
    control_vid = by_internal.get(control_internal_id, {}).get("vid_id", "")
    treated_vid = by_internal.get(treated_internal_id, {}).get("vid_id", "")

    payload = {
        "timestamp_et": eastern_now,
        "participant_id": pid,
        "page": page,
        "chosen_internal_id": video.get("id", ""),
        "chosen_title": video.get("title", ""),
        "chosen_vid_id": video.get("vid_id", ""),
        "control_internal_id": control_internal_id,
        "control_vid_id": control_vid,
        "treated_internal_id": treated_internal_id,
        "treated_vid_id": treated_vid,
        "treated_image_congruency": assign.get("image_congruency", ""),
        "treated_text_congruency": assign.get("text_congruency", ""),
    }

    try:
        requests.post(GOOGLE_SHEET_URL, json=payload, timeout=5)
    except Exception as e:
        print(f"Logging failed: {e}")

# --- SESSION STATE ---
if "page_index" not in st.session_state:
    st.session_state.page_index = 0
if "selections" not in st.session_state:
    st.session_state.selections = {}
if "logged_pages" not in st.session_state:
    st.session_state.logged_pages = set()
if "page_orders" not in st.session_state:
    st.session_state.page_orders = {}
if "page_assignments" not in st.session_state:
    st.session_state.page_assignments = {}

if total_pages == 0:
    st.error("No pages found.")
    st.stop()

current_page_number = pages[st.session_state.page_index]

# --- RANDOMIZATION ---
page_videos_full = videos_by_page[current_page_number]

if current_page_number not in st.session_state.page_orders:
    ids = [v["id"] for v in page_videos_full]
    random.shuffle(ids)
    st.session_state.page_orders[current_page_number] = ids

ordered_ids = st.session_state.page_orders[current_page_number]
video_lookup = {v["id"]: v for v in page_videos_full}
page_videos = [video_lookup[i] for i in ordered_ids if i in video_lookup]

if current_page_number not in st.session_state.page_assignments:
    ids_internal = [v["id"] for v in page_videos_full]
    if len(ids_internal) >= 2:
        control = random.choice(ids_internal)
        treated = [i for i in ids_internal if i != control][0]
        st.session_state.page_assignments[current_page_number] = {
            "control_internal_id": control,
            "treated_internal_id": treated,
            "image_congruency": random.choice(["more", "less"]),
            "text_congruency": random.choice(["more", "less"]),
        }
    else:
        st.session_state.page_assignments[current_page_number] = {}

current_assignment = st.session_state.page_assignments[current_page_number]

# --- HEADER ---
col1, col2 = st.columns([1, 4])
with col1:
    st.markdown("""<img src="https://upload.wikimedia.org/wikipedia/commons/b/b8/YouTube_Logo_2017.svg" width="120" style="margin-bottom: 5px;">""", unsafe_allow_html=True)
with col2:
    if total_pages > 1:
        progress_val = st.session_state.page_index / (total_pages - 1)
    else:
        progress_val = 1.0
    st.progress(progress_val)

st.caption("YouTube is a trademark of Google LLC. Used here for educational purposes only.")
st.markdown("---")

# --- VIDEO SELECTOR ---
def video_selector():
    current_selection = st.session_state.selections.get(current_page_number, "")

    if current_selection:
        pos = None
        for idx, v in enumerate(page_videos, start=1):
            if v["id"] == current_selection:
                pos = idx
                break
        if pos:
            st.success(f"✅ Selected: Video {pos}")
        else:
            st.success("✅ Selected")
    else:
        st.info("Click on a thumbnail below to select it.")

    # --- CSS INSIDE HTML ---
    # This is the secret to making it work reliably in st_click_detector.
    # We use 'flex-wrap: wrap' to handle the responsive layout automatically.
    html_css = """
    <style>
        .video-card {
            display: flex;
            flex-wrap: wrap; /* THIS IS KEY: Allows wrapping to next line */
            background-color: #ffffff;
            border: 1px solid #e0e0e0;
            border-radius: 12px;
            overflow: hidden;
            margin-bottom: 24px;
            cursor: pointer;
            transition: all 0.2s ease-in-out;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            font-family: 'Roboto', Arial, sans-serif;
            text-decoration: none;
            color: inherit;
            width: 100%;
        }
        
        .video-card:hover { background-color: #f9f9f9; }

        /* Thumbnail Container */
        /* Flex-basis 350px means it wants to be 350px wide. */
        /* Flex-grow 1 means if wrapped to its own line, it fills the space. */
        .video-thumbnail-container {
            flex: 1 1 350px; 
            position: relative;
            min-width: 300px; /* Prevent it from getting too skinny before wrapping */
        }

        .video-thumbnail-img {
            width: 100%;
            height: auto;
            display: block;
            aspect-ratio: 16/9;
            object-fit: cover;
        }

        /* Info Container */
        /* Flex-basis 300px. If there's room next to the image, it sits there. */
        /* If not, it wraps below. */
        .video-info {
            flex: 10 1 300px; 
            padding: 16px;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }

        .video-title {
            margin: 0 0 8px 0; font-size: 1.1rem; font-weight: 500; 
            color: #0f0f0f; line-height: 1.4;
            display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
        }

        .video-profile-row {
            display: flex; align-items: center; gap: 12px; margin-bottom: 8px;
        }
        
        /* Badges */
        .badge {
            position: absolute; background-color: rgba(0, 0, 0, 0.8); color: white;
            border-radius: 4px; font-family: sans-serif;
        }
        .duration-badge { bottom: 8px; right: 8px; padding: 2px 6px; font-size: 0.75rem; }
        .label-badge { top: 8px; left: 8px; padding: 2px 8px; font-size: 0.80rem; }
    </style>
    """
    
    html_content = ""
    for idx, v in enumerate(page_videos, start=1):
        label = f"Video {idx}"
        selected = v["id"] == current_selection
        thumb_src = get_thumbnail_src(v, current_assignment)

        if selected:
            card_style = "border: 2px solid #cc0000; box-shadow: 0 4px 12px rgba(204,0,0,0.25); background-color: #fff0f0;"
        else:
            card_style = ""

        html_content += f"""
        <a href="javascript:;" id='{v["id"]}' class="video-card" style="{card_style}">
            <div class="video-thumbnail-container">
                <img src='{thumb_src}' class="video-thumbnail-img" />
                <div class="badge label-badge">{label}</div>
                <div class="badge duration-badge">{v["duration"]}</div>
            </div>
            <div class="video-info">
                <div class="video-title">{v["title"]}</div>
                <div class="video-profile-row">
                     <img src='{v["profile"]}' style='width: 24px; height: 24px; border-radius: 50%;' />
                     <span style='color: #606060; font-size: 0.85rem;'>{v["channel"]}</span>
                </div>
                <div style='font-size: 0.85rem; color: #606060;'>
                    {v["views"]} • {v["years"]}
                </div>
            </div>
        </a>
        """

    # Force Refresh Timestamp
    html_content += f"<div style='display:none;'>{time.time()}</div>"

    # Explicit Clear to prevent ghosting
    placeholder = st.empty()
    placeholder.empty()
    
    with placeholder.container():
        click = click_detector(f"""
            <div style='width: 100%; display: flex; flex-direction: column;'>
                {html_css}
                {html_content}
            </div>
        """, key=f"responsive_select_{current_page_number}")

    if click and click != current_selection:
        st.session_state.selections[current_page_number] = click
        st.rerun()

video_selector()

# --- FOOTER ---
st.markdown("<br>", unsafe_allow_html=True)
col_l, col_r = st.columns([4, 1])

with col_r:
    if st.button("Continue", use_container_width=True):
        current_selection = st.session_state.selections.get(current_page_number, "")
        if not current_selection:
            st.toast("⚠️ Please select a video first.", icon="⚠️")
        else:
            selected_video = next((v for v in page_videos if v["id"] == current_selection), None)
            if selected_
