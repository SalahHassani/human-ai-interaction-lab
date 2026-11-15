from fastapi import APIRouter
from app.api.v1 import analytics, auth, experiments, health, participant

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(experiments.router)
api_router.include_router(participant.router)
api_router.include_router(analytics.router)