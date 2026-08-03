FROM python:3.12-slim

# Install OS-level dependencies for tesseract/opencv (raster fallback) and the
# OCRmyPDF text-layer step (ghostscript, qpdf, unpaper for --deskew/--clean).
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    ghostscript \
    qpdf \
    unpaper \
    pngquant \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install --no-cache-dir uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY src/ ./src/
COPY README.md ./

RUN uv sync --frozen --extra raster --extra ocr --no-dev

ENV MCP_TRANSPORT=streamable-http
ENV HOST=0.0.0.0
ENV PORT=8000

EXPOSE 8000

CMD ["uv", "run", "--frozen", "--no-dev", "python", "-m", "pdf_chart_parser.server"]
