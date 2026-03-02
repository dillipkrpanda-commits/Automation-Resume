import os
import base64
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
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
from fastapi.responses import JSONResponse

from database import SessionLocal, engine
from models import Base, ResumeLog


# Load environment variables
load_dotenv()

# Initialize FastAPI
app = FastAPI(title="Resume Automation API")

# Create database tables
Base.metadata.create_all(bind=engine)

# Rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"error": "Too many requests. Please try again later."},
    )


# Request schema
class ResumeRequest(BaseModel):
    name: str
    email: str
    role: str


@app.get("/")
def home():
    return {"message": "Resume Automation API is live 🚀"}


@app.post("/send-resume")
@limiter.limit("5/minute")
async def send_resume(request: Request, data: ResumeRequest):

    db = SessionLocal()

    try:
        # 1️⃣ Log request to database
        log_entry = ResumeLog(
            name=data.name,
            email=data.email,
            role=data.role
        )
        db.add(log_entry)
        db.commit()

        # 2️⃣ Prepare Email
        message = Mail(
            from_email=os.getenv("SENDER_EMAIL"),
            to_emails=data.email,
            subject=f"Dillip Panda | Resume for {data.role}",
            html_content=f"""
            <p>Hi {data.name},</p>
            <p>Thank you for your time and consideration for the {data.role} position.</p>
            <p>Please find my resume attached.</p>
            <p>Best regards,<br>Dillip Panda</p>
            """,
            plain_text_content=f"""
            Hi {data.name},
            Please find my resume attached for the {data.role} position.
            Regards,
            Dillip Panda
            """
        )

        # 3️⃣ Attach Resume
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

        # 4️⃣ Send Email
        sg = SendGridAPIClient(os.getenv("SENDGRID_API_KEY"))
        response = sg.send(message)

        if response.status_code != 202:
            raise HTTPException(status_code=500, detail="Email failed to send.")

        return {"status": "Resume sent successfully"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        db.close()


@app.get("/resume-analytics")
def get_resume_logs():
    db = SessionLocal()
    try:
        logs = db.query(ResumeLog).all()
        return logs
    finally:
        db.close()