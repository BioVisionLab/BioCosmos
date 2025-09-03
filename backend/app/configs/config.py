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
