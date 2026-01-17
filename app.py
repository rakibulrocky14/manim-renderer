import ast
import os
import shutil
import subprocess
from pathlib import Path

import streamlit as st

# --- Configuration ---
TEMP_DIR = Path("/tmp/manim")
TIMEOUT_SECONDS = 600  # 10 minutes

st.set_page_config(
    page_title="Manim Render Studio",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600&family=Playfair+Display:wght@600;700&display=swap');

    .stApp {
        background: radial-gradient(circle at 10% 20%, rgba(255, 244, 235, 0.9), transparent 50%),
                    linear-gradient(180deg, #f7f8fb 0%, #eef1f6 100%);
        color: #1f2a37;
    }
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2.5rem;
        max-width: 1200px;
    }
    body, div, p, label, input, textarea {
        font-family: 'Manrope', sans-serif;
    }
    h1, h2, h3 {
        font-family: 'Playfair Display', serif;
        font-weight: 700;
        color: #1f2a37;
    }
    .stButton>button {
        background: linear-gradient(135deg, #ff6b6b, #ff4b4b);
        color: white;
        border-radius: 10px;
        padding: 0.6rem 2.2rem;
        font-weight: 600;
        border: none;
        transition: all 0.3s ease;
        box-shadow: 0 10px 20px rgba(255, 75, 75, 0.2);
    }
    .stButton>button:hover {
        transform: translateY(-1px);
        box-shadow: 0 12px 24px rgba(255, 75, 75, 0.3);
    }
    .stTextArea textarea {
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
        border-radius: 12px;
        border: 1px solid #e0e0e0;
        background-color: #fbfbfd;
    }
    div[data-testid="stExpander"] {
        border: none;
        box-shadow: 0 8px 20px rgba(15, 23, 42, 0.08);
        background-color: white;
        border-radius: 12px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- Helper Functions ---
def clean_temp_dir():
    """Cleans up the temporary directory to avoid clutter."""
    if TEMP_DIR.exists():
        shutil.rmtree(TEMP_DIR)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)


def find_video_file(output_dir: Path) -> Path | None:
    """Recursively finds the mp4 file in the output directory."""
    mp4_files = list(output_dir.glob("**/*.mp4"))
    valid_files = [f for f in mp4_files if "partial_movie_files" not in str(f)]
    if valid_files:
        return max(valid_files, key=os.path.getmtime)
    return None


def get_quality_flag(quality_label: str) -> str:
    mapping = {
        "Low (480p, Fast)": "-ql",
        "Medium (720p, Standard)": "-qm",
        "High (1080p, HD)": "-qh",
        "Extra High (1440p)": "-qp",
        "4K (2160p)": "-qk",
    }
    return mapping.get(quality_label, "-qm")


def extract_scene_classes(source_code: str) -> list[str]:
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return []

    scene_classes: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for base in node.bases:
            if isinstance(base, ast.Name) and base.id == "Scene":
                scene_classes.append(node.name)
            elif isinstance(base, ast.Attribute) and base.attr == "Scene":
                scene_classes.append(node.name)
    return scene_classes


# --- UI Layout ---

with st.sidebar:
    st.title("⚙️ Settings")

    quality = st.selectbox(
        "Render Quality",
        [
            "Low (480p, Fast)",
            "Medium (720p, Standard)",
            "High (1080p, HD)",
            "Extra High (1440p)",
            "4K (2160p)",
        ],
        index=1,
    )

    st.info(
        """
    **Instructions:**
    1. Paste your Manim code on the right.
    2. Choose the Scene class to render.
    3. Click 'Render Scene'.
    """
    )

    st.markdown("---")
    st.markdown("Made with ❤️ using Manim & Streamlit")

st.title("🎬 Manim Render Studio")
st.markdown("### Paste your code below and bring your math to life.")

default_code = """from manim import *

class DemoScene(Scene):
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

scene_candidates = extract_scene_classes(code_input)
if not scene_candidates:
    scene_candidates = ["DemoScene"]

scene_name = st.selectbox("Scene Class", scene_candidates)

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
