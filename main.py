import os
import base64
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import (
    Mail,
    Attachment,
    FileContent,
    FileName,
    FileType,
    Disposition
)
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from sqlalchemy.orm import Session

from database import SessionLocal, engine
from models import Base, ResumeLog


# -----------------------------
# Load Environment Variables
# -----------------------------
load_dotenv()


# -----------------------------
# Initialize FastAPI
# -----------------------------
app = FastAPI(
    title="Resume Automation API",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)


# -----------------------------
# Enable CORS
# -----------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change in production if needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -----------------------------
# Create Database Tables
# -----------------------------
Base.metadata.create_all(bind=engine)


# -----------------------------
# Rate Limiter
# -----------------------------
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"error": "Too many requests. Please try again later."},
    )


# -----------------------------
# Database Dependency
# -----------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# -----------------------------
# Request Schema
# -----------------------------
class ResumeRequest(BaseModel):
    name: str
    email: EmailStr
    role: str


# -----------------------------
# Root Endpoint
# -----------------------------
@app.api_route("/", methods=["GET", "HEAD"])
def home():
    return {"message": "Resume Automation API is live 🚀"}


# -----------------------------
# Send Resume Endpoint
# -----------------------------
@app.post("/send-resume")
@limiter.limit("5/minute")
async def send_resume(
    request: Request,
    data: ResumeRequest,
    db: Session = Depends(get_db)
):
    try:
        # 1️⃣ Log request to database
        log_entry = ResumeLog(
            name=data.name,
            email=data.email,
            role=data.role
        )
        db.add(log_entry)
        db.commit()

        # 2️⃣ Validate Environment Variables
        sendgrid_key = os.getenv("SENDGRID_API_KEY")
        sender_email = os.getenv("SENDER_EMAIL")

        if not sendgrid_key or not sender_email:
            raise HTTPException(
                status_code=500,
                detail="Email service not configured properly."
            )

        # 3️⃣ Prepare Email
        message = Mail(
            from_email=sender_email,
            to_emails=data.email,
            subject=f"Dillip Panda | Resume for {data.role}",
            html_content=f"""
                <p>Hi {data.name},</p>
                <p>Please find my resume attached for the {data.role} position.</p>
                <p>Best regards,<br>Dillip Panda</p>
            """,
        )

        # 4️⃣ Attach Resume
        resume_path = "resume/Dillip_Panda_Resume.pdf"

        if not os.path.exists(resume_path):
            raise HTTPException(status_code=500, detail="Resume file not found.")

        with open(resume_path, "rb") as f:
            encoded_file = base64.b64encode(f.read()).decode()

        attachment = Attachment(
            FileContent(encoded_file),
            FileName("Dillip_Panda_Resume.pdf"),
            FileType("application/pdf"),
            Disposition("attachment")
        )

        message.attachment = attachment

        # 5️⃣ Send Email
        sg = SendGridAPIClient(sendgrid_key)
        response = sg.send(message)

        if response.status_code != 202:
            raise HTTPException(status_code=500, detail="Email failed to send.")

        return {"status": "Resume sent successfully"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -----------------------------
# Analytics Endpoint
# -----------------------------
@app.get("/resume-analytics")
def get_resume_logs(db: Session = Depends(get_db)):
    logs = db.query(ResumeLog).all()
    return logs

