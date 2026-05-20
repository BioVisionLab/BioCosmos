import torch
import yaml
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

script_dir = os.path.dirname(os.path.abspath(__file__))
_CONFIG_PATH = os.path.join(script_dir, "config.yaml")

_FRONT_MATTER_DELIMITER = "---"
_PROMPT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts")


def load_config():
    with open(_CONFIG_PATH, "r") as config_file:
        config = yaml.safe_load(config_file)
    return config


def get_image_path() -> str:
    config = load_config()
    return config["images"]["dir"]


def get_duck_db_path() -> str:
    config = load_config()
    duck_config = config["db"]["duck"]
    parent_dir = os.getenv("DUCK_DIR", ".")
    if not os.path.exists(parent_dir):
        os.makedirs(parent_dir)
    return os.path.join(parent_dir, duck_config["file"])


def get_lance_db_path() -> str:
    config = load_config()
    lance_config = config["db"]["lance"]
    parent_dir = os.getenv("LANCE_DIR", ".")
    if not os.path.exists(parent_dir):
        os.makedirs(parent_dir)
    return os.path.join(parent_dir, lance_config["file"])


class ImageMetaConfig:
    """
    Configuration for image metadata CSV file.
    This file includes information such as mask_name, uuid, species, class_dv, etc.
    """

    def __init__(self):
        config = load_config()
        self._image_meta_config = config.get("image_metadata", {})

    @property
    def path(self) -> str:
        parent_dir = os.getenv("IMAGE_META_DIR", ".")
        file_name = self._image_meta_config.get("file", "image_metadata.csv")
        full_path = os.path.join(parent_dir, file_name)
        if not os.path.exists(full_path):
            logger.info(f"Failed to find image metadata file at: {full_path}")
        return full_path

    @property
    def format(self) -> str:
        return self._image_meta_config.get("format", "csv")

    @property
    def skip(self) -> bool:
        skip = self._image_meta_config.get("skip", False)
        if isinstance(skip, bool):
            return skip
        if isinstance(skip, str):
            return skip.lower() in ["true", "1", "yes"]
        logger.info(
            f"Image meta skip config is not a valid boolean: {skip}. Falling back to False."
        )
        return False

    @property
    def table(self) -> str:
        return self._image_meta_config.get("table", "image_meta")


class UmapDataConfig:
    def __init__(self):
        config = load_config()
        self._umap_data_config = config.get("umap_data", {})

    @property
    def path(self) -> str:
        parent_dir = os.getenv("UMAP_DIR", ".")
        file_name = self._umap_data_config.get("file", "umap_embeddings.csv")
        full_path = os.path.join(parent_dir, file_name)
        if not os.path.exists(full_path):
            logger.info(f"Failed to find UMAP data file at: {full_path}")
        return full_path

    @property
    def skip(self) -> bool:
        skip = self._umap_data_config.get("skip", False)
        if isinstance(skip, bool):
            return skip
        if isinstance(skip, str):
            return skip.lower() in ["true", "1", "yes"]
        logger.info(
            f"UMAP skip config is not a valid boolean: {skip}. Falling back to False."
        )
        return False

    @property
    def table(self) -> str:
        return self._umap_data_config.get("table", "umap_embeddings")


class GbifConfig:
    def __init__(self):
        config = load_config()
        self._gbif_config = config.get("gbif", {})

    @property
    def skip(self) -> bool:
        skip = self._gbif_config.get("skip", False)
        if isinstance(skip, bool):
            return skip
        if isinstance(skip, str):
            return skip.lower() in ["true", "1", "yes"]
        logger.info(
            f"GBIF skip config is not a valid boolean: {skip}. Falling back to False."
        )
        return False

    @property
    def path(self) -> str:
        parent_dir = os.getenv("GBIF_DIR", ".")
        file_name = self._gbif_config.get("file", "gbif-lepi-2024-occurrence.tsv")
        full_path = os.path.join(parent_dir, file_name)
        if not os.path.exists(full_path):
            logger.info(f"Failed to find GBIF data file at: {full_path}")
        return full_path

    @property
    def table(self) -> str:
        return self._gbif_config.get("table", "gbif_meta")


class LepTraitConfig:
    def __init__(self):
        config = load_config()
        self._leptrait_config = config.get("leptrait", {})

    @property
    def url(self) -> str:
        default_url = "https://raw.githubusercontent.com/hhandika/LepTraits/refs/heads/main/consensus/consensus.csv"
        url = self._leptrait_config.get("url", default_url)
        if not url.startswith("http"):
            logger.info(f"LepTrait URL does not look remote: {url}")
        return url

    @property
    def skip(self) -> bool:
        skip = self._leptrait_config.get("skip", False)
        if isinstance(skip, bool):
            return skip
        if isinstance(skip, str):
            return skip.lower() in ["true", "1", "yes"]
        logger.info(
            f"LepTrait skip config is not a valid boolean: {skip}. Falling back to False."
        )
        return False

    # Backward compatibility if existing code still calls .path
    @property
    def path(self) -> str:
        return self.url

    @property
    def table(self) -> str:
        return self._leptrait_config.get("table", "lep_traits_consensus")


class ImageConfig:
    """
    Configuration for image ingestion.

    For embedding generation configurations, refer to EmbedderConfig.
    """

    def __init__(self):
        config = load_config()
        self._image_config = config.get("images", {})

    @property
    def dir(self) -> str:
        """
        Directory where images are stored.
        Use the .env IMAGE_DIR to override the default path.
        Default is './images'.
        """
        return os.getenv("IMAGE_DIR", "./images")

    @property
    def format(self) -> str:
        """
        Image file format to use when storing images in the database.
        Options: "jpeg", "png", "webp"
        Default is "webp".
        """
        return self._image_config.get("format", "webp")

    @property
    def max_resolution(self) -> int | None:
        """
        Maximum resolution for images. If set, images will be resized to this resolution.
        """
        max_res = self._image_config.get("max_resolution", None)
        if max_res is not None:
            try:
                max_res = int(max_res)
                if max_res <= 0:
                    logger.info(
                        f"Max resolution must be positive, got: {max_res}. Ignoring limit."
                    )
                    return None
                return max_res
            except ValueError:
                logger.info(
                    f"Max resolution is not a valid integer: {max_res}. Ignoring limit."
                )
                return None
        return None

    @property
    def thumbnail_resolution(self) -> int:
        """Maximum resolution for thumbnails. Default is 128."""
        thumb_res = self._image_config.get("thumbnail_resolution", 128)
        try:
            thumb_res = int(thumb_res)
            if thumb_res <= 0:
                logger.info(
                    f"Thumbnail resolution must be positive, got: {thumb_res}. Using default 128."
                )
                return 128
            return thumb_res
        except (ValueError, TypeError):
            logger.info(
                f"Thumbnail resolution is not a valid integer: {thumb_res}. Using default 128."
            )
            return 128

    @property
    def processed_dir(self) -> str:
        """Directory where processed images and thumbnails are saved."""
        return self._image_config.get("processed_dir", "static/webp")

    @property
    def thumbnail_dir(self) -> str:
        """Directory where thumbnails are saved."""
        return os.path.join(self.processed_dir, "thumbnails")

    @property
    def table(self) -> str:
        return self._image_config.get("table", "nymphalidae")

    @property
    def limit(self) -> int | None:
        limit = self._image_config.get("limit", None)
        if limit is not None:
            try:
                limit = int(limit)
                if limit <= 0:
                    logger.info(
                        f"Image limit must be positive, got: {limit}. Ignoring limit."
                    )
                    return None
                return limit
            except ValueError:
                logger.info(
                    f"Image limit is not a valid integer: {limit}. Ignoring limit."
                )
                return None
        return None


class EmbedderConfig:
    def __init__(self):
        config = load_config()
        self._embedder_config = config.get("embedder", {})

    @property
    def device(self) -> str:
        device = self._embedder_config.get("device", "default")
        valid_devices = ["default", "cpu", "cuda", "mps"]
        default = (
            torch.accelerator.current_accelerator().type
            if torch.accelerator.is_available()
            else "cpu"
        )
        if device not in valid_devices:
            logger.info(
                f"Invalid embedder device '{device}'. Falling back to 'default'."
            )
            return default
        match device:
            case "default":
                return default
            case "cpu":
                return "cpu"
            case "cuda":
                if torch.cuda.is_available():
                    return self._get_cuda_device()
                else:
                    logger.info("CUDA not available. Falling back to 'cpu'.")
                    return default
            case "mps":
                if torch.backends.mps.is_available():
                    return "mps"
                else:
                    logger.info("MPS not available. Falling back to 'cpu'.")
                    return default

    @property
    def batch_size(self) -> int:
        batch_size = self._embedder_config.get("batch_size", 8)
        try:
            batch_size = int(batch_size)
            if batch_size <= 0:
                logger.info(
                    f"Embedder batch size must be positive, got: {batch_size}. Falling back to 8."
                )
                return 8
            return batch_size
        except ValueError:
            logger.info(
                f"Embedder batch size is not a valid integer: {batch_size}. Falling back to 8."
            )
            return 8

    def _get_cuda_device(self) -> str:
        cuda_device = self._embedder_config.get("cuda_device", 0)
        try:
            cuda_device = int(cuda_device)
            if cuda_device < 0 or cuda_device >= torch.cuda.device_count():
                logger.info(
                    f"CUDA device index {cuda_device} is out of range. Falling back to 0."
                )
                return "cuda"
            return f"cuda:{cuda_device}"
        except ValueError:
            logger.info(
                f"CUDA device index is not a valid integer: {cuda_device}. Falling back to 0."
            )
            return "cuda"

    @property
    def reset(self) -> bool:
        reset = self._embedder_config.get("reset", False)
        if isinstance(reset, bool):
            return reset
        if isinstance(reset, str):
            return reset.lower() in ["true", "1", "yes"]
        logger.info(
            f"Embedder reset config is not a valid boolean: {reset}. Falling back to False."
        )
        return False

    @property
    def skip(self) -> bool:
        skip = self._embedder_config.get("skip", False)
        if isinstance(skip, bool):
            return skip
        if isinstance(skip, str):
            return skip.lower() in ["true", "1", "yes"]
        logger.info(
            f"Embedder skip config is not a valid boolean: {skip}. Falling back to False."
        )
        return False


class OpenAIConfig:
    def __init__(self):
        config = load_config()
        self._openai_config = config.get("openai", {})

    @property
    def api_url(self) -> str | None:
        api_url = os.getenv("LLM_API_URL", None)
        if api_url:
            return api_url
        return None

    @property
    def api_key(self) -> str | None:
        api_key = os.getenv("LLM_API_KEY", None)
        if api_key:
            return api_key
        return None

    @property
    def model(self) -> str | None:
        return self._openai_config.get("model", "gpt-4")


class PromptsConfig:
    def __init__(self):
        self._prompt_dir = _PROMPT_DIR

    @property
    def router_agent(self) -> str:
        return self._load_prompt("router_agent.md")

    @property
    def image_similarity(self) -> str:
        return self._resolve_path("image_similarity.md")

    @property
    def location_search(self) -> str:
        return self._resolve_path("location_search.md")

    @property
    def color_search(self) -> str:
        return self._resolve_path("color_search.md")

    @property
    def trait_search(self) -> str:
        return self._resolve_path("trait_search.md")

    def build_tool_definition(self, path: str) -> dict:
        """
        Build a complete OpenAI function-calling tool definition from a
        markdown file with YAML front matter and a description body.
        """
        description, front_matter = self._parse_front_matter(path)
        name = front_matter.get("name")
        if not name:
            raise ValueError(
                f"Tool markdown '{path}' is missing 'name' in front matter."
            )

        return {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": self._build_json_schema(front_matter),
            },
        }

    def _resolve_path(self, filename: str) -> str:
        """
        Resolve a filename to its full path under the prompts directory.
        Raises if the file does not exist.
        """
        prompt_path = os.path.join(self._prompt_dir, filename)
        if not os.path.exists(prompt_path):
            raise FileNotFoundError(f"Prompt file not found: '{prompt_path}'.")
        return prompt_path

    def _load_prompt(self, filename: str) -> str:
        """
        Load a plain system prompt string, with front matter stripped.
        Logs a warning and returns an empty string if the file is missing.
        """
        try:
            path = self._resolve_path(filename)
        except FileNotFoundError as e:
            logger.warning("%s Returning empty string.", e)
            return ""
        return self._parse_front_matter(path)[0]

    def _parse_front_matter(self, path: str) -> tuple[str, dict]:
        """
        Parse a markdown file into (body, front_matter).

        The 'title' key is consumed for debug logging only and never
        forwarded to the LLM.
        """
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read()

        if not raw.startswith(_FRONT_MATTER_DELIMITER):
            return raw.strip(), {}

        parts = raw.split(_FRONT_MATTER_DELIMITER, maxsplit=2)
        if len(parts) < 3:
            return raw.strip(), {}

        front_matter: dict = yaml.safe_load(parts[1]) or {}
        title = front_matter.pop("title", None)

        if title:
            logger.debug("Loaded prompt '%s' from '%s'", title, path)

        return parts[2].strip(), front_matter

    def _build_json_schema(self, front_matter: dict) -> dict:
        """Convert a 'parameters' front-matter block into an OpenAI JSON Schema object."""
        params: dict = front_matter.get("parameters", {})
        properties: dict = {}
        required: list[str] = []

        for name, spec in params.items():
            prop: dict = {"type": spec.get("type", "string")}
            if "description" in spec:
                prop["description"] = spec["description"].strip()
            if "enum" in spec:
                prop["enum"] = spec["enum"]
            if "default" in spec:
                prop["default"] = spec["default"]
            properties[name] = prop
            if spec.get("required", False):
                required.append(name)

        schema: dict = {"type": "object", "properties": properties}
        if required:
            schema["required"] = required
        return schema
