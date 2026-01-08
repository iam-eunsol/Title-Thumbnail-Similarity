import streamlit as st
from st_click_detector import click_detector
import os
import csv
import json
import random
from datetime import datetime
from zoneinfo import ZoneInfo
from collections import defaultdict

st.set_page_config(layout="wide", page_title="YouTube Experiment")

# --- LOAD VIDEO METADATA FROM JSON ---
with open("video_metadata.json", "r", encoding="utf-8") as f:
    all_videos = json.load(f)

# Group videos by `page`
videos_by_page = defaultdict(list)
for v in all_videos:
    page = v.get("page", 1)
    videos_by_page[page].append(v)

# Determine pages (1..N), capped at 10
pages = sorted(videos_by_page.keys())
MAX_PAGES = 10
pages = [p for p in pages if p >= 1][:MAX_PAGES]
total_pages = len(pages)

# --- GET PARTICIPANT ID FROM QUERY PARAMS (Qualtrics: ?pid=XXXX) ---
params = st.query_params
raw_pid = params.get("pid", None)

if raw_pid is None:
    participant_id = "unknown"
elif isinstance(raw_pid, list):
    participant_id = raw_pid[0]
else:
    participant_id = str(raw_pid)

# --- SIMPLE LOGGER ---
LOG_FILE = "choices_log.csv"

def log_choice(pid, page_number, video):
    """Log ET timestamp, participant id, page number, and basic video metadata."""
    file_exists = os.path.exists(LOG_FILE)
    eastern_now = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow([
                "timestamp_et",
                "participant_id",
                "page",
                "video_id",
                "video_title",
                "video_vid_id"
            ])
        writer.writerow([
            eastern_now,
            pid,
            page_number,
            video.get("id", ""),
            video.get("title", ""),
            video.get("vid_id", "")
        ])

# --- SESSION STATE ---
if "page_index" not in st.session_state:
    st.session_state.page_index = 0               # 0..total_pages-1
if "selections" not in st.session_state:
    st.session_state.selections = {}              # page_number -> video_id
if "logged_pages" not in st.session_state:
    st.session_state.logged_pages = set()         # pages already logged
if "page_orders" not in st.session_state:
    st.session_state.page_orders = {}             # page_number -> [video_ids in random order]

if total_pages == 0:
    st.error("No video pages found in video_metadata.json. Please contact the experimenter.")
    st.stop()

# Current page number (e.g., 1..10)
current_page_number = pages[st.session_state.page_index]

# --- RANDOMIZE ORDER OF 2 VIDEOS PER PAGE (PER SESSION) ---
page_videos_full = videos_by_page[current_page_number]

if len(page_videos_full) != 2:
    st.warning(f"Page {current_page_number} does not have exactly 2 videos (found {len(page_videos_full)}).")

video_by_id = {v["id"]: v for v in page_videos_full}

if current_page_number not in st.session_state.page_orders:
    ids = [v["id"] for v in page_videos_full]
    random.shuffle(ids)
    st.session_state.page_orders[current_page_number] = ids

ordered_ids = st.session_state.page_orders[current_page_number]
page_videos = [video_by_id[i] for i in ordered_ids if i in video_by_id]

# --- HEADER / INSTRUCTIONS ---
st.markdown(
    """
    <img src="https://upload.wikimedia.org/wikipedia/commons/b/b8/YouTube_Logo_2017.svg" width="150">
    <br>
    <small style="color: gray;">YouTube is a trademark of Google LLC. Used here for educational purposes only.</small>
    """,
    unsafe_allow_html=True
)

st.caption(f"Participant ID: {participant_id}")
st.markdown(f"### Page {current_page_number} of {pages[-1]}")

st.markdown(
    """
    <div style="
        background-color: #f9f9f9;
        border-left: 6px solid #e62117;
        padding: 16px 24px;
        margin: 16px 0 32px 0;
        font-size: 1.2rem;
        font-weight: 500;
        color: #222;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    ">
        📢 <span style="font-size:1.25rem;">Browse the YouTube video options below.</span><br>
        On each page, click on the thumbnail of the video you’d like to watch the most, then press
        <span style="font-weight:bold;">Continue</span> to confirm your selection for that page.
    </div>
    """,
    unsafe_allow_html=True
)

# --- VIDEO SELECTOR ---
def video_selector():
    current_selection = st.session_state.selections.get(current_page_number, "")
    html = ""
    for v in page_videos:
        selected = v["id"] == current_selection
        css_shadow = "0 0 8px rgba(230,33,23,0.2)" if selected else "none"
        css_border = "2px solid #e62117" if selected else "none"

        html += f"""
        <div style='
            background-color: #fff;
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
            border-radius: 6px;
        '>
            <a href="javascript:;" id='{v["id"]}' style='flex: 2; position: relative; display: block;'>
                <img src='https://img.youtube.com/vi/{v["vid_id"]}/hqdefault.jpg'
                     style='width: 100%; height: auto; border-radius: 6px;' />
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
            <div style='flex: 3; display: flex; flex-direction: column; justify-content: flex-start;'>
                <h4 style='margin: 0 0 4px 0; font-size: 1.3rem; font-weight: 600;'>{v["title"]}</h4>
                <p style='margin: 2px 0 10px 0; color: #777; font-size: 0.85rem;'>{v["views"]} • {v["years"]}</p>
                <div style='display: flex; align-items: center; gap: 8px; font-size: 0.9rem; color: #555; margin-top: 6px;'>
                    <img src='{v["profile"]}' style='width: 28px; height: 28px; border-radius: 50%;' alt='channel icon' />
                    <span>{v["channel"]}</span>
                </div>
            </div>
        </div>
        """

    click = click_detector(f"""
        <div style='display: flex; flex-direction: column; align-items: flex-start;'>
            {html}
        </div>
    """, key=f"video_click_page_{current_page_number}")

    if click and click != current_selection:
        st.session_state.selections[current_page_number] = click
        st.rerun()

    current_selection = st.session_state.selections.get(current_page_number, "")
    if current_selection:
        st.success(f"✅ Selected on this page: {current_selection}")
    else:
        st.info("Click on a thumbnail to select for this page.")

video_selector()

# --- CONTINUE BUTTON (NO PREVIOUS) ---
st.markdown("<br>", unsafe_allow_html=True)

if st.button("Continue ➡"):
    current_selection = st.session_state.selections.get(current_page_number, "")
    if not current_selection:
        st.warning("Please select a video before continuing.")
    else:
        selected_video = next((v for v in page_videos if v["id"] == current_selection), None)
        if selected_video is None:
            st.error("Selected video not found on this page (internal error).")
        else:
            # Log this page only once
            if current_page_number not in st.session_state.logged_pages:
                log_choice(participant_id, current_page_number, selected_video)
                st.session_state.logged_pages.add(current_page_number)

            # Move forward only
            if st.session_state.page_index < total_pages - 1:
                st.session_state.page_index += 1
                st.rerun()
            else:
                st.success("You have completed all pages. You may now return to the survey.")
