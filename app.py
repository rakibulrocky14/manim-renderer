import ast
import os
import re
import shutil
import subprocess
from pathlib import Path

import streamlit as st

# --- Configuration ---
TEMP_DIR = Path("/tmp/manim")
TIMEOUT_SECONDS = 600  # 10 minutes

# Known Manim Scene base classes
SCENE_BASE_CLASSES = {
    "Scene",
    "ThreeDScene",
    "MovingCameraScene",
    "ZoomedScene",
    "VectorScene",
    "LinearTransformationScene",
    "SampleSpaceScene",
}

st.set_page_config(
    page_title="Manim Render Studio",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');

    .stApp {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        background-attachment: fixed;
    }
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2.5rem;
        max-width: 1100px;
    }
    [data-testid="stSidebar"] {
        background: rgba(255,255,255,0.95);
        backdrop-filter: blur(10px);
    }
    [data-testid="stSidebar"] h1 {
        color: #1f2937 !important;
    }
    body, div, p, label, input, textarea, span {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    }
    h1, h2, h3 {
        font-family: 'Inter', sans-serif !important;
        font-weight: 700 !important;
        color: #ffffff !important;
    }
    .stMarkdown p, .stMarkdown h3 {
        color: rgba(255,255,255,0.9) !important;
    }
    .stButton>button {
        background: linear-gradient(135deg, #ff6b6b, #ee5a5a);
        color: white;
        border-radius: 12px;
        padding: 0.75rem 2.5rem;
        font-weight: 600;
        font-size: 1rem;
        border: none;
        transition: all 0.3s ease;
        box-shadow: 0 8px 24px rgba(238, 90, 90, 0.4);
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 12px 32px rgba(238, 90, 90, 0.5);
    }
    .stTextArea textarea {
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace !important;
        font-size: 14px;
        border-radius: 12px;
        border: 2px solid rgba(255,255,255,0.2);
        background-color: rgba(15, 23, 42, 0.95);
        color: #e2e8f0;
        padding: 1rem;
    }
    .stTextArea textarea:focus {
        border-color: #667eea;
        box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.3);
    }
    .stSelectbox > div > div {
        background-color: rgba(255,255,255,0.95);
        border-radius: 8px;
    }
    div[data-testid="stExpander"] {
        border: none;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15);
        background-color: rgba(255,255,255,0.95);
        border-radius: 12px;
        backdrop-filter: blur(10px);
    }
    .stVideo {
        border-radius: 12px;
        overflow: hidden;
        box-shadow: 0 8px 32px rgba(0,0,0,0.2);
    }
    .stDownloadButton > button {
        background: linear-gradient(135deg, #10b981, #059669);
        box-shadow: 0 8px 24px rgba(16, 185, 129, 0.4);
    }
    .stDownloadButton > button:hover {
        box-shadow: 0 12px 32px rgba(16, 185, 129, 0.5);
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
    """Extract all classes that inherit from any Scene type."""
    # First try AST parsing
    try:
        tree = ast.parse(source_code)
        scene_classes: list[str] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            for base in node.bases:
                base_name = None
                if isinstance(base, ast.Name):
                    base_name = base.id
                elif isinstance(base, ast.Attribute):
                    base_name = base.attr
                if base_name and (base_name in SCENE_BASE_CLASSES or "Scene" in base_name):
                    scene_classes.append(node.name)
                    break
        if scene_classes:
            return scene_classes
    except SyntaxError:
        pass

    # Fallback: regex-based detection
    pattern = r"class\s+(\w+)\s*\([^)]*(?:Scene|ThreeDScene|MovingCameraScene)[^)]*\)"
    matches = re.findall(pattern, source_code)
    return matches if matches else []


# --- UI Layout ---

with st.sidebar:
    st.title("Settings")

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

    st.markdown("---")

    st.markdown(
        """
    **How to use:**
    1. Paste your Manim code
    2. Select the Scene class
    3. Click Render
    
    **Supported:**
    - LaTeX / MathTex
    - All Manim CE features
    - Up to 10 min render time
    """
    )

st.title("Manim Render Studio")
st.markdown("#### Paste your Manim code and render beautiful math animations")

default_code = '''from manim import *

class DemoScene(Scene):
    def construct(self):
        # Create shapes
        circle = Circle(color=BLUE, fill_opacity=0.5)
        square = Square(color=GREEN, fill_opacity=0.5)
        
        # Position
        circle.shift(LEFT * 2)
        square.shift(RIGHT * 2)
        
        # Animate
        self.play(Create(circle), Create(square))
        self.play(circle.animate.shift(RIGHT * 4), square.animate.shift(LEFT * 4))
        self.play(FadeOut(circle), FadeOut(square))
'''

code_input = st.text_area("Python Code", value=default_code, height=350)

# Auto-detect scene classes
scene_candidates = extract_scene_classes(code_input)

col1, col2 = st.columns([2, 3])

with col1:
    if scene_candidates:
        scene_name = st.selectbox("Scene Class (auto-detected)", scene_candidates)
    else:
        scene_name = st.text_input(
            "Scene Class Name",
            value="DemoScene",
            help="Could not auto-detect. Enter the class name manually.",
        )

with col2:
    st.write("")  # Spacer
    st.write("")
    render_button = st.button("Render Scene", type="primary", use_container_width=True)

if render_button:
    if not code_input.strip():
        st.error("Please enter some Manim code.")
    elif not scene_name:
        st.error("Please specify a Scene class name.")
    else:
        # Prepare workspace
        clean_temp_dir()
        script_path = TEMP_DIR / "temp_script.py"

        # Write code to file
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(code_input)

        # Construct Command
        quality_flag = get_quality_flag(quality)
        cmd = [
            "manim",
            str(script_path),
            scene_name,
            "-o",
            "output.mp4",
            "--media_dir",
            str(TEMP_DIR),
            quality_flag,
            "--disable_caching",
        ]

        # UI Feedback
        progress_bar = st.progress(0, text="Initializing render engine...")

        log_expander = st.expander("Render Logs", expanded=True)

        try:
            progress_bar.progress(10, text="Starting Manim renderer...")

            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=TIMEOUT_SECONDS,
                cwd=str(TEMP_DIR),
            )

            # Show logs
            log_output = process.stdout + "\n" + process.stderr
            with log_expander:
                st.code(log_output, language="text")

            if process.returncode == 0:
                progress_bar.progress(90, text="Render complete! Loading video...")

                video_file = find_video_file(TEMP_DIR)

                if video_file and video_file.exists():
                    progress_bar.progress(100, text="Done!")

                    st.success("Render Successful!")
                    st.video(str(video_file))

                    # Download button
                    with open(video_file, "rb") as v:
                        st.download_button(
                            label="Download Video",
                            data=v,
                            file_name=f"{scene_name}.mp4",
                            mime="video/mp4",
                            use_container_width=True,
                        )
                else:
                    progress_bar.progress(100, text="Error")
                    st.error(
                        "Render finished but video file was not found. Check logs for details."
                    )
            else:
                progress_bar.progress(100, text="Render failed")
                st.error("Render Failed. Check the logs above for details.")

        except subprocess.TimeoutExpired:
            st.error(f"Render timed out after {TIMEOUT_SECONDS // 60} minutes.")
        except Exception as e:
            st.error(f"An unexpected error occurred: {str(e)}")
