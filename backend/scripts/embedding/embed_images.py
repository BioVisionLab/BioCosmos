#!/usr/bin/env python3
"""
Standalone image embedding script for BioCosmos.

This script processes images from a source directory, generates CLIP and UNICOM
embeddings, and creates a LanceDB database with embedded images. The output can
be used to replace existing lance_db and static folders.

Usage:
    python embed_images.py --input-dir /path/to/images --output-dir /path/to/output

    Or with background execution:
    nohup python embed_images.py --input-dir /path/to/images --output-dir /path/to/output > embed.log 2>&1 &
"""

import argparse
import logging
import sys
import os
from pathlib import Path

# Add backend to path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.embedder import ImageEmbedder
from app.services.clip import ClipModel
from app.services.unicom import UnicomModel
from app.database.lance import LanceDB
from app.configs.config import EmbedderConfig, ImageConfig


def setup_logging(log_file: str = "embedding.log"):
    """Configure logging for the script."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout),
        ],
    )


def create_embedder(output_dir: str) -> ImageEmbedder:
    """Initialize the image embedder with models and databases."""
    logger = logging.getLogger(__name__)

    logger.info("Loading CLIP model...")
    clip_model, clip_processor = ClipModel.load_model()
    clip_embedder = ClipModel(model=clip_model, processor=clip_processor)
    logger.info("CLIP model loaded successfully.")

    logger.info("Loading UNICOM model...")
    unicom_model, unicom_transform = UnicomModel.load_model()
    unicom_embedder = UnicomModel(model=unicom_model, transform=unicom_transform)
    logger.info("UNICOM model loaded successfully.")

    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Initialize LanceDB pointing to output directory
    logger.info(f"Initializing LanceDB at {output_dir}...")
    lance_db = LanceDB()
    # Note: LanceDB path is controlled by LANCE_DIR env var, which should be set to output_dir
    logger.info("LanceDB initialized successfully.")

    embedder = ImageEmbedder(
        clip_model=clip_model,
        clip_processor=clip_processor,
        unicom_model=unicom_model,
        unicom_transform=unicom_transform,
        lance_db=lance_db,
    )

    return embedder


def process_images(input_dir: str, output_dir: str):
    """
    Process images from input directory and generate embeddings.

    Args:
        input_dir: Directory containing images to process
        output_dir: Directory where lance_db and static folder will be created
    """
    logger = logging.getLogger(__name__)

    # Validate input directory
    if not os.path.isdir(input_dir):
        logger.error(f"Input directory does not exist: {input_dir}")
        sys.exit(1)

    logger.info(f"Starting image embedding process...")
    logger.info(f"Input directory: {input_dir}")
    logger.info(f"Output directory: {output_dir}")

    try:
        # Create embedder
        embedder = create_embedder(output_dir)

        # Override config to use input images directory
        embedder.config.dir = input_dir
        logger.info(f"Configured to process images from: {input_dir}")

        # Run ingestion
        embedder.ingest()
        logger.info("Image embedding process completed successfully!")

        # Print summary
        processed_dir = embedder.processed_dir
        logger.info(f"✓ Processed images saved to: {processed_dir}")
        logger.info(f"✓ Thumbnails saved to: {embedder.thumbnail_dir}")
        logger.info(f"✓ Vector database created")
        logger.info(f"\nTo use these outputs:")
        logger.info(f"  1. Backup current folders: backend/lance_db_lite, backend/static")
        logger.info(f"  2. Copy new lance_db to: backend/lance_db_lite")
        logger.info(f"  3. Copy new static/webp to: backend/static/webp")
        logger.info(f"  4. Restart the backend service")

        return True

    except Exception as e:
        logger.error(f"Error during image embedding: {e}", exc_info=True)
        sys.exit(1)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="BioCosmos Image Embedding Processor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process images and save to current directory
  python embed_images.py --input-dir /path/to/images --output-dir ./output

  # Run as background job
  nohup python embed_images.py --input-dir /path/to/images --output-dir ./output > embed.log 2>&1 &

  # Monitor background job
  tail -f embed.log
        """,
    )

    parser.add_argument(
        "--input-dir",
        required=True,
        help="Directory containing images to process",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory where output (lance_db, static) will be created",
    )
    parser.add_argument(
        "--log-file",
        default="embedding.log",
        help="Log file path (default: embedding.log)",
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.log_file)
    logger = logging.getLogger(__name__)

    logger.info("=" * 70)
    logger.info("BioCosmos Image Embedding Processor")
    logger.info("=" * 70)

    # Process images
    process_images(args.input_dir, args.output_dir)


if __name__ == "__main__":
    main()
