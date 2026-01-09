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

st.set_page_config(layout="wide", page_title="Video Selection Study")

# --- CUSTOM CSS (Layout Fixes) ---
st.markdown("""
<style>
    /* Fix Top Cutoff: Increase top padding */
    .block-container {
        padding-top: 4rem;
        padding-bottom: 5rem;
        max-width: 1000px;
    }
    
    /* Progress bar styling */
    .stProgress > div > div > div > div {
        background-color: #cc0000;
    }
    
    /* Button styling */
    .stButton button {
        background-color: #cc0000;
        color: white;
        border: none;
        border-radius: 2px;
        font-weight: 500;
        padding: 0.5rem 1rem;
    }
    .stButton button:hover {
        background-color: #ff0000;
        color: white;
        border: none;
    }

    /* Typography */
    h1, h2, h3, p, div { font-family: 'Roboto', Arial, sans-serif; }
</style>
""", unsafe_allow_html=True)

# --- CONFIGURATION ---
# REPLACE WITH YOUR GOOGLE APPS SCRIPT URL
GOOGLE_SHEET_URL = "https://script.google.com/macros/s/AKfycbzHUUlpdy7B4vZF7lTlBUyJBRScRN_j3PHvGSXH2n_yeTDOCKvBoV4SbLhqNl05yvEO/exec"

# --- LOAD VIDEO METADATA ---
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

# --- HEADER (Logo + Progress) ---
col1, col2 = st.columns([1, 4])
with col1:
    st.markdown(
        """<img src="https://upload.wikimedia.org/wikipedia/commons/b/b8/YouTube_Logo_2017.svg" width="120" style="margin-bottom: 5px;">""",
        unsafe_allow_html=True
    )
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

    # 1. DISPLAY INSTRUCTION/FEEDBACK AT THE TOP
    if current_selection:
        pos = None
        for idx, v in enumerate(page_videos, start=1):
            if v["id"] == current_selection:
                pos = idx
                break
        if pos is not None:
            st.success(f"✅ Selected: Video {pos}")
        else:
            st.success("✅ Selected")
    else:
        st.info("Click on a thumbnail below to select it.")

    # 2. BUILD HTML
    html = ""
    for idx, v in enumerate(page_videos, start=1):
        label = f"Video {idx}"
        selected = v["id"] == current_selection
        
        # --- STYLING LOGIC ---
        if selected:
            # Highlighted Style
            bg_color = "#fff0f0" # Very light red background
            css_border = "2px solid #cc0000"
            css_shadow = "0 4px 12px rgba(204,0,0,0.25)" # Deeper red shadow
        else:
            # Default Style
            bg_color = "#ffffff"
            css_border = "2px solid transparent"
            css_shadow = "0 2px 5px rgba(0,0,0,0.08)" # Soft grey shadow

        thumb_src = get_thumbnail_src(v, current_assignment)

        html += f"""
        <div style='
            background-color: {bg_color};
            width: 100%;
            max-width: 900px;
            display: flex;
            flex-direction: row;
            gap: 16px;
            padding: 12px 0;
            margin-bottom: 24px;
            align-items: flex-start;
            box-shadow: {css_shadow};
            border: {css_border};
            border-radius: 8px;
            transition: all 0.2s ease-in-out;
        '>
            <a href="javascript:;" id='{v["id"]}' style='flex: 2; position: relative; display: block;'>
                <img src='{thumb_src}'
                     style='width: 100%; height: auto; border-radius: 6px; margin-left: 12px;' />
                <div style='
                    position: absolute;
                    top: 8px;
                    left: 20px;
                    background-color: rgba(0, 0, 0, 0.75);
                    color: white;
                    padding: 2px 8px;
                    font-size: 0.80rem;
                    border-radius: 4px;
                    font-family: sans-serif;
                '>{label}</div>
                <div style='
                    position: absolute;
                    bottom: 8px;
                    right: 8px;
                    background-color: rgba(0, 0, 0, 0.75);
                    color: white;
                    padding: 2px 6px;
                    font-size: 0.75rem;
                    border-radius: 4px;
                    font-family: sans-serif;
                '>{v["duration"]}</div>
            </a>
            <div style='flex: 3; display: flex; flex-direction: column; justify-content: flex-start; padding-right: 12px;'>
                <h4 style='margin: 0 0 4px 0; font-size: 1.3rem; font-weight: 600;'>{v["title"]}</h4>
                <p style='margin: 2px 0 10px 0; color: #777; font-size: 0.85rem;'>{v["views"]} • {v["years"]}</p>
                <div style='display: flex; align-items: center; gap: 8px; font-size: 0.9rem; color: #555; margin-top: 6px;'>
                    <img src='{v["profile"]}' style='width: 28px; height: 28px; border-radius: 50%;' alt='channel icon' />
                    <span>{v["channel"]}</span>
                </div>
            </div>
        </div>
        """

    # 3. RENDER CLICK DETECTOR
    # Key includes selection to force refresh (prevents duplicate sets)
    click = click_detector(f"""
        <div style='display: flex; flex-direction: column; align-items: flex-start;'>
            {html}
        </div>
    """, key=f"video_click_page_{current_page_number}_{current_selection}")

    if click and click != current_selection:
        st.session_state.selections[current_page_number] = click
        st.rerun()

# Render selector
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
            if selected_video and current_page_number not in st.session_state.logged_pages:
                log_choice(participant_id, current_page_number, selected_video)
                st.session_state.logged_pages.add(current_page_number)
            
            if st.session_state.page_index < total_pages - 1:
                st.session_state.page_index += 1
                st.rerun()
            else:
                st.success("🎉 You have completed the study!")
                st.balloons()
