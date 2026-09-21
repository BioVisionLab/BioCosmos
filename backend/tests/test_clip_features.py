"""Tests for unwrapping CLIP's projected embeddings.

transformers 5 changed `get_text_features` and `get_image_features` to return
a `BaseModelOutputWithPooling` instead of a tensor. Nothing raised at import
or startup: the normalization downstream failed per query, the caller logged
it, and every visual search quietly came back empty. These pin the shapes so
a future version bump fails here rather than in the UI.
"""

import torch

from app.services.clip import projected_features


class FakePooledOutput:
    """Stands in for BaseModelOutputWithPooling.

    The real class carries the projected embedding in `pooler_output`, which
    the model overwrites with the projection before returning.
    """

    def __init__(self, pooler_output):
        self.pooler_output = pooler_output


class TestProjectedFeatures:
    def test_unwraps_a_pooled_output(self):
        projection = torch.ones(1, 512)
        assert projected_features(FakePooledOutput(projection)) is projection

    def test_passes_a_bare_tensor_through(self):
        """transformers 4.x returned the projection directly."""
        features = torch.ones(2, 512)
        assert projected_features(features) is features

    def test_the_result_can_be_normalized(self):
        """The failure was `'...' object has no attribute 'norm'`."""
        features = projected_features(FakePooledOutput(torch.full((1, 4), 3.0)))
        unit = features / features.norm(dim=-1, keepdim=True)
        assert torch.allclose(unit.norm(dim=-1), torch.ones(1))
