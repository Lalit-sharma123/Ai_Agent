from fastapi import APIRouter, Request
router = APIRouter(prefix="/api/tasks", tags=["tasks"])
@router.get("/status")
async def task_status(request: Request):
    return {"active": 0, "note": "No background task is running. Agent task execution is introduced in later phases."}
