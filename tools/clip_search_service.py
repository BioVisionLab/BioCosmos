import logging
import os 
from flask import Flask, request, jsonify
import chromadb # Import chromadb
from transformers import CLIPProcessor, CLIPModel # Keep CLIP imports
import torch
import base64
import io
from PIL import Image
import unicom # <-- Import UNICOM

# --- Configuration ---
CHROMA_DB_PATH = "./chroma_db" # Directory to store Chroma data locally
CLIP_COLLECTION_NAME = "biocosmos_images" # Renamed for clarity
CLIP_MODEL_NAME = "openai/clip-vit-base-patch32" # Renamed for clarity
UNICOM_COLLECTION_NAME = "biocosmos_images_unicom" # New collection for UNICOM
UNICOM_MODEL_NAME = "ViT-L/14@336px" # UNICOM model
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
TOP_K = 50 # Number of results to return

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Initialize Flask App ---
app = Flask(__name__)

# --- Load CLIP Model and Processor (for text search) ---
logger.info(f"Loading CLIP model: {CLIP_MODEL_NAME} for text processing...")
try:
    clip_model = CLIPModel.from_pretrained(CLIP_MODEL_NAME).to(DEVICE)
    clip_processor = CLIPProcessor.from_pretrained(CLIP_MODEL_NAME)
    logger.info(f"CLIP model loaded successfully on device: {DEVICE}")
except Exception as e:
    logger.error(f"Error loading CLIP model: {e}", exc_info=True)
    clip_model = None # Indicate failure

# --- Load UNICOM Model and Transform (for image search) ---
logger.info(f"Loading UNICOM model: {UNICOM_MODEL_NAME} for image processing...")
try:
    # Load UNICOM model (likely defaults to CPU) and transform
    _model, unicom_transform = unicom.load(UNICOM_MODEL_NAME) # Load without specifying device initially
    # Explicitly move the entire model to the target device
    unicom_model = _model.to(DEVICE)
    unicom_model.eval() # Set model to evaluation mode
    logger.info(f"UNICOM model and transform loaded and moved to {DEVICE} successfully")
except Exception as e:
    logger.error(f"Error loading or moving UNICOM model: {e}", exc_info=True)
    unicom_model = None # Indicate failure

# Exit if essential models failed to load
if clip_model is None and unicom_model is None:
    logger.error("Both CLIP and UNICOM models failed to load. Exiting.")
    exit(1)
elif clip_model is None:
    logger.warning("CLIP model failed to load. Text search will be unavailable.")
elif unicom_model is None:
     logger.warning("UNICOM model failed to load. Image search will be unavailable.")


# --- Initialize ChromaDB Client ---
logger.info(f"Initializing ChromaDB client with path: {CHROMA_DB_PATH}...")
try:
    # Ensure the directory exists
    if not os.path.exists(CHROMA_DB_PATH):
        os.makedirs(CHROMA_DB_PATH)
        logger.info(f"Created ChromaDB directory: {CHROMA_DB_PATH}")

    # Initialize persistent client
    chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)

    # Get or create the CLIP collection
    # No embedding function needed here if we generate embeddings manually
    clip_collection = chroma_client.get_or_create_collection(name=CLIP_COLLECTION_NAME)
    logger.info(f"Successfully connected to ChromaDB and got collection '{CLIP_COLLECTION_NAME}'.")
    logger.info(f"Collection '{CLIP_COLLECTION_NAME}' currently has {clip_collection.count()} items.")

    # Get or create the UNICOM collection
    unicom_collection = chroma_client.get_or_create_collection(name=UNICOM_COLLECTION_NAME)
    logger.info(f"Successfully connected to ChromaDB and got collection '{UNICOM_COLLECTION_NAME}'.")
    logger.info(f"Collection '{UNICOM_COLLECTION_NAME}' currently has {unicom_collection.count()} items.")


except Exception as e:
    logger.error(f"Error connecting to or getting collection from ChromaDB: {e}", exc_info=True)
    exit(1)

# --- Helper Function for Text Embedding (using CLIP model) ---
def get_text_embedding_clip(text):
    if clip_model is None: # Check if model loaded
         logger.error("CLIP model not available for text embedding.")
         return None
    inputs = clip_processor(text=text, return_tensors="pt", padding=True, truncation=True).to(DEVICE)
    with torch.no_grad():
        text_features = clip_model.get_text_features(**inputs)
    text_features /= text_features.norm(dim=-1, keepdim=True) # Normalize
    return text_features.cpu().numpy().tolist() # Return as list of lists for Chroma

# --- Helper Function for Image Embedding using UNICOM (from base64) ---
def get_image_embedding_unicom(base64_str):
    if unicom_model is None: # Check if UNICOM model loaded
        logger.error("UNICOM model not available for image embedding.")
        return None
    try:
        # Decode base64
        if ',' in base64_str:
            header, encoded = base64_str.split(',', 1)
        else:
            encoded = base64_str 
        image_data = base64.b64decode(encoded)
        image = Image.open(io.BytesIO(image_data)).convert("RGB")
        
        # Apply UNICOM's specific transform and add batch dimension
        image_tensor = unicom_transform(image).unsqueeze(0).to(DEVICE)
        
        # Get embedding from UNICOM model
        with torch.no_grad():
             # Assuming the model's forward pass returns features directly
             # Or if it has an encode_image method: image_features = unicom_model.encode_image(image_tensor)
             image_features = unicom_model(image_tensor) 
             # UNICOM might return features differently, adjust if needed based on library usage
        
        # Normalize (important for cosine similarity)
        image_features /= image_features.norm(dim=-1, keepdim=True) 
        
        return image_features.cpu().numpy().tolist() # Return as list of lists for Chroma
    except Exception as e:
        logger.error(f"Could not process base64 image with UNICOM: {e}", exc_info=True)
        return None

# --- Text Search Endpoint (Uses CLIP) --- 
@app.route('/search', methods=['GET'])
def search_text(): # Renamed function slightly for clarity
    if clip_model is None:
        return jsonify({"error": "Text search (CLIP) is not available."}), 503

    query = request.args.get('q')
    if not query:
        logger.warning("Received request with missing 'q' parameter.")
        return jsonify({"error": "Query parameter 'q' is required"}), 400

    logger.info(f"Received text search query (CLIP): '{query}'")

    try:
        # 1. Get text embedding using CLIP
        logger.info("Generating CLIP text embedding...")
        query_embeddings = get_text_embedding_clip(query)
        if query_embeddings is None: # Handle model load failure
             return jsonify({"error": "Failed to generate text embedding."}), 500
        logger.info("CLIP text embedding generated.")

        # 2. Search CLIP ChromaDB collection
        logger.info(f"Querying ChromaDB CLIP collection '{CLIP_COLLECTION_NAME}'...")
        search_results = clip_collection.query( # Use clip_collection
            query_embeddings=query_embeddings, 
            n_results=TOP_K,
            include=['metadatas', 'distances'] 
        )
        logger.info(f"ChromaDB CLIP query completed.")

        # 3. Process results (same logic as before)
        best_hits_per_species = {}
        if search_results and search_results['ids'] and search_results['ids'][0] and \
           search_results['metadatas'] and search_results['metadatas'][0] and \
           search_results['distances'] and search_results['distances'][0]:
            
            ids = search_results['ids'][0]
            metadatas = search_results['metadatas'][0]
            distances = search_results['distances'][0]

            for i in range(len(ids)):
                metadata = metadatas[i]
                distance = distances[i]
                hit_id = ids[i] 
                
                if metadata and 'species_folder' in metadata and 'image_filename' in metadata:
                    species_folder = metadata['species_folder']
                    image_filename = metadata['image_filename'] 
                    
                    # Keep track of the best hit (lowest distance) for each species_folder
                    if species_folder not in best_hits_per_species or distance < best_hits_per_species[species_folder]['distance']:
                        best_hits_per_species[species_folder] = {
                            'distance': distance,
                            'best_image_filename': image_filename, 
                            'id': hit_id # Include ID if needed elsewhere
                        }
                else:
                    logger.warning(f"CLIP Hit {hit_id} missing 'species_folder' or 'image_filename' in metadata: {metadata}")
        else:
             logger.info("ChromaDB (CLIP) returned no results or results in unexpected format.")


        # 4. Extract results (same logic)
        sorted_species = sorted(best_hits_per_species.items(), key=lambda item: item[1]['distance'])
        unique_results = [
            {
                "species_folder": species_folder,
                "best_image_filename": data['best_image_filename']
            } 
            for species_folder, data in sorted_species
        ]
        logger.info(f"Returning {len(unique_results)} unique species results from CLIP text search.")
        return jsonify(unique_results)

    except Exception as e:
        logger.error(f"Error during CLIP text search for query '{query}': {e}", exc_info=True)
        return jsonify({"error": "An internal error occurred during text search."}), 500


# --- Image Search Endpoint (Uses UNICOM) --- 
@app.route('/search_by_image', methods=['POST'])
def search_by_image():
    if unicom_model is None: # Check if UNICOM model is available
        return jsonify({"error": "Image search (UNICOM) is not available."}), 503

    logger.info("Received image search request (UNICOM).")
    try:
        data = request.get_json()
        if not data or 'image' not in data:
            logger.warning("Image search request missing 'image' field in JSON body.")
            return jsonify({"error": "Missing 'image' field in JSON body"}), 400
        
        base64_image = data['image']

        # 1. Get image embedding from base64 using UNICOM
        logger.info("Generating UNICOM image embedding from base64 data...")
        query_embeddings = get_image_embedding_unicom(base64_image)
        if query_embeddings is None:
             # Error logged in helper function
             return jsonify({"error": "Failed to process uploaded image using UNICOM."}), 400
        logger.info("UNICOM image embedding generated.")

        # 2. Search UNICOM ChromaDB collection
        logger.info(f"Querying ChromaDB UNICOM collection '{UNICOM_COLLECTION_NAME}' with image embedding...")
        search_results = unicom_collection.query( # Use unicom_collection
            query_embeddings=query_embeddings,
            n_results=TOP_K,
            include=['metadatas', 'distances']
        )
        logger.info("ChromaDB UNICOM query completed.")

        # 3. Process results (same logic as text search)
        best_hits_per_species = {}
        if search_results and search_results['ids'] and search_results['ids'][0] and \
           search_results['metadatas'] and search_results['metadatas'][0] and \
           search_results['distances'] and search_results['distances'][0]:
            
            ids = search_results['ids'][0]
            metadatas = search_results['metadatas'][0]
            distances = search_results['distances'][0]

            for i in range(len(ids)):
                metadata = metadatas[i]
                distance = distances[i]
                hit_id = ids[i] 
                if metadata and 'species_folder' in metadata and 'image_filename' in metadata:
                    species_folder = metadata['species_folder']
                    image_filename = metadata['image_filename']
                    # Keep track of the best hit (lowest distance) for each species_folder
                    if species_folder not in best_hits_per_species or distance < best_hits_per_species[species_folder]['distance']:
                        best_hits_per_species[species_folder] = {
                            'distance': distance,
                            'best_image_filename': image_filename,
                            'id': hit_id # Include ID if needed
                        }
                else:
                    logger.warning(f"UNICOM Hit {hit_id} missing 'species_folder' or 'image_filename' in metadata: {metadata}")
        else:
            logger.info("ChromaDB (UNICOM) returned no results or results in unexpected format for image search.")


        # 4. Extract results (same logic as text search)
        sorted_species = sorted(best_hits_per_species.items(), key=lambda item: item[1]['distance'])
        unique_results = [
            {
                "species_folder": species_folder,
                "best_image_filename": data['best_image_filename']
            } 
            for species_folder, data in sorted_species
        ]
        logger.info(f"Returning {len(unique_results)} unique species results from UNICOM image search.")
        return jsonify(unique_results)

    except Exception as e:
        logger.error(f"Error during UNICOM image search: {e}", exc_info=True)
        return jsonify({"error": "An internal error occurred during image search."}), 500

# --- Run Flask App ---
if __name__ == '__main__':
    logger.info("Starting Flask server for CLIP (text) and UNICOM (image) search...")
    app.run(host='0.0.0.0', port=5001, debug=False) # Using same port 5001 