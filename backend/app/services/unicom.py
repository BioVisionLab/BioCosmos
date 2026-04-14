import hashlib
import io
import logging
import numpy as np
import timm
import torch
import torch.nn as nn

from torchvision import transforms
from PIL import Image
from pathlib import Path
from PIL.Image import Image as PILImage

from ..configs.config import EmbedderConfig

logger = logging.getLogger(__name__)

UNICOM_MODEL_NAME = "ViT-L/14@336px"
MAX_UNICOM_RESOLUTION = 336
EMBED_DIM = 768
KNOWN_MISSING_KEYS = frozenset(
    {
        "backbone.cls_token",
        "backbone.norm_pre.weight",
        "backbone.norm_pre.bias",
    }
)
KNOWN_UNEXPECTED_KEYS = frozenset(
    {
        "backbone.patch_embed.proj.bias",
    }
)
UNICOM_MODELS = {
    "ViT-L/14@336px": {
        "url": "https://github.com/deepglint/unicom/releases/download/l14_336px/FP16-ViT-L-14-336px.pt",
        "filename": "FP16-ViT-L-14-336px.pt",
        "sha256": "3916ab5aed3b522fc90345be8b4457fe5dad60801ad2af5a6871c0c096e8d7ea",
    }
}


class UnicomViT(nn.Module):
    """ViT-L/14@336px backbone + UNICOM's feature projection head."""

    _PATCH_TOKENS = 576  # 24x24 patches at 336px / 14px patch size
    _BACKBONE_DIM = 1024  # ViT-L hidden dim
    _EMBED_DIM = EMBED_DIM  # UNICOM embedding dimension

    def __init__(self):
        super().__init__()
        self.backbone = timm.create_model(
            "vit_large_patch14_clip_336.openai",
            pretrained=False,
            num_classes=0,
            global_pool="",  # return full sequence [B, 577, 1024]
        )
        self.feature = nn.Sequential(
            nn.Linear(
                self._PATCH_TOKENS * self._BACKBONE_DIM,
                self._BACKBONE_DIM,
                bias=False,
            ),
            nn.BatchNorm1d(self._BACKBONE_DIM),
            nn.Linear(
                self._BACKBONE_DIM, self._EMBED_DIM, bias=False
            ),
            nn.BatchNorm1d(self._EMBED_DIM),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.backbone(x)  # [B, 577, 1024]
        x = x[:, 1:, :]  # [B, 576, 1024] — drop CLS token
        x = x.flatten(1)  # [B, 589824]
        x = self.feature(x)  # [B, 768]
        return x

    @classmethod
    def from_checkpoint(
        cls, model_path: Path, device: str
    ) -> "UnicomViT":
        """Build the model and load weights from a verified checkpoint."""
        model = cls()

        state_dict = torch.load(
            model_path, map_location="cpu", weights_only=True
        )
        state_dict = {k: v.float() for k, v in state_dict.items()}

        # Remap keys: feature.* stays, all others get backbone. prefix
        remapped = {
            k if k.startswith("feature.") else f"backbone.{k}": v
            for k, v in state_dict.items()
        }

        # Fix pos_embed: prepend CLS position [1,576,1024] -> [1,577,1024]
        if "backbone.pos_embed" in remapped:
            cls_pos = model.backbone.pos_embed[:, :1, :]
            remapped["backbone.pos_embed"] = torch.cat(
                [cls_pos, remapped["backbone.pos_embed"]], dim=1
            )

        missing, unexpected = model.load_state_dict(
            remapped, strict=False
        )

        # Warn only on genuinely unexpected mismatches
        unknown_missing = [
            k
            for k in missing
            if k not in KNOWN_MISSING_KEYS
            and not k.endswith("attn.qkv.bias")
        ]
        unknown_extra = [
            k for k in unexpected if k not in KNOWN_UNEXPECTED_KEYS
        ]

        if unknown_missing:
            logger.warning(
                f"Unexpected missing keys: {unknown_missing}"
            )
        if unknown_extra:
            logger.warning(f"Unexpected extra keys: {unknown_extra}")

        logger.debug(
            f"Suppressed {len(missing) - len(unknown_missing)} known missing keys."
        )
        logger.debug(
            f"Suppressed {len(unexpected) - len(unknown_extra)} known unexpected keys."
        )

        return model.to(device).eval()


class UnicomModel:
    def __init__(self, model=None, transform=None):
        self.model = model
        self.transform = transform

    @classmethod
    def load_model(cls):
        """Load the UNICOM model and its transform."""
        try:
            config = EmbedderConfig()
            model_info = UNICOM_MODELS[UNICOM_MODEL_NAME]
            model_path = cls._ensure_model_downloaded(model_info)

            model = UnicomViT.from_checkpoint(model_path, config.device)
            transform = transforms.Compose(
                [
                    transforms.Resize(
                        MAX_UNICOM_RESOLUTION,
                        interpolation=transforms.InterpolationMode.BICUBIC,
                    ),
                    transforms.CenterCrop(MAX_UNICOM_RESOLUTION),
                    transforms.ToTensor(),
                    transforms.Normalize(
                        mean=(0.48145466, 0.4578275, 0.40821073),
                        std=(0.26862954, 0.26130258, 0.27577711),
                    ),
                ]
            )
            logger.info(
                f"UNICOM model and transform loaded and moved to {config.device} successfully"
            )
            return model, transform
        except Exception as e:
            logger.error(
                f"Fatal error loading or moving UNICOM model: {e}",
                exc_info=True,
            )
            raise e

    @staticmethod
    def _ensure_model_downloaded(model_info: dict) -> Path:
        cache_dir = Path.home() / ".cache" / "unicom"
        cache_dir.mkdir(parents=True, exist_ok=True)
        model_path = cache_dir / model_info["filename"]

        if model_path.exists():
            if UnicomModel._verify_sha256(model_path, model_info["sha256"]):
                logger.debug(f"Model cache verified: {model_path}")
                return model_path
            logger.warning("SHA256 mismatch for cached model. Re-downloading.")
            model_path.unlink()

        logger.info(f"Downloading UNICOM model to {model_path}...")
        torch.hub.download_url_to_file(
            model_info["url"],
            dst=str(model_path),
            hash_prefix=model_info["sha256"][:16],
            progress=True,
        )

        if not UnicomModel._verify_sha256(model_path, model_info["sha256"]):
            model_path.unlink()
            raise RuntimeError(
                f"SHA256 verification failed after download: {model_path.name}"
            )

        logger.info(f"Model downloaded and verified: {model_path}")
        return model_path

    @staticmethod
    def _verify_sha256(path: Path, expected: str) -> bool:
        sha256 = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                sha256.update(chunk)
        return sha256.hexdigest() == expected


def get_unicom_ndims() -> int:
    """Get the dimensions of the UNICOM model's image embeddings."""
    # Return the pre-defined EMBED_DIM to avoid loading the model during import
    return EMBED_DIM


class UnicomImageEmbedder:
    def __init__(self, model, transform):
        """Initialize the UNICOM image embedder."""
        config = EmbedderConfig()
        self.device = config.device
        self.logger = logger
        self.model = model
        self.transform = transform

    def get_embedding_from_img(self, image_path):
        """Get the image embedding from a given image path."""
        if self.model is None:
            self.logger.error("UNICOM model not available for image embedding.")
            return None
        try:
            image = Image.open(image_path).convert("RGB")
            image = self._resize_image(image)
            return self.get_embedding(image)
        except Exception as e:
            self.logger.error(
                f"Could not process image {image_path}: {e}",
                exc_info=True,
            )
            return None

    def get_embedding_from_bytes(self, image_bytes: bytes):
        """Get the image embedding from a given base64 image bytes."""
        if self.model is None:
            self.logger.error("UNICOM model not available for image embedding.")
            return None
        try:
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            image = self._resize_image(image)
            return self.get_embedding(image)
        except Exception as e:
            self.logger.error(
                f"Could not process base64 image: {e}",
                exc_info=True,
            )
            return None

    def batch_get_embeddings(
        self, images: list[PILImage]
    ) -> list[np.ndarray]:
        """Get embeddings for a batch of PIL Images."""
        if self.model is None:
            self.logger.error("UNICOM model not available for image embedding.")
            return []
        try:
            images = [self._resize_image(img) for img in images]
            inputs = torch.stack(
                [self.transform(img) for img in images]
            ).to(self.device)
            with torch.no_grad():
                features = self.model(inputs)
            features /= features.norm(dim=-1, keepdim=True)
            return list(features.cpu().numpy())
        except Exception as e:
            self.logger.error(
                f"Error processing batch: {e}", exc_info=True
            )
            return []

    def get_embedding(self, image: PILImage) -> np.ndarray | None:
        """Get the image embedding from a given PIL Image."""
        if self.model is None:
            self.logger.error("UNICOM model not available for image embedding.")
            return None
        try:
            tensor = (
                self.transform(image).unsqueeze(0).to(self.device)
            )
            with torch.no_grad():
                features = self.model(tensor)
            features /= features.norm(dim=-1, keepdim=True)
            return features.cpu().numpy().squeeze()
        except Exception as e:
            self.logger.error(
                f"Could not process image: {e}", exc_info=True
            )
            return None

    def _resize_image(self, image: PILImage) -> PILImage:
        """Resize image to fit within MAX_UNICOM_RESOLUTION while maintaining aspect ratio."""
        max_dimension = max(image.size)
        if max_dimension > MAX_UNICOM_RESOLUTION:
            image.thumbnail(
                (MAX_UNICOM_RESOLUTION, MAX_UNICOM_RESOLUTION),
                Image.LANCZOS,
            )
        return image
