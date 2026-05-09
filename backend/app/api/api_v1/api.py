from fastapi import APIRouter
from app.api.route import StandardizedResponseRoute
from app.api.api_v1.endpoints import (
    auth, 
    chains, 
    schools, 
    academic, 
    dashboard,
    meta,
    ops,
    students, 
    parents, 
    performance,
    bulk,
    insights,
    notifications,
    reports,
    admin,
    ai_coach,
    user,
)

api_router = APIRouter(route_class=StandardizedResponseRoute)
api_router.include_router(auth.router, prefix="/user/auth", tags=["auth"])
api_router.include_router(user.router, prefix="/user", tags=["user"])
api_router.include_router(chains.router, prefix="/chains", tags=["chains"])
api_router.include_router(schools.router, prefix="/schools", tags=["schools"])
api_router.include_router(academic.router, prefix="/academic", tags=["academic"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(students.router, prefix="/students", tags=["students"])
api_router.include_router(parents.router, prefix="/parents", tags=["parents"])
api_router.include_router(performance.router, prefix="/performance", tags=["performance"])
api_router.include_router(bulk.router, prefix="/bulk", tags=["bulk"])
api_router.include_router(insights.router, prefix="/insights", tags=["ai-insights"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
api_router.include_router(reports.router, prefix="/reports", tags=["report-cards"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(ai_coach.router, prefix="/ai-coach", tags=["ai-coach"])
api_router.include_router(ops.router, prefix="/ops", tags=["ops"])
api_router.include_router(meta.router, prefix="/meta", tags=["meta"])
