
import uuid
import os
import shutil
from datetime import datetime
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, BackgroundTasks, Depends, HTTPException, status, UploadFile, File, Form
from psycopg import Connection
from psycopg.rows import dict_row

from starlette.responses import StreamingResponse, HTMLResponse
from bootstrap import UPLOAD_DIR, configure_app
from database import get_db_conn
from models import (
    SourceCreate, SourceDB, SourceUpdate, SourceType,
    ExerciseCreate, ExerciseDB,
    SourceSegmentCreate, SourceSegmentDB, SourceSegmentUpdate,
    AssetCreate, AssetDB,
    ProcessingResult, ProcessingPageResult,
    ExtractionMethod, SegmentStatus,
    ExerciseTagCreate,
    StructuredImport, ExerciseImport, TagImport, ExamType, ExerciseStatus,
    VariantStatus,
    VariantExerciseCreate, VariantExerciseDB,
    HierarchicalImport,
    UserRegister, UserLogin, UserDB, UserRole, Token,
    SubscriptionDB, SubscriptionPlan, SubscriptionStatus,
    HelpRequestCreate, HelpRequestDB, HelpFlagType, HelpRequestStatus,
    HelpResponseCreate, HelpResponseDB,
    NotificationDB, TeacherStats,
    GamificationProfile, get_level, BADGES,
    SelfEval, TeacherReviewStatus, ExerciseSubmitRequest,
    TeacherReviewRequest, ExerciseSubmissionDB, SubmissionForTeacher,
)
from pix2text_processor import get_pix2text_processor
from ai_tagger import get_ai_tagger
from exercise_extractor import get_exercise_extractor
from import_json import JSONImporter
from variant_generator import get_variant_generator
from pdf_generator import get_pdf_generator
from html_generator import get_html_generator
from email_service import (
    send_parent_invite, send_parent_linked, send_weekly_digest,
)
from auth import (
    get_current_user, get_optional_user, require_role, require_premium,
    require_pdf_premium, require_staff, check_school_teacher_limit, check_variant_gen_limit,
    _has_active_premium,
)
from routers.auth_router import router as auth_router
from routers.exercises_router import (
    create_exercise_record,
    router as exercises_router,
    tag_exercise_in_db,
)
from routers.help_router import router as help_router
from routers.league_router import router as league_router
from routers.parent_router import router as parent_router
from routers.study_router import router as study_router
from routers.system_router import router as system_router
from routers.variants_router import router as variants_router
from routers.learning_path_router import router as learning_path_router
from services.xp_service import award_xp as _award_xp, calc_base_xp as _calc_base_xp

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from rate_limit import limiter

# În producție (ENV=production) ascundem documentația API — reduce suprafața de recon.
_PROD = os.getenv("ENV", "").lower() in ("production", "prod")

app = FastAPI(
    title="Edu Content API",
    description="Backend API for managing educational exercises and variants.",
    version="0.1.0",
    docs_url=None if _PROD else "/docs",
    redoc_url=None if _PROD else "/redoc",
    openapi_url=None if _PROD else "/openapi.json",
)
configure_app(app)

# Rate limiting (brute-force / credential stuffing)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.include_router(auth_router)
app.include_router(exercises_router)
app.include_router(help_router)
app.include_router(league_router)
app.include_router(parent_router)
app.include_router(study_router)
app.include_router(system_router)
app.include_router(variants_router)
app.include_router(learning_path_router)


# --- Servire autentificată a fișierelor uploadate ---
# Înlocuiește vechiul mount static public `/uploads`. Fișierele sensibile
# (soluții elevi, corecții profesori, video-uri help, soluții diagnostic) sunt
# accesibile doar proprietarului sau personalului; restul (surse PDF) doar staff.
_STAFF_ROLES = (UserRole.TEACHER, UserRole.SCHOOL_TEACHER, UserRole.ADMIN)


@app.get("/uploads/{file_path:path}", tags=["Files"])
def serve_uploaded_file(
    file_path: str,
    conn: Connection = Depends(get_db_conn),
    current_user: UserDB = Depends(get_current_user),
):
    from fastapi.responses import FileResponse

    base = os.path.realpath(UPLOAD_DIR)
    target = os.path.realpath(os.path.join(base, file_path))
    # Anti path-traversal: ținta trebuie să fie strict în interiorul UPLOAD_DIR
    if target != base and not target.startswith(base + os.sep):
        raise HTTPException(status_code=404, detail="Fișier negăsit")
    if not os.path.isfile(target):
        raise HTTPException(status_code=404, detail="Fișier negăsit")

    is_staff = current_user.role in _STAFF_ROLES
    if not is_staff:
        rel = os.path.relpath(target, base).replace(os.sep, "/")
        filename = os.path.basename(target)
        uid = str(current_user.id)
        allowed = False

        if rel.startswith("submissions/"):
            # submission_{user_id}_{exercise_id}.ext — doar elevul care a trimis
            allowed = filename.startswith(f"submission_{uid}_")
        elif rel.startswith("teacher_files/"):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM exercise_submissions WHERE teacher_file_path = %s AND user_id = %s",
                    (f"/uploads/{rel}", uid),
                )
                allowed = cur.fetchone() is not None
        elif rel.startswith("help_videos/"):
            # {request_id}.ext — doar elevul care deține cererea de ajutor
            request_id = os.path.splitext(filename)[0]
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM help_requests WHERE id = %s AND student_id = %s",
                    (request_id, uid),
                )
                allowed = cur.fetchone() is not None
        elif filename.startswith("diagnostic_solution_"):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM diagnostic_tests WHERE solution_file_path = %s AND user_id = %s",
                    (filename, uid),
                )
                allowed = cur.fetchone() is not None
        # else: conținut (PDF-uri surse, bareme) — rămâne doar pentru staff

        if not allowed:
            raise HTTPException(status_code=403, detail="Acces interzis la acest fișier")

    return FileResponse(target)


# --- Helper functions ---

def _upsert_review_item(conn: Connection, student_id: str, exercise_id: str, source_reason: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO exercise_review_items
                (student_id, exercise_id, status, source_reason, fail_count, revisit_count, first_flagged_at, last_flagged_at, resolved_at)
            VALUES
                (%s, %s, 'open', %s, %s, 0, NOW(), NOW(), NULL)
            ON CONFLICT (student_id, exercise_id) DO UPDATE
            SET status='open',
                source_reason=EXCLUDED.source_reason,
                fail_count=exercise_review_items.fail_count + %s,
                revisit_count=exercise_review_items.revisit_count + 1,
                last_flagged_at=NOW(),
                resolved_at=NULL
            """,
            (
                student_id,
                exercise_id,
                source_reason,
                1 if source_reason in ("failed", "partial") else 0,
                1 if source_reason in ("failed", "partial") else 0,
            ),
        )


def _resolve_review_item(conn: Connection, student_id: str, exercise_id: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE exercise_review_items
            SET status='resolved', resolved_at=NOW()
            WHERE student_id=%s AND exercise_id=%s AND status='open'
            """,
            (student_id, exercise_id),
        )

def _create_source_in_db(source: SourceCreate, conn: Connection) -> dict:
    """Internal function to create source entry in database."""
    query = """
    INSERT INTO sources (name, type, year, session, profile, url_file_path, url_barem_path, notes)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    RETURNING id, name, type, year, session, profile, url_file_path, url_barem_path, notes, created_at;
    """
    with conn.cursor(row_factory=dict_row) as cur:
        type_value = source.type.value if isinstance(source.type, SourceType) else source.type
        cur.execute(query, (
            source.name, type_value, source.year, source.session,
            source.profile, source.url_file_path, source.url_barem_path, source.notes
        ))
        new_source = cur.fetchone()
        conn.commit()
        return new_source

def _extract_and_save_exercises(combined_text: str, context: dict, segment_id: uuid.UUID, conn: Connection):
    """Helper to extract exercises from text and save to DB."""
    try:
        extractor = get_exercise_extractor()
        extracted_exercises = extractor.extract_exercises(combined_text, context)
        
        from models import ExerciseCreate, ExamType, ExerciseStatus
        
        for ex_data in extracted_exercises:
            try:
                # Validate exam_type against enum
                try:
                    ex_exam_type = ExamType(ex_data.get('exam_type', 'alta'))
                except ValueError:
                    ex_exam_type = ExamType.ALTA

                exercise_to_create = ExerciseCreate(
                    exam_type=ex_exam_type,
                    statement_latex=ex_data.get('statement_latex', ''),
                    statement_text=ex_data.get('statement_text', ''),
                    solution_latex=ex_data.get('solution_latex', ''),
                    answer_latex=ex_data.get('answer_latex', ''),
                    scoring_guide_latex=ex_data.get('scoring_guide_latex', ''),
                    points=ex_data.get('points'),
                    difficulty=ex_data.get('difficulty'),
                    item_type=ex_data.get('item_type'),
                    subject_part=ex_data.get('subject_part'),
                    status=ExerciseStatus.DRAFT
                )
                
                # Create exercise in DB (reusing the endpoint function)
                new_ex = create_exercise_record(exercise_to_create, conn)
                
                # Link to source segment
                link_query = "INSERT INTO exercise_source_segments (exercise_id, source_segment_id) VALUES (%s, %s)"
                with conn.cursor() as cur:
                    cur.execute(link_query, (new_ex['id'], segment_id))
                conn.commit()
                
                # Auto-tag
                try:
                    tag_exercise_in_db(new_ex['id'], conn)
                except Exception:
                    pass # Ignore tagging errors during bulk extraction
                    
            except Exception as ex_err:
                print(f"Error creating extracted exercise: {ex_err}")
                conn.rollback()
    except Exception as extractor_err:
        print(f"Error during exercise extraction: {extractor_err}")

def _save_structured_exercises(exercises: List[ExerciseImport], segment_id: uuid.UUID, conn: Connection):
    """Helper to save structured exercises and their tags to DB."""
    from models import ExerciseCreate, ExerciseStatus
    
    for ex_data in exercises:
        try:
            exercise_to_create = ExerciseCreate(
                exam_type=ex_data.exam_type,
                profile=ex_data.profile,
                subject_part=ex_data.subject_part,
                item_type=ex_data.item_type,
                statement_latex=ex_data.statement_latex,
                statement_text=ex_data.statement_text,
                solution_latex=ex_data.solution_latex,
                answer_latex=ex_data.answer_latex,
                scoring_guide_latex=ex_data.scoring_guide_latex,
                scoring_guide_text=ex_data.scoring_guide_text,
                points=ex_data.points,
                difficulty=ex_data.difficulty,
                status=ExerciseStatus.DRAFT
            )
            
            # Create exercise in DB
            new_ex = create_exercise_record(exercise_to_create, conn)
            ex_id = new_ex['id']
            
            # Link to source segment
            link_query = "INSERT INTO exercise_source_segments (exercise_id, source_segment_id) VALUES (%s, %s)"
            with conn.cursor() as cur:
                cur.execute(link_query, (ex_id, segment_id))
            
            # Save tags
            if ex_data.tags:
                for t in ex_data.tags:
                    # Create/Get tag
                    tag_query = """
                    INSERT INTO tags (namespace, key, label)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (namespace, key) DO UPDATE SET label = EXCLUDED.label
                    RETURNING id;
                    """
                    with conn.cursor(row_factory=dict_row) as cur:
                        cur.execute(tag_query, (t.namespace, t.key, t.label))
                        res = cur.fetchone()
                        tag_id = res['id'] if isinstance(res, dict) else res[0]

                        # Link to exercise
                        link_tag_query = """
                        INSERT INTO exercise_tags (exercise_id, tag_id, weight, confidence, created_by)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (exercise_id, tag_id) DO UPDATE SET weight = EXCLUDED.weight
                        RETURNING tag_id;
                        """
                        cur.execute(link_tag_query, (ex_id, tag_id, t.weight, 1.0, 'manual_import'))
                        cur.fetchone() # consume result
            
            conn.commit()
        except Exception as ex_err:
            print(f"Error saving imported exercise: {ex_err}")
            conn.rollback()

# --- CRUD Operations for SOURCES ---

@app.post("/sources/", response_model=SourceDB, status_code=status.HTTP_201_CREATED)
def create_source(source: SourceCreate, conn: Connection = Depends(get_db_conn), _staff: UserDB = Depends(require_staff)):
    """Create a new source entry."""
    try:
        return _create_source_in_db(source, conn)
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Eroare internă de server")

@app.get("/sources/", response_model=List[SourceDB])
def read_sources(conn: Connection = Depends(get_db_conn), _staff: UserDB = Depends(require_staff)):
    """Retrieve a list of all sources."""
    query = "SELECT id, name, type, year, session, profile, url_file_path, url_barem_path, notes, created_at FROM sources ORDER BY year DESC NULLS LAST, created_at DESC;"
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query)
        sources = cur.fetchall()
        return sources


@app.get("/sources/with-stats")
def read_sources_with_stats(conn: Connection = Depends(get_db_conn), _staff: UserDB = Depends(require_staff)):
    """Toate sursele CU statistici (segmente / exerciții / tag-uri) într-UN SINGUR query.
    Înlocuiește N+1-ul din SourceList (o cerere /stats per sursă → 250 cereri)."""
    query = """
    SELECT s.id, s.name, s.type, s.year, s.session, s.profile,
           s.url_file_path, s.url_barem_path, s.notes, s.created_at,
           COALESCE(seg.segments_count, 0)  AS segments_count,
           COALESCE(agg.exercises_count, 0) AS exercises_count,
           COALESCE(agg.tags_count, 0)      AS tags_count
    FROM sources s
    LEFT JOIN (
        SELECT source_id, COUNT(*) AS segments_count
        FROM source_segments
        GROUP BY source_id
    ) seg ON seg.source_id = s.id
    LEFT JOIN (
        SELECT ss.source_id,
               COUNT(DISTINCT e.id)      AS exercises_count,
               COUNT(DISTINCT et.tag_id) AS tags_count
        FROM source_segments ss
        JOIN exercise_source_segments ess ON ess.source_segment_id = ss.id
        JOIN exercises e                  ON e.id = ess.exercise_id
        LEFT JOIN exercise_tags et        ON et.exercise_id = e.id
        GROUP BY ss.source_id
    ) agg ON agg.source_id = s.id
    ORDER BY s.year DESC NULLS LAST, s.created_at DESC;
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query)
        return cur.fetchall()


@app.get("/sources/downloadable")
def read_downloadable_sources(conn: Connection = Depends(get_db_conn), _user: UserDB = Depends(get_current_user)):
    """Sursele descărcabile (au fișier) — biblioteca de subiecte BAC pentru elevi și profesori.
    Accesibil oricărui utilizator autentificat (subiectele BAC sunt publice)."""
    query = """
    SELECT id, name, type, year, session, profile,
           (url_barem_path IS NOT NULL) AS has_barem
    FROM sources
    WHERE url_file_path IS NOT NULL
    ORDER BY year DESC NULLS LAST, session NULLS LAST, name;
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query)
        return cur.fetchall()


@app.get("/sources/{source_id}", response_model=SourceDB)
def read_source(source_id: uuid.UUID, conn: Connection = Depends(get_db_conn), _staff: UserDB = Depends(require_staff)):
    """Retrieve a single source by ID."""
    query = "SELECT id, name, type, year, session, profile, url_file_path, url_barem_path, notes, created_at FROM sources WHERE id = %s;"
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query, (source_id,))
        source = cur.fetchone()
        if source is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
        return source

@app.get("/sources/{source_id}/download")
def download_source_file(source_id: uuid.UUID, conn: Connection = Depends(get_db_conn), _user: UserDB = Depends(get_current_user)):
    """Descarcă fișierul original al sursei (varianta)."""
    from fastapi.responses import FileResponse
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT name, url_file_path FROM sources WHERE id = %s", (source_id,))
        row = cur.fetchone()
    if not row or not row["url_file_path"]:
        raise HTTPException(status_code=404, detail="Fișier negăsit")
    path = row["url_file_path"]
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Fișierul nu există pe server")
    filename = os.path.basename(path)
    return FileResponse(path, media_type="application/pdf", filename=filename)


@app.get("/sources/{source_id}/download-barem")
def download_barem_file(source_id: uuid.UUID, conn: Connection = Depends(get_db_conn), _user: UserDB = Depends(get_current_user)):
    """Descarcă baremul sursei."""
    from fastapi.responses import FileResponse
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT name, url_barem_path FROM sources WHERE id = %s", (source_id,))
        row = cur.fetchone()
    if not row or not row["url_barem_path"]:
        raise HTTPException(status_code=404, detail="Baremul nu este disponibil")
    path = row["url_barem_path"]
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Fișierul nu există pe server")
    filename = os.path.basename(path)
    return FileResponse(path, media_type="application/pdf", filename=filename)


@app.get("/sources/{source_id}/stats")
def read_source_stats(source_id: uuid.UUID, conn: Connection = Depends(get_db_conn), _staff: UserDB = Depends(require_staff)) -> Dict[str, Any]:
    """
    Statistici agregate pentru o sursă:
    - segments_count
    - exercises_count (distinct)
    - tags_count (distinct)
    """
    with conn.cursor(row_factory=dict_row) as cur:
        # Segmente
        cur.execute(
            """
            SELECT COUNT(*)::int AS segments_count
            FROM source_segments
            WHERE source_id = %s
            """,
            (source_id,),
        )
        seg = cur.fetchone() or {"segments_count": 0}

        # Exerciții distinct (via exercise_source_segments -> source_segments)
        cur.execute(
            """
            SELECT COUNT(DISTINCT e.id)::int AS exercises_count
            FROM exercises e
            JOIN exercise_source_segments ess ON ess.exercise_id = e.id
            JOIN source_segments ss ON ss.id = ess.source_segment_id
            WHERE ss.source_id = %s
            """,
            (source_id,),
        )
        ex = cur.fetchone() or {"exercises_count": 0}

        # Tag-uri distinct asociate exercițiilor din sursă
        cur.execute(
            """
            SELECT COUNT(DISTINCT t.id)::int AS tags_count
            FROM tags t
            JOIN exercise_tags et ON et.tag_id = t.id
            JOIN exercises e ON e.id = et.exercise_id
            JOIN exercise_source_segments ess ON ess.exercise_id = e.id
            JOIN source_segments ss ON ss.id = ess.source_segment_id
            WHERE ss.source_id = %s
            """,
            (source_id,),
        )
        tg = cur.fetchone() or {"tags_count": 0}

        return {
            "source_id": str(source_id),
            "segments_count": seg["segments_count"],
            "exercises_count": ex["exercises_count"],
            "tags_count": tg["tags_count"],
        }

@app.get("/sources/{source_id}/exercises")
def read_source_exercises(source_id: uuid.UUID, conn: Connection = Depends(get_db_conn), _staff: UserDB = Depends(require_staff)):
    """
    Lista exercițiilor asociate unei surse (distinct).
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT DISTINCT
              e.id,
              e.exam_type,
              e.profile,
              e.subject_part,
              e.item_type,
              e.statement_text,
              e.statement_latex,
              e.points,
              e.difficulty,
              e.status,
              e.created_at
            FROM exercises e
            JOIN exercise_source_segments ess ON ess.exercise_id = e.id
            JOIN source_segments ss ON ss.id = ess.source_segment_id
            WHERE ss.source_id = %s
            ORDER BY e.created_at DESC
            """,
            (source_id,),
        )
        return cur.fetchall()
@app.put("/sources/{source_id}", response_model=SourceDB)
def update_source(source_id: uuid.UUID, source: SourceUpdate, conn: Connection = Depends(get_db_conn), _staff: UserDB = Depends(require_staff)):
    """Update an existing source."""
    updates = []
    values = []

    update_data = source.model_dump(exclude_unset=True)

    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided for update")

    for key, value in update_data.items():
        updates.append(f"{key} = %s")
        # Convert enum to value if needed
        if isinstance(value, SourceType):
            value = value.value
        values.append(value)

    values.append(source_id)

    query = f"""
    UPDATE sources SET {', '.join(updates)}
    WHERE id = %s
    RETURNING id, name, type, year, session, profile, url_file_path, url_barem_path, notes, created_at;
    """

    try:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, values)
            updated_source = cur.fetchone()
            conn.commit()
            if updated_source is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
            return updated_source
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Eroare internă de server")

@app.delete("/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_source(source_id: uuid.UUID, conn: Connection = Depends(get_db_conn), _staff: UserDB = Depends(require_staff)):
    """Delete a source by ID."""
    query = "DELETE FROM sources WHERE id = %s RETURNING id;"
    try:
        with conn.cursor() as cur:
            cur.execute(query, (source_id,))
            deleted_count = cur.rowcount
            conn.commit()
            if deleted_count == 0:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Eroare internă de server")

# --- File Upload and Mathpix Logic ---

@app.post("/upload-and-process/")
async def upload_and_process(
    file: UploadFile = File(...),
    source_name: str = Form("Uploaded Document"),
    source_type: str = Form("pdf"),
    source_year: Optional[int] = Form(None),
    source_session: Optional[str] = Form(None),
    source_profile: Optional[str] = Form(None),
    source_notes: Optional[str] = Form(None),
    barem_file: Optional[UploadFile] = File(None),
    conn: Connection = Depends(get_db_conn),
    _staff: UserDB = Depends(require_staff),
):
    """
    Uploads a PDF file, saves it locally, creates a Source entry,
    and initiates the Mathpix processing (placeholder for now).
    """
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed.")

    # 1. Save the file locally
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not save file: {e}")

    # 2. Save barem file if provided
    barem_path = None
    if barem_file and barem_file.filename:
        barem_path = os.path.join(UPLOAD_DIR, f"barem_{barem_file.filename}")
        try:
            with open(barem_path, "wb") as buf:
                shutil.copyfileobj(barem_file.file, buf)
        except Exception as e:
            barem_path = None

    # 3. Convert source_type string to SourceType enum
    try:
        type_enum = SourceType(source_type)
    except ValueError:
        type_enum = SourceType.PDF  # Default to PDF if invalid

    # 4. Create Source entry in DB with all fields
    source_data = SourceCreate(
        name=source_name,
        type=type_enum,
        year=source_year,
        session=source_session,
        profile=source_profile,
        notes=source_notes,
        url_file_path=file_path,
        url_barem_path=barem_path,
    )

    try:
        source_entry = _create_source_in_db(source_data, conn)
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail="Eroare internă de server")

    # 5. Process PDF with pix2text
    try:
        processor = get_pix2text_processor()

        # Process the entire PDF
        print(f"Starting pix2text processing for: {file_path}")
        page_results = processor.process_pdf(file_path)

        # Combine all pages into a single segment
        combined_text = processor.combine_segment_text(page_results)

        # Create a source segment for the entire document
        segment_data = SourceSegmentCreate(
            source_id=source_entry["id"] if isinstance(source_entry["id"], uuid.UUID) else uuid.UUID(source_entry["id"]),
            page_start=1,
            page_end=len(page_results),
            raw_extraction=combined_text,
            status=SegmentStatus.PROCESSED,
            extraction_method=ExtractionMethod.PIX2TEXT
        )

        # Save segment to database
        segment_query = """
        INSERT INTO source_segments (source_id, page_start, page_end, raw_extraction, status, extraction_method)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id, source_id, page_start, page_end, raw_extraction, status, extraction_method, created_at;
        """

        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(segment_query, (
                segment_data.source_id,
                segment_data.page_start,
                segment_data.page_end,
                segment_data.raw_extraction,
                segment_data.status.value,
                segment_data.extraction_method.value
            ))
            segment_entry = cur.fetchone()
            conn.commit()

        # 5. Extract individual exercises using AI
        _extract_and_save_exercises(
            combined_text=combined_text,
            context={
                "year": source_data.year,
                "session": source_data.session,
                "notes": source_data.notes
            },
            segment_id=segment_entry["id"] if isinstance(segment_entry["id"], uuid.UUID) else uuid.UUID(segment_entry["id"]),
            conn=conn
        )

        # Prepare response with processing results
        processing_pages = [
            ProcessingPageResult(
                page_number=page['page_number'],
                raw_text=page.get('raw_text', ''),
                latex_formulas=page.get('latex_formulas', []),
                width=page.get('width'),
                height=page.get('height'),
                error=page.get('error')
            )
            for page in page_results
        ]

        # Convert to UUID if they're strings, otherwise use as-is
        source_uuid = source_entry["id"] if isinstance(source_entry["id"], uuid.UUID) else uuid.UUID(source_entry["id"])
        segment_uuid = segment_entry["id"] if isinstance(segment_entry["id"], uuid.UUID) else uuid.UUID(segment_entry["id"])

        return ProcessingResult(
            source_id=source_uuid,
            segment_id=segment_uuid,
            pages=processing_pages,
            combined_text=combined_text,
            total_pages=len(page_results),
            status="success"
        )

    except Exception as e:
        print(f"Error processing PDF with pix2text: {e}")
        # Return partial success with error info
        return {
            "message": "File uploaded and source entry created, but processing failed.",
            "source_id": source_entry["id"],
            "file_path": file_path,
            "error": str(e),
            "status": "partial_success"
        }

@app.post("/upload-with-json/")
async def upload_with_json(
    file: UploadFile = File(...),
    json_data: str = Form(...),
    source_name: str = Form("Uploaded Document"),
    source_type: str = Form("pdf"),
    source_year: Optional[int] = Form(None),
    source_session: Optional[str] = Form(None),
    source_profile: Optional[str] = Form(None),
    source_notes: Optional[str] = Form(None),
    barem_file: Optional[UploadFile] = File(None),
    conn: Connection = Depends(get_db_conn),
    _staff: UserDB = Depends(require_staff),
):
    """
    Uploads a file and a JSON string containing structured exercise data.
    """
    import json
    try:
        data = json.loads(json_data)
        structured_data = StructuredImport(**data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON data: {e}")

    # 1. Save the file locally
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not save file: {e}")

    # 1b. Save barem file if provided
    barem_path = None
    if barem_file and barem_file.filename:
        barem_path = os.path.join(UPLOAD_DIR, f"barem_{barem_file.filename}")
        try:
            with open(barem_path, "wb") as buf:
                shutil.copyfileobj(barem_file.file, buf)
        except Exception:
            barem_path = None

    # 2. Create Source entry
    try:
        type_enum = SourceType(source_type)
    except ValueError:
        type_enum = SourceType.PDF

    source_data = SourceCreate(
        name=source_name,
        type=type_enum,
        year=source_year,
        session=source_session,
        profile=source_profile,
        notes=source_notes,
        url_file_path=file_path,
        url_barem_path=barem_path,
    )

    try:
        source_entry = _create_source_in_db(source_data, conn)
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail="Eroare internă de server")

    # 3. Create a source segment (as a container for exercises)
    segment_query = """
    INSERT INTO source_segments (source_id, page_start, page_end, raw_extraction, status, extraction_method)
    VALUES (%s, %s, %s, %s, %s, %s)
    RETURNING id;
    """
    try:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(segment_query, (
                source_entry["id"], 1, 1, "Manual JSON Import", 
                SegmentStatus.PROCESSED.value, ExtractionMethod.MANUAL.value
            ))
            segment_id = cur.fetchone()["id"]
            conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error creating segment: {e}")

    # 4. Save exercises and tags
    _save_structured_exercises(structured_data.exercises, segment_id, conn)

    return {
        "status": "success",
        "source_id": source_entry["id"],
        "exercises_imported": len(structured_data.exercises)
    }

# --- CRUD Operations for SOURCE SEGMENTS ---

@app.post("/source-segments/", response_model=SourceSegmentDB, status_code=status.HTTP_201_CREATED)
def create_source_segment(segment: SourceSegmentCreate, conn: Connection = Depends(get_db_conn), _staff: UserDB = Depends(require_staff)):
    """Create a new source segment entry."""
    query = """
    INSERT INTO source_segments (source_id, page_start, page_end, raw_extraction, checksum, status, extraction_method)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    RETURNING id, source_id, page_start, page_end, raw_extraction, checksum, status, extraction_method, created_at;
    """
    try:
        with conn.cursor(row_factory=dict_row) as cur:
            status_value = segment.status.value if hasattr(segment.status, 'value') else segment.status
            method_value = segment.extraction_method.value if hasattr(segment.extraction_method, 'value') else segment.extraction_method

            cur.execute(query, (
                segment.source_id, segment.page_start, segment.page_end,
                segment.raw_extraction, segment.checksum, status_value, method_value
            ))
            new_segment = cur.fetchone()
            conn.commit()
            return new_segment
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Eroare internă de server")

@app.get("/source-segments/", response_model=List[SourceSegmentDB])
def read_source_segments(
    source_id: Optional[uuid.UUID] = None,
    conn: Connection = Depends(get_db_conn),
    _staff: UserDB = Depends(require_staff),
):
    """Retrieve source segments, optionally filtered by source_id."""
    if source_id:
        query = """
        SELECT id, source_id, page_start, page_end, raw_extraction, checksum, status, extraction_method, created_at
        FROM source_segments WHERE source_id = %s ORDER BY page_start;
        """
        params = (source_id,)
    else:
        query = """
        SELECT id, source_id, page_start, page_end, raw_extraction, checksum, status, extraction_method, created_at
        FROM source_segments ORDER BY created_at DESC;
        """
        params = ()

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query, params)
        segments = cur.fetchall()
        return segments

@app.get("/source-segments/{segment_id}", response_model=SourceSegmentDB)
def read_source_segment(segment_id: uuid.UUID, conn: Connection = Depends(get_db_conn), _staff: UserDB = Depends(require_staff)):
    """Retrieve a single source segment by ID."""
    query = """
    SELECT id, source_id, page_start, page_end, raw_extraction, checksum, status, extraction_method, created_at
    FROM source_segments WHERE id = %s;
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query, (segment_id,))
        segment = cur.fetchone()
        if segment is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source segment not found")
        return segment

# --- PDF Processing Endpoint ---

@app.post("/process-pdf/{source_id}", response_model=ProcessingResult)
async def process_existing_pdf(
    source_id: uuid.UUID,
    page_start: Optional[int] = None,
    page_end: Optional[int] = None,
    conn: Connection = Depends(get_db_conn),
    _staff: UserDB = Depends(require_staff),
):
    """
    Process an already uploaded PDF using pix2text.
    Can optionally specify a page range to process.
    """
    # 1. Get the source from database
    query = "SELECT id, url_file_path, year, session, notes FROM sources WHERE id = %s;"
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query, (source_id,))
        source = cur.fetchone()

    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    pdf_path = source.get('url_file_path')
    if not pdf_path or not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="PDF file not found")

    try:
        processor = get_pix2text_processor()

        # Process PDF (either full or specific range)
        if page_start and page_end:
            print(f"Processing pages {page_start}-{page_end} of: {pdf_path}")
            page_results = processor.process_pdf_segment(pdf_path, page_start, page_end)
        else:
            print(f"Processing entire PDF: {pdf_path}")
            page_results = processor.process_pdf(pdf_path)
            page_start = 1
            page_end = len(page_results)

        # Combine text from all processed pages
        combined_text = processor.combine_segment_text(page_results)

        # Create a source segment entry
        segment_data = SourceSegmentCreate(
            source_id=source_id,
            page_start=page_start,
            page_end=page_end,
            raw_extraction=combined_text,
            status=SegmentStatus.PROCESSED,
            extraction_method=ExtractionMethod.PIX2TEXT
        )

        # Save to database
        segment_query = """
        INSERT INTO source_segments (source_id, page_start, page_end, raw_extraction, status, extraction_method)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id, source_id, page_start, page_end, raw_extraction, status, extraction_method, created_at;
        """

        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(segment_query, (
                segment_data.source_id,
                segment_data.page_start,
                segment_data.page_end,
                segment_data.raw_extraction,
                segment_data.status.value,
                segment_data.extraction_method.value
            ))
            segment_entry = cur.fetchone()
            conn.commit()

        # 5. Extract individual exercises using AI
        _extract_and_save_exercises(
            combined_text=combined_text,
            context={
                "year": source.get('year'),
                "session": source.get('session'),
                "notes": source.get('notes')
            },
            segment_id=segment_entry["id"] if isinstance(segment_entry["id"], uuid.UUID) else uuid.UUID(segment_entry["id"]),
            conn=conn
        )
        processing_pages = [
            ProcessingPageResult(
                page_number=page['page_number'],
                raw_text=page.get('raw_text', ''),
                latex_formulas=page.get('latex_formulas', []),
                width=page.get('width'),
                height=page.get('height'),
                error=page.get('error')
            )
            for page in page_results
        ]

        # Convert segment_id to UUID if it's a string
        segment_uuid = segment_entry["id"] if isinstance(segment_entry["id"], uuid.UUID) else uuid.UUID(segment_entry["id"])

        return ProcessingResult(
            source_id=source_id,
            segment_id=segment_uuid,
            pages=processing_pages,
            combined_text=combined_text,
            total_pages=len(page_results),
            status="success"
        )

    except Exception as e:
        conn.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error processing PDF: {str(e)}"
        )

# --- JSON Import Endpoint ---

@app.post("/import-json/")
async def import_json_endpoint(
    json_file: UploadFile = File(...),
    include_containers: bool = Form(True),
    varianta_file: Optional[UploadFile] = File(None),
    barem_file: Optional[UploadFile] = File(None),
    conn: Connection = Depends(get_db_conn),
    _staff: UserDB = Depends(require_staff),
):
    """
    Upload și procesare fișier JSON cu exerciții.

    Suportă automat două formate:
    - LEGACY: exercises[] plate cu tag_catalog[]
    - IERARHIC: exercises[] grupate cu subpoints[] nested

    Opțional: varianta_file și barem_file — PDF-uri atașate sursei create.
    """
    import json as json_mod

    if not json_file.filename.lower().endswith('.json'):
        raise HTTPException(status_code=400, detail="Doar fișiere JSON sunt acceptate")

    try:
        content = await json_file.read()
        try:
            data = json_mod.loads(content)
        except json_mod.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"JSON invalid: {e}")

        if 'source' not in data:
            raise HTTPException(status_code=400, detail="JSON lipsește cheia: source")
        if 'exercises' not in data:
            raise HTTPException(status_code=400, detail="JSON lipsește cheia: exercises")

        # Salvează PDF-urile dacă au fost trimise
        varianta_path = None
        barem_path = None

        if varianta_file and varianta_file.filename:
            varianta_path = os.path.join(UPLOAD_DIR, varianta_file.filename)
            with open(varianta_path, "wb") as f:
                shutil.copyfileobj(varianta_file.file, f)

        if barem_file and barem_file.filename:
            barem_path = os.path.join(UPLOAD_DIR, f"barem_{barem_file.filename}")
            with open(barem_path, "wb") as f:
                shutil.copyfileobj(barem_file.file, f)

        # Dacă avem varianta PDF, suprascrie url_file_path din JSON
        if varianta_path:
            data['source']['url_file_path'] = varianta_path
        if barem_path:
            data['source']['url_barem_path'] = barem_path

        # Folosește noul importer unificat (detectează automat formatul)
        importer = JSONImporter(json_data=data, include_containers=include_containers, conn=conn)

        try:
            stats = importer.run()
            conn.commit()
            return {
                "status": "success",
                "message": f"Import finalizat pentru {json_file.filename}",
                "statistics": stats,
                "has_varianta": varianta_path is not None,
                "has_barem": barem_path is not None,
            }
        except Exception as e:
            conn.rollback()
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Eroare la import: {str(e)}")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Eroare: {str(e)}")

# --- Hierarchical Import Endpoint ---

@app.post("/import-hierarchical/")
async def import_hierarchical_endpoint(
    json_file: UploadFile = File(...),
    conn: Connection = Depends(get_db_conn),
    _staff: UserDB = Depends(require_staff),
):
    """
    Import ierarhic de exerciții cu subpuncte nested.

    Formatul JSON trebuie să conțină:
    - source: date despre sursa PDF
    - exercises: lista de exerciții cu `subiect`, `exercise_num`, opțional `subpoints[]`

    Auto-generează tag-uri de poziție: subiect, exercise, subpoint, path, year, session
    Exercițiile cu subpoints se desfac în container + copii individuali.
    """
    import json as json_mod
    import tempfile

    if not json_file.filename.lower().endswith('.json'):
        raise HTTPException(status_code=400, detail="Doar fișiere JSON sunt acceptate")

    try:
        content = await json_file.read()
        try:
            data = json_mod.loads(content)
        except json_mod.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"JSON invalid: {e}")

        # Validare minimă
        if 'source' not in data:
            raise HTTPException(status_code=400, detail="JSON lipsește cheia: source")
        if 'exercises' not in data:
            raise HTTPException(status_code=400, detail="JSON lipsește cheia: exercises")

        # Rulează importul ierarhic
        importer = JSONImporter(json_data=data, include_containers=True, conn=conn)

        try:
            stats = importer.run()
            conn.commit()
            return {
                "status": "success",
                "format": "hierarchical",
                "message": f"Import finalizat pentru {json_file.filename}",
                "statistics": stats
            }
        except Exception as e:
            conn.rollback()
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Eroare la import: {str(e)}")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Eroare la procesarea fișierului: {str(e)}")

# # NOTIFICĂRI

@app.get("/notifications/", response_model=List[NotificationDB], tags=["Notifications"])
def get_notifications(
    current_user: UserDB = Depends(get_current_user),
    conn: Connection = Depends(get_db_conn),
):
    """Returnează notificările utilizatorului curent (neacceptate primele)."""
    with conn.cursor(row_factory=dict_row) as cur:
        if current_user.role in (UserRole.STUDENT, UserRole.SCHOOL_TEACHER) and datetime.now().weekday() == 4:
            cur.execute(
                "SELECT COUNT(*) as cnt FROM exercise_review_items WHERE student_id=%s AND status='open'",
                (str(current_user.id),),
            )
            review_count = cur.fetchone()["cnt"]

            if review_count > 0:
                cur.execute(
                    """
                    SELECT 1 FROM notifications
                    WHERE user_id=%s AND type='review_reminder' AND DATE(created_at)=CURRENT_DATE
                    """,
                    (str(current_user.id),),
                )
                already_sent = cur.fetchone()
                if not already_sent:
                    cur.execute(
                        """
                        INSERT INTO notifications (user_id, type, title, body, related_id)
                        VALUES (%s, 'review_reminder', %s, %s, NULL)
                        """,
                        (
                            str(current_user.id),
                            "Vineri de revizuire",
                            f"Ai {review_count} exerciții nerezolvate de revăzut.",
                        ),
                    )
                    conn.commit()

        cur.execute(
            """
            SELECT id, user_id, type, title, body, is_read, related_id, created_at
            FROM notifications
            WHERE user_id = %s
            ORDER BY is_read ASC, created_at DESC
            LIMIT 50
            """,
            (str(current_user.id),),
        )
        return [NotificationDB(**r) for r in cur.fetchall()]

@app.put("/notifications/{notif_id}/read", tags=["Notifications"])
def mark_notification_read(
    notif_id: uuid.UUID,
    current_user: UserDB = Depends(get_current_user),
    conn: Connection = Depends(get_db_conn),
):
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE notifications SET is_read = TRUE WHERE id = %s AND user_id = %s",
            (str(notif_id), str(current_user.id)),
        )
        conn.commit()
    return {"ok": True}

@app.put("/notifications/read-all", tags=["Notifications"])
def mark_all_notifications_read(
    current_user: UserDB = Depends(get_current_user),
    conn: Connection = Depends(get_db_conn),
):
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE notifications SET is_read = TRUE WHERE user_id = %s",
            (str(current_user.id),),
        )
        conn.commit()
    return {"ok": True}

# # TEACHER STATS

@app.get("/teacher/stats", response_model=TeacherStats, tags=["Teacher"])
def teacher_stats(
    teacher_id: Optional[str] = None,
    current_user: UserDB = Depends(require_role(UserRole.TEACHER, UserRole.SCHOOL_TEACHER, UserRole.ADMIN)),
    conn: Connection = Depends(get_db_conn),
):
    """
    Statistici pentru profesor.
    - Profesor: vede propriile statistici (fără timp mediu).
    - Admin: poate pasa teacher_id pentru a vedea statisticile oricărui profesor
      și vede și timpul mediu de răspuns.
    """
    is_admin = current_user.role == UserRole.ADMIN

    # Determină pentru ce profesor se calculează statisticile
    if is_admin and teacher_id:
        target_id = teacher_id
    else:
        target_id = str(current_user.id)

    with conn.cursor(row_factory=dict_row) as cur:
        # Total per status (doar cererile asignate profesorului)
        cur.execute(
            """
            SELECT status, COUNT(*) as cnt
            FROM help_requests
            WHERE assigned_teacher_id = %s
            GROUP BY status
            """,
            (target_id,),
        )
        status_counts = {r["status"]: r["cnt"] for r in cur.fetchall()}

        # Cereri neasignate (pending fără profesor)
        cur.execute("SELECT COUNT(*) as cnt FROM help_requests WHERE status = 'pending' AND assigned_teacher_id IS NULL")
        unassigned_pending = (cur.fetchone() or {}).get("cnt", 0)

        # Total per tip (cereri asignate)
        cur.execute(
            """
            SELECT flag_type, COUNT(*) as cnt
            FROM help_requests
            WHERE assigned_teacher_id = %s
            GROUP BY flag_type
            """,
            (target_id,),
        )
        type_counts = {r["flag_type"]: r["cnt"] for r in cur.fetchall()}

        # Timp mediu de răspuns — doar pentru admin
        avg_hours = None
        if is_admin:
            cur.execute(
                """
                SELECT AVG(EXTRACT(EPOCH FROM (hr2.created_at - hr.created_at)) / 3600) as avg_hours
                FROM help_requests hr
                JOIN help_responses hr2 ON hr2.request_id = hr.id
                WHERE hr2.teacher_id = %s
                """,
                (target_id,),
            )
            avg_row = cur.fetchone()
            avg_hours = round(avg_row["avg_hours"], 1) if avg_row and avg_row["avg_hours"] else None

    total = sum(status_counts.values())
    return TeacherStats(
        total_requests=total,
        pending=status_counts.get("pending", 0) + int(unassigned_pending),
        assigned=status_counts.get("assigned", 0),
        resolved=status_counts.get("resolved", 0),
        by_type=type_counts,
        avg_response_hours=avg_hours,
    )

# =============================================================================
# --- Exercise Completion ---
# =============================================================================

@app.post("/exercises/{exercise_id}/complete", tags=["Student"])
def mark_exercise_complete(
    exercise_id: str,
    conn: Connection = Depends(get_db_conn),
    current_user=Depends(get_current_user),
):
    """Elevul marchează un exercițiu ca rezolvat (toggle)."""
    if current_user.role not in (UserRole.STUDENT, UserRole.SCHOOL_TEACHER):
        raise HTTPException(status_code=403, detail="Doar elevii pot marca exerciții")

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT id, completed FROM student_progress WHERE student_id=%s AND exercise_id=%s",
            (str(current_user.id), exercise_id),
        )
        row = cur.fetchone()
        if row:
            new_val = not row["completed"]
            cur.execute(
                "UPDATE student_progress SET completed=%s, completed_at=%s WHERE id=%s",
                (new_val, datetime.now() if new_val else None, str(row["id"])),
            )
        else:
            new_val = True
            cur.execute(
                """INSERT INTO student_progress (student_id, exercise_id, completed, completed_at)
                   VALUES (%s, %s, TRUE, NOW())
                   ON CONFLICT (student_id, exercise_id) DO UPDATE
                   SET completed=TRUE, completed_at=NOW()""",
                (str(current_user.id), exercise_id),
            )

        # Acordă XP dacă marchează ca rezolvat (nu la unmark)
        xp_gained = 0
        new_badges = []
        if new_val:
            _resolve_review_item(conn, str(current_user.id), exercise_id)
            # XP bazat pe dificultate exercițiu
            cur.execute("SELECT difficulty, metadata FROM exercises WHERE id=%s", (exercise_id,))
            ex_row = cur.fetchone()
            difficulty = (ex_row["difficulty"] or 5) if ex_row else 5
            xp_gained = max(10, difficulty * 15)

            # Streak bonus +20% dacă streak >= 3
            cur.execute(
                "SELECT streak_current, last_active_date FROM student_gamification WHERE user_id=%s",
                (str(current_user.id),),
            )
            gam = cur.fetchone()
            today = datetime.now().date()

            if gam:
                last_date = gam["last_active_date"]
                streak = gam["streak_current"]
                if last_date == today:
                    pass  # deja activ azi, streak rămâne
                elif last_date and (today - last_date).days == 1:
                    streak += 1  # zi consecutivă
                else:
                    streak = 1  # restart streak
                if streak >= 3:
                    xp_gained = int(xp_gained * 1.2)
                cur.execute(
                    """UPDATE student_gamification
                       SET xp_total = xp_total + %s,
                           streak_current = %s,
                           streak_max = GREATEST(streak_max, %s),
                           last_active_date = %s,
                           updated_at = NOW()
                       WHERE user_id = %s""",
                    (xp_gained, streak, streak, today, str(current_user.id)),
                )
                new_xp_total = gam["xp_total"] + xp_gained if "xp_total" in gam else xp_gained
            else:
                streak = 1
                cur.execute(
                    """INSERT INTO student_gamification (user_id, xp_total, streak_current, streak_max, last_active_date)
                       VALUES (%s, %s, 1, 1, %s)""",
                    (str(current_user.id), xp_gained, today),
                )
                cur.execute("SELECT xp_total FROM student_gamification WHERE user_id=%s", (str(current_user.id),))
                new_xp_total = (cur.fetchone() or {}).get("xp_total", xp_gained)

            # Log XP
            cur.execute(
                "INSERT INTO xp_log (user_id, xp_gained, reason, reference_id) VALUES (%s, %s, %s, %s)",
                (str(current_user.id), xp_gained, "exercise_completed", exercise_id),
            )

            # Verifică insigne noi
            cur.execute("SELECT badge_key FROM student_badges WHERE user_id=%s", (str(current_user.id),))
            existing_badges = {r["badge_key"] for r in cur.fetchall()}

            cur.execute("SELECT COUNT(*) as cnt FROM student_progress WHERE student_id=%s AND completed=TRUE", (str(current_user.id),))
            total_completed = cur.fetchone()["cnt"]

            cur.execute(
                """SELECT e.metadata->>'subiect' as subiect FROM student_progress sp
                   JOIN exercises e ON e.id=sp.exercise_id
                   WHERE sp.student_id=%s AND sp.completed=TRUE AND e.metadata IS NOT NULL""",
                (str(current_user.id),),
            )
            completed_subiects = {r["subiect"] for r in cur.fetchall() if r["subiect"]}

            cur.execute("SELECT xp_total FROM student_gamification WHERE user_id=%s", (str(current_user.id),))
            xp_row = cur.fetchone()
            current_xp = xp_row["xp_total"] if xp_row else xp_gained

            to_check = [
                ("first_exercise",  total_completed >= 1),
                ("exercises_10",    total_completed >= 10),
                ("exercises_50",    total_completed >= 50),
                ("exercises_100",   total_completed >= 100),
                ("first_s1",        "1" in completed_subiects),
                ("first_s2",        "2" in completed_subiects),
                ("first_s3",        "3" in completed_subiects),
                ("streak_3",        streak >= 3),
                ("streak_5",        streak >= 5),
                ("streak_7",        streak >= 7),
                ("streak_14",       streak >= 14),
                ("streak_30",       streak >= 30),
                ("xp_500",          current_xp >= 500),
                ("xp_1000",         current_xp >= 1000),
                ("xp_3000",         current_xp >= 3000),
            ]
            for badge_key, condition in to_check:
                if condition and badge_key not in existing_badges:
                    cur.execute(
                        "INSERT INTO student_badges (user_id, badge_key) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                        (str(current_user.id), badge_key),
                    )
                    new_badges.append(badge_key)
        else:
            _upsert_review_item(conn, str(current_user.id), exercise_id, "marked_unresolved")

        conn.commit()
    return {"exercise_id": exercise_id, "completed": new_val, "xp_gained": xp_gained, "new_badges": new_badges}


@app.get("/exercises/{exercise_id}/complete", tags=["Student"])
def get_exercise_complete_status(
    exercise_id: str,
    conn: Connection = Depends(get_db_conn),
    current_user=Depends(get_current_user),
):
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT completed FROM student_progress WHERE student_id=%s AND exercise_id=%s",
            (str(current_user.id), exercise_id),
        )
        row = cur.fetchone()
    return {"exercise_id": exercise_id, "completed": row["completed"] if row else False}


@app.get("/student/completed-exercise-ids", tags=["Student"])
def get_completed_exercise_ids(
    conn: Connection = Depends(get_db_conn),
    current_user=Depends(get_current_user),
):
    """Returnează lista de id-uri de exerciții marcate rezolvate de utilizatorul curent."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT exercise_id FROM student_progress WHERE student_id=%s AND completed=TRUE",
            (str(current_user.id),),
        )
        rows = cur.fetchall()
    return [str(r[0]) for r in rows]


@app.get("/student/pending-exercise-ids", tags=["Student"])
def get_pending_exercise_ids(
    conn: Connection = Depends(get_db_conn),
    current_user=Depends(get_current_user),
):
    """Returnează id-urile exercițiilor cu soluție trimisă dar neverificată de profesor."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT exercise_id FROM exercise_submissions WHERE user_id=%s AND teacher_status='pending'",
            (str(current_user.id),),
        )
        rows = cur.fetchall()
    return [str(r[0]) for r in rows]

# =============================================================================
# --- Gamification Endpoints ---
# =============================================================================

@app.get("/student/gamification", response_model=GamificationProfile, tags=["Student"])
def get_my_gamification(
    conn: Connection = Depends(get_db_conn),
    current_user=Depends(get_current_user),
):
    """Returnează profilul de gamification al utilizatorului curent."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT xp_total, streak_current, streak_max, last_active_date FROM student_gamification WHERE user_id=%s",
            (str(current_user.id),),
        )
        gam = cur.fetchone()
        if not gam:
            gam = {"xp_total": 0, "streak_current": 0, "streak_max": 0, "last_active_date": None}

        cur.execute(
            "SELECT badge_key, earned_at FROM student_badges WHERE user_id=%s ORDER BY earned_at DESC",
            (str(current_user.id),),
        )
        badge_rows = cur.fetchall()

    badges = []
    for row in badge_rows:
        meta = BADGES.get(row["badge_key"], {})
        badges.append({
            "key": row["badge_key"],
            "label": meta.get("label", row["badge_key"]),
            "icon": meta.get("icon", "🏅"),
            "desc": meta.get("desc", ""),
            "earned_at": row["earned_at"].isoformat() if row["earned_at"] else None,
        })

    return GamificationProfile(
        xp_total=gam["xp_total"],
        streak_current=gam["streak_current"],
        streak_max=gam["streak_max"],
        last_active_date=str(gam["last_active_date"]) if gam["last_active_date"] else None,
        level=get_level(gam["xp_total"]),
        badges=badges,
    )


@app.get("/student/gamification/{student_id}", response_model=GamificationProfile, tags=["Student"])
def get_student_gamification(
    student_id: str,
    conn: Connection = Depends(get_db_conn),
    current_user=Depends(get_current_user),
):
    """Returnează profilul de gamification al unui elev — pentru părinte sau admin."""
    if current_user.role == UserRole.PARENT:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM parent_student WHERE parent_id=%s AND student_id=%s",
                (str(current_user.id), student_id),
            )
            if not cur.fetchone():
                raise HTTPException(status_code=403, detail="Acces interzis")
    elif current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Acces interzis")

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT xp_total, streak_current, streak_max, last_active_date FROM student_gamification WHERE user_id=%s",
            (student_id,),
        )
        gam = cur.fetchone()
        if not gam:
            gam = {"xp_total": 0, "streak_current": 0, "streak_max": 0, "last_active_date": None}

        cur.execute(
            "SELECT badge_key, earned_at FROM student_badges WHERE user_id=%s ORDER BY earned_at DESC",
            (student_id,),
        )
        badge_rows = cur.fetchall()

    badges = []
    for row in badge_rows:
        meta = BADGES.get(row["badge_key"], {})
        badges.append({
            "key": row["badge_key"],
            "label": meta.get("label", row["badge_key"]),
            "icon": meta.get("icon", "🏅"),
            "desc": meta.get("desc", ""),
            "earned_at": row["earned_at"].isoformat() if row["earned_at"] else None,
        })

    return GamificationProfile(
        xp_total=gam["xp_total"],
        streak_current=gam["streak_current"],
        streak_max=gam["streak_max"],
        last_active_date=str(gam["last_active_date"]) if gam["last_active_date"] else None,
        level=get_level(gam["xp_total"]),
        badges=badges,
    )


# =============================================================================
# --- Exercise Submissions (autoevaluare + foto + corecție profesor) ---
# =============================================================================



@app.post("/exercises/{exercise_id}/submit", response_model=ExerciseSubmissionDB, tags=["Student"])
async def submit_exercise(
    exercise_id: str,
    body: ExerciseSubmitRequest,
    conn: Connection = Depends(get_db_conn),
    current_user=Depends(get_current_user),
):
    """
    Pasul 1: Elevul trimite autoevaluarea (failed/partial/complete).
    Primește 10% din XP-ul de bază imediat.
    """
    if current_user.role not in (UserRole.STUDENT, UserRole.SCHOOL_TEACHER):
        raise HTTPException(status_code=403, detail="Doar elevii pot trimite soluții")

    with conn.cursor(row_factory=dict_row) as cur:
        # XP de bază
        cur.execute("SELECT difficulty FROM exercises WHERE id=%s", (exercise_id,))
        ex = cur.fetchone()
        if not ex:
            raise HTTPException(status_code=404, detail="Exercițiu inexistent")
        base_xp = _calc_base_xp(ex["difficulty"] or 5)
        xp_self = max(1, round(base_xp * 0.10))

        # Upsert submission
        cur.execute(
            """INSERT INTO exercise_submissions
                   (user_id, exercise_id, self_eval, teacher_status, xp_self_eval)
               VALUES (%s, %s, %s, 'pending', %s)
               ON CONFLICT (user_id, exercise_id) DO UPDATE
               SET self_eval = EXCLUDED.self_eval,
                   teacher_status = CASE
                       WHEN exercise_submissions.teacher_status IS NULL THEN 'pending'
                       ELSE exercise_submissions.teacher_status END,
                   updated_at = NOW()
               RETURNING *""",
            (str(current_user.id), exercise_id, body.self_eval, xp_self),
        )
        row = cur.fetchone()

        # Acordă XP self_eval doar dacă e prima dată
        xp_awarded = _award_xp(conn, str(current_user.id), xp_self, "self_eval", exercise_id)

        # NU marcăm completed în student_progress — asta se face la aprobare profesor
        # Marcăm în review_items ca să fie vizibil în lista de revăzut
        _upsert_review_item(conn, str(current_user.id), exercise_id, body.self_eval.value)
        conn.commit()

    return ExerciseSubmissionDB(**row)


@app.post("/exercises/{exercise_id}/submit-photo", tags=["Student"])
async def upload_submission_photo(
    exercise_id: str,
    photo: UploadFile = File(...),
    conn: Connection = Depends(get_db_conn),
    current_user=Depends(get_current_user),
):
    """
    Pasul 2 (opțional): Elevul încarcă fotografie sau PDF cu soluția.
    Primește +40% din XP-ul de bază (total 50%).
    """
    if current_user.role not in (UserRole.STUDENT, UserRole.SCHOOL_TEACHER):
        raise HTTPException(status_code=403, detail="Doar elevii pot încărca soluții")

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT id, xp_photo FROM exercise_submissions WHERE user_id=%s AND exercise_id=%s",
            (str(current_user.id), exercise_id),
        )
        sub = cur.fetchone()
        if not sub:
            raise HTTPException(status_code=400, detail="Trimite mai întâi autoevaluarea")

        # Salvează fișier (imagine sau PDF)
        original_name = photo.filename or "solution.jpg"
        ext = os.path.splitext(original_name)[1].lower() or ".jpg"
        allowed_exts = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".pdf"}
        if ext not in allowed_exts:
            raise HTTPException(status_code=400, detail="Tipul de fișier nu este acceptat. Folosește imagine sau PDF.")
        filename = f"submission_{current_user.id}_{exercise_id}{ext}"
        photo_dir = os.path.join(UPLOAD_DIR, "submissions")
        os.makedirs(photo_dir, exist_ok=True)
        photo_path_disk = os.path.join(photo_dir, filename)
        photo_url = f"/uploads/submissions/{filename}"
        with open(photo_path_disk, "wb") as f:
            shutil.copyfileobj(photo.file, f)

        # XP foto — doar dacă nu a mai primit foto XP
        cur.execute("SELECT difficulty, statement_text FROM exercises WHERE id=%s", (exercise_id,))
        ex = cur.fetchone()
        base_xp = _calc_base_xp((ex["difficulty"] or 5) if ex else 5)
        xp_photo = max(1, round(base_xp * 0.40))
        extra_xp = xp_photo if sub["xp_photo"] == 0 else 0

        cur.execute(
            """UPDATE exercise_submissions
               SET photo_path=%s, photo_uploaded_at=NOW(), xp_photo=%s, teacher_status='pending', updated_at=NOW()
               WHERE user_id=%s AND exercise_id=%s RETURNING *""",
            (photo_url, xp_photo, str(current_user.id), exercise_id),
        )
        row = cur.fetchone()
        submission_id = str(row["id"])

        if extra_xp > 0:
            _award_xp(conn, str(current_user.id), extra_xp, "photo_upload", exercise_id)

        # Notifică toți profesorii / adminii că există o nouă soluție de corectat
        cur.execute(
            "SELECT id FROM users WHERE role IN ('teacher', 'admin') AND is_active = TRUE"
        )
        teachers = cur.fetchall()
        ex_short = ((ex["statement_text"] or "")[:60] + "…") if ex and ex.get("statement_text") else "exercițiu"
        for t in teachers:
            cur.execute(
                """INSERT INTO notifications (user_id, type, title, body, related_id)
                   VALUES (%s, 'new_submission', %s, %s, %s)
                   ON CONFLICT DO NOTHING""",
                (
                    str(t["id"]),
                    "Soluție nouă de corectat",
                    f"{current_user.full_name} a trimis o soluție: {ex_short}",
                    submission_id,
                ),
            )

        conn.commit()

    return {"status": "ok", "photo_path": photo_url, "xp_awarded": extra_xp}


@app.get("/exercises/{exercise_id}/submission", tags=["Student"])
def get_my_submission(
    exercise_id: str,
    conn: Connection = Depends(get_db_conn),
    current_user=Depends(get_current_user),
):
    """Statusul submisiei curente a elevului pentru un exercițiu."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT * FROM exercise_submissions WHERE user_id=%s AND exercise_id=%s",
            (str(current_user.id), exercise_id),
        )
        row = cur.fetchone()
    if not row:
        return None
    return ExerciseSubmissionDB(**row)


@app.get("/student/submissions", tags=["Student"])
def get_my_submissions(
    conn: Connection = Depends(get_db_conn),
    current_user=Depends(get_current_user),
):
    """Lista tuturor submisiilor elevului curent."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """SELECT es.*, e.statement_text, e.statement_latex
               FROM exercise_submissions es
               JOIN exercises e ON e.id = es.exercise_id
               WHERE es.user_id=%s ORDER BY es.created_at DESC""",
            (str(current_user.id),),
        )
        return cur.fetchall()


@app.get("/student/review-items", tags=["Student"])
def get_review_items(
    conn: Connection = Depends(get_db_conn),
    current_user=Depends(get_current_user),
):
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT
                ri.id,
                ri.exercise_id,
                ri.source_reason,
                ri.fail_count,
                ri.revisit_count,
                ri.first_flagged_at,
                ri.last_flagged_at,
                e.exam_type,
                e.profile,
                e.subject_part,
                e.item_type,
                e.statement_latex,
                e.statement_text,
                e.answer_latex,
                e.solution_latex,
                e.scoring_guide_latex,
                e.scoring_guide_text,
                e.difficulty,
                e.estimated_time_sec,
                e.points,
                e.metadata,
                e.status,
                e.created_at,
                e.updated_at
            FROM exercise_review_items ri
            JOIN exercises e ON e.id = ri.exercise_id
            WHERE ri.student_id=%s AND ri.status='open'
            ORDER BY ri.last_flagged_at DESC
            """,
            (str(current_user.id),),
        )
        return cur.fetchall()


# =============================================================================
# --- Teacher: Verificare soluții (doar EtoX teachers + admin) ---
# =============================================================================

@app.get("/teacher/submissions", tags=["Teacher"])
def get_pending_submissions(
    status: Optional[str] = "pending",
    conn: Connection = Depends(get_db_conn),
    current_user=Depends(get_current_user),
):
    """Lista submisiilor care așteaptă corecție — doar profesori EtoX și admin."""
    if current_user.role not in (UserRole.TEACHER, UserRole.SCHOOL_TEACHER, UserRole.ADMIN):
        raise HTTPException(status_code=403, detail="Acces interzis")

    with conn.cursor(row_factory=dict_row) as cur:
        query = """
            SELECT es.id, es.user_id, u.full_name as student_name, u.email as student_email,
                   es.exercise_id, e.statement_text as exercise_statement,
                   e.statement_latex as exercise_statement_latex, e.difficulty,
                   es.self_eval, es.photo_path, es.teacher_status, es.teacher_note,
                   es.teacher_file_path, es.assigned_teacher_id,
                   es.xp_self_eval, es.xp_photo, es.xp_teacher,
                   es.created_at, es.reviewed_at,
                   rv.full_name as reviewer_name,
                   at.full_name as assigned_teacher_name
            FROM exercise_submissions es
            JOIN users u ON u.id = es.user_id
            JOIN exercises e ON e.id = es.exercise_id
            LEFT JOIN users rv ON rv.id = es.reviewed_by
            LEFT JOIN users at ON at.id = es.assigned_teacher_id
        """
        params = []
        conditions = []

        if current_user.role != UserRole.ADMIN:
            if status == "pending":
                conditions.append("(es.teacher_status = 'pending' AND (es.assigned_teacher_id = %s OR es.assigned_teacher_id IS NULL))")
                params.append(str(current_user.id))
            elif status in ("correct", "incorrect"):
                conditions.append("es.teacher_status = %s")
                params.append(status)
                conditions.append("(es.reviewed_by = %s OR es.assigned_teacher_id = %s)")
                params.extend([str(current_user.id), str(current_user.id)])
            elif status and status != "all":
                conditions.append("es.teacher_status = %s")
                params.append(status)
                conditions.append("(es.assigned_teacher_id = %s OR es.reviewed_by = %s)")
                params.extend([str(current_user.id), str(current_user.id)])
            else:
                conditions.append(
                    "((es.teacher_status = 'pending' AND (es.assigned_teacher_id = %s OR es.assigned_teacher_id IS NULL)) "
                    "OR (es.teacher_status IN ('correct', 'incorrect') AND (es.reviewed_by = %s OR es.assigned_teacher_id = %s)))"
                )
                params.extend([str(current_user.id), str(current_user.id), str(current_user.id)])
        elif status and status != "all":
            conditions.append("es.teacher_status = %s")
            params.append(status)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY es.created_at ASC"
        cur.execute(query, params)
        return cur.fetchall()


@app.post("/teacher/submissions/assign-pending", tags=["Teacher"])
def assign_pending_submissions(
    conn: Connection = Depends(get_db_conn),
    current_user=Depends(get_current_user),
):
    """Profesorul preia toate submisiile fără profesor atribuit."""
    if current_user.role not in (UserRole.TEACHER, UserRole.SCHOOL_TEACHER, UserRole.ADMIN):
        raise HTTPException(status_code=403, detail="Acces interzis")

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """UPDATE exercise_submissions
               SET assigned_teacher_id=%s, updated_at=NOW()
               WHERE teacher_status='pending' AND assigned_teacher_id IS NULL
               RETURNING id""",
            (str(current_user.id),),
        )
        rows = cur.fetchall()
        conn.commit()

    return {"assigned": len(rows)}


@app.post("/teacher/submissions/{submission_id}/review", tags=["Teacher"])
def review_submission(
    submission_id: str,
    body: TeacherReviewRequest,
    conn: Connection = Depends(get_db_conn),
    current_user=Depends(get_current_user),
):
    """Profesorul EtoX marchează submisia ca corectă sau incorectă."""
    if current_user.role not in (UserRole.TEACHER, UserRole.SCHOOL_TEACHER, UserRole.ADMIN):
        raise HTTPException(status_code=403, detail="Acces interzis")

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT * FROM exercise_submissions WHERE id=%s",
            (submission_id,),
        )
        sub = cur.fetchone()
        if not sub:
            raise HTTPException(status_code=404, detail="Submisie inexistentă")

        cur.execute("SELECT difficulty FROM exercises WHERE id=%s", (str(sub["exercise_id"]),))
        ex = cur.fetchone()
        base_xp = _calc_base_xp((ex["difficulty"] or 5) if ex else 5)

        xp_teacher = 0
        if body.status == TeacherReviewStatus.CORRECT and sub["xp_teacher"] == 0:
            # Acordă XP complet la aprobare (100% din baza)
            xp_teacher = max(10, base_xp)
            _award_xp(conn, str(sub["user_id"]), xp_teacher, "teacher_correct", str(sub["exercise_id"]))

            # Marchează exercițiul ca rezolvat în student_progress
            cur.execute(
                """INSERT INTO student_progress (student_id, exercise_id, completed, completed_at, last_seen_at)
                   VALUES (%s, %s, TRUE, NOW(), NOW())
                   ON CONFLICT (student_id, exercise_id) DO UPDATE
                   SET completed=TRUE, completed_at=NOW(), last_seen_at=NOW()""",
                (str(sub["user_id"]), str(sub["exercise_id"])),
            )
            _resolve_review_item(conn, str(sub["user_id"]), str(sub["exercise_id"]))

        cur.execute(
            """UPDATE exercise_submissions
               SET teacher_status=%s, reviewed_by=%s, reviewed_at=NOW(),
                   teacher_note=%s, xp_teacher=%s, updated_at=NOW()
               WHERE id=%s RETURNING *""",
            (body.status, str(current_user.id), body.note, xp_teacher, submission_id),
        )
        row = cur.fetchone()

        is_correct = body.status == TeacherReviewStatus.CORRECT
        notif_title = "Soluție aprobată ✅" if is_correct else "Soluție incorectă ❌"
        notif_body = f"{'Exercițiul a fost marcat ca rezolvat' if is_correct else 'Soluția ta este incorectă — poți retrimite'}."
        if body.note:
            notif_body += f" Notă: {body.note}"
        if xp_teacher > 0:
            notif_body += f" +{xp_teacher} XP!"
        cur.execute(
            """INSERT INTO notifications (user_id, type, title, body, related_id)
               VALUES (%s, 'submission_reviewed', %s, %s, %s)""",
            (str(sub["user_id"]), notif_title, notif_body, submission_id),
        )

        conn.commit()

    return row


@app.post("/teacher/submissions/{submission_id}/upload-file", tags=["Teacher"])
async def upload_teacher_file(
    submission_id: str,
    file: UploadFile = File(...),
    conn: Connection = Depends(get_db_conn),
    current_user=Depends(get_current_user),
):
    """Profesorul încarcă un fișier (PDF/imagine) cu rezolvarea detaliată."""
    if current_user.role not in (UserRole.TEACHER, UserRole.SCHOOL_TEACHER, UserRole.ADMIN):
        raise HTTPException(status_code=403, detail="Acces interzis")

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT id, user_id FROM exercise_submissions WHERE id=%s", (submission_id,))
        sub = cur.fetchone()
        if not sub:
            raise HTTPException(status_code=404, detail="Submisie inexistentă")

        ext = os.path.splitext(file.filename or "solution.pdf")[1].lower() or ".pdf"
        allowed_exts = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".pdf"}
        if ext not in allowed_exts:
            raise HTTPException(status_code=400, detail="Tipul de fișier nu este acceptat.")

        filename = f"teacher_{current_user.id}_{submission_id}{ext}"
        file_dir = os.path.join(UPLOAD_DIR, "teacher_files")
        os.makedirs(file_dir, exist_ok=True)
        file_path_disk = os.path.join(file_dir, filename)
        file_url = f"/uploads/teacher_files/{filename}"
        with open(file_path_disk, "wb") as f:
            shutil.copyfileobj(file.file, f)

        cur.execute(
            "UPDATE exercise_submissions SET teacher_file_path=%s, updated_at=NOW() WHERE id=%s",
            (file_url, submission_id),
        )

        # Notifică studentul că există un fișier nou
        cur.execute(
            """INSERT INTO notifications (user_id, type, title, body, related_id)
               VALUES (%s, 'teacher_file', 'Fișier de la profesor 📎', %s, %s)""",
            (
                str(sub["user_id"]),
                "Profesorul ți-a încărcat un fișier cu rezolvarea detaliată. Verifică-l în platforma EtoX.",
                submission_id,
            ),
        )
        conn.commit()

    return {"status": "ok", "file_url": file_url}


@app.post("/teacher/help-requests/{request_id}/schedule", tags=["Teacher"])
def schedule_live_help(
    request_id: str,
    body: dict,
    conn: Connection = Depends(get_db_conn),
    current_user=Depends(get_current_user),
):
    """Profesorul programează o sesiune live pentru un elev care a cerut ajutor."""
    if current_user.role not in (UserRole.TEACHER, UserRole.SCHOOL_TEACHER, UserRole.ADMIN):
        raise HTTPException(status_code=403, detail="Acces interzis")

    scheduled_at = body.get("scheduled_at")  # ISO datetime string
    zoom_link = body.get("zoom_link", "")
    if not scheduled_at:
        raise HTTPException(status_code=400, detail="scheduled_at este obligatoriu")

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT * FROM help_requests WHERE id=%s", (request_id,))
        req = cur.fetchone()
        if not req:
            raise HTTPException(status_code=404, detail="Cerere inexistentă")

        # Actualizează cererea cu programarea
        cur.execute(
            """UPDATE help_requests
               SET status='assigned', assigned_teacher_id=%s,
                   scheduled_at=%s, zoom_link=%s
               WHERE id=%s""",
            (str(current_user.id), scheduled_at, zoom_link, request_id),
        )

        # Data formatată
        from datetime import datetime as dt
        try:
            sched_dt = dt.fromisoformat(scheduled_at.replace("Z", "+00:00"))
            date_str = sched_dt.strftime("%d.%m.%Y la %H:%M")
        except Exception:
            date_str = scheduled_at

        # Notifică elevul
        cur.execute(
            """INSERT INTO notifications (user_id, type, title, body, related_id)
               VALUES (%s, 'live_scheduled', %s, %s, %s)""",
            (
                str(req["student_id"]),
                "Sesiune live programată 📅",
                f"Profesorul ți-a programat o sesiune live pe {date_str}."
                + (f" Link: {zoom_link}" if zoom_link else ""),
                request_id,
            ),
        )

        # Notifică părintele dacă există
        cur.execute(
            "SELECT parent_id FROM parent_student WHERE student_id=%s",
            (str(req["student_id"]),),
        )
        for parent_row in cur.fetchall():
            cur.execute("SELECT full_name FROM users WHERE id=%s", (str(req["student_id"]),))
            student = cur.fetchone()
            student_name = student["full_name"] if student else "Elevul"
            cur.execute(
                """INSERT INTO notifications (user_id, type, title, body, related_id)
                   VALUES (%s, 'live_scheduled', %s, %s, %s)""",
                (
                    str(parent_row["parent_id"]),
                    f"Sesiune live programată pentru {student_name}",
                    f"{student_name} are o sesiune live cu profesorul pe {date_str}.",
                    request_id,
                ),
            )

        # Adaugă în calendarul elevului
        import json as _json
        plan_date = sched_dt.strftime("%Y-%m-%d") if 'sched_dt' in dir() else scheduled_at[:10]
        cur.execute(
            """INSERT INTO study_plan_days
               (user_id, plan_date, session_type, filters, note, created_by, teacher_id)
               VALUES (%s, %s, 'live_session', %s, %s, 'teacher', %s)""",
            (
                str(req["student_id"]),
                plan_date,
                _json.dumps({}),
                f"Sesiune live cu profesorul la {date_str}" + (f"\nLink: {zoom_link}" if zoom_link else ""),
                str(current_user.id),
            ),
        )

        conn.commit()

    return {"status": "scheduled", "scheduled_at": scheduled_at}


@app.get("/teacher/help-requests/live", tags=["Teacher"])
def get_live_help_requests(
    conn: Connection = Depends(get_db_conn),
    current_user=Depends(get_current_user),
):
    """Returnează cererile de ajutor live nerezolvate."""
    if current_user.role not in (UserRole.TEACHER, UserRole.SCHOOL_TEACHER, UserRole.ADMIN):
        raise HTTPException(status_code=403, detail="Acces interzis")

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """SELECT hr.*, u.full_name as student_name, u.email as student_email,
                      e.statement_text, e.statement_latex, e.difficulty
               FROM help_requests hr
               JOIN users u ON u.id = hr.student_id
               LEFT JOIN exercises e ON e.id = hr.exercise_id
               WHERE hr.flag_type = 'LIVE' AND hr.status IN ('pending', 'assigned')
               ORDER BY hr.created_at DESC""",
        )
        return cur.fetchall()


@app.get("/teacher/submissions/stats", tags=["Teacher"])
def get_submission_stats(
    conn: Connection = Depends(get_db_conn),
    current_user=Depends(get_current_user),
):
    if current_user.role not in (UserRole.TEACHER, UserRole.SCHOOL_TEACHER, UserRole.ADMIN):
        raise HTTPException(status_code=403, detail="Acces interzis")
    with conn.cursor(row_factory=dict_row) as cur:
        if current_user.role == UserRole.ADMIN:
            cur.execute("""
                SELECT
                    COUNT(*) FILTER (WHERE teacher_status='pending') as pending,
                    COUNT(*) FILTER (WHERE teacher_status='correct') as correct,
                    COUNT(*) FILTER (WHERE teacher_status='incorrect') as incorrect,
                    COUNT(*) as total
                FROM exercise_submissions
                WHERE photo_path IS NOT NULL
            """)
        else:
            cur.execute(
                """
                SELECT
                    COUNT(*) FILTER (
                        WHERE teacher_status='pending'
                          AND (assigned_teacher_id = %s OR assigned_teacher_id IS NULL)
                    ) as pending,
                    COUNT(*) FILTER (
                        WHERE teacher_status='correct'
                          AND (reviewed_by = %s OR assigned_teacher_id = %s)
                    ) as correct,
                    COUNT(*) FILTER (
                        WHERE teacher_status='incorrect'
                          AND (reviewed_by = %s OR assigned_teacher_id = %s)
                    ) as incorrect,
                    COUNT(*) FILTER (
                        WHERE (teacher_status='pending' AND (assigned_teacher_id = %s OR assigned_teacher_id IS NULL))
                           OR (teacher_status IN ('correct', 'incorrect') AND (reviewed_by = %s OR assigned_teacher_id = %s))
                    ) as total
                FROM exercise_submissions
                WHERE photo_path IS NOT NULL
                """,
                (
                    str(current_user.id),
                    str(current_user.id),
                    str(current_user.id),
                    str(current_user.id),
                    str(current_user.id),
                    str(current_user.id),
                    str(current_user.id),
                    str(current_user.id),
                ),
            )
        return cur.fetchone()


# =============================================================================
# --- Study Sessions ---
# =============================================================================
