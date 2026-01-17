import streamlit as st
import subprocess
import sys
import os
import re
import glob
import shutil
from pathlib import Path

# --- Configuration ---
TEMP_DIR = Path("/tmp/manim")
TIMEOUT_SECONDS = 600  # 10 minutes

st.set_page_config(
    page_title="Manim Render Studio",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Custom CSS for Elegant Look ---
st.markdown("""
    <style>
    .stApp {
        background-color: #f8f9fa;
    }
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 1200px;
    }
    h1 {
        font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
        font-weight: 700;
        color: #2c3e50;
    }
    h3 {
        font-weight: 600;
        color: #34495e;
    }
    .stButton>button {
        background-color: #ff4b4b;
        color: white;
        border-radius: 8px;
        padding: 0.5rem 2rem;
        font-weight: 600;
        border: none;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        background-color: #ff3333;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .stTextArea textarea {
        font-family: 'Source Code Pro', monospace;
        border-radius: 8px;
        border: 1px solid #e0e0e0;
    }
    div[data-testid="stExpander"] {
        border: none;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        background-color: white;
        border-radius: 8px;
    }
    </style>
""", unsafe_allow_html=True)

# --- Helper Functions ---
def clean_temp_dir():
    """Cleans up the temporary directory to avoid clutter."""
    if TEMP_DIR.exists():
        shutil.rmtree(TEMP_DIR)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

def find_video_file(output_dir):
    """Recursively finds the mp4 file in the output directory."""
    mp4_files = list(output_dir.glob("**/*.mp4"))
    # Filter out partial movie files if any
    valid_files = [f for f in mp4_files if "partial_movie_files" not in str(f)]
    if valid_files:
        # Return the most recently modified file
        return max(valid_files, key=os.path.getmtime)
    return None

def get_quality_flag(quality_label):
    mapping = {
        "Low (480p, Fast)": "-ql",
        "Medium (720p, Standard)": "-qm",
        "High (1080p, HD)": "-qh",
        "Extra High (1440p)": "-qp",
        "4K (2160p)": "-qk"
    }
    return mapping.get(quality_label, "-qm")

# --- UI Layout ---

with st.sidebar:
    st.title("⚙️ Settings")
    
    scene_name = st.text_input("Scene Class Name", value="Scene", help="The name of the class in your code that you want to render.")
    
    quality = st.selectbox(
        "Render Quality",
        ["Low (480p, Fast)", "Medium (720p, Standard)", "High (1080p, HD)", "Extra High (1440p)", "4K (2160p)"],
        index=1
    )
    
    st.info("""
    **Instructions:**
    1. Paste your Manim code on the right.
    2. Ensure your Scene class name matches the input above.
    3. Click 'Render Scene'.
    """)
    
    st.markdown("---")
    st.markdown("Made with ❤️ using Manim & Streamlit")

st.title("🎬 Manim Render Studio")
st.markdown("### Paste your code below and bring your math to life.")

default_code = """from manim import *

class Scene(Scene):
    def construct(self):
        circle = Circle()
        circle.set_fill(PINK, opacity=0.5)
        
        square = Square()
        square.set_fill(BLUE, opacity=0.5)
        square.next_to(circle, RIGHT, buff=0.5)
        
        self.play(Create(circle), Create(square))
        self.wait()
"""

code_input = st.text_area("Python Code", value=default_code, height=400)

col1, col2 = st.columns([1, 4])
with col1:
    render_button = st.button("🚀 Render Scene")

if render_button:
    if not code_input.strip():
        st.error("Please enter some Manim code.")
    else:
        # Prepare workspace
        clean_temp_dir()
        script_path = TEMP_DIR / "temp_script.py"
        
        # Write code to file
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(code_input)
            
        # Construct Command
        # manim script.py SceneName -o output.mp4 --media_dir /tmp/manim -q<flag>
        quality_flag = get_quality_flag(quality)
        cmd = [
            "manim",
            str(script_path),
            scene_name,
            "-o", "output.mp4",
            "--media_dir", str(TEMP_DIR),
            quality_flag,
            "--disable_caching"  # Ensure fresh render
        ]
        
        # UI Feedback
        progress_bar = st.progress(0)
        status_text = st.empty()
        status_text.text("Initializing render engine...")
        
        log_expander = st.expander("Show Render Logs", expanded=False)
        log_container = log_expander.empty()
        
        try:
            # Execute Render
            status_text.text("Rendering... This might take a moment.")
            progress_bar.progress(20)
            
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=TIMEOUT_SECONDS,
                cwd=str(TEMP_DIR) # Run inside temp dir
            )
            
            # Show logs
            log_output = f"STDOUT:\n{process.stdout}\n\nSTDERR:\n{process.stderr}"
            log_container.code(log_output)
            
            if process.returncode == 0:
                progress_bar.progress(90)
                status_text.text("Render complete! Processing video...")
                
                video_file = find_video_file(TEMP_DIR)
                
                if video_file and video_file.exists():
                    progress_bar.progress(100)
                    status_text.success("Render Successful!")
                    st.video(str(video_file))
                    
                    # Download button
                    with open(video_file, "rb") as v:
                        st.download_button(
                            label="⬇️ Download Video",
                            data=v,
                            file_name=f"{scene_name}.mp4",
                            mime="video/mp4"
                        )
                else:
                    status_text.error("Render finished but video file was not found.")
            else:
                progress_bar.progress(100)
                status_text.error("Render Failed. Check logs above for details.")
                
        except subprocess.TimeoutExpired:
            status_text.error(f"Render timed out after {TIMEOUT_SECONDS} seconds.")
        except Exception as e:
            status_text.error(f"An unexpected error occurred: {str(e)}")
