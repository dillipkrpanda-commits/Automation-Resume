import os
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
    allow_origins=[
        "http://dillipkumarpanda.in",
        "https://dillipkumarpanda.in",
        "http://www.dillipkumarpanda.in",
        "https://www.dillipkumarpanda.in",
        "https://dillipkrpanda-commits.github.io"
    ],
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
class ContactRequest(BaseModel):
    name: str
    email: EmailStr
    message: str


# -----------------------------
# Root Endpoint
# -----------------------------
@app.api_route("/", methods=["GET", "HEAD"])
def home():
    return {"message": "Resume Automation API is live 🚀"}


# -----------------------------
# Send Resume Endpoint
# -----------------------------
@app.post("/contact")
@limiter.limit("5/minute")
async def contact(
    request: Request,
    data: ContactRequest,
    db: Session = Depends(get_db)
):
    try:
        # 1️⃣ Log inquiry to database
        log_entry = ResumeLog(
            name=data.name,
            email=data.email,
            role=data.message  # reuse existing column
        )
        db.add(log_entry)
        db.commit()

        # 2️⃣ Validate environment variables
        sendgrid_key = os.getenv("SENDGRID_API_KEY")
        sender_email = os.getenv("SENDER_EMAIL")

        if not sendgrid_key or not sender_email:
            raise HTTPException(
                status_code=500,
                detail="Email service not configured properly."
            )

        # 3️⃣ Build Email
        message = Mail(
            from_email=("Portfolio Contact", sender_email),
            to_emails="contact@dillipkumarpanda.in",
            subject=f"New Portfolio Inquiry from {data.name}",
            html_content=f"""
            <h3>New Portfolio Inquiry</h3>

            <p><strong>Name:</strong> {data.name}</p>
            <p><strong>Email:</strong> {data.email}</p>
            <p><strong>Message:</strong></p>
            <p>{data.message}</p>

            <hr>
            <p>This message was submitted from your website.</p>
            """,
            plain_text_content=f"""
            New Portfolio Inquiry

            Name: {data.name}
            Email: {data.email}

            Message:
            {data.message}
            """
        )

        # 🔥 Important — allows you to click Reply
        message.reply_to = data.email

        # 4️⃣ Send email
        sg = SendGridAPIClient(sendgrid_key)
        response = sg.send(message)

        if response.status_code != 202:
            raise HTTPException(
                status_code=500,
                detail="Email failed to send."
            )

        return {"status": "Message sent successfully"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# -----------------------------
# Analytics Endpoint
# -----------------------------
@app.get("/resume-analytics")
def get_resume_logs(db: Session = Depends(get_db)):
    logs = db.query(ResumeLog).all()
    return logs






