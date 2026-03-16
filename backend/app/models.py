"""
Database Models sesuai Project Concept
- roles, users, cameras, counting_areas, visitor_daily, visit_events, daily_stats
"""
from typing import Optional, List, Any
from datetime import datetime, date
from sqlmodel import SQLModel, Field, Column, Relationship
from sqlalchemy import JSON, UniqueConstraint, Text


class Role(SQLModel, table=True):
    """Tabel roles untuk role-based access control"""
    __tablename__ = "roles"
    
    role_id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, max_length=30)  # ADMIN, OPERATOR
    
    users: List["User"] = Relationship(back_populates="role")


class User(SQLModel, table=True):
    """Tabel users untuk autentikasi"""
    __tablename__ = "users"
    
    user_id: Optional[int] = Field(default=None, primary_key=True)
    role_id: int = Field(foreign_key="roles.role_id")
    full_name: str = Field(max_length=120)
    username: str = Field(unique=True, index=True, max_length=60)
    password_hash: str = Field(max_length=255)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    role: Optional[Role] = Relationship(back_populates="users")


class Camera(SQLModel, table=True):
    """Tabel cameras untuk menyimpan konfigurasi kamera CCTV"""
    __tablename__ = "cameras"
    
    camera_id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=120)
    location: Optional[str] = Field(default=None, max_length=160)
    stream_url: Optional[str] = Field(default=None, sa_column=Column(Text))
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    counting_areas: List["CountingArea"] = Relationship(back_populates="camera")


class CountingArea(SQLModel, table=True):
    """Tabel counting_areas untuk konfigurasi ROI/area hitung per kamera"""
    __tablename__ = "counting_areas"
    
    area_id: Optional[int] = Field(default=None, primary_key=True)
    camera_id: int = Field(foreign_key="cameras.camera_id", index=True)
    name: str = Field(max_length=120)
    roi_polygon: Any = Field(sa_column=Column(JSON))  # titik polygon [[x,y], ...]
    direction_mode: str = Field(default="BOTH", max_length=10)  # IN/OUT/BOTH
    is_active: bool = Field(default=True)
    
    camera: Optional[Camera] = Relationship(back_populates="counting_areas")


class Employee(SQLModel, table=True):
    """Tabel employees untuk daftar pegawai yang harus diabaikan dari hitungan pelanggan"""
    __tablename__ = "employees"

    employee_id: Optional[int] = Field(default=None, primary_key=True)
    employee_code: str = Field(unique=True, index=True, max_length=60)
    full_name: str = Field(max_length=120)
    face_embedding: Optional[Any] = Field(default=None, sa_column=Column(JSON))
    face_image_path: Optional[str] = Field(default=None, sa_column=Column(Text))
    notes: Optional[str] = Field(default=None, max_length=255)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class VisitorDaily(SQLModel, table=True):
    """
    Tabel visitor_daily untuk pengunjung unik harian
    Aturan: masuk berkali-kali dalam sehari tetap dihitung 1
    """
    __tablename__ = "visitor_daily"
    __table_args__ = (UniqueConstraint("visit_date", "visitor_key", name="uq_visitor_day"),)
    
    visitor_daily_id: Optional[int] = Field(default=None, primary_key=True)
    visit_date: date = Field(index=True)
    visitor_key: str = Field(max_length=100, index=True)  # hash/uuid anonim
    first_seen_at: datetime
    last_seen_at: datetime
    notes: Optional[str] = Field(default=None, max_length=255)


class VisitEvent(SQLModel, table=True):
    """Tabel visit_events untuk catatan kejadian kunjungan"""
    __tablename__ = "visit_events"
    
    event_id: Optional[int] = Field(default=None, primary_key=True)
    camera_id: int = Field(foreign_key="cameras.camera_id", index=True)
    area_id: int = Field(foreign_key="counting_areas.area_id", index=True)
    event_time: datetime = Field(index=True)
    track_id: Optional[str] = Field(default=None, max_length=80)
    visitor_key: str = Field(max_length=100, index=True)
    direction: Optional[str] = Field(default=None, max_length=10)  # IN/OUT
    person_type: str = Field(default="CUSTOMER", max_length=20, index=True)
    employee_id: Optional[int] = Field(default=None, index=True)
    face_match_score: Optional[float] = Field(default=None)
    recognition_source: Optional[str] = Field(default=None, max_length=50)
    confidence_avg: Optional[float] = Field(default=None)
    snapshot_path: Optional[str] = Field(default=None, sa_column=Column(Text))
    created_at: datetime = Field(default_factory=datetime.utcnow)


class DailyStats(SQLModel, table=True):
    """Tabel daily_stats untuk statistik harian (cache untuk dashboard cepat)"""
    __tablename__ = "daily_stats"
    
    stat_date: date = Field(primary_key=True)
    camera_id: int = Field(primary_key=True, foreign_key="cameras.camera_id")
    total_events: int = Field(default=0)
    unique_visitors: int = Field(default=0)
    total_in: int = Field(default=0)
    total_out: int = Field(default=0)
    last_updated_at: datetime = Field(default_factory=datetime.utcnow)
