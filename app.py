import ast
import base64
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlencode

import streamlit as st

# --- Configuration ---
TIMEOUT_SECONDS = 600  # 10 minutes

# Global process reference for stopping renders
if "current_process" not in st.session_state:
    st.session_state.current_process = None
if "render_active" not in st.session_state:
    st.session_state.render_active = False

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
        font-family: 'Manrope', -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Helvetica', 'Arial', sans-serif;
    }
    h1, h2, h3 {
        font-family: 'Playfair Display', Georgia, 'Times New Roman', serif;
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
        transition: all 0.3s ease;
    }
    div[data-testid="stExpander"]:hover {
        box-shadow: 0 10px 25px rgba(15, 23, 42, 0.12);
        transform: translateY(-2px);
    }
    div[data-testid="stExpander"][data-state="open"] {
        box-shadow: 0 12px 30px rgba(15, 23, 42, 0.15);
    }
    /* Success/Error message padding */
    .stAlert {
        padding: 1rem 1.5rem;
        border-radius: 10px;
        margin: 1rem 0;
    }
    /* Video container separation */
    .stVideo {
        margin: 1.5rem 0;
        padding: 1rem;
        background-color: #f8f9fa;
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
    }
    /* Download button styling */
    .stDownloadButton {
        margin-top: 1rem;
        margin-bottom: 1.5rem;
    }
    /* Selectbox spacing */
    .stSelectbox {
        margin-bottom: 1.5rem;
    }
    /* Section dividers */
    hr {
        margin: 2rem 0;
        border: none;
        border-top: 2px solid #e5e7eb;
    }
    /* Responsive breakpoints */
    @media (max-width: 768px) {
        .main .block-container {
            padding-top: 1rem;
            padding-bottom: 1.5rem;
            padding-left: 1rem;
            padding-right: 1rem;
        }
        .stButton>button {
            padding: 0.5rem 1.5rem;
            font-size: 14px;
        }
        h1 {
            font-size: 2rem !important;
        }
        h2 {
            font-size: 1.5rem !important;
        }
    }
    @media (max-width: 480px) {
        .main .block-container {
            padding: 0.5rem;
        }
        h1 {
            font-size: 1.5rem !important;
        }
        h2 {
            font-size: 1.2rem !important;
        }
    }
    /* Button disabled state */
    .stButton>button:disabled {
        background: linear-gradient(135deg, #cccccc, #999999);
        cursor: not-allowed;
        opacity: 0.6;
    }
    /* Button loading state (when rendering) */
    .stButton>button[data-loading="true"] {
        background: linear-gradient(135deg, #ffa500, #ff8c00);
        cursor: wait;
    }
    .stButton>button[data-loading="true"]::after {
        content: " ⏳";
    }
    /* Dark mode support */
    @media (prefers-color-scheme: dark) {
        .stApp {
            background: radial-gradient(circle at 10% 20%, rgba(30, 30, 50, 0.9), transparent 50%),
                        linear-gradient(180deg, #1a1a2e 0%, #16213e 100%);
            color: #e4e4e7;
        }
        h1, h2, h3 {
            color: #f4f4f5;
        }
        .stTextArea textarea {
            background-color: #27272a;
            border: 1px solid #3f3f46;
            color: #e4e4e7;
        }
        div[data-testid="stExpander"] {
            background-color: #27272a;
            box-shadow: 0 8px 20px rgba(0, 0, 0, 0.4);
        }
        .stVideo {
            background-color: #27272a;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        }
        .stAlert {
            background-color: #27272a;
        }
        hr {
            border-top: 2px solid #3f3f46;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# --- Helper Functions ---
def create_temp_dir() -> Path:
    """Creates a unique temporary directory for this render session."""
    unique_id = uuid.uuid4().hex[:8]
    temp_dir = Path(tempfile.gettempdir()) / f"manim_{unique_id}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir


def cleanup_temp_dir(temp_dir: Path) -> None:
    """Safely removes the temporary directory."""
    try:
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
    except Exception:
        pass  # Ignore cleanup errors


def find_video_file(output_dir: Path, output_name: str = "output.mp4") -> Path | None:
    """Recursively finds the mp4 file in the output directory."""
    # First try the expected output path
    expected_paths = [
        output_dir / "videos" / "scene" / "480p15" / output_name,
        output_dir / "videos" / "scene" / "720p30" / output_name,
        output_dir / "videos" / "scene" / "1080p60" / output_name,
        output_dir / "videos" / "scene" / "1440p60" / output_name,
        output_dir / "videos" / "scene" / "2160p60" / output_name,
        output_dir / output_name,
    ]
    
    for path in expected_paths:
        if path.exists():
            return path
    
    # Fallback: search for any mp4 file
    mp4_files = list(output_dir.glob("**/*.mp4"))
    valid_files = [f for f in mp4_files if "partial_movie_files" not in str(f)]
    if valid_files:
        return max(valid_files, key=os.path.getmtime)
    return None


def get_quality_flag(quality_label: str) -> str:
    """Extract quality flag from label string."""
    mapping = {
        "Low (480p, Fast) - ~10s, 1-2 MB": "-ql",
        "Medium (720p, Standard) - ~30s, 3-5 MB": "-qm",
        "High (1080p, HD) - ~1min, 8-12 MB": "-qh",
        "Extra High (1440p) - ~2min, 15-25 MB": "-qp",
        "4K (2160p) - ~5min, 30-50 MB": "-qk",
    }
    return mapping.get(quality_label, "-qm")


def extract_scene_classes(source_code: str) -> list[str]:
    """Extract all classes that inherit from any Scene type."""
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


def count_animations(source_code: str) -> int:
    """Count the number of self.play() and self.wait() calls in the code more accurately."""
    # Parse the AST to count method calls more accurately
    try:
        tree = ast.parse(source_code)
        play_count = 0

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # Check if it's a method call on self
                if isinstance(node.func, ast.Attribute):
                    if isinstance(node.func.value, ast.Name) and node.func.value.id == "self":
                        # Count play, wait, add, and other animation methods
                        if node.func.attr in ["play", "wait", "add", "remove"]:
                            play_count += 1

        return max(play_count, 1)  # At least 1 to avoid division by zero
    except:
        # Fallback to regex if AST parsing fails
        play_count = len(re.findall(r"self\.play\s*\(", source_code))
        wait_count = len(re.findall(r"self\.wait\s*\(", source_code))
        return max(play_count + wait_count, 1)


def ensure_manim_import(code: str) -> str:
    """
    Ensures the code has manim import if it uses manim classes.
    Smarter detection using AST to avoid duplicate imports.
    """
    try:
        # Parse the code to check for existing imports
        tree = ast.parse(code)
        has_manim_import = False

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if 'manim' in alias.name:
                        has_manim_import = True
                        break
            elif isinstance(node, ast.ImportFrom):
                if node.module and 'manim' in node.module:
                    has_manim_import = True
                    break

        if has_manim_import:
            return code

        # Check if code uses manim classes
        manim_indicators = [
            "Scene", "ThreeDScene", "MovingCameraScene",
            "Circle", "Square", "Triangle", "Rectangle",
            "Tex", "MathTex", "Text",
            "Create", "Write", "FadeIn", "FadeOut",
            "Transform", "ReplacementTransform",
            "UP", "DOWN", "LEFT", "RIGHT",
            "BLUE", "RED", "GREEN", "PINK", "YELLOW"
        ]

        # Use AST to find Name nodes
        uses_manim = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in manim_indicators:
                uses_manim = True
                break

        if uses_manim:
            return "from manim import *\n\n" + code

        return code

    except SyntaxError:
        # Fallback to simple string check if AST parsing fails
        if "from manim import" in code or "import manim" in code:
            return code
        manim_indicators = ["Scene", "Circle", "Square", "Tex", "MathTex", "Create", "Write"]
        if any(indicator in code for indicator in manim_indicators):
            return "from manim import *\n\n" + code
        return code


def format_code(code: str) -> str:
    """Basic code formatting - validates syntax and normalizes whitespace."""
    try:
        # Parse to validate syntax
        tree = ast.parse(code)

        # Basic formatting: normalize line breaks and indentation
        lines = code.split('\n')
        formatted_lines = []

        for line in lines:
            # Remove trailing whitespace
            line = line.rstrip()
            if line:
                formatted_lines.append(line)
            else:
                # Keep empty lines between blocks
                if formatted_lines and formatted_lines[-1] != '':
                    formatted_lines.append('')

        # Remove multiple consecutive empty lines
        result = []
        prev_empty = False
        for line in formatted_lines:
            if line == '':
                if not prev_empty:
                    result.append(line)
                prev_empty = True
            else:
                result.append(line)
                prev_empty = False

        return '\n'.join(result)
    except SyntaxError:
        # If code has syntax errors, return as-is
        return code


class RenderProgressTracker:
    """Tracks render progress in real-time based on manim output."""
    
    # Render stages with their progress weight
    STAGES = {
        "init": (0, 5, "Initializing..."),
        "parsing": (5, 10, "Parsing scene..."),
        "latex": (10, 20, "Compiling LaTeX..."),
        "rendering": (20, 85, "Rendering animations..."),
        "combining": (85, 95, "Combining video segments..."),
        "writing": (95, 99, "Writing final video..."),
        "done": (100, 100, "Complete!"),
    }
    
    def __init__(self, total_animations: int):
        self.total_animations = total_animations
        self.current_animation = 0
        self.current_stage = "init"
        self.current_animation_progress = 0
        self.last_status = ""
        
    def parse_line(self, line: str) -> tuple[int, str]:
        """
        Parse a line of manim output and return (progress_percent, status_message).
        """
        line_lower = line.lower().strip()
        
        # Skip empty lines
        if not line_lower:
            return self._calculate_progress(), self.last_status
        
        # Detect stage transitions
        if "error" in line_lower or "traceback" in line_lower:
            return self._calculate_progress(), f"Error: {line[:50]}..."
        
        # LaTeX compilation
        if "tex" in line_lower and ("writing" in line_lower or "compiling" in line_lower):
            self.current_stage = "latex"
            self.last_status = "Compiling LaTeX..."
            return self._calculate_progress(), self.last_status
        
        # Animation detection - look for "Animation X:" pattern
        anim_match = re.search(r"animation\s+(\d+)", line_lower)
        if anim_match:
            self.current_stage = "rendering"
            self.current_animation = int(anim_match.group(1))
            
            # Extract animation name if present
            name_match = re.search(r"animation\s+\d+\s*:\s*(\w+)", line, re.IGNORECASE)
            anim_name = name_match.group(1) if name_match else "animation"
            
            self.last_status = f"Rendering {anim_name} ({self.current_animation}/{self.total_animations})"
        
        # Progress percentage within current animation
        percent_match = re.search(r"(\d+)%", line)
        if percent_match and self.current_stage == "rendering":
            self.current_animation_progress = int(percent_match.group(1))
            return self._calculate_progress(), self.last_status
        
        # Combining/concatenating partial movies
        if "partial movie" in line_lower or "combining" in line_lower or "concatenat" in line_lower:
            self.current_stage = "combining"
            self.last_status = "Combining video segments..."
            return self._calculate_progress(), self.last_status
        
        # Writing final file
        if ("writing" in line_lower or "saved" in line_lower) and "tex" not in line_lower:
            self.current_stage = "writing"
            self.last_status = "Writing final video..."
            return self._calculate_progress(), self.last_status
        
        # File ready
        if "file ready" in line_lower or "movie ready" in line_lower:
            self.current_stage = "done"
            self.last_status = "Complete!"
            return 100, self.last_status
        
        # Scene initialization
        if "scene" in line_lower and self.current_stage == "init":
            self.current_stage = "parsing"
            self.last_status = "Parsing scene..."
        
        return self._calculate_progress(), self.last_status or "Processing..."
    
    def _calculate_progress(self) -> int:
        """Calculate overall progress based on current stage and animation."""
        stage_start, stage_end, _ = self.STAGES.get(self.current_stage, (0, 5, ""))
        
        if self.current_stage == "rendering" and self.total_animations > 0:
            # Calculate progress within rendering stage based on animations
            render_start, render_end, _ = self.STAGES["rendering"]
            render_range = render_end - render_start
            
            # Progress = completed animations + current animation progress
            completed_progress = (self.current_animation - 1) / self.total_animations
            current_progress = (self.current_animation_progress / 100) / self.total_animations
            
            total_anim_progress = completed_progress + current_progress
            return int(render_start + (render_range * total_anim_progress))
        
        return stage_start


def run_manim_with_progress(
    cmd: list,
    cwd: str,
    timeout: int,
    total_animations: int,
    progress_bar,
    status_text,
) -> tuple[bool, str]:
    """
    Run manim command with real-time progress updates.
    Returns (success: bool, log_output: str).
    """
    log_lines: list[str] = []
    tracker = RenderProgressTracker(total_animations)
    
    # Log the command being run
    log_lines.append(f"Command: {' '.join(cmd)}\n")
    log_lines.append(f"Working directory: {cwd}\n")
    log_lines.append("-" * 50 + "\n")
    
    status_text.text("Starting render...")
    progress_bar.progress(0)
    
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=cwd,
            bufsize=1,
            universal_newlines=True,
        )

        # Store process in session state for stop functionality
        st.session_state.current_process = process
        st.session_state.render_active = True

        start_time = time.time()
        last_progress = 0

        while True:
            # Check if user requested stop
            if not st.session_state.render_active:
                process.kill()
                log_lines.append("\n[Render stopped by user]\n")
                return (False, "".join(log_lines))

            # Check timeout
            elapsed = time.time() - start_time
            if elapsed > timeout:
                process.kill()
                raise subprocess.TimeoutExpired(cmd, timeout)
            
            if process.stdout is None:
                break
            
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            
            if line:
                log_lines.append(line)
                progress, status = tracker.parse_line(line)
                
                # Only update if progress increased (avoid flickering)
                if progress > last_progress:
                    last_progress = progress
                    progress_bar.progress(min(progress, 100))
                
                if status:
                    status_text.text(status)
        
        # Wait for process to complete and get return code
        return_code = process.wait()
        
        # Log the return code
        log_lines.append("-" * 50 + "\n")
        log_lines.append(f"Process exited with code: {return_code}\n")
        
        # Final progress
        if return_code == 0:
            progress_bar.progress(100)
            status_text.text("Render complete!")
        else:
            status_text.text("Render failed!")

        # Clear process reference
        st.session_state.current_process = None
        st.session_state.render_active = False

        return (return_code == 0, "".join(log_lines))
        
    except subprocess.TimeoutExpired:
        log_lines.append(f"\nProcess timed out after {timeout} seconds\n")
        st.session_state.current_process = None
        st.session_state.render_active = False
        raise
    except Exception as e:
        log_lines.append(f"\nException: {str(e)}\n")
        st.session_state.current_process = None
        st.session_state.render_active = False
        return (False, "".join(log_lines))


# --- UI Layout ---

with st.sidebar:
    st.title("⚙️ Settings")

    # Video size control
    video_width = st.slider(
        "Video Preview Width (%)",
        min_value=30,
        max_value=100,
        value=100,
        step=10,
        help="Adjust the width of the video preview"
    )

    st.markdown("")  # spacing

    quality = st.selectbox(
        "Render Quality",
        [
            "Low (480p, Fast) - ~10s, 1-2 MB",
            "Medium (720p, Standard) - ~30s, 3-5 MB",
            "High (1080p, HD) - ~1min, 8-12 MB",
            "Extra High (1440p) - ~2min, 15-25 MB",
            "4K (2160p) - ~5min, 30-50 MB",
        ],
        index=1,
        help="Higher quality means better resolution but longer render time and larger file size.",
    )

    st.info(
        """
**📖 Instructions:**

1. Paste your Manim code below
2. Select the Scene class to render
3. Click 'Render Scene' to create your animation

[📚 Manim Documentation](https://docs.manim.community/)
    """
    )

    st.markdown("---")
    st.markdown("✨ Made with **Manim** 🎬 & **Streamlit** ⚡")

st.title("🎬 Manim Render Studio")
st.markdown("## Paste your code below and bring your math to life.")

# Keyboard shortcuts (Ctrl+Enter to render)
st.markdown(
    """
    <script>
    document.addEventListener('keydown', function(e) {
        // Ctrl+Enter or Cmd+Enter to trigger render
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
            e.preventDefault();
            // Find and click the render button
            const buttons = window.parent.document.querySelectorAll('button');
            for (let btn of buttons) {
                if (btn.innerText.includes('Render Scene')) {
                    btn.click();
                    break;
                }
            }
        }
    });
    </script>
    <style>
    /* Keyboard shortcut hint */
    .shortcut-hint {
        font-size: 0.85rem;
        color: #6b7280;
        margin-top: -0.5rem;
        margin-bottom: 1rem;
    }
    </style>
    <div class="shortcut-hint">💡 Tip: Press <kbd>Ctrl</kbd>+<kbd>Enter</kbd> to render</div>
    """,
    unsafe_allow_html=True
)

# Load code from URL parameter if present
try:
    query_params = st.query_params
    if "code" in query_params:
        encoded_code = query_params["code"]
        decoded_code = base64.b64decode(encoded_code).decode('utf-8')
        if "code_input" not in st.session_state or st.session_state.code_input == default_code:
            st.session_state.code_input = decoded_code
            st.success("📥 Code loaded from shared link!")
except Exception:
    pass  # Ignore URL parameter errors

# Default code with LaTeX example
default_code = '''from manim import *

class DemoScene(Scene):
    def construct(self):
        # LaTeX formula
        formula = MathTex(r"e^{i\pi} + 1 = 0", font_size=72)
        formula.set_color(BLUE)
        
        # Title
        title = Text("Euler's Identity", font_size=48)
        title.next_to(formula, UP, buff=0.8)
        
        # Animate
        self.play(Write(title))
        self.play(Write(formula))
        self.wait(1)
        
        # Transform
        circle = Circle(color=PINK, fill_opacity=0.5)
        self.play(ReplacementTransform(formula, circle))
        self.wait(0.5)
'''

# Code editor header
col_header1, col_header2, col_header3, col_header4 = st.columns([1.5, 1, 1, 1])
with col_header1:
    st.markdown("### 📝 Manim Scene Code")
with col_header2:
    if st.button("🔗 Share"):
        st.session_state.show_share = True
with col_header3:
    if st.button("✨ Format"):
        st.session_state.format_code = True
with col_header4:
    if st.button("🗑️ Clear"):
        st.session_state.code_cleared = True

# Initialize session state for code
if "code_input" not in st.session_state:
    st.session_state.code_input = default_code
if "code_cleared" in st.session_state and st.session_state.code_cleared:
    st.session_state.code_input = ""
    st.session_state.code_cleared = False
if "format_code" in st.session_state and st.session_state.format_code:
    st.session_state.code_input = format_code(st.session_state.code_input)
    st.session_state.format_code = False
    st.success("✨ Code formatted!")

# Show syntax highlighted preview option
show_preview = st.checkbox("👁️ Show syntax-highlighted preview with line numbers", value=False)

if show_preview:
    # Split view: editor and preview side by side
    col_edit, col_preview = st.columns([1, 1])
    with col_edit:
        st.caption("**Editor:**")
        code_input = st.text_area(
            "Code Editor",
            value=st.session_state.code_input,
            height=400,
            label_visibility="collapsed",
            key="code_editor"
        )
    with col_preview:
        st.caption("**Preview (with syntax highlighting & line numbers):**")
        st.code(st.session_state.code_input, language="python", line_numbers=True)
else:
    code_input = st.text_area(
        "Code Editor",
        value=st.session_state.code_input,
        height=400,
        label_visibility="collapsed",
        key="code_editor"
    )

# Update session state
if code_input != st.session_state.code_input:
    st.session_state.code_input = code_input

# Show share link if requested
if "show_share" in st.session_state and st.session_state.show_share:
    encoded_code = base64.b64encode(code_input.encode('utf-8')).decode('utf-8')
    # Get current URL without query params
    base_url = "http://localhost:8501"  # This will be replaced by actual URL in production
    share_url = f"{base_url}?code={encoded_code}"

    st.info("🔗 **Share this link to share your code:**")
    st.code(share_url, language="text")
    st.caption("⚠️ Note: The link contains your entire code encoded in the URL. Keep it safe if it contains sensitive information.")

    if st.button("✅ Done"):
        st.session_state.show_share = False
        st.rerun()

# Auto-detect scene classes
scene_candidates = extract_scene_classes(code_input)

if scene_candidates:
    scene_name = st.selectbox("Scene Class (auto-detected)", scene_candidates)
else:
    scene_name = st.text_input(
        "Scene Class Name",
        value="DemoScene",
        help="Could not auto-detect. Enter the class name manually.",
    )

st.markdown("---")

# Show confirmation checkbox for complex scenes
if code_input and len(code_input) > 500:
    st.info("💡 This appears to be a complex scene. Rendering may take several minutes.")
    confirm_render = st.checkbox("I understand and want to render this scene", value=True)
else:
    confirm_render = True

render_button = st.button("🎬 Render Scene", use_container_width=False, disabled=not confirm_render)

if render_button:
    if not code_input.strip():
        st.error("⚠️ Please enter some Manim code.")
    elif not scene_name:
        st.error("⚠️ Please specify a Scene class name.")
    elif scene_name not in code_input:
        st.error(f"⚠️ Scene class '{scene_name}' not found in your code. Please check the class name.")
    elif scene_candidates and scene_name not in scene_candidates:
        st.warning(f"⚠️ Warning: '{scene_name}' may not be a valid Scene class. Detected classes: {', '.join(scene_candidates)}")
        st.info("Attempting to render anyway...")

    if code_input.strip() and scene_name and scene_name in code_input:
        # Prepare code (add import if missing)
        final_code = ensure_manim_import(code_input)

        # Check for syntax errors first
        try:
            ast.parse(final_code)
        except SyntaxError as e:
            st.error(f"❌ Syntax error in your code at line {e.lineno}: {e.msg}")
            st.stop()

        # Count animations for progress tracking
        total_animations = count_animations(final_code)

        # Create unique temp directory for this render
        temp_dir = create_temp_dir()
        script_path = temp_dir / "scene.py"

        # UI elements for progress (defined outside try for cleanup)
        with st.spinner("⏳ Initializing render..."):
            time.sleep(0.3)  # Brief loading indicator

        status_text = st.empty()
        progress_bar = st.progress(0)

        # Stop button
        stop_button_placeholder = st.empty()
        if st.session_state.render_active:
            if stop_button_placeholder.button("🛑 Stop Render", key="stop_render"):
                st.session_state.render_active = False
                st.warning("⏹️ Stopping render...")
                st.rerun()

        try:
            # Write code to file
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(final_code)

            # Construct Command
            quality_flag = get_quality_flag(quality)
            cmd = [
                "manim",
                str(script_path),
                scene_name,
                "-o",
                "output.mp4",
                "--media_dir",
                str(temp_dir),
                quality_flag,
                "--disable_caching",
                "-v", "INFO",  # Verbose output for progress tracking
            ]

            # Run render with progress tracking
            success, log_output = run_manim_with_progress(
                cmd=cmd,
                cwd=str(temp_dir),
                timeout=TIMEOUT_SECONDS,
                total_animations=total_animations,
                progress_bar=progress_bar,
                status_text=status_text,
            )

            # Keep progress UI visible for a moment before clearing
            time.sleep(0.5)

            # Find video file
            video_file = find_video_file(temp_dir)
            
            if success and video_file and video_file.exists():
                # SUCCESS - Show video and download
                st.success("✅ Render Successful!")

                # Read video bytes BEFORE cleanup
                video_bytes = video_file.read_bytes()

                # Video preview with size control
                if video_width < 100:
                    col_vid1, col_vid2, col_vid3 = st.columns([
                        (100 - video_width) // 2,
                        video_width,
                        (100 - video_width) // 2
                    ])
                    with col_vid2:
                        st.video(video_bytes)
                else:
                    st.video(video_bytes)

                # Download button  
                st.download_button(
                    label="Download Video",
                    data=video_bytes,
                    file_name=f"{scene_name}.mp4",
                    mime="video/mp4",
                )

                # Logs (collapsed)
                with st.expander("📋 Render Logs", expanded=False):
                    st.code(log_output, language="text")
                    
            elif success and not video_file:
                # Render succeeded but no video found
                all_files = list(temp_dir.rglob("*"))
                debug_info = "\n\nFiles in temp directory:\n"
                for f in all_files:
                    if f.is_file():
                        debug_info += f"  {f}\n"
                
                st.error("❌ Render completed but video file was not found.")
                with st.expander("📋 Render Logs", expanded=True):
                    st.code(log_output + debug_info, language="text")
            else:
                # FAILED - Show error and logs
                st.error("❌ Render Failed!")
                with st.expander("📋 Render Logs", expanded=True):
                    st.code(log_output, language="text")

        except subprocess.TimeoutExpired:
            status_text.empty()
            progress_bar.empty()
            st.error(f"⏱️ Render timed out after {TIMEOUT_SECONDS} seconds ({TIMEOUT_SECONDS // 60} minutes).")
        except Exception as e:
            status_text.empty()
            progress_bar.empty()
            st.error(f"❌ An unexpected error occurred: {str(e)}")
            import traceback
            with st.expander("🔍 Error Details", expanded=True):
                st.code(traceback.format_exc(), language="text")
        finally:
            # Always cleanup temp directory
            cleanup_temp_dir(temp_dir)
