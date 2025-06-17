from fastapi import APIRouter

router = APIRouter()

@router.get("/image-search")
async def image_search():
    return {"message": "Image search endpoint"}


