# BioCosmos Image Embedding Pipeline

Standalone image embedding processor for BioCosmos butterfly image database. This pipeline processes raw images, generates CLIP and UNICOM embeddings, and creates a searchable vector database (LanceDB).

## Features

- **Batch Processing**: Process multiple images efficiently with configurable batch sizes
- **GPU Acceleration**: Automatic GPU detection (CUDA, MPS, CPU fallback)
- **Embedding Models**: CLIP for text-image similarity, UNICOM for image-image similarity
- **Vector Database**: LanceDB for fast semantic search
- **Image Optimization**: Automatic resizing and format conversion (WebP)
- **Standalone**: Runs independently without full backend environment
- **Background Execution**: Support for long-running background processes

## Quick Start

### 1. Install Dependencies

```bash
# Navigate to embedding folder
cd backend/scripts/embedding

# Install requirements
pip install -r requirements.txt
```

### 2. Process Images

```bash
# Basic usage
./run_embedder.sh /path/to/images /path/to/output

# Run in background
./run_embedder.sh /path/to/images /path/to/output --background

# Monitor background process
tail -f /path/to/output/embedding.log
```

### 3. Use Generated Data

```bash
# Backup existing data
cp -r ../../lance_db_lite ../../lance_db_lite.backup
cp -r ../../static/webp ../../static/webp.backup

# Copy new data
cp -r /path/to/output/lance_db_lite ../../
cp -r /path/to/output/static/webp ../../static/

# Restart backend service
docker-compose restart backend
```

## Usage Examples

### Process a Directory of Images

```bash
./run_embedder.sh ./butterfly_images ./output
```

### Run as Background Job (No TTY Required)

```bash
# Start background process
./run_embedder.sh ./butterfly_images ./output --background

# Check status
tail -f ./output/embedding.log

# Stop if needed (get PID from log, then)
kill <PID>
```

### Integrate Into CI/CD

```bash
# In your CI/CD script
cd backend/scripts/embedding
pip install -r requirements.txt
python embed_images.py \
    --input-dir /path/to/new/images \
    --output-dir /path/to/output \
    --log-file embedding.log
```

### Docker Usage

```bash
# Build image with embedding dependencies
docker build -f Dockerfile.embedder -t biocosmos-embedder .

# Run embedder in container
docker run -v /path/to/images:/input \
           -v /path/to/output:/output \
           biocosmos-embedder \
           python embed_images.py --input-dir /input --output-dir /output
```

## Output Structure

After running the pipeline, you'll have:

```
/path/to/output/
├── lance_db_lite/          # Vector database with embeddings
│   └── nymphalidae_table   # Collection of image embeddings
├── static/
│   └── webp/
│       ├── IMG_001.webp    # Full-resolution image
│       ├── IMG_002.webp
│       └── thumbnails/     # Thumbnails (optional)
│           ├── IMG_001_thumbnail.webp
│           └── IMG_002_thumbnail.webp
└── embedding.log           # Detailed processing log
```

## Configuration

Edit `config.example.yaml` to customize:

```yaml
# Image Processing Settings
images:
  # Maximum resolution in pixels (0 = no resizing)
  max_resolution: 800
  thumbnail_resolution: 128
  format: "webp"  # Options: jpeg, png, webp
  limit: null     # Maximum images to process (null = all)

# Embedding Settings
embedder:
  skip: false
  device: "default"  # Options: default, cpu, cuda, mps
  batch_size: 150    # Adjust based on GPU memory
  reset: true        # Re-embed existing images
```

## Performance Tuning

### Adjust Batch Size

Lower batch size for limited GPU memory, increase for faster processing:

```yaml
embedder:
  batch_size: 32   # For limited GPU (e.g., 4GB)
  batch_size: 150  # For high-end GPU (e.g., 24GB)
```

### GPU Selection

```bash
# Use specific GPU
CUDA_VISIBLE_DEVICES=0 ./run_embedder.sh ./images ./output

# Use MPS (Apple Silicon)
export DEVICE=mps
./run_embedder.sh ./images ./output
```

## Troubleshooting

### Out of Memory Error

- Reduce `batch_size` in config
- Use `--device cpu` to process on CPU
- Process images in smaller batches

### Missing Models

Models are downloaded automatically on first run. Ensure internet connection and sufficient disk space (~10GB for CLIP + UNICOM).

### Slow Processing

- Increase `batch_size` if GPU memory allows
- Use GPU: ensure PyTorch detects CUDA/MPS
- Check system resources: `nvidia-smi` or `top`

### Models Not Detected

Reinstall transformers:

```bash
pip install --upgrade transformers
```

## Integration with Backend

### Incremental Updates

When new images are added:

1. Process new images: `./run_embedder.sh ./new_images ./new_output`
2. Merge with existing database (coming soon)
3. Restart backend

### Monitoring Embeddings

```bash
# View embedding count
python -c "
from backend.database.lance import LanceDB
db = LanceDB()
print(f'Total embeddings: {db.count_entries(\"nymphalidae\")}')
"
```

## API Reference

### embed_images.py

```bash
python embed_images.py \
    --input-dir /path/to/images \
    --output-dir /path/to/output \
    [--log-file embedding.log]
```

**Arguments:**
- `--input-dir`: Directory containing images to process (required)
- `--output-dir`: Output directory for lance_db and static (required)
- `--log-file`: Log file path (default: `embedding.log`)

### run_embedder.sh

```bash
./run_embedder.sh <input_dir> <output_dir> [--background]
```

**Arguments:**
- `input_dir`: Directory with images (required)
- `output_dir`: Output destination (required)
- `--background`: Run as background process (optional)

## Requirements

- Python 3.10+
- 8GB+ RAM (16GB recommended)
- 4GB+ VRAM for GPU acceleration (optional)
- 20GB+ disk space for models and output

## License

Part of BioCosmos project (MIT License)
