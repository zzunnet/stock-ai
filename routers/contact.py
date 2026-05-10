from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, Field

from services.contacts import create_contact_message

router = APIRouter(prefix="/api/contact", tags=["contact"])


class ContactRequest(BaseModel):
    name: str = Field("", max_length=80)
    email: str = Field(..., max_length=160)
    subject: str = Field("", max_length=120)
    message: str = Field(..., min_length=5, max_length=3000)
    website: str = Field("", max_length=200)


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("CF-Connecting-IP") or request.headers.get("X-Forwarded-For") or ""
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""


@router.post("")
def submit_contact(req: ContactRequest, request: Request):
    if req.website:
        return {"ok": True, "message": "문의가 접수되었습니다."}
    email = req.email.strip().lower()
    if not email or "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(status_code=400, detail="유효한 이메일 주소를 입력해주세요.")
    item = create_contact_message(
        name=req.name.strip(),
        email=email,
        subject=req.subject.strip(),
        message=req.message.strip(),
        ip=_client_ip(request),
        user_agent=request.headers.get("User-Agent", "")[:500],
    )
    return {"ok": True, "id": item["id"], "message": "문의가 접수되었습니다. 확인 후 연락드리겠습니다."}
