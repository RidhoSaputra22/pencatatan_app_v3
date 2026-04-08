

"""
Visitor Monitoring API - Backend FastAPI
Sesuai dengan Project Concept: monitoring pengunjung perpustakaan dengan YOLOv5
Database: SQLite (tanpa Docker)
"""
from datetime import datetime, date
from typing import List, Optional, Any

from collections import defaultdict

from fastapi import FastAPI, Depends, HTTPException, Query, Form, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from sqlalchemy import or_
from sqlmodel import Session, select

from .settings import settings
from .db import init_db, get_session, engine
from .models import (
    Role, User, Camera, CountingArea,
    Employee, VisitorDaily, VisitEvent, DailyStats
)
from .auth import (
    hash_password, verify_password, create_access_token,
    get_user_by_username, get_role_by_name, require_role
)
from .face_engine import extract_face_embedding, face_engine_status, store_employee_photo
from .stream_relay import (
    start_udp_receiver,
    stop_udp_receiver,
    generate_relay_frames,
    get_relay_state,
)

import os
from pathlib import Path

app = FastAPI(title="Visitor Monitoring API", version="1.0.0")

# Footage storage directory
FOOTAGE_DIR = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / "storage" / "footage"
FOOTAGE_DIR.mkdir(parents=True, exist_ok=True)
EMPLOYEE_FACES_DIR = Path(settings.employee_faces_dir)
EMPLOYEE_FACES_DIR.mkdir(parents=True, exist_ok=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve uploaded footage files as static
app.mount("/storage/footage", StaticFiles(directory=str(FOOTAGE_DIR)), name="footage")
app.mount(
    "/storage/employee_faces",
    StaticFiles(directory=str(EMPLOYEE_FACES_DIR)),
    name="employee_faces",
)

# UDP Stream Relay configuration
UDP_RELAY_HOST = os.getenv("UDP_RELAY_HOST", "0.0.0.0")
UDP_RELAY_PORT = int(os.getenv("UDP_RELAY_PORT", "9999"))
EMPLOYEE_CODE_MAX_LENGTH = 10


# ==================== Pydantic Schemas ====================

class LoginIn(BaseModel):
    username: str
    password: str

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserCreate(BaseModel):
    username: str
    password: str
    full_name: str
    role: str = "OPERATOR"

class UserOut(BaseModel):
    user_id: int
    username: str
    full_name: str
    role: str
    is_active: bool

class CameraCreate(BaseModel):
    name: str
    location: Optional[str] = None
    stream_url: Optional[str] = None

class CameraUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    stream_url: Optional[str] = None
    is_active: Optional[bool] = None

class CameraOut(BaseModel):
    camera_id: int
    name: str
    location: Optional[str] = None
    stream_url: Optional[str] = None
    is_active: bool

class CountingAreaCreate(BaseModel):
    camera_id: int
    name: str
    roi_polygon: Any  # [[x,y], ...]
    direction_mode: str = "BOTH"

class CountingAreaUpdate(BaseModel):
    name: Optional[str] = None
    roi_polygon: Optional[Any] = None
    direction_mode: Optional[str] = None
    is_active: Optional[bool] = None

class CountingAreaOut(BaseModel):
    area_id: int
    camera_id: int
    name: str
    roi_polygon: Any
    direction_mode: str
    is_active: bool


class EmployeeOut(BaseModel):
    employee_id: int
    employee_code: str
    full_name: str
    notes: Optional[str] = None
    is_active: bool
    has_face_embedding: bool
    face_image_path: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class EventIn(BaseModel):
    """Payload dari edge worker saat ada event kunjungan"""
    camera_id: int
    area_id: Optional[int] = None
    event_time: datetime
    track_id: Optional[str] = None
    visitor_key: str
    direction: Optional[str] = None  # IN/OUT
    person_type: str = "CUSTOMER"
    employee_id: Optional[int] = None
    face_match_score: Optional[float] = None
    recognition_source: Optional[str] = None
    confidence_avg: Optional[float] = None

class DailyStatsOut(BaseModel):
    stat_date: date
    camera_id: int
    total_events: int
    unique_visitors: int
    total_in: int
    total_out: int

class DashboardSummary(BaseModel):
    """Summary untuk dashboard"""
    date: date
    total_events: int
    unique_visitors: int
    total_in: int
    total_out: int


def serialize_employee(employee: Employee) -> EmployeeOut:
    return EmployeeOut(
        employee_id=employee.employee_id,
        employee_code=employee.employee_code,
        full_name=employee.full_name,
        notes=employee.notes,
        is_active=employee.is_active,
        has_face_embedding=bool(employee.face_embedding),
        face_image_path=employee.face_image_path,
        created_at=employee.created_at,
        updated_at=employee.updated_at,
    )


# ==================== Startup Event ====================

@app.on_event("startup")
def on_startup():
    """Initialize database, seed data, and start UDP stream receiver"""
    init_db()

    # Start UDP stream receiver for client CCTV streaming
    start_udp_receiver(host=UDP_RELAY_HOST, port=UDP_RELAY_PORT)
    print(f"[backend] UDP stream relay started on {UDP_RELAY_HOST}:{UDP_RELAY_PORT}")
    
    with Session(engine) as session:
        # Create roles if not exist
        admin_role = get_role_by_name(session, "ADMIN")
        if not admin_role:
            admin_role = Role(name="ADMIN")
            session.add(admin_role)
            session.commit()
            session.refresh(admin_role)
        
        operator_role = get_role_by_name(session, "OPERATOR")
        if not operator_role:
            operator_role = Role(name="OPERATOR")
            session.add(operator_role)
            session.commit()
            session.refresh(operator_role)
        
        # Create admin user if not exist
        admin = get_user_by_username(session, settings.admin_username)
        if not admin:
            admin = User(
                username=settings.admin_username,
                password_hash=hash_password(settings.admin_password),
                full_name=settings.admin_fullname,
                role_id=admin_role.role_id,
                is_active=True,
            )
            session.add(admin)
            session.commit()

        # Create default camera if not exist
        cam = session.exec(select(Camera)).first()
        if not cam:
            cam = Camera(
                name=settings.default_camera_name,
                location=settings.default_camera_location,
                stream_url=settings.default_camera_stream,
                is_active=True,
            )
            session.add(cam)
            session.commit()
            session.refresh(cam)
            
            # Create default counting area
            area = CountingArea(
                camera_id=cam.camera_id,
                name=settings.default_area_name,
                roi_polygon=settings.default_area_roi(),
                direction_mode=settings.default_area_direction_mode,
                is_active=True,
            )
            session.add(area)
            session.commit()


# ==================== Health Check ====================

@app.get("/health")
async def health():
    """Health check endpoint"""
    try:
        with Session(engine) as session:
            session.exec(select(User).limit(1))
        
        return {
            "status": "healthy", 
            "timestamp": datetime.utcnow().isoformat(),
            "database": "sqlite"
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail={
            "status": "unhealthy",
            "error": str(e),
        })

# ==================== Stream Relay (Client CCTV → Backend → Edge) ====================

@app.get("/stream/relay")
def stream_relay():
    """
    MJPEG relay endpoint.
    Client mengirim frame CCTV via UDP → backend menerima →
    endpoint ini menyajikan sebagai MJPEG stream untuk edge worker.
    
    Edge worker bisa menggunakan URL ini sebagai EDGE_STREAM_URL:
      EDGE_STREAM_URL=http://localhost:8000/stream/relay
    """
    response = StreamingResponse(
        generate_relay_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    response.headers["X-Accel-Buffering"] = "no"
    return response


@app.get("/stream/relay/health")
def stream_relay_health():
    """Health check untuk stream relay — digunakan frontend untuk cek status."""
    state = get_relay_state()
    return {
        "status": "receiving" if state["has_frame"] else "waiting",
        "udp_port": UDP_RELAY_PORT,
        **state,
    }


# ==================== Auth Endpoints ====================

@app.post("/api/auth/login", response_model=TokenOut)
def login(payload: LoginIn, session: Session = Depends(get_session)):
    user = get_user_by_username(session, payload.username)
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username/password")
    if not user.is_active:
        raise HTTPException(status_code=401, detail="User is inactive")
    return TokenOut(access_token=create_access_token(user.username))

@app.get("/api/me", response_model=UserOut)
def me(user: User = Depends(require_role("ADMIN", "OPERATOR")), session: Session = Depends(get_session)):
    role = session.get(Role, user.role_id)
    return UserOut(
        user_id=user.user_id, 
        username=user.username, 
        full_name=user.full_name,
        role=role.name if role else "UNKNOWN",
        is_active=user.is_active
    )


# ==================== User Management ====================

@app.post("/api/users", response_model=UserOut)
def create_user(payload: UserCreate, session: Session = Depends(get_session), _: User = Depends(require_role("ADMIN"))):
    if get_user_by_username(session, payload.username):
        raise HTTPException(status_code=400, detail="Username already exists")
    
    role = get_role_by_name(session, payload.role.upper())
    if not role:
        raise HTTPException(status_code=400, detail=f"Role '{payload.role}' not found")
    
    u = User(
        username=payload.username, 
        password_hash=hash_password(payload.password), 
        full_name=payload.full_name,
        role_id=role.role_id,
        is_active=True
    )
    session.add(u)
    session.commit()
    session.refresh(u)
    return UserOut(
        user_id=u.user_id, 
        username=u.username, 
        full_name=u.full_name,
        role=role.name,
        is_active=u.is_active
    )

@app.get("/api/users", response_model=List[UserOut])
def list_users(session: Session = Depends(get_session), _: User = Depends(require_role("ADMIN"))):
    users = session.exec(select(User)).all()
    result = []
    for u in users:
        role = session.get(Role, u.role_id)
        result.append(UserOut(
            user_id=u.user_id, 
            username=u.username, 
            full_name=u.full_name,
            role=role.name if role else "UNKNOWN",
            is_active=u.is_active
        ))
    return result

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None

@app.put("/api/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, payload: UserUpdate, session: Session = Depends(get_session), admin: User = Depends(require_role("ADMIN"))):
    """Update user (admin only)"""
    u = session.get(User, user_id)
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    
    if payload.full_name is not None:
        u.full_name = payload.full_name
    if payload.role is not None:
        role = get_role_by_name(session, payload.role.upper())
        if not role:
            raise HTTPException(status_code=400, detail=f"Role '{payload.role}' not found")
        u.role_id = role.role_id
    if payload.password is not None:
        u.password_hash = hash_password(payload.password)
    if payload.is_active is not None:
        u.is_active = payload.is_active
    u.updated_at = datetime.utcnow()
    
    session.add(u)
    session.commit()
    session.refresh(u)
    role = session.get(Role, u.role_id)
    return UserOut(
        user_id=u.user_id,
        username=u.username,
        full_name=u.full_name,
        role=role.name if role else "UNKNOWN",
        is_active=u.is_active
    )

@app.delete("/api/users/{user_id}")
def delete_user(user_id: int, session: Session = Depends(get_session), admin: User = Depends(require_role("ADMIN"))):
    """Deactivate/delete user (admin only). Cannot delete yourself."""
    u = session.get(User, user_id)
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    if u.user_id == admin.user_id:
        raise HTTPException(status_code=400, detail="Tidak bisa menghapus akun sendiri")
    
    u.is_active = False
    u.updated_at = datetime.utcnow()
    session.add(u)
    session.commit()
    return {"ok": True, "message": f"User '{u.username}' dinonaktifkan"}


# ==================== Employee Management ====================

@app.get("/api/employees", response_model=List[EmployeeOut])
def list_employees(
    session: Session = Depends(get_session),
    _: User = Depends(require_role("ADMIN", "OPERATOR")),
):
    employees = session.exec(select(Employee).order_by(Employee.full_name)).all()
    return [serialize_employee(employee) for employee in employees]


@app.get("/api/employees/registry")
def employee_registry(
    session: Session = Depends(get_session),
    _: User = Depends(require_role("ADMIN", "OPERATOR")),
):
    employees = session.exec(select(Employee).where(Employee.is_active == True)).all()
    registry = []
    for employee in employees:
        if not employee.face_embedding:
            continue
        registry.append(
            {
                "employee_id": employee.employee_id,
                "employee_code": employee.employee_code,
                "full_name": employee.full_name,
                "face_embedding": employee.face_embedding,
                "updated_at": employee.updated_at.isoformat(),
            }
        )
    return {"items": registry}


@app.post("/api/employees", response_model=EmployeeOut)
async def create_employee(
    employee_code: str = Form(...),
    full_name: str = Form(...),
    notes: Optional[str] = Form(None),
    photo: UploadFile = File(...),
    session: Session = Depends(get_session),
    _: User = Depends(require_role("ADMIN")),
):
    available, reason = face_engine_status()
    if not available:
        raise HTTPException(status_code=503, detail=f"Face engine belum siap: {reason}")

    employee_code = employee_code.strip()
    full_name = full_name.strip()
    notes = notes.strip() if notes else None
    if not employee_code or not full_name:
        raise HTTPException(status_code=400, detail="Kode pegawai dan nama wajib diisi")
    if len(employee_code) > EMPLOYEE_CODE_MAX_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Kode pegawai maksimal {EMPLOYEE_CODE_MAX_LENGTH} karakter",
        )

    existing = session.exec(
        select(Employee).where(Employee.employee_code == employee_code)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Kode pegawai sudah digunakan")

    photo_bytes = await photo.read()
    try:
        face_data = extract_face_embedding(photo_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    employee = Employee(
        employee_code=employee_code,
        full_name=full_name,
        notes=notes,
        face_embedding=face_data["embedding"],
        is_active=True,
    )
    session.add(employee)
    session.commit()
    session.refresh(employee)

    employee.face_image_path = store_employee_photo(
        employee.employee_id,
        employee.employee_code,
        photo_bytes,
        photo.filename or "",
    )
    employee.updated_at = datetime.utcnow()
    session.add(employee)
    session.commit()
    session.refresh(employee)
    return serialize_employee(employee)


@app.put("/api/employees/{employee_id}", response_model=EmployeeOut)
async def update_employee(
    employee_id: int,
    employee_code: Optional[str] = Form(None),
    full_name: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    is_active: Optional[bool] = Form(None),
    photo: Optional[UploadFile] = File(None),
    session: Session = Depends(get_session),
    _: User = Depends(require_role("ADMIN")),
):
    employee = session.get(Employee, employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Pegawai tidak ditemukan")

    if employee_code is not None:
        employee_code = employee_code.strip()
        if not employee_code:
            raise HTTPException(status_code=400, detail="Kode pegawai tidak boleh kosong")
        if len(employee_code) > EMPLOYEE_CODE_MAX_LENGTH:
            raise HTTPException(
                status_code=400,
                detail=f"Kode pegawai maksimal {EMPLOYEE_CODE_MAX_LENGTH} karakter",
            )
        existing = session.exec(
            select(Employee).where(
                Employee.employee_code == employee_code,
                Employee.employee_id != employee_id,
            )
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Kode pegawai sudah digunakan")
        employee.employee_code = employee_code

    if full_name is not None:
        full_name = full_name.strip()
        if not full_name:
            raise HTTPException(status_code=400, detail="Nama pegawai tidak boleh kosong")
        employee.full_name = full_name

    if notes is not None:
        employee.notes = notes.strip() or None

    if is_active is not None:
        employee.is_active = is_active

    if photo is not None and photo.filename:
        available, reason = face_engine_status()
        if not available:
            raise HTTPException(status_code=503, detail=f"Face engine belum siap: {reason}")

        photo_bytes = await photo.read()
        try:
            face_data = extract_face_embedding(photo_bytes)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

        employee.face_embedding = face_data["embedding"]
        employee.face_image_path = store_employee_photo(
            employee.employee_id,
            employee.employee_code,
            photo_bytes,
            photo.filename or "",
        )

    employee.updated_at = datetime.utcnow()
    session.add(employee)
    session.commit()
    session.refresh(employee)
    return serialize_employee(employee)


@app.delete("/api/employees/{employee_id}")
def delete_employee(
    employee_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(require_role("ADMIN")),
):
    employee = session.get(Employee, employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Pegawai tidak ditemukan")

    employee.is_active = False
    employee.updated_at = datetime.utcnow()
    session.add(employee)
    session.commit()
    return {"ok": True, "message": f"Pegawai '{employee.full_name}' dinonaktifkan"}


# ==================== Camera Management ====================

@app.get("/api/cameras/discover")
def discover_cameras(_: User = Depends(require_role("ADMIN"))):
    """
    Detect available video capture devices on the system (Linux).
    Uses v4l2 to enumerate /dev/video* and opencv to test each one.
    Returns a list of { index, device, name, status }.
    """
    import sys
    import platform
    import glob
    import cv2
    import subprocess

    result = []
    max_test_index = 10  # Scan up to 10 devices for Windows/Mac
    system = platform.system()

    if system == "Linux":
        devices = sorted(glob.glob("/dev/video*"))
        # Try to get device names via v4l2-ctl
        device_names = {}
        try:
            output = subprocess.check_output(
                ["v4l2-ctl", "--list-devices"], stderr=subprocess.STDOUT, text=True
            )
            current_name = None
            for line in output.splitlines():
                if not line.startswith("\t") and line.strip():
                    current_name = line.strip().rstrip(":")
                    if "(" in current_name:
                        current_name = current_name[:current_name.index("(")].strip()
                elif line.strip().startswith("/dev/video") and current_name:
                    device_names[line.strip()] = current_name
        except Exception:
            pass

        seen_indices = set()
        for dev_path in devices:
            try:
                idx = int(dev_path.replace("/dev/video", ""))
            except ValueError:
                continue
            if idx in seen_indices:
                continue
            seen_indices.add(idx)
            name = device_names.get(dev_path, f"Video Device {idx}")
            # Quick test: can opencv open it?
            status = "unknown"
            try:
                cap = cv2.VideoCapture(idx)
                if cap.isOpened():
                    ret, _ = cap.read()
                    status = "available" if ret else "no-frame"
                    cap.release()
                else:
                    status = "unavailable"
            except Exception:
                status = "error"
            result.append({
                "index": idx,
                "device": dev_path,
                "name": name,
                "status": status,
            })
    else:
        # Windows/Mac: try index 0..max_test_index
        for idx in range(max_test_index):
            # Device string for info only
            if system == "Windows":
                dev_path = f"DirectShow:{idx}"
            elif system == "Darwin":
                dev_path = f"AVFoundation:{idx}"
            else:
                dev_path = f"Device:{idx}"
            name = f"Video Device {idx}"
            status = "unknown"
            try:
                cap = cv2.VideoCapture(idx)
                if cap.isOpened():
                    ret, _ = cap.read()
                    status = "available" if ret else "no-frame"
                    cap.release()
                else:
                    status = "unavailable"
            except Exception:
                status = "error"
            result.append({
                "index": idx,
                "device": dev_path,
                "name": name,
                "status": status,
            })
    return result


@app.get("/api/cameras", response_model=List[CameraOut])
def list_cameras(session: Session = Depends(get_session), _: User = Depends(require_role("ADMIN", "OPERATOR"))):
    cameras = session.exec(select(Camera)).all()
    return [CameraOut(
        camera_id=c.camera_id, 
        name=c.name, 
        location=c.location,
        stream_url=c.stream_url, 
        is_active=c.is_active
    ) for c in cameras]

@app.get("/api/cameras/{camera_id}", response_model=CameraOut)
def get_camera(camera_id: int, session: Session = Depends(get_session), _: User = Depends(require_role("ADMIN", "OPERATOR"))):
    cam = session.get(Camera, camera_id)
    if not cam:
        raise HTTPException(status_code=404, detail="Camera not found")
    return CameraOut(
        camera_id=cam.camera_id, 
        name=cam.name, 
        location=cam.location,
        stream_url=cam.stream_url, 
        is_active=cam.is_active
    )

@app.post("/api/cameras", response_model=CameraOut)
def create_camera(payload: CameraCreate, session: Session = Depends(get_session), _: User = Depends(require_role("ADMIN"))):
    cam = Camera(
        name=payload.name,
        location=payload.location,
        stream_url=payload.stream_url,
        is_active=True
    )
    session.add(cam)
    session.commit()
    session.refresh(cam)
    return CameraOut(
        camera_id=cam.camera_id, 
        name=cam.name, 
        location=cam.location,
        stream_url=cam.stream_url, 
        is_active=cam.is_active
    )

@app.put("/api/cameras/{camera_id}", response_model=CameraOut)
def update_camera(camera_id: int, payload: CameraUpdate, session: Session = Depends(get_session), _: User = Depends(require_role("ADMIN"))):
    cam = session.get(Camera, camera_id)
    if not cam:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(cam, k, v)
    session.add(cam)
    session.commit()
    session.refresh(cam)
    return CameraOut(
        camera_id=cam.camera_id, 
        name=cam.name, 
        location=cam.location,
        stream_url=cam.stream_url, 
        is_active=cam.is_active
    )

@app.delete("/api/cameras/{camera_id}")
def delete_camera(camera_id: int, session: Session = Depends(get_session), _: User = Depends(require_role("ADMIN"))):
    """Delete camera and its counting areas (admin only)"""
    cam = session.get(Camera, camera_id)
    if not cam:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    # Delete associated counting areas first
    areas = session.exec(select(CountingArea).where(CountingArea.camera_id == camera_id)).all()
    for area in areas:
        session.delete(area)
    
    session.delete(cam)
    session.commit()
    return {"ok": True, "message": f"Camera '{cam.name}' deleted"}


# ==================== Counting Area Management ====================

@app.get("/api/cameras/{camera_id}/areas", response_model=List[CountingAreaOut])
def list_counting_areas(camera_id: int, session: Session = Depends(get_session), _: User = Depends(require_role("ADMIN", "OPERATOR"))):
    areas = session.exec(select(CountingArea).where(CountingArea.camera_id == camera_id)).all()
    return [CountingAreaOut(
        area_id=a.area_id,
        camera_id=a.camera_id,
        name=a.name,
        roi_polygon=a.roi_polygon,
        direction_mode=a.direction_mode,
        is_active=a.is_active
    ) for a in areas]

@app.post("/api/areas", response_model=CountingAreaOut)
def create_counting_area(payload: CountingAreaCreate, session: Session = Depends(get_session), _: User = Depends(require_role("ADMIN"))):
    cam = session.get(Camera, payload.camera_id)
    if not cam:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    area = CountingArea(
        camera_id=payload.camera_id,
        name=payload.name,
        roi_polygon=payload.roi_polygon,
        direction_mode=payload.direction_mode,
        is_active=True
    )
    session.add(area)
    session.commit()
    session.refresh(area)
    return CountingAreaOut(
        area_id=area.area_id,
        camera_id=area.camera_id,
        name=area.name,
        roi_polygon=area.roi_polygon,
        direction_mode=area.direction_mode,
        is_active=area.is_active
    )

@app.put("/api/areas/{area_id}", response_model=CountingAreaOut)
def update_counting_area(area_id: int, payload: CountingAreaUpdate, session: Session = Depends(get_session), _: User = Depends(require_role("ADMIN"))):
    area = session.get(CountingArea, area_id)
    if not area:
        raise HTTPException(status_code=404, detail="Counting area not found")
    
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(area, k, v)
    session.add(area)
    session.commit()
    session.refresh(area)
    return CountingAreaOut(
        area_id=area.area_id,
        camera_id=area.camera_id,
        name=area.name,
        roi_polygon=area.roi_polygon,
        direction_mode=area.direction_mode,
        is_active=area.is_active
    )

@app.delete("/api/areas/{area_id}")
def delete_counting_area(area_id: int, session: Session = Depends(get_session), _: User = Depends(require_role("ADMIN"))):
    """Delete counting area (admin only)"""
    area = session.get(CountingArea, area_id)
    if not area:
        raise HTTPException(status_code=404, detail="Counting area not found")
    
    session.delete(area)
    session.commit()
    return {"ok": True, "message": f"Counting area '{area.name}' deleted"}


# ==================== Event Ingestion (dari Edge) ====================

@app.post("/api/events/ingest")
def ingest_event(payload: EventIn, session: Session = Depends(get_session)):
    """
    Endpoint untuk menerima event kunjungan dari edge worker.
    Logika pengunjung unik harian:
    - Cek apakah (visit_date, visitor_key) sudah ada di visitor_daily
    - Jika belum ada → insert visitor_daily (unik bertambah)
    - Jika sudah ada → update last_seen_at saja (unik tidak bertambah)
    """
    # Get default area if not specified
    area_id = payload.area_id
    if not area_id:
        area = session.exec(
            select(CountingArea).where(CountingArea.camera_id == payload.camera_id, CountingArea.is_active == True)
        ).first()
        area_id = area.area_id if area else 1

    person_type = (payload.person_type or "CUSTOMER").upper()
    if person_type not in {"CUSTOMER", "EMPLOYEE"}:
        person_type = "CUSTOMER"
    
    # Create visit event
    ev = VisitEvent(
        camera_id=payload.camera_id,
        area_id=area_id,
        event_time=payload.event_time,
        track_id=payload.track_id,
        visitor_key=payload.visitor_key,
        direction=payload.direction,
        person_type=person_type,
        employee_id=payload.employee_id,
        face_match_score=payload.face_match_score,
        recognition_source=payload.recognition_source,
        confidence_avg=payload.confidence_avg
    )
    session.add(ev)

    if person_type == "EMPLOYEE":
        session.commit()
        return {
            "ok": True,
            "is_new_unique": False,
            "ignored_employee": True,
        }

    # Handle unique daily visitor
    visit_date = payload.event_time.date()
    is_new_unique = False
    
    visitor_daily = session.exec(
        select(VisitorDaily).where(
            VisitorDaily.visit_date == visit_date,
            VisitorDaily.visitor_key == payload.visitor_key
        )
    ).first()
    
    if not visitor_daily:
        # New unique visitor for today
        visitor_daily = VisitorDaily(
            visit_date=visit_date,
            visitor_key=payload.visitor_key,
            first_seen_at=payload.event_time,
            last_seen_at=payload.event_time
        )
        session.add(visitor_daily)
        is_new_unique = True
    else:
        # Update last seen time
        visitor_daily.last_seen_at = payload.event_time

    # Update daily stats
    stats = session.exec(
        select(DailyStats).where(
            DailyStats.stat_date == visit_date,
            DailyStats.camera_id == payload.camera_id
        )
    ).first()
    
    if not stats:
        stats = DailyStats(
            stat_date=visit_date,
            camera_id=payload.camera_id,
            total_events=0,
            unique_visitors=0,
            total_in=0,
            total_out=0
        )
        session.add(stats)
    
    stats.total_events += 1
    if is_new_unique:
        stats.unique_visitors += 1
    if payload.direction == "IN":
        stats.total_in += 1
    elif payload.direction == "OUT":
        stats.total_out += 1
    stats.last_updated_at = datetime.utcnow()

    session.commit()
    return {"ok": True, "is_new_unique": is_new_unique}


# ==================== Statistics Endpoints ====================

@app.get("/api/stats/daily", response_model=List[DailyStatsOut])
def stats_daily(
    day: Optional[date] = None, 
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    camera_id: Optional[int] = None,
    session: Session = Depends(get_session), 
    _: User = Depends(require_role("ADMIN", "OPERATOR"))
):
    """Get daily statistics with optional filters"""
    q = select(DailyStats)
    
    if day:
        q = q.where(DailyStats.stat_date == day)
    if from_date:
        q = q.where(DailyStats.stat_date >= from_date)
    if to_date:
        q = q.where(DailyStats.stat_date <= to_date)
    if camera_id:
        q = q.where(DailyStats.camera_id == camera_id)
    
    rows = session.exec(q.order_by(DailyStats.stat_date.desc())).all()
    return [DailyStatsOut(
        stat_date=r.stat_date, 
        camera_id=r.camera_id, 
        total_events=r.total_events,
        unique_visitors=r.unique_visitors,
        total_in=r.total_in, 
        total_out=r.total_out
    ) for r in rows]

@app.get("/api/stats/summary", response_model=DashboardSummary)
def stats_summary(
    day: Optional[date] = None,
    session: Session = Depends(get_session), 
    _: User = Depends(require_role("ADMIN", "OPERATOR"))
):
    """Get summary for dashboard (aggregated across all cameras)"""
    target_date = day or date.today()
    
    stats = session.exec(
        select(DailyStats).where(DailyStats.stat_date == target_date)
    ).all()
    
    total_events = sum(s.total_events for s in stats)
    unique_visitors = sum(s.unique_visitors for s in stats)
    total_in = sum(s.total_in for s in stats)
    total_out = sum(s.total_out for s in stats)
    
    return DashboardSummary(
        date=target_date,
        total_events=total_events,
        unique_visitors=unique_visitors,
        total_in=total_in,
        total_out=total_out
    )


# ==================== Reports ====================

@app.get("/api/reports/csv")
def report_csv(
    from_day: date, 
    to_day: date, 
    camera_id: Optional[int] = None,
    session: Session = Depends(get_session), 
    _: User = Depends(require_role("ADMIN", "OPERATOR"))
):
    """Export daily statistics to CSV as downloadable file"""
    import io, csv
    
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["Tanggal", "Camera ID", "Total Event", "Pengunjung Unik", "Masuk", "Keluar"])
    
    q = select(DailyStats).where(
        DailyStats.stat_date >= from_day, 
        DailyStats.stat_date <= to_day
    )
    if camera_id:
        q = q.where(DailyStats.camera_id == camera_id)
    
    rows = session.exec(q.order_by(DailyStats.stat_date)).all()
    for r in rows:
        writer.writerow([
            r.stat_date.isoformat(), 
            r.camera_id, 
            r.total_events,
            r.unique_visitors, 
            r.total_in, 
            r.total_out
        ])
    
    out.seek(0)
    filename = f"laporan_pengunjung_{from_day}_{to_day}.csv"
    
    return StreamingResponse(
        iter([out.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.get("/api/reports/events")
def report_events(
    from_date: date,
    to_date: date,
    camera_id: Optional[int] = None,
    limit: int = 1000,
    session: Session = Depends(get_session),
    _: User = Depends(require_role("ADMIN", "OPERATOR"))
):
    """Get detailed visit events for reporting"""
    from datetime import datetime as dt
    
    q = select(VisitEvent).where(
        VisitEvent.event_time >= dt.combine(from_date, dt.min.time()),
        VisitEvent.event_time <= dt.combine(to_date, dt.max.time())
    )
    if camera_id:
        q = q.where(VisitEvent.camera_id == camera_id)
    
    events = session.exec(q.order_by(VisitEvent.event_time.desc()).limit(limit)).all()
    employee_ids = sorted({event.employee_id for event in events if event.employee_id})
    employee_names = {}
    if employee_ids:
        employees = session.exec(
            select(Employee).where(Employee.employee_id.in_(employee_ids))
        ).all()
        employee_names = {employee.employee_id: employee.full_name for employee in employees}
    
    return [{
        "event_id": e.event_id,
        "camera_id": e.camera_id,
        "area_id": e.area_id,
        "event_time": e.event_time.isoformat(),
        "track_id": e.track_id,
        "visitor_key": e.visitor_key,
        "direction": e.direction,
        "person_type": e.person_type,
        "employee_id": e.employee_id,
        "employee_name": employee_names.get(e.employee_id),
        "face_match_score": e.face_match_score,
        "recognition_source": e.recognition_source,
        "confidence_avg": e.confidence_avg
    } for e in events]


@app.delete("/api/events/{event_id}")
def delete_event(event_id: int, session: Session = Depends(get_session), _: User = Depends(require_role("ADMIN"))):
    """Delete a specific visit event (admin only)"""
    ev = session.get(VisitEvent, event_id)
    if not ev:
        raise HTTPException(status_code=404, detail="Event not found")
    session.delete(ev)
    session.commit()
    return {"ok": True, "message": "Event deleted"}

@app.get("/api/visitors/daily")
def list_visitor_daily(
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    limit: int = 500,
    session: Session = Depends(get_session),
    _: User = Depends(require_role("ADMIN", "OPERATOR"))
):
    """List unique daily visitors"""
    from datetime import datetime as dt
    
    q = select(VisitorDaily)
    if from_date:
        q = q.where(VisitorDaily.visit_date >= from_date)
    if to_date:
        q = q.where(VisitorDaily.visit_date <= to_date)
    
    visitors = session.exec(q.order_by(VisitorDaily.visit_date.desc()).limit(limit)).all()
    
    return [{
        "visitor_daily_id": v.visitor_daily_id,
        "visit_date": v.visit_date.isoformat(),
        "visitor_key": v.visitor_key,
        "first_seen_at": v.first_seen_at.isoformat(),
        "last_seen_at": v.last_seen_at.isoformat(),
        "notes": v.notes
    } for v in visitors]

@app.get("/api/cameras/list/all", response_model=List[CameraOut])
def list_all_cameras(session: Session = Depends(get_session), _: User = Depends(require_role("ADMIN", "OPERATOR"))):
    """List all cameras (including inactive) for admin management"""
    cameras = session.exec(select(Camera)).all()
    return [CameraOut(
        camera_id=c.camera_id, 
        name=c.name, 
        location=c.location,
        stream_url=c.stream_url, 
        is_active=c.is_active
    ) for c in cameras]


@app.post("/api/admin/reset-db")
def reset_database(
    session: Session = Depends(get_session),
    user: User = Depends(require_role("ADMIN"))
):
    """
    Reset semua data pengunjung (visitor_daily, visit_events, daily_stats)
    Hanya bisa diakses oleh ADMIN
    """
    try:
        # Delete all visitor data
        session.exec(select(VisitEvent)).all()
        for event in session.exec(select(VisitEvent)).all():
            session.delete(event)
        
        for visitor in session.exec(select(VisitorDaily)).all():
            session.delete(visitor)
        
        for stat in session.exec(select(DailyStats)).all():
            session.delete(stat)
        
        session.commit()
        
        return {
            "status": "success",
            "message": "Database visitor berhasil direset",
            "reset_by": user.username
        }
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Error reset database: {str(e)}")

@app.get("/api/stats/per_second")
def stats_per_second(
    day: date = Query(..., description="Tanggal (YYYY-MM-DD)"),
    camera_id: Optional[int] = Query(None),
    session: Session = Depends(get_session),
    _: User = Depends(require_role("ADMIN", "OPERATOR"))
):
    """Statistik event per detik untuk 1 hari (untuk chart granular)."""
    from datetime import datetime, timedelta
    start_dt = datetime.combine(day, datetime.min.time())
    end_dt = datetime.combine(day, datetime.max.time())
    q = select(VisitEvent).where(
        VisitEvent.event_time >= start_dt,
        VisitEvent.event_time <= end_dt,
        or_(VisitEvent.person_type == None, VisitEvent.person_type != "EMPLOYEE"),
    )
    if camera_id:
        q = q.where(VisitEvent.camera_id == camera_id)
    events = session.exec(q).all()
    # Group by second
    buckets = defaultdict(int)
    for e in events:
        sec = e.event_time.replace(microsecond=0)
        buckets[sec] += 1
    # Format output: list of {second: ISO, count: int}
    result = [
        {"second": dt.isoformat(), "count": buckets[dt]}
        for dt in sorted(buckets.keys())
    ]
    return result


# ==================== Footage Upload (Client CCTV) ====================

ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".avi", ".mkv", ".mov", ".flv", ".wmv", ".webm"}
MAX_FOOTAGE_SIZE = 500 * 1024 * 1024  # 500 MB


@app.post("/api/footage/upload")
async def upload_footage(
    video: UploadFile = File(...),
    set_as_source: bool = Form(False),
    camera_id: int = Form(1),
    session: Session = Depends(get_session),
    _: User = Depends(require_role("ADMIN")),
):
    """
    Upload file video CCTV dari client melalui frontend.
    Video disimpan di backend/storage/footage/ dan bisa diset sebagai sumber kamera.
    """
    import re
    import uuid

    if not video.filename:
        raise HTTPException(status_code=400, detail="Nama file tidak boleh kosong")

    ext = os.path.splitext(video.filename)[1].lower()
    if ext not in ALLOWED_VIDEO_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Format file tidak didukung. Format yang diterima: {', '.join(ALLOWED_VIDEO_EXTENSIONS)}",
        )

    # Sanitize filename: keep only safe chars
    base_name = re.sub(r"[^\w\-.]", "_", os.path.splitext(video.filename)[0])
    unique_name = f"{base_name}_{uuid.uuid4().hex[:8]}{ext}"
    file_path = FOOTAGE_DIR / unique_name

    # Read and save with size check
    total_size = 0
    with open(file_path, "wb") as f:
        while True:
            chunk = await video.read(1024 * 1024)  # 1MB chunks
            if not chunk:
                break
            total_size += len(chunk)
            if total_size > MAX_FOOTAGE_SIZE:
                f.close()
                file_path.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=413,
                    detail=f"File terlalu besar. Maksimum {MAX_FOOTAGE_SIZE // (1024*1024)} MB",
                )
            f.write(chunk)

    # Optionally set as camera source
    footage_abs_path = str(file_path.resolve())
    if set_as_source:
        cam = session.get(Camera, camera_id)
        if cam:
            cam.stream_url = footage_abs_path
            session.add(cam)
            session.commit()

    return {
        "ok": True,
        "filename": unique_name,
        "size_mb": round(total_size / (1024 * 1024), 2),
        "path": footage_abs_path,
        "set_as_source": set_as_source,
    }


@app.get("/api/footage")
def list_footage(_: User = Depends(require_role("ADMIN", "OPERATOR"))):
    """List semua file footage yang sudah diupload."""
    files = []
    for f in sorted(FOOTAGE_DIR.iterdir()):
        if f.is_file() and f.suffix.lower() in ALLOWED_VIDEO_EXTENSIONS:
            stat = f.stat()
            files.append({
                "filename": f.name,
                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                "path": str(f.resolve()),
                "uploaded_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
            })
    return files


@app.delete("/api/footage/{filename}")
def delete_footage(
    filename: str,
    session: Session = Depends(get_session),
    _: User = Depends(require_role("ADMIN")),
):
    """Hapus file footage yang sudah diupload."""
    import re

    # Sanitize: only allow safe filename chars
    if not re.match(r"^[\w\-. ]+$", filename):
        raise HTTPException(status_code=400, detail="Nama file tidak valid")

    file_path = FOOTAGE_DIR / filename
    # Prevent path traversal
    if not file_path.resolve().parent == FOOTAGE_DIR.resolve():
        raise HTTPException(status_code=400, detail="Path tidak valid")

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File tidak ditemukan")

    # Check if any camera is using this file as source
    abs_path = str(file_path.resolve())
    cameras = session.exec(select(Camera).where(Camera.stream_url == abs_path)).all()
    if cameras:
        cam_names = ", ".join(c.name for c in cameras)
        raise HTTPException(
            status_code=409,
            detail=f"File sedang digunakan oleh kamera: {cam_names}. Ubah sumber kamera terlebih dahulu.",
        )

    file_path.unlink()
    return {"ok": True, "message": f"File '{filename}' berhasil dihapus"}


@app.post("/api/footage/{filename}/set-source")
def set_footage_as_source(
    filename: str,
    camera_id: int = Query(1),
    session: Session = Depends(get_session),
    _: User = Depends(require_role("ADMIN")),
):
    """Set file footage sebagai sumber video kamera."""
    import re

    if not re.match(r"^[\w\-. ]+$", filename):
        raise HTTPException(status_code=400, detail="Nama file tidak valid")

    file_path = FOOTAGE_DIR / filename
    if not file_path.resolve().parent == FOOTAGE_DIR.resolve():
        raise HTTPException(status_code=400, detail="Path tidak valid")

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File tidak ditemukan")

    cam = session.get(Camera, camera_id)
    if not cam:
        raise HTTPException(status_code=404, detail="Kamera tidak ditemukan")

    cam.stream_url = str(file_path.resolve())
    session.add(cam)
    session.commit()

    return {
        "ok": True,
        "message": f"Kamera '{cam.name}' akan menggunakan footage '{filename}'",
        "stream_url": cam.stream_url,
    }
