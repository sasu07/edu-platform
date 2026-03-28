from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import uuid


# --- ENUM-like types (for Pydantic validation) ---
class SourceType(str, Enum):
    PDF = "pdf"
    OFICIAL = "oficial"
    CULEGERE = "culegere"


class ExamType(str, Enum):
    BACALAUREAT = "bacalaureat"
    EVALUARE_NATIONALA = "evaluare_nationala"
    SIMULARE = "simulare"
    OLIMPIADA = "olimpiada"
    ALTA = "alta"


class SubjectPart(str, Enum):
    ALGEBRA = "algebra"
    GEOMETRIE = "geometrie"
    ANALIZA = "analiza"
    TRIGONOMETRIE = "trigonometrie"
    PROBABILITATI = "probabilitati"
    COMBINATORICA = "combinatorica"
    TEORIA_NUMERELOR = "teoria_numerelor"


class ItemType(str, Enum):
    SUBIECT_1 = "subiect_1"
    SUBIECT_2 = "subiect_2"
    SUBIECT_3 = "subiect_3"
    PROBLEMA = "problema"
    EXERCITIU = "exercitiu"


class ExerciseStatus(str, Enum):
    DRAFT = "DRAFT"
    REVIEW = "REVIEW"
    READY = "READY"
    ARCHIVED = "ARCHIVED"


class SegmentStatus(str, Enum):
    EXTRACTED = "EXTRACTED"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"


class ExtractionMethod(str, Enum):
    MANUAL = "MANUAL"
    PIX2TEXT = "pix2text"
    MATHPIX = "mathpix"
    OTHER = "other"


class AssetType(str, Enum):
    IMAGE = "image"
    DIAGRAM = "diagram"
    GRAPH = "graph"
    TABLE = "table"


# --- Base Models ---

class SourceBase(BaseModel):
    name: str = Field(..., max_length=255)
    type: SourceType
    year: Optional[int] = None
    session: Optional[str] = Field(None, max_length=50)
    url_file_path: Optional[str] = Field(None, max_length=512)
    notes: Optional[str] = None


class SourceCreate(SourceBase):
    pass


class SourceUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    type: Optional[SourceType] = None
    year: Optional[int] = None
    session: Optional[str] = Field(None, max_length=50)
    url_file_path: Optional[str] = Field(None, max_length=512)
    notes: Optional[str] = None


class SourceDB(SourceBase):
    id: uuid.UUID
    created_at: datetime

    class Config:
        from_attributes = True
        json_encoders = {
            uuid.UUID: str,
            datetime: lambda dt: dt.isoformat()
        }


# --- Source Segments Models ---

class SourceSegmentBase(BaseModel):
    source_id: uuid.UUID
    page_start: int
    page_end: int
    raw_extraction: Optional[str] = None
    checksum: Optional[str] = Field(None, max_length=64)
    status: SegmentStatus = SegmentStatus.EXTRACTED
    extraction_method: ExtractionMethod


class SourceSegmentCreate(SourceSegmentBase):
    pass


class SourceSegmentUpdate(BaseModel):
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    raw_extraction: Optional[str] = None
    checksum: Optional[str] = None
    status: Optional[SegmentStatus] = None
    extraction_method: Optional[ExtractionMethod] = None


class SourceSegmentDB(SourceSegmentBase):
    id: uuid.UUID
    created_at: datetime

    class Config:
        from_attributes = True
        json_encoders = {
            uuid.UUID: str,
            datetime: lambda dt: dt.isoformat()
        }


# --- Exercise Models ---

class ExerciseBase(BaseModel):
    exam_type: ExamType
    profile: Optional[str] = Field(None, max_length=50)
    subject_part: Optional[SubjectPart] = None
    item_type: Optional[ItemType] = None
    statement_latex: str
    statement_text: Optional[str] = None
    answer_latex: Optional[str] = None
    solution_latex: Optional[str] = None
    scoring_guide_latex: Optional[str] = None
    scoring_guide_text: Optional[str] = None
    difficulty: Optional[int] = Field(None, ge=1, le=10)
    estimated_time_sec: Optional[int] = None
    points: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None
    status: ExerciseStatus = ExerciseStatus.DRAFT
    created_by_user_id: Optional[uuid.UUID] = None


class ExerciseCreate(ExerciseBase):
    pass


class ExerciseUpdate(BaseModel):
    exam_type: Optional[ExamType] = None
    profile: Optional[str] = None
    subject_part: Optional[SubjectPart] = None
    item_type: Optional[ItemType] = None
    statement_latex: Optional[str] = None
    statement_text: Optional[str] = None
    answer_latex: Optional[str] = None
    solution_latex: Optional[str] = None
    scoring_guide_latex: Optional[str] = None
    scoring_guide_text: Optional[str] = None
    difficulty: Optional[int] = Field(None, ge=1, le=10)
    estimated_time_sec: Optional[int] = None
    points: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None
    status: Optional[ExerciseStatus] = None


class ExerciseDB(ExerciseBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        json_encoders = {
            uuid.UUID: str,
            datetime: lambda dt: dt.isoformat()
        }


# --- Asset Models ---

class AssetBase(BaseModel):
    exercise_id: uuid.UUID
    type: AssetType
    file_path: str = Field(..., max_length=512)
    caption: Optional[str] = None
    latex_ref: Optional[str] = Field(None, max_length=255)


class AssetCreate(AssetBase):
    pass


class AssetDB(AssetBase):
    id: uuid.UUID
    created_at: datetime

    class Config:
        from_attributes = True
        json_encoders = {
            uuid.UUID: str,
            datetime: lambda dt: dt.isoformat()
        }


# --- Segment Region Models ---

class SegmentRegionBase(BaseModel):
    source_segment_id: uuid.UUID
    page_number: int
    bbox: Dict[str, Any]  # JSON object with bounding box coordinates


class SegmentRegionCreate(SegmentRegionBase):
    pass


class SegmentRegionDB(SegmentRegionBase):
    id: uuid.UUID

    class Config:
        from_attributes = True
        json_encoders = {
            uuid.UUID: str
        }


# --- Exercise Source Segment (many-to-many) Models ---

class ExerciseSourceSegmentBase(BaseModel):
    exercise_id: uuid.UUID
    source_segment_id: uuid.UUID
    role: Optional[str] = Field(None, max_length=50)


class ExerciseSourceSegmentCreate(ExerciseSourceSegmentBase):
    pass


# --- Tag Models ---

class TagBase(BaseModel):
    namespace: str = Field(..., max_length=255)
    key: str = Field(..., max_length=255)
    label: Optional[str] = Field(None, max_length=255)
    parent_id: Optional[uuid.UUID] = None


class TagCreate(TagBase):
    pass


class TagDB(TagBase):
    id: uuid.UUID
    created_at: datetime

    class Config:
        from_attributes = True
        json_encoders = {
            uuid.UUID: str,
            datetime: lambda dt: dt.isoformat()
        }


# --- Exercise Tag Models ---

class ExerciseTagBase(BaseModel):
    exercise_id: uuid.UUID
    tag_id: uuid.UUID
    weight: float = 1.0
    confidence: float = 1.0
    created_by: Optional[str] = Field(None, max_length=50)
    created_by_user_id: Optional[uuid.UUID] = None


class ExerciseTagCreate(ExerciseTagBase):
    pass


class ExerciseTagDB(ExerciseTagBase):
    class Config:
        from_attributes = True
        json_encoders = {
            uuid.UUID: str
        }


# --- Processing Result Models (for API responses) ---

class TagImport(BaseModel):
    namespace: str = Field(..., max_length=255)
    key: str = Field(..., max_length=255)
    label: Optional[str] = Field(None, max_length=255)
    weight: float = 1.0

class ExerciseImport(BaseModel):
    exam_type: ExamType
    profile: Optional[str] = Field(None, max_length=50)
    subject_part: Optional[SubjectPart] = None
    item_type: Optional[ItemType] = None
    statement_latex: str
    statement_text: Optional[str] = None
    answer_latex: Optional[str] = None
    solution_latex: Optional[str] = None
    scoring_guide_latex: Optional[str] = None
    scoring_guide_text: Optional[str] = None
    difficulty: Optional[int] = Field(None, ge=1, le=10)
    points: Optional[int] = None
    tags: Optional[List[TagImport]] = None

class StructuredImport(BaseModel):
    exercises: List[ExerciseImport]


# --- Hierarchical Import Models (grouped exercises with subpoints) ---

class SubpointImport(BaseModel):
    """Un subpunct (a, b, c) dintr-un exercițiu compus."""
    subpoint: str  # "a", "b", "c"
    statement_latex: str
    statement_text: Optional[str] = None
    answer_latex: Optional[str] = None
    solution_latex: Optional[str] = None
    scoring_guide_latex: Optional[str] = None
    scoring_guide_text: Optional[str] = None
    points: Optional[int] = None
    difficulty: Optional[int] = Field(None, ge=1, le=10)


class GroupedExerciseImport(BaseModel):
    """Exercițiu din JSON de import - poate conține subpuncte nested."""
    external_id: str
    subiect: int  # 1, 2, 3
    exercise_num: int  # 1, 2, 3...
    exam_type: str = "BAC"
    profile: Optional[str] = None
    statement_latex: str
    statement_text: Optional[str] = None
    answer_latex: Optional[str] = None
    solution_latex: Optional[str] = None
    scoring_guide_latex: Optional[str] = None
    scoring_guide_text: Optional[str] = None
    difficulty: Optional[int] = Field(None, ge=1, le=10)
    estimated_time_sec: Optional[int] = None
    points: Optional[int] = None
    status: str = "DRAFT"
    subpoints: Optional[List[SubpointImport]] = None
    tags: Optional[List[TagImport]] = None
    source_ref: Optional[Dict[str, int]] = None


class HierarchicalImport(BaseModel):
    """Format de import ierarhic cu exerciții grupate."""
    source: Dict[str, Any]
    exercises: List[GroupedExerciseImport]

class ProcessingPageResult(BaseModel):
    """Result from processing a single page"""
    page_number: int
    raw_text: str
    latex_formulas: List[str]
    width: Optional[int] = None
    height: Optional[int] = None
    error: Optional[str] = None


class ProcessingResult(BaseModel):
    """Complete result from PDF processing"""
    source_id: uuid.UUID
    segment_id: Optional[uuid.UUID] = None
    pages: List[ProcessingPageResult]
    combined_text: str
    total_pages: int
    status: str


# --- Variant Models ---

class VariantStatus(str, Enum):
    DRAFT = "DRAFT"
    READY = "READY"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


class VariantBase(BaseModel):
    name: str = Field(..., max_length=255)
    exam_type: ExamType
    profile: Optional[str] = Field(None, max_length=50)
    year: Optional[int] = None
    session: Optional[str] = Field(None, max_length=50)
    total_points: Optional[int] = None
    duration_minutes: Optional[int] = None
    instructions: Optional[str] = None
    status: VariantStatus = VariantStatus.DRAFT
    created_by_user_id: Optional[uuid.UUID] = None


class VariantCreate(VariantBase):
    pass


class VariantUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    exam_type: Optional[ExamType] = None
    profile: Optional[str] = None
    year: Optional[int] = None
    session: Optional[str] = None
    total_points: Optional[int] = None
    duration_minutes: Optional[int] = None
    instructions: Optional[str] = None
    status: Optional[VariantStatus] = None


class VariantDB(VariantBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        json_encoders = {
            uuid.UUID: str,
            datetime: lambda dt: dt.isoformat()
        }


# --- Variant Exercise Models ---

class VariantExerciseBase(BaseModel):
    variant_id: uuid.UUID
    exercise_id: uuid.UUID
    order_index: int
    section_name: Optional[str] = Field(None, max_length=100)


class VariantExerciseCreate(VariantExerciseBase):
    pass


class VariantExerciseDB(VariantExerciseBase):
    id: uuid.UUID
    created_at: datetime

    class Config:
        from_attributes = True
        json_encoders = {
            uuid.UUID: str,
            datetime: lambda dt: dt.isoformat()
        }


# --- Auth / User Models ---

class UserRole(str, Enum):
    STUDENT = "student"
    TEACHER = "teacher"            # Profesor al platformei — răspunde la cereri de ajutor
    SCHOOL_TEACHER = "school_teacher"  # Profesor de școală — generează variante/fișe
    ADMIN = "admin"


class UserRegister(BaseModel):
    email: str = Field(..., max_length=255)
    password: str = Field(..., min_length=6)
    full_name: str = Field(..., max_length=255)
    role: UserRole = UserRole.STUDENT
    # school_teacher poate specifica instituția
    school_name: Optional[str] = Field(None, max_length=255)


class UserLogin(BaseModel):
    email: str
    password: str


class UserDB(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True
        json_encoders = {
            uuid.UUID: str,
            datetime: lambda dt: dt.isoformat()
        }


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserDB


# --- Subscription Models ---

class SubscriptionPlan(str, Enum):
    FREE = "free"
    PREMIUM_HELP = "premium_help"   # Acces cereri de ajutor (tutoring)
    PREMIUM_PDF = "premium_pdf"     # Acces download PDF variante BAC
    PREMIUM_GEN = "premium_gen"     # Generare nelimitată exerciții + variante BAC
    PREMIUM = "premium"             # Acces complet (help + PDF + generare)


class SubscriptionStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class SubscriptionDB(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    plan_type: SubscriptionPlan
    status: SubscriptionStatus
    expires_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True
        json_encoders = {
            uuid.UUID: str,
            datetime: lambda dt: dt.isoformat()
        }


# --- Help Request Models ---

class HelpFlagType(str, Enum):
    WRITTEN = "WRITTEN"    # Rezolvare scrisă
    VIDEO = "VIDEO"        # Rezolvare video
    LIVE = "LIVE"          # Sesiune live Zoom


class HelpRequestStatus(str, Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    RESOLVED = "resolved"


class HelpRequestCreate(BaseModel):
    exercise_id: uuid.UUID
    flag_type: HelpFlagType
    notes: Optional[str] = None


class HelpRequestDB(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    exercise_id: uuid.UUID
    flag_type: HelpFlagType
    status: HelpRequestStatus
    notes: Optional[str] = None
    assigned_teacher_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        json_encoders = {
            uuid.UUID: str,
            datetime: lambda dt: dt.isoformat()
        }


class HelpResponseCreate(BaseModel):
    content_text: Optional[str] = None
    zoom_link: Optional[str] = Field(None, max_length=512)
    scheduled_at: Optional[datetime] = None


class HelpResponseDB(BaseModel):
    id: uuid.UUID
    request_id: uuid.UUID
    teacher_id: uuid.UUID
    content_text: Optional[str] = None
    video_path: Optional[str] = None
    zoom_link: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True
        json_encoders = {
            uuid.UUID: str,
            datetime: lambda dt: dt.isoformat()
        }


# --- Notificări ---

class NotificationDB(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    type: str
    title: str
    body: Optional[str] = None
    is_read: bool
    related_id: Optional[uuid.UUID] = None
    created_at: datetime

    class Config:
        from_attributes = True
        json_encoders = {uuid.UUID: str, datetime: lambda dt: dt.isoformat()}


# --- Teacher Stats ---

class TeacherStats(BaseModel):
    total_requests: int
    pending: int
    assigned: int
    resolved: int
    by_type: Dict[str, int]
    avg_response_hours: Optional[float] = None


# --- School Teacher Subscription Info ---

class SchoolTeacherUsage(BaseModel):
    variants_this_month: int
    variant_limit: Optional[int]   # None = nelimitat (premium)
    is_premium: bool