from fastapi import FastAPI
from .routers import image_search, text_search


app = FastAPI()

app.include_router(image_search.router)
app.include_router(text_search.router)

@app.get("/")
async def root():
    models.test()
    return {"message": "Welcome to the CLIP Service"}
