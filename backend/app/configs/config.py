import torch
import yaml
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

script_dir = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(script_dir, "config.yaml")


def load_config():
    with open(CONFIG_PATH, "r") as config_file:
        config = yaml.safe_load(config_file)
    return config


def get_image_path() -> str:
    config = load_config()
    return config["images"]["dir"]


def get_duck_db_path() -> str:
    config = load_config()
    duck_config = config["db"]["duck"]
    parent_dir = duck_config.get("dir", ".")
    if not os.path.exists(parent_dir):
        os.makedirs(parent_dir)
    return os.path.join(parent_dir, duck_config["file"])


def get_lance_db_path() -> str:
    config = load_config()
    lance_config = config["db"]["lance"]
    parent_dir = lance_config.get("dir", ".")
    if not os.path.exists(parent_dir):
        os.makedirs(parent_dir)
    return os.path.join(parent_dir, lance_config["file"])


class GbifConfig:
    def __init__(self):
        config = load_config()
        self._gbif_config = config.get("gbif", {})

    @property
    def path(self) -> str:
        parent_dir = self._gbif_config.get("dir", ".")
        file_name = self._gbif_config.get(
            "file", "gbif-lepi-2024-occurrence.tsv"
        )
        full_path = os.path.join(parent_dir, file_name)
        if not os.path.exists(full_path):
            logger.info(
                f"Failed to find GBIF data file at: {full_path}"
            )
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

    # Backward compatibility if existing code still calls .path
    @property
    def path(self) -> str:
        return self.url

    @property
    def table(self) -> str:
        return self._leptrait_config.get(
            "table", "lep_traits_consensus"
        )


class ImageConfig:
    def __init__(self):
        config = load_config()
        self._image_config = config.get("images", {})

    @property
    def dir(self) -> str:
        return self._image_config.get("dir", ".")

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

    @property
    def reset(self) -> bool:
        return self._image_config.get("reset", False)


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
                    logger.info(
                        "CUDA not available. Falling back to 'cpu'."
                    )
                    return default
            case "mps":
                if torch.backends.mps.is_available():
                    return "mps"
                else:
                    logger.info(
                        "MPS not available. Falling back to 'cpu'."
                    )
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
            if (
                cuda_device < 0
                or cuda_device >= torch.cuda.device_count()
            ):
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
