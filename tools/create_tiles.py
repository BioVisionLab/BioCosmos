import logging
import os
import pickle
import math
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance # Added ImageFilter, ImageEnhance
import numpy as np
from concurrent.futures import ProcessPoolExecutor # For parallel processing
import time # <-- Add import for time module

# --- Configuration ---
INPUT_TSNE_FILE = "./tsne_outputs/unicom_tsne_coords.pkl" # Input file with IDs and coords
INPUT_IMAGE_DIR = "../public/images/nymphalidae_new" # Base directory of original images
OUTPUT_TILE_DIR = "../public/dataset-tiles" # Output directory for tiles (inside Next.js public)
TILE_SIZE = 256 # Pixels (width and height)
IMAGE_SIZE_ON_TILE = 128 # Size of individual images placed onto the tiles (standard res)
MAX_ZOOM = 9 # Max zoom level to generate tiles for
NUM_WORKERS = None # Use all available CPU cores
BACKGROUND_COLOR = (0, 0, 0, 0) # Fully Transparent background

CREATE_HQ_TILES = True # Generate @2x tiles for high-DPI displays
SHADOW_RADIUS = 4      # Gaussian blur radius for shadow (adjust for desired softness)
SHADOW_OPACITY = 0.4   # Shadow darkness (0=invisible, 1=black). Lower values are more subtle.

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Helper Functions ---
def load_data(filepath):
    """Loads data from a pickle file."""
    logger.info(f"Loading data from {filepath}...")
    try:
        with open(filepath, 'rb') as f:
            data = pickle.load(f)
        logger.info(f"Loaded data with keys: {data.keys()}")
        # Basic validation
        if 'ids' not in data or 'coords' not in data or 'metadatas' not in data: # Check for metadatas
             raise ValueError("Pickle file must contain 'ids', 'coords', and 'metadatas' keys.")
        if not (len(data['ids']) == len(data['coords']) == len(data['metadatas'])):
             raise ValueError("Mismatch between number of IDs, coordinates, and metadatas.")
        logger.info(f"Found {len(data['ids'])} data points.")
        return data['ids'], data['coords'], data['metadatas'] # Return metadatas
    except FileNotFoundError:
        logger.error(f"Input file not found: {filepath}")
        return None, None, None # Adjusted return
    except Exception as e:
        logger.error(f"Error loading data: {e}", exc_info=True)
        return None, None, None # Adjusted return

def normalize_coords(coords):
    """Normalizes coordinates to the range [padding, 1 - padding]."""
    logger.info("Normalizing t-SNE coordinates with padding...")
    padding = 0.05 # Add 5% padding on each side
    min_vals = np.min(coords, axis=0)
    max_vals = np.max(coords, axis=0)
    range_vals = max_vals - min_vals
    range_vals[range_vals == 0] = 1 # Avoid division by zero

    # Scale to [0, 1] first
    normalized_zero_one = (coords - min_vals) / range_vals
    # Then scale to [0, 1 - 2*padding] and add padding
    normalized_padded = padding + normalized_zero_one * (1.0 - 2 * padding)

    logger.info(f"Coordinates normalized to range approx [{padding}, {1.0-padding}].")
    return normalized_padded

def process_tile(args):
    """Processes and generates a single tile (standard and @2x)."""
    z, tile_x, tile_y, points_in_tile_indices, normalized_coords, ids, metadatas = args # Add metadatas to args

    tile_path = os.path.join(OUTPUT_TILE_DIR, str(z), str(tile_x), f"{tile_y}.png")
    tile_path_hq = os.path.join(OUTPUT_TILE_DIR, str(z), str(tile_x), f"{tile_y}@2x.png")

    # --- Check if tiles already exist ---
    std_exists = os.path.exists(tile_path)
    hq_exists = not CREATE_HQ_TILES or os.path.exists(tile_path_hq)

    if std_exists and hq_exists:
        return True

    # --- Create blank tiles ---
    tile_image = None if std_exists else Image.new('RGBA', (TILE_SIZE, TILE_SIZE), BACKGROUND_COLOR)
    tile_image_hq = None if hq_exists else Image.new('RGBA', (TILE_SIZE * 2, TILE_SIZE * 2), BACKGROUND_COLOR)

    num_tiles_per_axis = 2**z
    tile_processed_count = 0

    # --- Iterate through points relevant to this tile ---
    for idx in points_in_tile_indices:
        point_id = ids[idx]
        metadata = metadatas[idx] # <-- Get metadata for this point
        px, py = normalized_coords[idx]

        # Calculate base grid position (fractional tile coords)
        grid_x = px * num_tiles_per_axis
        grid_y = py * num_tiles_per_axis

        # Calculate center pixel position *within* the current tile
        center_x = (grid_x - tile_x) * TILE_SIZE
        center_y = (grid_y - tile_y) * TILE_SIZE
        center_x_hq = center_x * 2
        center_y_hq = center_y * 2

        # --- Construct image path using metadata ---
        if 'species_folder' not in metadata or 'image_filename' not in metadata:
             logger.warning(f"Tile {z}/{tile_x}/{tile_y}: Missing metadata keys for ID {point_id}")
             continue
        img_path = os.path.join(INPUT_IMAGE_DIR, metadata['species_folder'], metadata['image_filename'])

        # --- Check if file exists (no longer using debug logs) ---
        if not os.path.exists(img_path):
            # logger.info(f"Tile {z}/{tile_x}/{tile_y}: Correct path ({img_path}) but file DOES NOT EXIST for ID {point_id}") # Keep commented unless needed
            continue

        try:
            with Image.open(img_path) as img_original:
                img_original = img_original.convert("RGBA")

                # --- Prepare High-Res (@2x) ---
                if tile_image_hq is not None:
                    size_hq = IMAGE_SIZE_ON_TILE * 2
                    paste_x_hq = int(center_x_hq - (size_hq / 2))
                    paste_y_hq = int(center_y_hq - (size_hq / 2))

                    image_hq = img_original.copy()
                    image_hq.thumbnail((size_hq, size_hq), Image.Resampling.LANCZOS)
                    actual_size_hq = image_hq.size

                    # Create shadow for HQ
                    shadow_radius_hq = SHADOW_RADIUS * 2
                    shadow_mask_hq = Image.new("L", (actual_size_hq[0] + shadow_radius_hq*2, actual_size_hq[1] + shadow_radius_hq*2), 0)
                    shadow_mask_hq.paste(image_hq.split()[-1], (shadow_radius_hq, shadow_radius_hq)) # Paste alpha channel
                    shadow_mask_hq = shadow_mask_hq.filter(ImageFilter.GaussianBlur(radius=shadow_radius_hq))
                    # Adjust opacity/darkness - Lower enhance value means darker shadow (closer to black)
                    enhancer = ImageEnhance.Brightness(shadow_mask_hq)
                    shadow_mask_hq = enhancer.enhance(1.0 - SHADOW_OPACITY) # Enhance towards black

                    # Paste shadow HQ
                    shadow_paste_x_hq = paste_x_hq - shadow_radius_hq
                    shadow_paste_y_hq = paste_y_hq - shadow_radius_hq
                    # Create a black image for the shadow color
                    shadow_color_img_hq = Image.new("RGBA", shadow_mask_hq.size, (0, 0, 0, 255))
                    tile_image_hq.paste(shadow_color_img_hq, (shadow_paste_x_hq, shadow_paste_y_hq), mask=shadow_mask_hq)

                    # Paste image HQ (use alpha mask)
                    tile_image_hq.paste(image_hq, (paste_x_hq, paste_y_hq), mask=image_hq)

                # --- Prepare Standard Res ---
                if tile_image is not None:
                    size_std = IMAGE_SIZE_ON_TILE
                    paste_x_std = int(center_x - (size_std / 2))
                    paste_y_std = int(center_y - (size_std / 2))

                    image_std = img_original.copy()
                    image_std.thumbnail((size_std, size_std), Image.Resampling.LANCZOS)
                    actual_size_std = image_std.size

                    # Create shadow for standard res
                    shadow_radius_std = SHADOW_RADIUS
                    shadow_mask_std = Image.new("L", (actual_size_std[0] + shadow_radius_std*2, actual_size_std[1] + shadow_radius_std*2), 0)
                    shadow_mask_std.paste(image_std.split()[-1], (shadow_radius_std, shadow_radius_std))
                    shadow_mask_std = shadow_mask_std.filter(ImageFilter.GaussianBlur(radius=shadow_radius_std))
                    enhancer = ImageEnhance.Brightness(shadow_mask_std)
                    shadow_mask_std = enhancer.enhance(1.0 - SHADOW_OPACITY)

                    # Paste shadow standard
                    shadow_paste_x_std = paste_x_std - shadow_radius_std
                    shadow_paste_y_std = paste_y_std - shadow_radius_std
                    shadow_color_img_std = Image.new("RGBA", shadow_mask_std.size, (0, 0, 0, 255))
                    tile_image.paste(shadow_color_img_std, (shadow_paste_x_std, shadow_paste_y_std), mask=shadow_mask_std)

                    # Paste image standard
                    tile_image.paste(image_std, (paste_x_std, paste_y_std), mask=image_std)

                tile_processed_count += 1 # Count successful processing of this image point

        except Exception as e:
            # Log the type of the exception as well
            logger.warning(f"Error processing image {img_path} for tile {z}/{tile_x}/{tile_y}: {type(e).__name__} - {e}")
            continue

    # --- Save the generated tiles ---
    saved_std = False
    saved_hq = False
    # Save standard tile if it was generated and has content
    if tile_image is not None and tile_processed_count > 0:
        try:
            tile_dir = os.path.dirname(tile_path)
            os.makedirs(tile_dir, exist_ok=True)
            tile_image.save(tile_path, 'PNG')
            saved_std = True
        except Exception as e:
            logger.error(f"Error saving standard tile {tile_path}: {e}", exc_info=True)
            # Return False if standard tile saving fails, as HQ depends on it conceptually
            return False

    # Save HQ tile if enabled, generated, and has content
    if CREATE_HQ_TILES and tile_image_hq is not None and tile_processed_count > 0:
        try:
            tile_dir = os.path.dirname(tile_path_hq)
            os.makedirs(tile_dir, exist_ok=True)
            tile_image_hq.save(tile_path_hq, 'PNG')
            saved_hq = True
        except Exception as e:
            logger.error(f"Error saving HQ tile {tile_path_hq}: {e}", exc_info=True)
            # Decide if failure to save HQ should mark the whole task as failed (optional)
            # return False

    # --- Restore Original Success Logic ---
    final_success = (std_exists or saved_std) and (hq_exists or not CREATE_HQ_TILES or saved_hq)
    # logger.info(f"Tile {z}/{tile_x}/{tile_y}: Returning success = {final_success}") # Keep commented
    return final_success

# --- Main Tiling Function --- 
# Reverting to the version that plots points at all zoom levels using overlap margin
def create_tiles():
    logger.info("--- Starting Tile Generation (Plotting Points with Overlap at All Zooms) ---")
    
    # --- Add Input Directory Check ---
    logger.info(f"Checking input image directory: {INPUT_IMAGE_DIR}")
    if not os.path.isdir(INPUT_IMAGE_DIR):
        logger.error(f"Input image directory NOT FOUND: {os.path.abspath(INPUT_IMAGE_DIR)}")
        logger.error("Please ensure INPUT_IMAGE_DIR is set correctly relative to the script's location.")
        return
    try:
        subdirs = [d for d in os.listdir(INPUT_IMAGE_DIR) if os.path.isdir(os.path.join(INPUT_IMAGE_DIR, d))]
        if not subdirs:
            logger.error(f"Input image directory exists but contains NO subdirectories (species folders): {os.path.abspath(INPUT_IMAGE_DIR)}")
            return
        logger.info(f"Input image directory found and contains {len(subdirs)} subdirectories.")
    except Exception as e:
        logger.error(f"Error accessing input image directory contents: {e}")
        return
    # --- End Input Directory Check ---
    
    ids, coords, metadatas = load_data(INPUT_TSNE_FILE)
    if ids is None or coords is None or metadatas is None:
        return

    normalized_coords = normalize_coords(coords) # Normalizes with padding
    num_points = len(ids)
    tasks = []

    # Calculate margin based on image size and shadow radius, normalized relative to a single tile size
    margin_pixels = (IMAGE_SIZE_ON_TILE / 2) + SHADOW_RADIUS
    margin_normalized_tile = margin_pixels / TILE_SIZE

    for z in range(MAX_ZOOM + 1):
        logger.info(f"Processing zoom level {z}...")
        num_tiles_per_axis = 2**z
        total_tiles_at_zoom = 0
        for tx in range(num_tiles_per_axis):
            # Ensure output directory exists for the column
            col_dir_std = os.path.join(OUTPUT_TILE_DIR, str(z), str(tx))
            os.makedirs(col_dir_std, exist_ok=True)
            if CREATE_HQ_TILES:
                col_dir_hq = os.path.join(OUTPUT_TILE_DIR, str(z), str(tx)) # HQ often shares dir
                os.makedirs(col_dir_hq, exist_ok=True)

            for ty in range(num_tiles_per_axis):
                # Calculate the search range in normalized coordinates [0, 1] including the margin
                search_x0 = (tx - margin_normalized_tile) / num_tiles_per_axis
                search_x1 = (tx + 1 + margin_normalized_tile) / num_tiles_per_axis
                search_y0 = (ty - margin_normalized_tile) / num_tiles_per_axis
                search_y1 = (ty + 1 + margin_normalized_tile) / num_tiles_per_axis

                # Use numpy to efficiently find points within the search range
                px = normalized_coords[:, 0]
                py = normalized_coords[:, 1]
                mask = (px >= search_x0) & (px < search_x1) & (py >= search_y0) & (py < search_y1)
                points_in_range_indices = np.where(mask)[0]

                # If any points overlap this tile's extended region, create a task
                if len(points_in_range_indices) > 0:
                    tasks.append((z, tx, ty, points_in_range_indices.tolist(), normalized_coords, ids, metadatas))
                    total_tiles_at_zoom += 1
            
        logger.info(f"Zoom level {z}: Identified {total_tiles_at_zoom} tiles potentially needing generation based on overlap.")

    logger.info(f"Total potential tiles tasks across all zoom levels: {len(tasks)}")
    if not tasks:
        logger.info("No tasks generated. Exiting.")
        return

    logger.info(f"Starting parallel processing with {NUM_WORKERS if NUM_WORKERS else 'all available'} workers...")
    start_time = time.time()
    successful_tiles = 0
    failed_tiles = 0
    
    with ProcessPoolExecutor(max_workers=NUM_WORKERS) as executor:
        # Use the original process_tile function for all tasks
        results = executor.map(process_tile, tasks)
        for i, success in enumerate(results):
            if success:
                successful_tiles += 1
            else:
                failed_tiles += 1
            # Log progress less frequently for potentially larger task lists
            if (i + 1) % 500 == 0: 
                 logger.info(f"Processed {i + 1}/{len(tasks)} tile tasks... (Success: {successful_tiles}, Failed: {failed_tiles})")

    end_time = time.time()
    logger.info(f"Tile processing finished in {end_time - start_time:.2f} seconds.")
    logger.info(f"Completed {successful_tiles} tile tasks successfully (includes checking existing/empty).")
    if failed_tiles > 0:
         logger.warning(f"{failed_tiles} tile tasks failed. Check previous logs.")

    logger.info("--- Tile Generation Complete ---")

# --- Run the Process ---
if __name__ == '__main__':
    create_tiles()
