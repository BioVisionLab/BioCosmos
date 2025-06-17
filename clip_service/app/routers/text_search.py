from fastapi import APIRouter

router = APIRouter()

@router.get("/text-search")
async def text_search():
    return {"message": "Text search endpoint"}


