from lancedb.pydantic import LanceModel, Vector
from lancedb.embeddings import get_registry

DB_DIR = "lance_db"
DB_FILE = "biocosmos.lance"

clip = get_registry().get("open-clip").create()


class DbSchema(LanceModel):
    img_id: str
    species: str
    # img_uri: str = clip.SourceField()
    img_bytes: bytes = clip.SourceField()
    clip_embeddings: Vector(clip.ndims()) = clip.VectorField()
