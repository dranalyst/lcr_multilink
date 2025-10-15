from fastapi import APIRouter, Request,Depends, HTTPException, Request, status
from datetime import datetime
import os
import json
from .auth import get_current_user
from models.phoneuser import PhoneUsers
from typing import Annotated

router = APIRouter( prefix="/testCallLogs",
    tags=["testCallLogs"])

UPLOAD_DIR = "upload"  # This is relative to where main.py is located
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/file_upload/", status_code=status.HTTP_200_OK)
async def receive_logs(request: Request,
                       current_user: Annotated[PhoneUsers, Depends(get_current_user)]):
    """
        Secure endpoint to receive uploaded call logs (JSON payload).
        Requires Authorization: Bearer <token> header.
        Saves uploaded logs into the /uploads folder.
        """

    # Parse incoming JSON payload
    logs = await request.json()

    # Format file name with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = f"call_log_{timestamp}.json"
    file_path = os.path.join(UPLOAD_DIR, file_name)

    # Save JSON to file
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False, indent=4)

    print(f"✔️ Call log saved to: {file_path}")
    return {"status": "ok", "file": file_name}


#from fastapi import APIRouter, Request
#from pydantic import BaseModel
#from typing import List
#
#router = APIRouter()
#
#class CallLogEntry(BaseModel):
#    phone_number: str
#    call_time: str
#    duration: str
#    status: str
#
#@router.post("/upload/")
#async def receive_logs(logs: List[CallLogEntry]):
    # Your current code that processes logs
#    print("Received logs:", logs)
#    return {"status": "ok"}


