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


def _as_bool(value, label: str, *, default: bool = False) -> bool:
    """Coerce a YAML value that is meant to be a flag.

    YAML gives real booleans for `true`/`false`, but a quoted value, an
    environment-substituted string, or a hand-edited `"yes"` all arrive as
    text. Anything else is a typo: it is logged and treated as the default
    rather than silently taken as truthy.

    This reproduces, exactly, the block copy-pasted into every `skip` property
    below -- including that a string outside the accepted set returns False
    without logging. Keeping it identical is what makes migrating those onto
    this helper a pure deletion later.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ["true", "1", "yes"]
    logger.info(f"{label} is not a valid boolean: {value}. Falling back to {default}.")
    return default


def _env_str(name: str) -> str | None:
    """A string setting from the environment, or None when unset or blank.

    Strips one pair of matching quotes as well as whitespace. `uv run
    --env-file` unquotes `KEY="value"`, but a value exported by the shell or
    another loader can keep them, and a quoted credential is simply wrong:
    NCBI answers 400 to an ``api_key`` sent as ``"abc"``.
    """
    value = (os.getenv(name) or "").strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1].strip()
    return value or None


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
        """The filtered view every reader queries."""
        return self._image_meta_config.get("table", "image_meta")

    @property
    def source_table(self) -> str:
        """The raw ingested table the view is defined over."""
        return self._image_meta_config.get("source_table", "image_meta_source")

    @property
    def input_table(self) -> str:
        """The source minus recorded excluded families; the harmonizer's input."""
        return self._image_meta_config.get("input_table", "image_meta_input")

    @property
    def excluded_table(self) -> str:
        """Images the harmonizer resolved to an excluded family."""
        return self._image_meta_config.get("excluded_table", "image_meta_excluded")

    @property
    def exclude_families(self) -> list[str]:
        """Recorded families left out of the view, lowercased and trimmed."""
        families = self._image_meta_config.get("exclude_families") or []
        if isinstance(families, str):
            families = [families]
        return sorted({str(f).strip().lower() for f in families if str(f).strip()})


class MorphospaceConfig:
    """Tables written offline by `morphospace integrate`; read-only here."""

    def __init__(self):
        config = load_config()
        self._morphospace_config = config.get("morphospace", {})

    def _table(self, name: str) -> str:
        return self._morphospace_config.get(f"{name}_table", f"morphospace_{name}")

    @property
    def scope_table(self) -> str:
        return self._table("scope")

    @property
    def points_table(self) -> str:
        return self._table("points")

    @property
    def species_table(self) -> str:
        return self._table("species")

    @property
    def disparity_table(self) -> str:
        return self._table("disparity")

    @property
    def extremes_table(self) -> str:
        return self._table("extremes")


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


class ColConfig:
    """
    Configuration for the Catalogue of Life (CoL) taxonomy backbone.

    The source is a ColDP release directory pointed at by the COL_DIR
    environment variable. CoL replaces GBIF as the classification source; the
    per-occurrence taxonomic update comes from `colharmonize` run artifacts
    under `reports_dir`.
    """

    def __init__(self):
        config = load_config()
        self._col_config = config.get("col", {})

    @property
    def skip(self) -> bool:
        skip = self._col_config.get("skip", False)
        if isinstance(skip, bool):
            return skip
        if isinstance(skip, str):
            return skip.lower() in ["true", "1", "yes"]
        logger.info(
            f"CoL skip config is not a valid boolean: {skip}. Falling back to False."
        )
        return False

    @property
    def dir(self) -> str:
        """Directory holding the extracted ColDP release."""
        return os.getenv("COL_DIR", ".")

    def _resolve(self, file_name: str) -> str:
        full_path = os.path.join(self.dir, file_name)
        if not os.path.exists(full_path):
            logger.info(f"Failed to find CoL data file at: {full_path}")
        return full_path

    @property
    def path(self) -> str:
        """Path to NameUsage.tsv, the CoL name usage table."""
        return self._resolve(self._col_config.get("file", "NameUsage.tsv"))

    @property
    def vernacular_path(self) -> str:
        """Path to VernacularName.tsv, the CoL common-name table."""
        return self._resolve(
            self._col_config.get("vernacular_file", "VernacularName.tsv")
        )

    @property
    def type_material_path(self) -> str:
        """Path to TypeMaterial.tsv, the CoL type specimen table."""
        return self._resolve(
            self._col_config.get("type_material_file", "TypeMaterial.tsv")
        )

    @property
    def reference_path(self) -> str:
        """Path to Reference.tsv, the CoL bibliography."""
        return self._resolve(self._col_config.get("reference_file", "Reference.tsv"))

    @property
    def table(self) -> str:
        return self._col_config.get("table", "col_taxonomy")

    @property
    def type_material_table(self) -> str:
        return self._col_config.get("type_material_table", "col_type_material")

    @property
    def reference_table(self) -> str:
        return self._col_config.get("reference_table", "col_reference")

    @property
    def vernacular_table(self) -> str:
        return self._col_config.get("vernacular_table", "col_vernacular")

    @property
    def clade_rank(self) -> str | None:
        """Rank column used to restrict the backbone, e.g. 'order'."""
        return self._col_config.get("clade_rank") or None

    @property
    def clade_value(self) -> str | None:
        """Value of `clade_rank` to keep. None ingests all of CoL."""
        return self._col_config.get("clade_value") or None

    @property
    def cache_dir(self) -> str:
        """Directory holding the reusable CoL reference index.

        Relative paths resolve under DUCK_DIR, next to the database, so a
        container keeps the index on the same volume as its data instead of
        rebuilding it from the release on every restart.
        """
        configured = self._col_config.get("cache_dir")
        if not configured:
            # colharmonize's own default, so a developer who has run the CLI
            # does not end up with a second 3.6 GB copy of the same index.
            return os.path.join(os.path.expanduser("~"), ".cache", "colharmonize")
        if os.path.isabs(configured):
            return configured
        return os.path.join(os.getenv("DUCK_DIR", "."), configured)

    @property
    def matches_table(self) -> str:
        return self._col_config.get("matches_table", "col_taxonomy_matches")

    @property
    def variants_table(self) -> str:
        return self._col_config.get("variants_table", "col_taxon_variants")

    @property
    def candidates_table(self) -> str:
        return self._col_config.get("candidates_table", "col_taxonomy_candidates")

    @property
    def occurrence_status_table(self) -> str:
        return self._col_config.get("occurrence_status_table", "image_meta_taxonomy")


class LocalityConfig:
    """
    Configuration for the per-occurrence locality table.

    The source is `gbif_meta`, joined to `image_meta` on uuid = occurrenceID,
    because `image_meta` carries no locality columns of its own.
    `coordinates_table` is produced offline by `geoharmonize integrate`; the
    backend only ever reads it.
    """

    def __init__(self):
        config = load_config()
        self._locality_config = config.get("locality", {})

    @property
    def skip(self) -> bool:
        skip = self._locality_config.get("skip", False)
        if isinstance(skip, bool):
            return skip
        if isinstance(skip, str):
            return skip.lower() in ["true", "1", "yes"]
        logger.info(
            f"Locality skip config is not a valid boolean: {skip}. Falling back to False."
        )
        return False

    @property
    def table(self) -> str:
        return self._locality_config.get("table", "image_meta_locality")

    @property
    def coordinates_table(self) -> str:
        """Table written by `geoharmonize integrate`, absent until it has run."""
        return self._locality_config.get("coordinates_table", "image_meta_coordinates")


class ProvenanceConfig:
    """
    Configuration for the per-occurrence provenance table.

    The source is `gbif_meta`, joined to `image_meta` on uuid = occurrenceID,
    the same join LocalityConfig's table uses -- but for who holds the
    specimen (institutionCode) and how they identify it (catalogNumber)
    rather than where it was found.
    """

    def __init__(self):
        config = load_config()
        self._provenance_config = config.get("provenance", {})

    @property
    def skip(self) -> bool:
        skip = self._provenance_config.get("skip", False)
        if isinstance(skip, bool):
            return skip
        if isinstance(skip, str):
            return skip.lower() in ["true", "1", "yes"]
        logger.info(
            f"Provenance skip config is not a valid boolean: {skip}. Falling back to False."
        )
        return False

    @property
    def table(self) -> str:
        return self._provenance_config.get("table", "image_meta_provenance")


class InstitutionConfig:
    """
    Configuration for the institution directory: code -> name and website.

    Resolved by instharmonize from the public GBIF registries, for the codes
    behind the collection's images.
    """

    def __init__(self):
        config = load_config()
        self._institution_config = config.get("institutions", {}) or {}

    @property
    def skip(self) -> bool:
        return _as_bool(
            self._institution_config.get("skip", False), "Institutions skip config"
        )

    @property
    def table(self) -> str:
        return self._institution_config.get("table", "institution_directory")

    @property
    def overrides_path(self) -> str | None:
        """An extra overrides TOML, resolved relative to config.yaml."""
        path = self._institution_config.get("overrides")
        if not path:
            return None
        return os.path.join(script_dir, os.path.expanduser(path))


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

    @property
    def index_table(self) -> str:
        """The per-occurrence trait table both searches filter on."""
        return self._leptrait_config.get("index_table", "image_meta_traits")


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
        accelerator = (
            torch.accelerator.current_accelerator()
            if torch.accelerator.is_available()
            else None
        )
        default = accelerator.type if accelerator is not None else "cpu"
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
            case _:
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


class SearchIndexConfig:
    """Whether the startup search-index maintenance runs.

    Off by default, which is the opposite polarity to the `skip` flags above.
    Those name an ingestion source and say "do not read it", so their code
    default is False and the shipped YAML turns them on. This one names the
    work itself, so a bare `false` -- or an absent stanza, on a config.yaml
    written before this existed -- means "do not spend the time".

    The index is not required for the site to work: without one, LanceDB
    falls back to a brute-force cosine scan, which is correct but slow.
    Training it is minutes of work that a restart does not invalidate, so
    paying for it on every boot is the wrong default -- this asks to be turned
    on for the boot that needs it.
    """

    def __init__(self):
        config = load_config()
        self._search_index_config = config.get("search_index", {})

    @property
    def build_vector(self) -> bool:
        """Build the LanceDB vector indexes if they are missing."""
        return _as_bool(
            self._search_index_config.get("build_vector", False),
            "search_index.build_vector",
        )


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
        return (os.getenv("LLM_MODEL") or "").strip() or self._openai_config.get(
            "model", "gpt-4"
        )


class CrossrefConfig:
    """Contact details for the CrossRef REST API.

    CrossRef routes requests that identify a contact (``mailto``) to its
    "polite" pool, which has higher limits and more reliable service than the
    anonymous public pool. The address is deployment-specific, so it comes
    from the environment rather than config.yaml.
    """

    @property
    def mailto(self) -> str | None:
        return _env_str("CROSSREF_MAILTO")


class NcbiConfig:
    """Credentials for the NCBI E-utilities and Datasets APIs.

    NCBI asks every E-utilities caller to identify itself with ``tool`` and
    ``email``, and allows 10 requests per second with an API key instead of 3
    without one. Both are deployment-specific, so they come from the
    environment. The contact address falls back to the CrossRef one, since it
    is usually the same maintainer.
    """

    @property
    def api_key(self) -> str | None:
        return _env_str("NCBI_API_KEY")

    @property
    def email(self) -> str | None:
        return _env_str("NCBI_EMAIL") or CrossrefConfig().mailto


class PromptsConfig:
    def __init__(self):
        self._prompt_dir = _PROMPT_DIR

    @property
    def router_agent(self) -> str:
        return self._load_prompt("router_agent.md")

    @property
    def common_name_search(self) -> str:
        return self._resolve_path("common_name_search.md")

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

    def load_tool_description(self, path: str) -> str:
        """Load only the descriptive body of a tool prompt file."""
        return self._parse_front_matter(path)[0]

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
