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
    profile: Optional[str] = Field(None, max_length=100)
    url_file_path: Optional[str] = Field(None, max_length=512)
    url_barem_path: Optional[str] = Field(None, max_length=512)
    notes: Optional[str] = None


class SourceCreate(SourceBase):
    pass


class SourceUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    type: Optional[SourceType] = None
    year: Optional[int] = None
    session: Optional[str] = Field(None, max_length=50)
    profile: Optional[str] = Field(None, max_length=100)
    url_file_path: Optional[str] = Field(None, max_length=512)
    url_barem_path: Optional[str] = Field(None, max_length=512)
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
    answer_numeric_value: Optional[float] = None
    answer_numeric_expression: Optional[str] = None
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
    answer_numeric_value: Optional[float] = None
    answer_numeric_expression: Optional[str] = None
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
    PARENT = "parent"              # Părinte — urmărește progresul elevului
    ADMIN = "admin"


class UserRegister(BaseModel):
    email: str = Field(..., max_length=255)
    password: str = Field(..., min_length=8)
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


# --- Parent Models ---

class ParentLinkRequest(BaseModel):
    parent_email: str = Field(..., max_length=255)
    parent_name: Optional[str] = Field(None, max_length=255)

class ParentStudentDB(BaseModel):
    id: uuid.UUID
    parent_id: uuid.UUID
    student_id: uuid.UUID
    parent_email: str
    parent_name: str
    student_name: str
    linked_at: datetime

    class Config:
        from_attributes = True
        json_encoders = {uuid.UUID: str, datetime: lambda dt: dt.isoformat()}

class StudentActivityDay(BaseModel):
    date: str          # YYYY-MM-DD
    exercises_seen: int
    exercises_completed: int
    variants_generated: int
    flags_sent: int

class ParentStudentStats(BaseModel):
    student_id: str
    student_name: str
    student_email: str
    total_exercises_seen: int
    total_exercises_completed: int
    total_variants_generated: int
    total_flags_sent: int
    total_review_items_open: int
    last_active_at: Optional[str]
    activity_last_30_days: List[StudentActivityDay]
    completion_by_subiect: Dict[str, int]   # {"1": 12, "2": 5, "3": 3}

# --- Gamification Models ---

LEVELS = [
    (0,    "Debutant",    "⭐"),
    (500,  "Aspirant",   "🔥"),
    (1500, "Competitor", "⚡"),
    (4000, "Elite",      "💎"),
    (8000, "BAC Ready",  "🏆"),
]

BADGES = {
    "first_exercise":   {"label": "Primul exercițiu",       "icon": "🎯", "desc": "Ai rezolvat primul exercițiu"},
    "streak_3":         {"label": "3 zile consecutive",     "icon": "🔥", "desc": "Activ 3 zile la rând"},
    "streak_5":         {"label": "5 zile consecutive",     "icon": "⚔️", "desc": "Ai ținut ritmul 5 zile la rând"},
    "streak_7":         {"label": "O săptămână",            "icon": "📅", "desc": "Activ 7 zile la rând"},
    "streak_14":        {"label": "Două săptămâni",         "icon": "🌟", "desc": "Activ 14 zile la rând"},
    "streak_30":        {"label": "Luna de foc",            "icon": "🌙", "desc": "Activ 30 zile la rând"},
    "exercises_10":     {"label": "10 exerciții",           "icon": "📚", "desc": "Ai rezolvat 10 exerciții"},
    "exercises_50":     {"label": "50 exerciții",           "icon": "📖", "desc": "Ai rezolvat 50 de exerciții"},
    "exercises_100":    {"label": "100 exerciții",          "icon": "🎓", "desc": "Ai rezolvat 100 de exerciții"},
    "first_s1":         {"label": "S1 deblocat",            "icon": "1️⃣", "desc": "Primul exercițiu din Subiectul I"},
    "first_s2":         {"label": "S2 deblocat",            "icon": "2️⃣", "desc": "Primul exercițiu din Subiectul II"},
    "first_s3":         {"label": "S3 deblocat",            "icon": "3️⃣", "desc": "Primul exercițiu din Subiectul III"},
    "xp_500":           {"label": "500 XP",                 "icon": "⚡", "desc": "Ai acumulat 500 XP"},
    "xp_1000":          {"label": "1000 XP",                "icon": "💥", "desc": "Ai acumulat 1000 XP"},
    "xp_3000":          {"label": "3000 XP",                "icon": "🏆", "desc": "Ai acumulat 3000 XP"},
}


def get_level(xp: int) -> dict:
    level_info = LEVELS[0]
    for min_xp, name, icon in LEVELS:
        if xp >= min_xp:
            level_info = (min_xp, name, icon)
    # XP until next level
    idx = next((i for i, (m, _, _) in enumerate(LEVELS) if m == level_info[0]), 0)
    if idx + 1 < len(LEVELS):
        next_xp = LEVELS[idx + 1][0]
        xp_in_level = xp - level_info[0]
        xp_needed = next_xp - level_info[0]
    else:
        next_xp = level_info[0]
        xp_in_level = xp - level_info[0]
        xp_needed = 1
    return {
        "name": level_info[1],
        "icon": level_info[2],
        "xp_total": xp,
        "xp_in_level": xp_in_level,
        "xp_for_next": xp_needed,
        "progress_pct": min(100, round(xp_in_level / xp_needed * 100)) if xp_needed else 100,
        "is_max": idx + 1 >= len(LEVELS),
    }


class GamificationProfile(BaseModel):
    xp_total: int
    streak_current: int
    streak_max: int
    last_active_date: Optional[str]
    level: dict
    badges: List[dict]


class XPLogEntry(BaseModel):
    xp_gained: int
    reason: str
    created_at: datetime

    class Config:
        json_encoders = {datetime: lambda dt: dt.isoformat()}


# --- Exercise Submission Models ---

class SelfEval(str, Enum):
    FAILED   = "failed"
    PARTIAL  = "partial"
    COMPLETE = "complete"

class TeacherReviewStatus(str, Enum):
    PENDING   = "pending"
    CORRECT   = "correct"
    INCORRECT = "incorrect"

class ExerciseSubmitRequest(BaseModel):
    self_eval: SelfEval

class TeacherReviewRequest(BaseModel):
    status: TeacherReviewStatus
    note: Optional[str] = None

class ExerciseSubmissionDB(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    exercise_id: uuid.UUID
    self_eval: SelfEval
    photo_path: Optional[str]
    photo_uploaded_at: Optional[datetime]
    teacher_status: Optional[str]
    reviewed_by: Optional[uuid.UUID]
    reviewed_at: Optional[datetime]
    teacher_note: Optional[str]
    xp_self_eval: int
    xp_photo: int
    xp_teacher: int
    created_at: datetime

    class Config:
        from_attributes = True
        json_encoders = {uuid.UUID: str, datetime: lambda dt: dt.isoformat()}

class SubmissionForTeacher(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    student_name: str
    student_email: str
    exercise_id: uuid.UUID
    exercise_statement: Optional[str]
    self_eval: SelfEval
    photo_path: Optional[str]
    teacher_status: Optional[str]
    teacher_note: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
        json_encoders = {uuid.UUID: str, datetime: lambda dt: dt.isoformat()}


# --- Study / Saved Sets Request Models ---

class ExerciseSetCreateRequest(BaseModel):
    exercise_ids: List[uuid.UUID]
    filters: Dict[str, Any] = Field(default_factory=dict)
    name: Optional[str] = None
    linked_plan: Optional[str] = None


class ExerciseSetUpdateRequest(BaseModel):
    name: Optional[str] = None
    linked_plan: Optional[str] = None


class StudySessionStartRequest(BaseModel):
    session_type: str = "test_scurt"
    filters: Dict[str, Any] = Field(default_factory=dict)
    plan_day_id: Optional[str] = None


class StudySessionCompleteRequest(BaseModel):
    exercises_completed: int = 0
    duration_sec: int = 0


class StudyPlanDayCreateRequest(BaseModel):
    plan_date: str
    session_type: str = "test_scurt"
    filters: Dict[str, Any] = Field(default_factory=dict)
    note: Optional[str] = None
    user_id: Optional[str] = None
    student_id: Optional[str] = None


class AdminParentStudentLinkRequest(BaseModel):
    parent_id: str
    student_id: str


class ClassGroupCreateRequest(BaseModel):
    name: str
    allow_anonymous: bool = True


class ClassGroupJoinRequest(BaseModel):
    class_code: str
    pseudonym: Optional[str] = None
    is_anonymous: bool = False


class ClassMembershipUpdateRequest(BaseModel):
    pseudonym: Optional[str] = None
    is_anonymous: bool = False


class WeeklyChallengeCreateRequest(BaseModel):
    title: str
    description: Optional[str] = None
    target_count: int = Field(default=1, ge=1, le=500)
    subiect_tag: Optional[str] = None
