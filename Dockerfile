# Base Image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install System Dependencies
# texlive-latex-extra includes a good middle-ground set of packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libcairo2-dev \
    libpango1.0-dev \
    ffmpeg \
    pkg-config \
    texlive-latex-extra \
    texlive-fonts-recommended \
    texlive-science \
    latexmk \
    && rm -rf /var/lib/apt/lists/*

# Work Directory
WORKDIR /app

# Install Python Dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy App
COPY . .

# Expose Streamlit Port
EXPOSE 8501

# Run App
CMD sh -c "streamlit run app.py --server.port=${PORT:-8501} --server.address=0.0.0.0 --server.headless=true"
