import logging
import os
import pickle
import json

# --- Configuration ---
INPUT_TSNE_FILE = "./tsne_outputs/unicom_tsne_coords.pkl" # Input file with IDs and coords
OUTPUT_METADATA_DIR = "../public/dataset-metadata" # Output directory for metadata JSON
OUTPUT_METADATA_FILE = os.path.join(OUTPUT_METADATA_DIR, "metadata.json")

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Helper Functions ---
def load_ids(filepath):
    """Loads only the IDs from the t-SNE pickle file."""
    logger.info(f"Loading IDs from {filepath}...")
    try:
        with open(filepath, 'rb') as f:
            data = pickle.load(f)
        if 'ids' not in data:
             raise ValueError("Pickle file must contain an 'ids' key.")
        logger.info(f"Loaded {len(data['ids'])} IDs.")
        return data['ids']
    except FileNotFoundError:
        logger.error(f"Input file not found: {filepath}")
        return None
    except Exception as e:
        logger.error(f"Error loading IDs: {e}", exc_info=True)
        return None

def parse_image_id(image_id):
    """Extracts folder, filename, and derives scientific name from ID."""
    try:
        parts = image_id.split('_', 1)
        if len(parts) != 2:
            logger.warning(f"Unexpected image ID format: {image_id}. Cannot parse.")
            return None, None, None
        folder_name, filename = parts
        
        # Derive scientific name (simple approach: replace _ with space, capitalize first word)
        name_parts = folder_name.split('_')
        if len(name_parts) == 2:
            genus = name_parts[0].capitalize()
            species = name_parts[1].lower()
            scientific_name = f"{genus} {species}"
        else: # Fallback if format is different
            scientific_name = folder_name.replace('_', ' ').capitalize()
            
        return folder_name, filename, scientific_name
    except Exception as e:
        logger.warning(f"Error parsing ID {image_id}: {e}")
        return None, None, None

# --- Main Metadata Generation Function ---
def create_metadata():
    logger.info("--- Starting Metadata JSON Generation ---")
    ids = load_ids(INPUT_TSNE_FILE)
    if ids is None:
        return # Error logged in load_ids
        
    metadata_map = {}
    processed_count = 0
    skipped_count = 0

    logger.info(f"Processing {len(ids)} IDs to generate metadata...")
    
    for image_id in ids:
        folder, filename, sci_name = parse_image_id(image_id)
        if folder and filename and sci_name:
            metadata_map[image_id] = {
                "id": image_id,
                "folder": folder,
                "filename": filename,
                "scientificName": sci_name
                # Add other fields here later if needed (e.g., common name from a lookup)
            }
            processed_count += 1
        else:
            skipped_count += 1
            
        if (processed_count + skipped_count) % 1000 == 0: # Log progress
             logger.info(f"Processed {processed_count + skipped_count}/{len(ids)} IDs...")

    logger.info(f"Finished processing IDs. Generated metadata for {processed_count} items. Skipped {skipped_count} items due to parsing errors.")

    # --- Save Metadata JSON ---
    logger.info(f"Saving metadata map to {OUTPUT_METADATA_FILE}...")
    try:
        # Ensure output directory exists
        os.makedirs(OUTPUT_METADATA_DIR, exist_ok=True)
        logger.info(f"Ensured output directory exists: {OUTPUT_METADATA_DIR}")
            
        with open(OUTPUT_METADATA_FILE, 'w') as f:
            json.dump(metadata_map, f, indent=2) # Use indent for readability
        
        logger.info("Successfully saved metadata JSON file.")

    except Exception as e:
        logger.error(f"Error saving metadata JSON: {e}", exc_info=True)
        return

    logger.info("--- Metadata JSON Generation Complete ---")

# --- Run the Process ---
if __name__ == '__main__':
    create_metadata() 