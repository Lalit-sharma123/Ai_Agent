import shutil
import subprocess
from pathlib import Path
from uuid import uuid4
from urllib.parse import urlparse
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from ..database import DesktopAction, get_db
from ..services.workspace import resolve_workspace_path, WorkspaceError

router=APIRouter(prefix="/api/desktop",tags=["desktop"])

class ProposeAction(BaseModel):
    action_type: str = Field(pattern="^(open_app|open_url|open_file)$")
    target: str = Field(min_length=1,max_length=2000)

class Approval(BaseModel):
    approved: bool

def _out(row: DesktopAction):
    return {"id":row.id,"action_type":row.action_type,"target":row.target,"status":row.status,
            "result":row.result,"created_at":row.created_at.isoformat()}

@router.get("/apps")
def list_apps(request: Request):
    settings=request.app.state.settings
    apps=[x.strip() for x in settings.allowed_desktop_apps.split(",") if x.strip()]
    return {"allowed_apps":[{"name":x,"available":shutil.which(x) is not None} for x in apps],
            "note":"Only explicitly allowlisted apps can be launched."}

@router.post("/actions")
def propose_action(body: ProposeAction, request: Request, db: Session=Depends(get_db)):
    target=body.target.strip()
    if body.action_type=="open_url":
        parsed=urlparse(target)
        if parsed.scheme not in {"http","https"} or not parsed.hostname:
            raise HTTPException(400,"Only complete HTTP/HTTPS URLs can be opened.")
    elif body.action_type=="open_file":
        try: target=str(resolve_workspace_path(target))
        except WorkspaceError as exc: raise HTTPException(403,str(exc)) from exc
        if not Path(target).is_file(): raise HTTPException(404,"File not found inside approved workspace.")
    else:
        allowed={x.strip() for x in request.app.state.settings.allowed_desktop_apps.split(",") if x.strip()}
        if target.casefold() in {"calculator", "calc"}:
            candidates = [x for x in ("gnome-calculator", "kcalc", "galculator", "xcalc") if x in allowed and shutil.which(x)]
            if not candidates: raise HTTPException(404,"No supported calculator app is installed. Install gnome-calculator, kcalc, galculator, or xcalc and add it to ALLOWED_DESKTOP_APPS.")
            target = candidates[0]
        if target not in allowed: raise HTTPException(403,"Application is not allowlisted.")
        if not shutil.which(target): raise HTTPException(404,"Application is not installed or not on PATH.")
    row=DesktopAction(id=str(uuid4()),action_type=body.action_type,target=target,status="pending_approval",result="Approval required before execution.")
    db.add(row);db.commit();db.refresh(row)
    return _out(row)

@router.get("/actions")
def list_actions(db: Session=Depends(get_db)):
    return [_out(x) for x in db.query(DesktopAction).order_by(DesktopAction.created_at.desc()).limit(100).all()]

@router.post("/actions/{action_id}/approve")
def approve_action(action_id: str, body: Approval, request: Request, db: Session=Depends(get_db)):
    row=db.get(DesktopAction,action_id)
    if row is None: raise HTTPException(404,"Action not found.")
    if row.status!="pending_approval": raise HTTPException(409,f"Action is {row.status}.")
    if not body.approved:
        row.status="rejected";row.result="User rejected the action.";db.commit();db.refresh(row);return _out(row)
    try:
        if row.action_type=="open_url":
            # Launch a configured browser only; no shell is used.
            candidates=[x.strip() for x in request.app.state.settings.allowed_desktop_apps.split(",") if x.strip()]
            app=next((x for x in candidates if x in {"firefox","chromium","google-chrome","xdg-open"} and shutil.which(x)),None)
            if not app: raise HTTPException(503,"No approved browser launcher is installed.")
            subprocess.Popen([app,row.target],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
        elif row.action_type=="open_file":
            path=resolve_workspace_path(row.target)
            if not path.is_file(): raise HTTPException(404,"File is no longer available.")
            candidates=[x.strip() for x in request.app.state.settings.allowed_desktop_apps.split(",") if x.strip()]
            app=next((x for x in candidates if x in {"code","xdg-open"} and shutil.which(x)),None)
            if not app: raise HTTPException(503,"No approved file opener is installed.")
            subprocess.Popen([app,str(path)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
        else:
            subprocess.Popen([row.target],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
        row.status="executed";row.result="Launch request submitted to the operating system."
    except HTTPException:
        raise
    except Exception as exc:
        row.status="failed";row.result=str(exc)
    db.commit();db.refresh(row)
    return _out(row)
