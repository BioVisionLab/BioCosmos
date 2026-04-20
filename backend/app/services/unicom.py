import hashlib
import io
import logging
import numpy as np
import torch
import torch.nn as nn

import torch.nn.functional as F
from torch.nn.init import trunc_normal_
from torchvision import transforms
from PIL import Image
from pathlib import Path
from PIL.Image import Image as PILImage

from ..configs.config import EmbedderConfig

logger = logging.getLogger(__name__)

class DropPath(nn.Module):
    """Drop paths (Stochastic Depth) per sample (when applied in main path of residual blocks)."""
    def __init__(self, drop_prob: float = 0., scale_by_keep: bool = True):
        super(DropPath, self).__init__()
        self.drop_prob = drop_prob
        self.scale_by_keep = scale_by_keep

    def forward(self, x):
        if self.drop_prob == 0. or not self.training:
            return x
        keep_prob = 1 - self.drop_prob
        shape = (x.shape[0],) + (1,) * (x.ndim - 1)
        random_tensor = x.new_empty(shape).bernoulli_(keep_prob)
        if keep_prob > 0.0 and self.scale_by_keep:
            random_tensor.div_(keep_prob)
        return x * random_tensor

class PatchEmbedding(nn.Module):
    def __init__(
        self,
        input_size=224,
        patch_size=32,
        in_channels: int = 3,
        dim: int = 768,
    ):
        super().__init__()
        if isinstance(input_size, int):
            input_size = (input_size, input_size)
        if isinstance(patch_size, int):
            patch_size = (patch_size, patch_size)
        H = input_size[0] // patch_size[0]
        W = input_size[1] // patch_size[1]
        self.num_patches = H * W
        self.proj = nn.Conv2d(
            in_channels,
            dim,
            kernel_size=patch_size,
            stride=patch_size,
        )

    def forward(self, x):
        x = self.proj(x).flatten(2).transpose(1, 2)
        return x


class Mlp(nn.Module):
    def __init__(self, dim, dim_hidden):
        super().__init__()
        self.fc1 = nn.Linear(dim, dim_hidden)
        self.act = nn.ReLU6()
        self.fc2 = nn.Linear(dim_hidden, dim)

    def forward(self, x):
        x = self.fc1(x)
        x = self.act(x)
        x = self.fc2(x)
        return x


class Attention(nn.Module):
    def __init__(self, dim, num_heads):
        super().__init__()
        self.num_heads = num_heads
        head_dim = dim // num_heads
        self.scale = head_dim**-0.5
        self.qkv = nn.Linear(dim, dim * 3, bias=False)
        self.proj = nn.Linear(dim, dim)

    def forward(self, x):
        device_type = x.device.type
        with torch.amp.autocast(
            device_type=device_type, enabled=True
        ):
            B, L, D = x.shape
            qkv = (
                self.qkv(x)
                .reshape(B, L, 3, self.num_heads, D // self.num_heads)
                .permute(2, 0, 3, 1, 4)
            )
            # B, L, 3, heads, head_dim ->
            # 3, B, heads, L, head_dim
            q, k, v = qkv[0], qkv[1], qkv[2]
            # q B, heads, L, head_dim

            attn_output = F.scaled_dot_product_attention(
                q, k, v, None, dropout_p=0.0
            )
            attn_output = (
                attn_output.permute(2, 0, 1, 3).contiguous()
            )  # [seq_length, batch_size, num_heads, head_dim]
            attn_output = attn_output.view(
                L, B, -1
            )  # [seq_length, batch_size, embedding_dim]
            attn_output = attn_output.permute(
                1, 0, 2
            )  # [batch_size, seq_length, embedding_dim]
            x = self.proj(attn_output)

        return x


class Block(nn.Module):
    def __init__(
        self,
        dim: int,
        num_heads: int,
        mlp_ratio: int = 4,
        drop_path: float = 0.0,
        patch_n: int = 32,
        using_checkpoint=False,
    ):
        super().__init__()
        self.using_checkpoint = using_checkpoint
        self.norm1 = nn.LayerNorm(dim)
        self.norm2 = nn.LayerNorm(dim)
        self.attn = Attention(dim, num_heads)
        if drop_path > 0:
            self.drop_path = DropPath(drop_path)
        else:
            self.drop_path = nn.Identity()
        self.mlp = Mlp(dim, dim * mlp_ratio)
        self.extra_gflops = (
            num_heads * patch_n * (dim // num_heads) * patch_n * 2
        ) / (1000**3)

    def forward_impl(self, x):
        device_type = x.device.type
        with torch.amp.autocast(
            device_type=device_type, enabled=True
        ):
            x = x + self.drop_path(self.attn(self.norm1(x)))
            x = x + self.drop_path(self.mlp(self.norm2(x)))
        return x

    def forward(self, x):
        return self.forward_impl(x)


class VisionTransformer(nn.Module):
    def __init__(
        self,
        input_size=224,
        patch_size=32,
        in_channels=3,
        dim=768,
        embedding_size=768,
        depth=12,
        num_heads=12,
        mlp_ratio=4,
        drop_path_rate=0.0,
        using_checkpoint=True,
    ):
        super().__init__()
        self.dim = dim
        self.patch_embed = PatchEmbedding(
            input_size,
            patch_size,
            in_channels,
            dim,
        )
        self.pos_embed = nn.Parameter(
            torch.zeros(1, self.patch_embed.num_patches, dim)
        )
        dpr = [
            x.item() for x in torch.linspace(0, drop_path_rate, depth)
        ]

        self.blocks = nn.ModuleList(
            [
                Block(
                    dim,
                    num_heads,
                    mlp_ratio,
                    dpr[i],
                    self.patch_embed.num_patches,
                    using_checkpoint,
                )
                for i in range(depth)
            ]
        )
        self.norm = nn.LayerNorm(dim)

        self.feature = nn.Sequential(
            nn.Linear(dim * self.patch_embed.num_patches, dim, False),
            nn.BatchNorm1d(dim, eps=2e-5),
            nn.Linear(dim, embedding_size, False),
            nn.BatchNorm1d(embedding_size, eps=2e-5),
        )

        trunc_normal_(self.pos_embed, std=0.02)
        self.apply(self._init_weights)
        self.extra_gflops = 0.0
        for _block in self.blocks:
            self.extra_gflops += _block.extra_gflops

    def _init_weights(self, m):
        if isinstance(m, nn.Linear):
            trunc_normal_(m.weight, std=0.02)
            if isinstance(m, nn.Linear) and m.bias is not None:
                nn.init.constant_(m.bias, 0)
        elif isinstance(m, nn.LayerNorm):
            nn.init.constant_(m.bias, 0)
            nn.init.constant_(m.weight, 1.0)

    def forward_features(self, x):
        B = x.shape[0]
        x = self.patch_embed(x)
        x = x + self.pos_embed
        for func in self.blocks:
            x = func(x)
        x = self.norm(x.float())
        return torch.reshape(
            x, (B, self.patch_embed.num_patches * self.dim)
        )

    def forward(self, x):
        x = self.forward_features(x)
        x = self.feature(x)
        return x


logger = logging.getLogger(__name__)

UNICOM_MODEL_NAME = "ViT-L/14@336px"
EMBED_DIM = 768

UNICOM_MODELS = {
    "ViT-L/14@336px": {
        "url": "https://github.com/deepglint/unicom/releases/download/l14_336px/FP16-ViT-L-14-336px.pt",
        "filename": "FP16-ViT-L-14-336px.pt",
        "sha256": "3916ab5aed3b522fc90345be8b4457fe5dad60801ad2af5a6871c0c096e8d7ea",
    }
}


class UnicomModel:
    def __init__(self, model=None, transform=None):
        self.model = model
        self.transform = transform

    @staticmethod
    def _convert_image_to_rgb(image):
        return image.convert("RGB")

    @classmethod
    def load_model(cls):
        """Load the UNICOM model and its transform."""
        try:
            config = EmbedderConfig()
            model_info = UNICOM_MODELS[UNICOM_MODEL_NAME]
            model_path = cls._ensure_model_downloaded(model_info)

            # 1. Build the exact original architecture inline
            model = VisionTransformer(
                input_size=336,
                patch_size=14,
                in_channels=3,
                dim=1024,
                embedding_size=768,
                depth=24,
                num_heads=16,
                drop_path_rate=0.1,
                using_checkpoint=False,
            )

            # 2. Load the checkpoint safely
            state_dict = torch.load(
                model_path, map_location="cpu", weights_only=True
            )
            
            # 3. Convert FP16 checkpoint weights to FP32
            state_dict_fp32 = {k: v.float() for k, v in state_dict.items()}

            # 4. Load weights directly (no key remapping needed!)
            model.load_state_dict(state_dict_fp32, strict=True)
            model = model.to(config.device).eval()

            # 5. Build the transform explicitly inline
            transform = transforms.Compose([
                transforms.Resize(336, interpolation=transforms.InterpolationMode.BICUBIC),
                transforms.CenterCrop(336),
                cls._convert_image_to_rgb,
                transforms.ToTensor(),
                transforms.Normalize(
                    mean=(0.48145466, 0.4578275, 0.40821073),
                    std=(0.26862954, 0.26130258, 0.27577711),
                ),
            ])

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
