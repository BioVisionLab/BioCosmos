#!/bin/bash
# Helper script to run the image embedding process with proper environment setup

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$PROJECT_ROOT"
VENV_PATH="$BACKEND_DIR/.venv"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Print formatted messages
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# Check arguments
if [ $# -lt 2 ]; then
    echo "Usage: $0 <input_dir> <output_dir> [--background]"
    echo ""
    echo "Arguments:"
    echo "  input_dir    - Directory containing images to process"
    echo "  output_dir   - Directory where lance_db and static will be created"
    echo "  --background - Run process in background (optional)"
    echo ""
    echo "Examples:"
    echo "  $0 ./images ./output"
    echo "  $0 ./images ./output --background"
    exit 1
fi

INPUT_DIR="$1"
OUTPUT_DIR="$2"
RUN_BACKGROUND="${3:-}"

# Validate input directory
if [ ! -d "$INPUT_DIR" ]; then
    log_error "Input directory does not exist: $INPUT_DIR"
    exit 1
fi

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Activate virtual environment
if [ ! -d "$VENV_PATH" ]; then
    log_error "Virtual environment not found at: $VENV_PATH"
    log_info "Please set up the backend environment first"
    exit 1
fi

source "$VENV_PATH/bin/activate"
log_info "Virtual environment activated"

# Get absolute paths
INPUT_DIR=$(cd "$INPUT_DIR" && pwd)
OUTPUT_DIR=$(cd "$OUTPUT_DIR" && pwd)

log_info "Configuration:"
log_info "  Input directory:  $INPUT_DIR"
log_info "  Output directory: $OUTPUT_DIR"
log_info "  Virtual env:      $VENV_PATH"

# Set environment variables for the script
export LANCE_DIR="$OUTPUT_DIR/lance_db_lite"
export DUCK_DIR="$OUTPUT_DIR/duck_db"
export IMAGE_DIR="$INPUT_DIR"
export IMAGE_META_DIR="./data"
export GBIF_DIR="./data"
export UMAP_DIR="./data"

# Change to backend directory
cd "$BACKEND_DIR"

# Run the embedding script
if [ "$RUN_BACKGROUND" = "--background" ]; then
    log_info "Running embedding process in background..."
    nohup python scripts/embed_images.py \
        --input-dir "$INPUT_DIR" \
        --output-dir "$OUTPUT_DIR" \
        --log-file "$OUTPUT_DIR/embedding.log" > /dev/null 2>&1 &
    PID=$!
    log_info "Process started with PID: $PID"
    log_info "Monitor progress with: tail -f $OUTPUT_DIR/embedding.log"
else
    log_info "Running embedding process..."
    python scripts/embed_images.py \
        --input-dir "$INPUT_DIR" \
        --output-dir "$OUTPUT_DIR" \
        --log-file "$OUTPUT_DIR/embedding.log"
fi

log_info "Done!"
