from fastapi import APIRouter, Request
router = APIRouter()
@router.get("/health")
async def health(request: Request):
    settings = request.app.state.settings
    models = request.app.state.models
    return {"status": "ok", "app": settings.app_name,
            "model": await models.health(settings.default_model_provider)}
