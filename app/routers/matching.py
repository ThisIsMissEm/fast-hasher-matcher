from fastapi import APIRouter

router = APIRouter()

@router.get("/match", tags=["matching"])
async def match():
    return {"success": "ok"}
