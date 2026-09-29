"""API routing configuration."""
from fastapi import APIRouter

from app.api.v1 import auth, workflows, resumes, evidence, approvals, versions, consents, process
from app.api.v1 import profiles, analysis, matching, interviews
from app.api.v1 import dashboard, admin, chat, companies
from app.api.v1 import coding

# Initialize the v1 router
api_router = APIRouter()

# Include sub-routers
api_router.include_router(auth.router)
api_router.include_router(process.router)  # DB-free resume processing
api_router.include_router(workflows.router)
api_router.include_router(resumes.router)
api_router.include_router(evidence.router)
api_router.include_router(approvals.router)   # Lab 12: officer approval workflow
api_router.include_router(versions.router)    # Lab 12: versioning & rollback
api_router.include_router(consents.router)    # Lab 12: student consent management

# Lab 13: Domain Specialists
api_router.include_router(profiles.router)
api_router.include_router(analysis.router)
api_router.include_router(matching.router)
api_router.include_router(interviews.router)

# Lab 14: Capstone
api_router.include_router(dashboard.router)
api_router.include_router(admin.router)

# Chatbot Integration
api_router.include_router(chat.router)

# Recruitment Drives & Company Preparedness
api_router.include_router(companies.router)

# Coding Practice
api_router.include_router(coding.router)
