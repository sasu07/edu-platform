
import uuid
import os
import shutil
from datetime import datetime
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, BackgroundTasks, Depends, HTTPException, status, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from psycopg import Connection
from psycopg.rows import dict_row

from starlette.responses import StreamingResponse, HTMLResponse
from database import get_db_conn, close_db_pool
from models import (
    SourceCreate, SourceDB, SourceUpdate, SourceType,
    ExerciseCreate, ExerciseDB, ExerciseUpdate,
    SourceSegmentCreate, SourceSegmentDB, SourceSegmentUpdate,
    AssetCreate, AssetDB,
    ProcessingResult, ProcessingPageResult,
    ExtractionMethod, SegmentStatus,
    TagCreate, TagDB, ExerciseTagCreate,
    StructuredImport, ExerciseImport, TagImport, ExamType, ExerciseStatus,
    VariantCreate, VariantDB, VariantUpdate, VariantStatus,
    VariantExerciseCreate, VariantExerciseDB,
    HierarchicalImport,
    UserRegister, UserLogin, UserDB, UserRole, Token,
    SubscriptionDB, SubscriptionPlan, SubscriptionStatus,
    HelpRequestCreate, HelpRequestDB, HelpFlagType, HelpRequestStatus,
    HelpResponseCreate, HelpResponseDB,
    NotificationDB, TeacherStats, SchoolTeacherUsage,
    ParentLinkRequest, ParentStudentDB, ParentStudentStats, StudentActivityDay,
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
    send_new_request_to_teacher, send_response_to_student,
    send_parent_invite, send_parent_linked, send_weekly_digest,
)
from auth import (
    hash_password, verify_password, create_access_token,
    get_current_user, get_optional_user, require_role, require_premium,
    require_pdf_premium, check_school_teacher_limit, check_variant_gen_limit,
    _has_active_premium, _has_pdf_access, _has_help_access, _has_gen_access,
)

app = FastAPI(
    title="Edu Content API",
    description="Backend API for managing educational exercises and variants.",
    version="0.1.0"
)

# --- CORS Configuration for Frontend Development + Docker ---
origins = [
    "http://localhost",
    "http://localhost:3000",      # Docker frontend (nginx)
    "http://localhost:5173",      # Vite dev server
    "http://localhost:5174",
    "http://localhost:8080",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

# --- File Storage Setup ---
UPLOAD_DIR = "uploaded_files"
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

@app.on_event("startup")
def startup_event():
    """Rulează doar migrările SQL care nu au fost aplicate încă."""
    import glob as glob_mod
    from database import conn_pool
    if conn_pool is None:
        return
    with conn_pool.connection() as conn:
        # Tabel de tracking — creat o singură dată
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    filename VARCHAR(255) PRIMARY KEY,
                    applied_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
        conn.commit()

        with conn.cursor() as cur:
            cur.execute("SELECT filename FROM schema_migrations")
            applied = {row[0] for row in cur.fetchall()}

        migrations_dir = os.path.join(os.path.dirname(__file__), "migrations")
        sql_files = sorted(glob_mod.glob(os.path.join(migrations_dir, "*.sql")))

        for sql_file in sql_files:
            filename = os.path.basename(sql_file)
            if filename in applied:
                continue
            with open(sql_file, "r") as f:
                sql = f.read()
            try:
                with conn.cursor() as cur:
                    cur.execute(sql)
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO schema_migrations (filename) VALUES (%s)",
                        (filename,),
                    )
                conn.commit()
            except Exception as e:
                conn.rollback()
                print(f"Migration {filename} skipped: {e}")


@app.on_event("shutdown")
def shutdown_event():
    close_db_pool()

# --- Helper functions ---

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
                new_ex = create_exercise(exercise_to_create, conn)
                
                # Link to source segment
                link_query = "INSERT INTO exercise_source_segments (exercise_id, source_segment_id) VALUES (%s, %s)"
                with conn.cursor() as cur:
                    cur.execute(link_query, (new_ex['id'], segment_id))
                conn.commit()
                
                # Auto-tag
                try:
                    tag_exercise_endpoint(new_ex['id'], conn)
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
            new_ex = create_exercise(exercise_to_create, conn)
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
def create_source(source: SourceCreate, conn: Connection = Depends(get_db_conn)):
    """Create a new source entry."""
    try:
        return _create_source_in_db(source, conn)
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database error: {e}")

@app.get("/sources/", response_model=List[SourceDB])
def read_sources(conn: Connection = Depends(get_db_conn)):
    """Retrieve a list of all sources."""
    query = "SELECT id, name, type, year, session, profile, url_file_path, url_barem_path, notes, created_at FROM sources ORDER BY year DESC NULLS LAST, created_at DESC;"
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query)
        sources = cur.fetchall()
        return sources

@app.get("/sources/{source_id}", response_model=SourceDB)
def read_source(source_id: uuid.UUID, conn: Connection = Depends(get_db_conn)):
    """Retrieve a single source by ID."""
    query = "SELECT id, name, type, year, session, profile, url_file_path, url_barem_path, notes, created_at FROM sources WHERE id = %s;"
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query, (source_id,))
        source = cur.fetchone()
        if source is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
        return source

@app.get("/sources/{source_id}/download")
def download_source_file(source_id: uuid.UUID, conn: Connection = Depends(get_db_conn)):
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
def download_barem_file(source_id: uuid.UUID, conn: Connection = Depends(get_db_conn)):
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
def read_source_stats(source_id: uuid.UUID, conn: Connection = Depends(get_db_conn)) -> Dict[str, Any]:
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
def read_source_exercises(source_id: uuid.UUID, conn: Connection = Depends(get_db_conn)):
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
def update_source(source_id: uuid.UUID, source: SourceUpdate, conn: Connection = Depends(get_db_conn)):
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
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database error: {e}")

@app.delete("/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_source(source_id: uuid.UUID, conn: Connection = Depends(get_db_conn)):
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
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database error: {e}")

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
    conn: Connection = Depends(get_db_conn)
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
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

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
    conn: Connection = Depends(get_db_conn)
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
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

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
def create_source_segment(segment: SourceSegmentCreate, conn: Connection = Depends(get_db_conn)):
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
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database error: {e}")

@app.get("/source-segments/", response_model=List[SourceSegmentDB])
def read_source_segments(
    source_id: Optional[uuid.UUID] = None,
    conn: Connection = Depends(get_db_conn)
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
def read_source_segment(segment_id: uuid.UUID, conn: Connection = Depends(get_db_conn)):
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

# --- CRUD Operations for EXERCISES ---

@app.post("/exercises/", response_model=ExerciseDB, status_code=status.HTTP_201_CREATED)
def create_exercise(exercise: ExerciseCreate, conn: Connection = Depends(get_db_conn)):
    """Create a new exercise entry."""
    query = """
    INSERT INTO exercises (
        exam_type, profile, subject_part, item_type, statement_latex, statement_text,
        answer_latex, solution_latex, scoring_guide_latex, scoring_guide_text,
        difficulty, estimated_time_sec, points, metadata, status, created_by_user_id
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    RETURNING id, exam_type, profile, subject_part, item_type, statement_latex, statement_text,
              answer_latex, solution_latex, scoring_guide_latex, scoring_guide_text,
              difficulty, estimated_time_sec, points, metadata, status, created_by_user_id,
              created_at, updated_at;
    """
    try:
        with conn.cursor(row_factory=dict_row) as cur:
            # Convert enums to their string values
            exam_type_value = exercise.exam_type.value if hasattr(exercise.exam_type, 'value') else exercise.exam_type
            subject_part_value = exercise.subject_part.value if exercise.subject_part and hasattr(exercise.subject_part, 'value') else exercise.subject_part
            item_type_value = exercise.item_type.value if exercise.item_type and hasattr(exercise.item_type, 'value') else exercise.item_type
            status_value = exercise.status.value if hasattr(exercise.status, 'value') else exercise.status

            # Convert metadata dict to JSON string if present
            import json
            metadata_json = json.dumps(exercise.metadata) if exercise.metadata else None

            cur.execute(query, (
                exam_type_value, exercise.profile, subject_part_value, item_type_value,
                exercise.statement_latex, exercise.statement_text,
                exercise.answer_latex, exercise.solution_latex,
                exercise.scoring_guide_latex, exercise.scoring_guide_text,
                exercise.difficulty, exercise.estimated_time_sec, exercise.points,
                metadata_json, status_value, exercise.created_by_user_id
            ))
            new_exercise = cur.fetchone()
            conn.commit()
            return new_exercise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database error: {e}")

@app.get("/exercises/", response_model=List[ExerciseDB])
def read_exercises(
    exam_type: Optional[str] = None,
    status_filter: Optional[str] = None,
    subiect_tag: Optional[str] = None,       # "1", "2", "3" — tag namespace=subiect
    topic_tag: Optional[str] = None,          # tag key din namespace=topic
    method_tag: Optional[str] = None,         # tag key din namespace=method
    difficulty_min: Optional[int] = None,
    difficulty_max: Optional[int] = None,
    has_solution: Optional[bool] = None,      # True = doar cu soluție
    has_scoring_guide: Optional[bool] = None, # True = doar cu barem
    subject_part: Optional[str] = None,       # S1, S2, S3
    profile: Optional[str] = None,            # mate-info, st-nat, tehnologic, pedagogic
    year: Optional[int] = None,               # an examene (via sources)
    only_roots: Optional[bool] = None,        # True = nu include copii (parent_external_id IS NULL)
    exclude_seen: Optional[bool] = None,      # True = exclude exercises already seen by user
    is_container: Optional[bool] = None,      # True = doar containere, False = doar simple
    limit: Optional[int] = None,              # Limită număr rezultate (cu ORDER BY RANDOM())
    conn: Connection = Depends(get_db_conn),
    current_user: Optional[UserDB] = Depends(get_optional_user),
):
    """Retrieve exercises, optionally filtered by multiple criteria."""
    conditions = []
    params: list = []

    if exam_type:
        conditions.append("e.exam_type = %s")
        params.append(exam_type)

    if status_filter:
        conditions.append("e.status = %s")
        params.append(status_filter)
    else:
        conditions.append("(e.status != 'ARCHIVED' OR e.status IS NULL)")

    if subject_part:
        conditions.append("e.subject_part = %s")
        params.append(subject_part)

    if profile:
        conditions.append("e.profile = %s")
        params.append(profile)

    if difficulty_min is not None:
        conditions.append("(e.difficulty >= %s OR e.difficulty IS NULL)")
        params.append(difficulty_min)

    if difficulty_max is not None:
        conditions.append("(e.difficulty <= %s OR e.difficulty IS NULL)")
        params.append(difficulty_max)

    if has_solution:
        conditions.append("(e.solution_latex IS NOT NULL OR e.answer_latex IS NOT NULL)")

    if has_scoring_guide:
        conditions.append("(e.scoring_guide_latex IS NOT NULL OR e.scoring_guide_text IS NOT NULL)")

    if only_roots:
        conditions.append("e.metadata::jsonb->>'parent_external_id' IS NULL")

    if is_container is True:
        conditions.append("(e.metadata::jsonb->>'is_container')::boolean = true")
    elif is_container is False:
        conditions.append("(e.metadata::jsonb->>'is_container' IS NULL OR (e.metadata::jsonb->>'is_container')::boolean = false)")

    # Snapshot conditions/params WITHOUT exclude_seen (used for fallback)
    conditions_no_seen = list(conditions)
    params_no_seen: list = list(params)

    if exclude_seen and current_user:
        conditions.append("""
            e.id NOT IN (
                SELECT exercise_id FROM user_seen_exercises WHERE user_id = %s
            )
        """)
        params.append(str(current_user.id))

    def _add(cond, param=None):
        conditions.append(cond)
        conditions_no_seen.append(cond)
        if param is not None:
            params.append(param)
            params_no_seen.append(param)

    if year:
        _add("""
            EXISTS (
                SELECT 1 FROM exercise_source_segments ess
                JOIN source_segments sg ON sg.id = ess.source_segment_id
                JOIN sources s ON s.id = sg.source_id
                WHERE ess.exercise_id = e.id AND s.year = %s
            )
        """, year)

    if subiect_tag:
        _add("""
            EXISTS (
                SELECT 1 FROM exercise_tags et2
                JOIN tags t2 ON et2.tag_id = t2.id
                WHERE et2.exercise_id = e.id
                  AND t2.namespace = 'subiect'
                  AND t2.key = %s
            )
        """, subiect_tag)

    if topic_tag:
        _add("""
            EXISTS (
                SELECT 1 FROM exercise_tags et3
                JOIN tags t3 ON et3.tag_id = t3.id
                WHERE et3.exercise_id = e.id
                  AND t3.namespace = 'topic'
                  AND t3.key = %s
            )
        """, topic_tag)

    if method_tag:
        _add("""
            EXISTS (
                SELECT 1 FROM exercise_tags et4
                JOIN tags t4 ON et4.tag_id = t4.id
                WHERE et4.exercise_id = e.id
                  AND t4.namespace = 'method'
                  AND t4.key = %s
            )
        """, method_tag)

    where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

    if limit:
        query = f"""
        SELECT * FROM (
            SELECT DISTINCT e.id, e.exam_type, e.profile, e.subject_part, e.item_type,
                   e.statement_latex, e.statement_text,
                   e.answer_latex, e.solution_latex, e.scoring_guide_latex, e.scoring_guide_text,
                   e.difficulty, e.estimated_time_sec, e.points, e.metadata, e.status,
                   e.created_by_user_id, e.created_at, e.updated_at
            FROM exercises e{where_clause}
        ) sub
        ORDER BY RANDOM() LIMIT {int(limit)};
        """
    else:
        query = f"""
        SELECT DISTINCT e.id, e.exam_type, e.profile, e.subject_part, e.item_type,
               e.statement_latex, e.statement_text,
               e.answer_latex, e.solution_latex, e.scoring_guide_latex, e.scoring_guide_text,
               e.difficulty, e.estimated_time_sec, e.points, e.metadata, e.status,
               e.created_by_user_id, e.created_at, e.updated_at
        FROM exercises e{where_clause}
        ORDER BY e.created_at DESC;
        """

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query, tuple(params))
        exercises = cur.fetchall()

        # Dacă exclude_seen a filtrat tot, returnează fără restricția de seen
        if len(exercises) == 0 and exclude_seen and current_user:
            fallback_where = " WHERE " + " AND ".join(conditions_no_seen) if conditions_no_seen else ""
            if limit:
                fallback_query = f"""
                SELECT * FROM (
                    SELECT DISTINCT e.id, e.exam_type, e.profile, e.subject_part, e.item_type,
                           e.statement_latex, e.statement_text,
                           e.answer_latex, e.solution_latex, e.scoring_guide_latex, e.scoring_guide_text,
                           e.difficulty, e.estimated_time_sec, e.points, e.metadata, e.status,
                           e.created_by_user_id, e.created_at, e.updated_at
                    FROM exercises e{fallback_where}
                ) sub
                ORDER BY RANDOM() LIMIT {int(limit)};
                """
            else:
                fallback_query = f"""
                SELECT * FROM (
                    SELECT DISTINCT e.id, e.exam_type, e.profile, e.subject_part, e.item_type,
                           e.statement_latex, e.statement_text,
                           e.answer_latex, e.solution_latex, e.scoring_guide_latex, e.scoring_guide_text,
                           e.difficulty, e.estimated_time_sec, e.points, e.metadata, e.status,
                           e.created_by_user_id, e.created_at, e.updated_at
                    FROM exercises e{fallback_where}
                ) sub
                ORDER BY RANDOM();
                """
            cur.execute(fallback_query, tuple(params_no_seen))
            exercises = cur.fetchall()

        return exercises

@app.get("/exercises/filter-options")
def get_exercise_filter_options(
    subiect_tag: Optional[str] = None,
    profile: Optional[str] = None,
    year: Optional[int] = None,
    topic_tag: Optional[str] = None,
    conn: Connection = Depends(get_db_conn),
):
    """Returnează valorile disponibile pentru filtrele de exerciții, filtrate contextual."""

    # Build base exercise subquery based on current selections
    conditions = ["(e.status != 'ARCHIVED' OR e.status IS NULL)"]
    params: list = []

    if subiect_tag:
        conditions.append("""
            EXISTS (
                SELECT 1 FROM exercise_tags et2
                JOIN tags t2 ON et2.tag_id = t2.id
                WHERE et2.exercise_id = e.id AND t2.namespace = 'subiect' AND t2.key = %s
            )
        """)
        params.append(subiect_tag)

    if profile:
        conditions.append("e.profile = %s")
        params.append(profile)

    if year:
        conditions.append("""
            EXISTS (
                SELECT 1 FROM exercise_source_segments ess
                JOIN source_segments sg ON sg.id = ess.source_segment_id
                JOIN sources s ON s.id = sg.source_id
                WHERE ess.exercise_id = e.id AND s.year = %s
            )
        """)
        params.append(year)

    if topic_tag:
        conditions.append("""
            EXISTS (
                SELECT 1 FROM exercise_tags et3
                JOIN tags t3 ON et3.tag_id = t3.id
                WHERE et3.exercise_id = e.id AND t3.namespace = 'topic' AND t3.key = %s
            )
        """)
        params.append(topic_tag)

    where = "WHERE " + " AND ".join(conditions)
    base_ids = f"SELECT e.id FROM exercises e {where}"

    with conn.cursor(row_factory=dict_row) as cur:
        # Profiles and years are always static (top-level filters)
        cur.execute("SELECT DISTINCT profile FROM exercises WHERE profile IS NOT NULL ORDER BY profile")
        profiles = [r['profile'] for r in cur.fetchall()]

        cur.execute("""
            SELECT DISTINCT s.year FROM sources s
            JOIN source_segments sg ON sg.source_id = s.id
            JOIN exercise_source_segments ess ON ess.source_segment_id = sg.id
            WHERE s.year IS NOT NULL ORDER BY s.year DESC
        """)
        years = [r['year'] for r in cur.fetchall()]

        # Topics filtered by current context
        cur.execute(f"""
            SELECT t.key, t.label, COUNT(DISTINCT et.exercise_id) as cnt
            FROM tags t
            JOIN exercise_tags et ON et.tag_id = t.id
            WHERE t.namespace = 'topic'
              AND et.exercise_id IN ({base_ids})
            GROUP BY t.key, t.label
            ORDER BY cnt DESC
        """, tuple(params))
        topics = [{'key': r['key'], 'label': r['label'], 'count': r['cnt']} for r in cur.fetchall()]

        # Methods filtered by current context
        cur.execute(f"""
            SELECT t.key, t.label, COUNT(DISTINCT et.exercise_id) as cnt
            FROM tags t
            JOIN exercise_tags et ON et.tag_id = t.id
            WHERE t.namespace = 'method'
              AND et.exercise_id IN ({base_ids})
            GROUP BY t.key, t.label
            ORDER BY cnt DESC
            LIMIT 30
        """, tuple(params))
        methods = [{'key': r['key'], 'label': r['label'], 'count': r['cnt']} for r in cur.fetchall()]

    return {"profiles": profiles, "years": years, "topics": topics, "methods": methods}


@app.get("/exercises/batch-children")
def get_exercises_batch_children(ids: str, conn: Connection = Depends(get_db_conn)):
    """
    Returnează copiii pentru mai mulți părinți dintr-o singură cerere.
    ids = comma-separated UUIDs ale exercițiilor container.
    Răspuns: { parent_id: [children] }
    """
    id_list = [i.strip() for i in ids.split(",") if i.strip()]
    if not id_list:
        return {}
    try:
        parsed_ids = [str(uuid.UUID(i)) for i in id_list]
    except ValueError:
        raise HTTPException(status_code=400, detail="IDs invalide")

    with conn.cursor(row_factory=dict_row) as cur:
        placeholders = ",".join(["%s"] * len(parsed_ids))
        cur.execute(
            f"SELECT id, metadata::jsonb->>'external_id' as ext_id FROM exercises WHERE id IN ({placeholders})",
            tuple(parsed_ids)
        )
        parents = cur.fetchall()
        ext_to_parent_id = {p['ext_id']: str(p['id']) for p in parents if p['ext_id']}

        if not ext_to_parent_id:
            return {pid: [] for pid in parsed_ids}

        ext_ids = list(ext_to_parent_id.keys())
        ext_placeholders = ",".join(["%s"] * len(ext_ids))
        cur.execute(
            f"""SELECT id, exam_type, profile, subject_part, item_type,
                       statement_latex, statement_text, answer_latex, solution_latex,
                       scoring_guide_latex, scoring_guide_text,
                       difficulty, estimated_time_sec, points, metadata, status,
                       created_at, updated_at
                FROM exercises
                WHERE metadata::jsonb->>'parent_external_id' IN ({ext_placeholders})
                ORDER BY metadata::jsonb->>'subpoint' ASC""",
            tuple(ext_ids)
        )
        all_children = cur.fetchall()

    result: dict = {pid: [] for pid in parsed_ids}
    for child in all_children:
        parent_ext = child['metadata'].get('parent_external_id') if child['metadata'] else None
        if parent_ext and parent_ext in ext_to_parent_id:
            parent_id = ext_to_parent_id[parent_ext]
            result[parent_id].append(child)

    return result


@app.get("/exercises/{exercise_id}", response_model=ExerciseDB)
def read_exercise(exercise_id: uuid.UUID, conn: Connection = Depends(get_db_conn)):
    """Retrieve a single exercise by ID."""
    query = """
    SELECT id, exam_type, profile, subject_part, item_type, statement_latex, statement_text,
           answer_latex, solution_latex, scoring_guide_latex, scoring_guide_text,
           difficulty, estimated_time_sec, points, metadata, status, created_by_user_id,
           created_at, updated_at
    FROM exercises WHERE id = %s;
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query, (exercise_id,))
        exercise = cur.fetchone()
        if exercise is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exercise not found")
        return exercise

@app.put("/exercises/{exercise_id}", response_model=ExerciseDB)
def update_exercise(exercise_id: uuid.UUID, exercise: ExerciseUpdate, conn: Connection = Depends(get_db_conn)):
    """Update an existing exercise."""
    updates = []
    values = []

    update_data = exercise.model_dump(exclude_unset=True)

    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided for update")

    import json
    for key, value in update_data.items():
        updates.append(f"{key} = %s")
        # Convert enum to value if needed
        if hasattr(value, 'value'):
            value = value.value
        # Convert dict to JSON string
        if isinstance(value, dict):
            value = json.dumps(value)
        values.append(value)

    # Add updated_at timestamp
    updates.append("updated_at = CURRENT_TIMESTAMP")
    values.append(exercise_id)

    query = f"""
    UPDATE exercises SET {', '.join(updates)}
    WHERE id = %s
    RETURNING id, exam_type, profile, subject_part, item_type, statement_latex, statement_text,
              answer_latex, solution_latex, scoring_guide_latex, scoring_guide_text,
              difficulty, estimated_time_sec, points, metadata, status, created_by_user_id,
              created_at, updated_at;
    """

    try:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, values)
            updated_exercise = cur.fetchone()
            conn.commit()
            if updated_exercise is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exercise not found")
            return updated_exercise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database error: {e}")

@app.delete("/exercises/{exercise_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_exercise(exercise_id: uuid.UUID, conn: Connection = Depends(get_db_conn)):
    """Delete an exercise by ID."""
    query = "DELETE FROM exercises WHERE id = %s RETURNING id;"
    try:
        with conn.cursor() as cur:
            cur.execute(query, (exercise_id,))
            deleted_count = cur.rowcount
            conn.commit()
            if deleted_count == 0:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exercise not found")
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database error: {e}")

# --- CRUD for TAGS ---

@app.post("/tags/", response_model=TagDB, status_code=status.HTTP_201_CREATED)
def create_tag(tag: TagCreate, conn: Connection = Depends(get_db_conn)):
    """Create a new tag."""
    query = """
    INSERT INTO tags (namespace, key, label, parent_id)
    VALUES (%s, %s, %s, %s)
    ON CONFLICT (namespace, key) DO UPDATE SET label = EXCLUDED.label
    RETURNING id, namespace, key, label, parent_id, created_at;
    """
    try:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, (tag.namespace, tag.key, tag.label, tag.parent_id))
            new_tag = cur.fetchone()
            conn.commit()
            return new_tag
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

@app.get("/tags/", response_model=List[TagDB])
def read_tags(namespace: Optional[str] = None, conn: Connection = Depends(get_db_conn)):
    """Retrieve all tags, optionally filtered by namespace."""
    if namespace:
        query = "SELECT id, namespace, key, label, parent_id, created_at FROM tags WHERE namespace = %s ORDER BY namespace, key;"
        params = (namespace,)
    else:
        query = "SELECT id, namespace, key, label, parent_id, created_at FROM tags ORDER BY namespace, key;"
        params = ()

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query, params)
        return cur.fetchall()

# --- AI Tagging Endpoint ---

@app.post("/exercises/{exercise_id}/tag")
def tag_exercise_endpoint(exercise_id: uuid.UUID, conn: Connection = Depends(get_db_conn)):
    """Trigger AI tagging for a specific exercise."""
    # 1. Fetch exercise
    query = "SELECT statement_text, solution_latex FROM exercises WHERE id = %s;"
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query, (exercise_id,))
        exercise = cur.fetchone()

    if not exercise:
        raise HTTPException(status_code=404, detail="Exercise not found")

    # 2. Call AI Tagger
    tagger = get_ai_tagger()
    tags = tagger.tag_exercise(exercise['statement_text'], exercise['solution_latex'])

    # 3. Save tags and links
    results = []
    try:
        for t in tags:
            # Create/Get tag
            tag_query = """
            INSERT INTO tags (namespace, key, label)
            VALUES (%s, %s, %s)
            ON CONFLICT (namespace, key) DO UPDATE SET label = EXCLUDED.label
            RETURNING id;
            """
            with conn.cursor() as cur:
                cur.execute(tag_query, (t['namespace'], t['key'], t['label']))
                res = cur.fetchone()
                if res:
                    # Handle both dict and tuple rows
                    tag_id = res['id'] if isinstance(res, dict) else res[0]
                else:
                    continue

                # Link to exercise
                link_query = """
                INSERT INTO exercise_tags (exercise_id, tag_id, weight, confidence, created_by)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (exercise_id, tag_id) DO UPDATE SET weight = EXCLUDED.weight
                RETURNING tag_id;
                """
                cur.execute(link_query, (exercise_id, tag_id, t.get('weight', 1.0), 0.8, 'model'))
                # Just consume the result to ensure it runs
                cur.fetchone()

            results.append(t)
        conn.commit()
        return {"status": "success", "tags_applied": results}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error applying tags: {e}")

@app.get("/exercises/{exercise_id}/tags")
def get_exercise_tags(exercise_id: uuid.UUID, conn: Connection = Depends(get_db_conn)):
    """Get all tags associated with an exercise."""
    query = """
    SELECT t.id, t.namespace, t.key, t.label, et.weight
    FROM exercise_tags et
    JOIN tags t ON et.tag_id = t.id
    WHERE et.exercise_id = %s
    ORDER BY t.namespace, t.key;
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query, (exercise_id,))
        return cur.fetchall()

@app.post("/exercises/{exercise_id}/tags/{tag_id}")
def add_tag_to_exercise(exercise_id: uuid.UUID, tag_id: uuid.UUID, conn: Connection = Depends(get_db_conn)):
    """Link an existing tag to an exercise."""
    query = """
    INSERT INTO exercise_tags (exercise_id, tag_id, weight, confidence, created_by)
    VALUES (%s, %s, 1.0, 1.0, 'manual')
    ON CONFLICT (exercise_id, tag_id) DO NOTHING
    RETURNING exercise_id;
    """
    try:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, (exercise_id, tag_id))
            result = cur.fetchone()
            conn.commit()
            if result:
                return {"status": "added"}
            return {"status": "already_exists"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error adding tag: {e}")

@app.delete("/exercises/{exercise_id}/tags/{tag_id}")
def remove_tag_from_exercise(exercise_id: uuid.UUID, tag_id: uuid.UUID, conn: Connection = Depends(get_db_conn)):
    """Remove a tag from an exercise."""
    query = "DELETE FROM exercise_tags WHERE exercise_id = %s AND tag_id = %s;"
    try:
        with conn.cursor() as cur:
            cur.execute(query, (exercise_id, tag_id))
            conn.commit()
            return {"status": "removed"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error removing tag: {e}")

# --- PDF Processing Endpoint ---

@app.post("/process-pdf/{source_id}", response_model=ProcessingResult)
async def process_existing_pdf(
    source_id: uuid.UUID,
    page_start: Optional[int] = None,
    page_end: Optional[int] = None,
    conn: Connection = Depends(get_db_conn)
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
    conn: Connection = Depends(get_db_conn)
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
    conn: Connection = Depends(get_db_conn)
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

@app.get("/exercises/{exercise_id}/children")
def get_exercise_children(exercise_id: uuid.UUID, conn: Connection = Depends(get_db_conn)):
    """
    Returnează copiii (subpunctele) unui exercițiu container.
    Caută exerciții unde metadata->parent_external_id = parent's external_id.
    """
    # Mai întâi obține external_id al parentului
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT metadata::jsonb->>'external_id' as external_id FROM exercises WHERE id = %s",
            (exercise_id,)
        )
        parent = cur.fetchone()
        if not parent:
            raise HTTPException(status_code=404, detail="Exercițiul nu a fost găsit")

        parent_ext_id = parent['external_id']
        if not parent_ext_id:
            return []

        # Caută copiii
        cur.execute("""
            SELECT id, exam_type, profile, subject_part, item_type,
                   statement_latex, statement_text, answer_latex, solution_latex,
                   scoring_guide_latex, scoring_guide_text,
                   difficulty, estimated_time_sec, points, metadata, status,
                   created_at, updated_at
            FROM exercises
            WHERE metadata::jsonb->>'parent_external_id' = %s
            ORDER BY metadata::jsonb->>'subpoint' ASC
        """, (parent_ext_id,))
        children = cur.fetchall()
        return children


@app.get("/exercises/by-path/{path:path}")
def get_exercises_by_path(path: str, conn: Connection = Depends(get_db_conn)):
    """
    Returnează exerciții pe baza tag-ului path.

    Exemple:
      /exercises/by-path/S1       → toate exercițiile din Subiectul I
      /exercises/by-path/S3/2     → exercițiul S3-2 (parent + copii)
      /exercises/by-path/S3/2/a   → doar subpunctul a de la S3-2
    """
    with conn.cursor(row_factory=dict_row) as cur:
        # Caută exact sau prefix match
        cur.execute("""
            SELECT DISTINCT e.id, e.exam_type, e.profile, e.subject_part, e.item_type,
                   e.statement_latex, e.statement_text, e.difficulty,
                   e.points, e.metadata, e.status, e.created_at, e.updated_at,
                   e.metadata::jsonb->>'path' as path_sort
            FROM exercises e
            JOIN exercise_tags et ON e.id = et.exercise_id
            JOIN tags t ON et.tag_id = t.id
            WHERE t.namespace = 'path'
              AND (t.key = %s OR t.key LIKE %s)
            ORDER BY path_sort ASC
        """, (path, path + '/%'))
        results = cur.fetchall()
        return results

# --- CRUD Operations for VARIANTS ---

@app.post("/variants/", response_model=VariantDB, status_code=status.HTTP_201_CREATED)
def create_variant(variant: VariantCreate, conn: Connection = Depends(get_db_conn)):
    """Create a new variant (test subject)."""
    query = """
    INSERT INTO variants (
        name, exam_type, profile, year, session, total_points,
        duration_minutes, instructions, status, created_by_user_id
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    RETURNING id, name, exam_type, profile, year, session, total_points,
              duration_minutes, instructions, status, created_by_user_id,
              created_at, updated_at;
    """
    try:
        with conn.cursor(row_factory=dict_row) as cur:
            exam_type_value = variant.exam_type.value if hasattr(variant.exam_type, 'value') else variant.exam_type
            status_value = variant.status.value if hasattr(variant.status, 'value') else variant.status

            cur.execute(query, (
                variant.name, exam_type_value, variant.profile, variant.year, variant.session,
                variant.total_points, variant.duration_minutes, variant.instructions,
                status_value, variant.created_by_user_id
            ))
            new_variant = cur.fetchone()
            conn.commit()
            return new_variant
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database error: {e}")

@app.get("/variants/", response_model=List[VariantDB])
def read_variants(
    exam_type: Optional[str] = None,
    status_filter: Optional[str] = None,
    conn: Connection = Depends(get_db_conn)
):
    """Retrieve variants, optionally filtered by exam_type or status."""
    conditions = []
    params = []

    if exam_type:
        conditions.append("exam_type = %s")
        params.append(exam_type)

    if status_filter:
        conditions.append("status = %s")
        params.append(status_filter)

    where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

    query = f"""
    SELECT id, name, exam_type, profile, year, session, total_points,
           duration_minutes, instructions, status, created_by_user_id,
           created_at, updated_at
    FROM variants{where_clause} ORDER BY created_at DESC;
    """

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query, tuple(params))
        variants = cur.fetchall()
        return variants

@app.get("/variants/my", tags=["Variants"])
def my_variants_early(
    current_user: UserDB = Depends(get_current_user),
    conn: Connection = Depends(get_db_conn),
):
    """Returnează variantele generate de utilizatorul curent."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT id, name, exam_type, profile, year, session,
                   total_points, duration_minutes, status, created_at, updated_at
            FROM variants
            WHERE created_by_user_id_fk = %s
            ORDER BY created_at DESC
            """,
            (str(current_user.id),),
        )
        return cur.fetchall()

@app.get("/variants/{variant_id}", response_model=VariantDB)
def read_variant(variant_id: uuid.UUID, conn: Connection = Depends(get_db_conn)):
    """Retrieve a single variant by ID."""
    query = """
    SELECT id, name, exam_type, profile, year, session, total_points,
           duration_minutes, instructions, status, created_by_user_id,
           created_at, updated_at
    FROM variants WHERE id = %s;
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query, (variant_id,))
        variant = cur.fetchone()
        if variant is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variant not found")
        return variant

@app.put("/variants/{variant_id}", response_model=VariantDB)
def update_variant(variant_id: uuid.UUID, variant: VariantUpdate, conn: Connection = Depends(get_db_conn)):
    """Update an existing variant."""
    updates = []
    values = []

    update_data = variant.model_dump(exclude_unset=True)

    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided for update")

    for key, value in update_data.items():
        updates.append(f"{key} = %s")
        if hasattr(value, 'value'):
            value = value.value
        values.append(value)

    values.append(variant_id)

    query = f"""
    UPDATE variants SET {', '.join(updates)}
    WHERE id = %s
    RETURNING id, name, exam_type, profile, year, session, total_points,
              duration_minutes, instructions, status, created_by_user_id,
              created_at, updated_at;
    """

    try:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, values)
            updated_variant = cur.fetchone()
            conn.commit()
            if updated_variant is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variant not found")
            return updated_variant
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database error: {e}")

@app.delete("/variants/{variant_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_variant(variant_id: uuid.UUID, conn: Connection = Depends(get_db_conn)):
    """Delete a variant by ID."""
    query = "DELETE FROM variants WHERE id = %s RETURNING id;"
    try:
        with conn.cursor() as cur:
            cur.execute(query, (variant_id,))
            deleted_count = cur.rowcount
            conn.commit()
            if deleted_count == 0:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variant not found")
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database error: {e}")

# --- Operations for VARIANT EXERCISES ---

@app.post("/variants/{variant_id}/exercises/")
def add_exercises_to_variant(
    variant_id: uuid.UUID,
    exercise_ids: List[uuid.UUID],
    conn: Connection = Depends(get_db_conn)
):
    """Add multiple exercises to a variant with automatic ordering."""
    try:
        # Get current max order_index for this variant
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT COALESCE(MAX(order_index), -1) as max_order FROM variant_exercises WHERE variant_id = %s",
                (variant_id,)
            )
            result = cur.fetchone()
            current_max = result['max_order'] if result else -1

        # Insert exercises
        query = """
        INSERT INTO variant_exercises (variant_id, exercise_id, order_index)
        VALUES (%s, %s, %s)
        ON CONFLICT (variant_id, exercise_id) DO NOTHING
        RETURNING id;
        """

        added_count = 0
        with conn.cursor(row_factory=dict_row) as cur:
            for idx, exercise_id in enumerate(exercise_ids):
                cur.execute(query, (variant_id, exercise_id, current_max + idx + 1))
                if cur.fetchone():
                    added_count += 1

        conn.commit()
        return {"status": "success", "added_count": added_count}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

@app.get("/variants/{variant_id}/exercises/")
def get_variant_exercises(variant_id: uuid.UUID, conn: Connection = Depends(get_db_conn)):
    """Get all exercises for a specific variant, ordered by order_index."""
    query = """
    SELECT
        ve.id, ve.variant_id, ve.exercise_id, ve.order_index, ve.section_name,
        e.statement_latex, e.statement_text, e.points, e.item_type, e.subject_part,
        e.difficulty, e.exam_type
    FROM variant_exercises ve
    JOIN exercises e ON ve.exercise_id = e.id
    WHERE ve.variant_id = %s
    ORDER BY ve.order_index;
    """

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query, (variant_id,))
        exercises = cur.fetchall()
        return exercises

@app.delete("/variants/{variant_id}/exercises/{exercise_id}")
def remove_exercise_from_variant(
    variant_id: uuid.UUID,
    exercise_id: uuid.UUID,
    conn: Connection = Depends(get_db_conn)
):
    """Remove an exercise from a variant."""
    query = "DELETE FROM variant_exercises WHERE variant_id = %s AND exercise_id = %s RETURNING id;"
    try:
        with conn.cursor() as cur:
            cur.execute(query, (variant_id, exercise_id))
            deleted_count = cur.rowcount
            conn.commit()
            if deleted_count == 0:
                raise HTTPException(status_code=404, detail="Exercise not found in variant")
            return {"status": "success"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

@app.put("/variants/{variant_id}/exercises/reorder")
def reorder_variant_exercises(
    variant_id: uuid.UUID,
    exercise_order: List[uuid.UUID],
    conn: Connection = Depends(get_db_conn)
):
    """Reorder exercises in a variant by providing the exercise IDs in desired order."""
    query = """
    UPDATE variant_exercises
    SET order_index = %s
    WHERE variant_id = %s AND exercise_id = %s;
    """
    try:
        with conn.cursor() as cur:
            for idx, exercise_id in enumerate(exercise_order):
                cur.execute(query, (idx, variant_id, exercise_id))
        conn.commit()
        return {"status": "success", "reordered_count": len(exercise_order)}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

# --- PDF Download Endpoint ---

@app.get("/variants/{variant_id}/download-pdf")
def download_variant_pdf(
    variant_id: uuid.UUID,
    current_user: UserDB = Depends(require_pdf_premium),
    conn: Connection = Depends(get_db_conn),
):
    """
    Generează și descarcă PDF-ul unei variante.
    """
    # Verifică dacă varianta există
    query = "SELECT id, name FROM variants WHERE id = %s;"
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query, (variant_id,))
        variant = cur.fetchone()

    if not variant:
        raise HTTPException(status_code=404, detail="Varianta nu a fost găsită")

    try:
        generator = get_pdf_generator(conn)
        pdf_buffer = generator.generate_variant_pdf(variant_id)

        # Creează un filename sigur din numele variantei
        safe_name = variant['name'].replace(' ', '_').replace('/', '-')
        filename = f"{safe_name}.pdf"

        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Eroare la generarea PDF-ului: {str(e)}"
        )

@app.get("/variants/{variant_id}/preview-exam", response_class=HTMLResponse)
def preview_variant_exam(variant_id: uuid.UUID, conn: Connection = Depends(get_db_conn)):
    query = "SELECT id FROM variants WHERE id = %s;"
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query, (variant_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Varianta nu a fost găsită")
    try:
        return HTMLResponse(content=get_html_generator(conn).generate(variant_id, mode="exam"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Eroare: {str(e)}")

@app.get("/variants/{variant_id}/preview-solutions", response_class=HTMLResponse)
def preview_variant_solutions(variant_id: uuid.UUID, conn: Connection = Depends(get_db_conn)):
    query = "SELECT id FROM variants WHERE id = %s;"
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query, (variant_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Varianta nu a fost găsită")
    try:
        generator = get_html_generator(conn)
        html = generator.generate(variant_id, mode="solutions")
        return HTMLResponse(content=html)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Eroare: {str(e)}")

@app.get("/variants/{variant_id}/preview-barem", response_class=HTMLResponse)
def preview_variant_barem(variant_id: uuid.UUID, conn: Connection = Depends(get_db_conn)):
    query = "SELECT id FROM variants WHERE id = %s;"
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query, (variant_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Varianta nu a fost găsită")
    try:
        generator = get_html_generator(conn)
        html = generator.generate(variant_id, mode="barem")
        return HTMLResponse(content=html)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Eroare: {str(e)}")

# --- Auto-Generation Endpoint ---

@app.post("/variants/generate")
async def generate_variant_auto(
    request: Request,
    current_user: UserDB = Depends(get_current_user),
    conn: Connection = Depends(get_db_conn),
):
    """
    Generează automat exerciții pentru o variantă.

    Acceptă două moduri:

    **Mod 1 — JSON** (folosit de frontend):
        {"variant_id": "uuid-here"}
        Generează exerciții pentru o variantă deja existentă.

    **Mod 2 — Form data** (creare + generare):
        name, exam_type, profile, year, session, difficulty_min, difficulty_max
        Creează variantă nouă și generează exerciții.

    Selecție pe tag-ul `subiect`:
    - Bacalaureat:
        * Subiectul I:   6 exerciții simple (5p fiecare)     — tag subiect:1
        * Subiectul II:  2 probleme × 3 subpuncte (15p)      — tag subiect:2
        * Subiectul III: 2 probleme × 3 subpuncte (15p)      — tag subiect:3
    """
    import json as json_mod
    import hashlib

    # Verifică limita lunară de variante pentru utilizatorii fără Premium Gen
    if current_user.role in (UserRole.SCHOOL_TEACHER, UserRole.STUDENT):
        check_variant_gen_limit(str(current_user.id), conn)

    try:
        generator = get_variant_generator(conn)
        content_type = request.headers.get("content-type", "")

        # ── Mod 1: JSON body cu variant_id ──
        if "application/json" in content_type:
            body = await request.json()
            variant_id = body.get("variant_id")
            if not variant_id:
                raise HTTPException(status_code=400, detail="Lipsește variant_id din body")

            difficulty_range = None
            if body.get("difficulty_min") is not None and body.get("difficulty_max") is not None:
                difficulty_range = (body["difficulty_min"], body["difficulty_max"])

            result = generator.generate_for_existing_variant(
                variant_id=uuid.UUID(variant_id),
                difficulty_range=difficulty_range,
            )

            # Calculează fingerprint și salvează owner-ul
            _save_variant_meta(conn, variant_id, current_user, result)

            return {
                "status": "success",
                "message": f"Exerciții generate pentru varianta: {result['name']}",
                **result
            }

        # ── Mod 2: Form data (creare + generare) ──
        else:
            form = await request.form()
            name = form.get("name")
            exam_type = form.get("exam_type")

            if not name or not exam_type:
                raise HTTPException(
                    status_code=400,
                    detail="Câmpurile 'name' și 'exam_type' sunt obligatorii"
                )

            profile = form.get("profile") or None
            year_str = form.get("year")
            year = int(year_str) if year_str else None
            session = form.get("session") or None
            diff_min_str = form.get("difficulty_min")
            diff_max_str = form.get("difficulty_max")
            dur_str = form.get("duration_minutes", "180")

            difficulty_range = None
            if diff_min_str and diff_max_str:
                difficulty_range = (int(diff_min_str), int(diff_max_str))

            result = generator.generate_variant(
                name=str(name),
                exam_type=str(exam_type),
                profile=str(profile) if profile else None,
                year=year,
                session=str(session) if session else None,
                difficulty_range=difficulty_range,
                duration_minutes=int(dur_str),
            )

            _save_variant_meta(conn, str(result.get("variant_id", "")), current_user, result)

            return {
                "status": "success",
                "message": f"Variantă generată automat: {name}",
                **result
            }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error generating variant: {e}")

# ─── Helper: salvează owner + fingerprint pe variantă ────────────────────────

def _save_variant_meta(conn: Connection, variant_id: str, user: UserDB, result: dict) -> None:
    """Salvează created_by_user_id_fk și fingerprint pe variantă."""
    import hashlib
    if not variant_id:
        return
    try:
        # Colectează toate exercise_id-urile din rezultat
        ex_ids: list[str] = []
        for subj in result.get("subjects", []):
            for ex in subj.get("exercises", []):
                ex_ids.append(str(ex.get("id", ex.get("exercise_id", ""))))
                for child in ex.get("children", []):
                    ex_ids.append(str(child.get("id", child.get("exercise_id", ""))))

        fingerprint = hashlib.sha256(",".join(sorted(ex_ids)).encode()).hexdigest()[:32] if ex_ids else None

        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE variants
                SET created_by_user_id_fk = %s, fingerprint = %s
                WHERE id = %s
                """,
                (str(user.id), fingerprint, variant_id),
            )
        conn.commit()
    except Exception:
        pass  # non-critical

# # VARIANTE — endpoint-uri suplimentare

@app.get("/school-teacher/usage", response_model=SchoolTeacherUsage, tags=["School Teacher"])
def school_teacher_usage(
    current_user: UserDB = Depends(require_role(UserRole.SCHOOL_TEACHER, UserRole.ADMIN)),
    conn: Connection = Depends(get_db_conn),
):
    """Returnează utilizarea lunară a variantelor pentru un school_teacher."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT COUNT(*) as cnt FROM variants
            WHERE created_by_user_id_fk = %s
              AND DATE_TRUNC('month', created_at) = DATE_TRUNC('month', NOW())
            """,
            (str(current_user.id),),
        )
        cnt = cur.fetchone()["cnt"]

    is_premium = _has_active_premium(str(current_user.id), conn)
    return SchoolTeacherUsage(
        variants_this_month=cnt,
        variant_limit=None if is_premium else 5,
        is_premium=is_premium,
    )

# # NOTIFICĂRI

@app.get("/notifications/", response_model=List[NotificationDB], tags=["Notifications"])
def get_notifications(
    current_user: UserDB = Depends(get_current_user),
    conn: Connection = Depends(get_db_conn),
):
    """Returnează notificările utilizatorului curent (neacceptate primele)."""
    with conn.cursor(row_factory=dict_row) as cur:
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
    current_user: UserDB = Depends(require_role(UserRole.TEACHER, UserRole.ADMIN)),
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

@app.get("/admin/teachers", tags=["Admin"])
def list_teachers(
    _admin: UserDB = Depends(require_role(UserRole.ADMIN)),
    conn: Connection = Depends(get_db_conn),
):
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT id, full_name, email FROM users WHERE role = 'teacher' ORDER BY full_name"
        )
        return cur.fetchall()


@app.post("/admin/teachers", response_model=UserDB, tags=["Admin"])
def create_teacher(
    body: UserRegister,
    _admin: UserDB = Depends(require_role(UserRole.ADMIN)),
    conn: Connection = Depends(get_db_conn),
):
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT id FROM users WHERE email = %s", (body.email,))
        if cur.fetchone():
            raise HTTPException(status_code=400, detail="Email deja înregistrat")

        cur.execute(
            """
            INSERT INTO users (email, password_hash, full_name, role)
            VALUES (%s, %s, %s, 'teacher')
            RETURNING id, email, full_name, role, is_active, created_at
            """,
            (body.email, hash_password(body.password), body.full_name),
        )
        user_row = cur.fetchone()
        conn.commit()

    return UserDB(**user_row)

# # HELP REQUESTS — endpoint suplimentar cu răspunsuri incluse (pentru student)

@app.get("/help-requests/my-full", tags=["Help"])
def my_help_requests_full(
    current_user: UserDB = Depends(get_current_user),
    conn: Connection = Depends(get_db_conn),
):
    """Student: cererile proprii cu răspunsul și datele exercițiului incluse."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT
                hr.id,
                hr.flag_type,
                hr.status,
                hr.notes,
                hr.created_at,
                hr.updated_at,
                e.statement_latex,
                e.difficulty,
                e.points,
                e.metadata->>'path' AS exercise_path,
                hr.exercise_id,
                -- Răspunsul profesorului (cel mai recent)
                hrsp.content_text,
                hrsp.video_path,
                hrsp.zoom_link,
                hrsp.scheduled_at,
                hrsp.created_at AS responded_at,
                u.full_name AS teacher_name
            FROM help_requests hr
            JOIN exercises e ON e.id = hr.exercise_id
            LEFT JOIN help_responses hrsp ON hrsp.request_id = hr.id
            LEFT JOIN users u ON u.id = hrsp.teacher_id
            WHERE hr.student_id = %s
            ORDER BY hr.created_at DESC
            """,
            (str(current_user.id),),
        )
        return cur.fetchall()

# # AUTH ENDPOINTS

@app.post("/auth/register", response_model=Token, tags=["Auth"])
def register(body: UserRegister, conn: Connection = Depends(get_db_conn)):
    allowed_roles = (UserRole.STUDENT, UserRole.SCHOOL_TEACHER)
    if body.role not in allowed_roles:
        raise HTTPException(status_code=400, detail="Conturile de profesor platformă se creează doar de administrator")

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT id FROM users WHERE email = %s", (body.email,))
        if cur.fetchone():
            raise HTTPException(status_code=400, detail="Email deja înregistrat")

        cur.execute(
            """
            INSERT INTO users (email, password_hash, full_name, role)
            VALUES (%s, %s, %s, %s)
            RETURNING id, email, full_name, role, is_active, created_at
            """,
            (body.email, hash_password(body.password), body.full_name, body.role.value),
        )
        user_row = cur.fetchone()

        # Crează abonament free implicit
        cur.execute(
            "INSERT INTO subscriptions (user_id, plan_type, status) VALUES (%s, 'free', 'active')",
            (str(user_row["id"]),),
        )
        conn.commit()

    user = UserDB(**user_row)
    token = create_access_token(str(user.id), user.role.value)
    return Token(access_token=token, user=user)

@app.post("/auth/login", response_model=Token, tags=["Auth"])
def login(body: UserLogin, conn: Connection = Depends(get_db_conn)):
    """Login cu email și parolă."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT id, email, full_name, role, is_active, created_at, password_hash FROM users WHERE email = %s",
            (body.email,),
        )
        row = cur.fetchone()

    if not row or not verify_password(body.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Email sau parolă incorectă")
    if not row["is_active"]:
        raise HTTPException(status_code=403, detail="Cont dezactivat")

    user = UserDB(**{k: v for k, v in row.items() if k != "password_hash"})
    token = create_access_token(str(user.id), user.role.value)
    return Token(access_token=token, user=user)

@app.get("/auth/me", response_model=UserDB, tags=["Auth"])
def me(current_user: UserDB = Depends(get_current_user)):
    """Returnează datele utilizatorului autentificat."""
    return current_user

@app.get("/auth/me/access", tags=["Auth"])
def my_access(
    current_user: UserDB = Depends(get_current_user),
    conn: Connection = Depends(get_db_conn),
):
    """Returnează drepturile de acces ale utilizatorului curent."""
    is_staff = current_user.role in ("teacher", "school_teacher", "admin")
    return {
        "can_help_requests": is_staff or _has_help_access(str(current_user.id), conn),
        "can_download_pdf": is_staff or _has_pdf_access(str(current_user.id), conn),
        "can_unlimited_gen": is_staff or _has_gen_access(str(current_user.id), conn),
    }


@app.get("/auth/me/limits", tags=["Auth"])
def my_limits(
    current_user: UserDB = Depends(get_current_user),
    conn: Connection = Depends(get_db_conn),
):
    """Returnează utilizarea și limitele lunare de generare pentru utilizatorul curent."""
    is_staff = current_user.role in ("teacher", "school_teacher", "admin")
    has_gen = is_staff or _has_gen_access(str(current_user.id), conn)

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT COUNT(*) as cnt FROM exercise_generation_logs
            WHERE user_id = %s
              AND DATE_TRUNC('month', created_at) = DATE_TRUNC('month', NOW())
            """,
            (str(current_user.id),),
        )
        ex_row = cur.fetchone()

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT COUNT(*) as cnt FROM variants
            WHERE created_by_user_id_fk = %s
              AND DATE_TRUNC('month', created_at) = DATE_TRUNC('month', NOW())
            """,
            (str(current_user.id),),
        )
        var_row = cur.fetchone()

    ex_used = ex_row["cnt"] if ex_row else 0
    var_used = var_row["cnt"] if var_row else 0

    return {
        "exercise_gen_used": ex_used,
        "exercise_gen_limit": None if has_gen else 3,
        "variant_gen_used": var_used,
        "variant_gen_limit": None if has_gen else 1,
        "has_unlimited_gen": has_gen,
    }


@app.post("/exercise-generations/log", tags=["Exercises"])
def log_exercise_generation(
    current_user: UserDB = Depends(get_current_user),
    conn: Connection = Depends(get_db_conn),
):
    """Înregistrează o generare de exerciții. Returnează 403 dacă limita lunară a fost atinsă."""
    is_staff = current_user.role in ("teacher", "school_teacher", "admin")

    if not is_staff and not _has_gen_access(str(current_user.id), conn):
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT COUNT(*) as cnt FROM exercise_generation_logs
                WHERE user_id = %s
                  AND DATE_TRUNC('month', created_at) = DATE_TRUNC('month', NOW())
                """,
                (str(current_user.id),),
            )
            row = cur.fetchone()

        if row and row["cnt"] >= 3:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Limita de 3 generări de exerciții/lună (plan Free) a fost atinsă. Upgrade la Premium Gen pentru generare nelimitată.",
            )

    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO exercise_generation_logs (user_id) VALUES (%s)",
            (str(current_user.id),),
        )
    conn.commit()
    return {"ok": True}


# --- Exercise Sets ---

@app.post("/exercise-sets/", tags=["ExerciseSets"])
def save_exercise_set(
    body: Dict[str, Any],
    current_user: UserDB = Depends(get_current_user),
    conn: Connection = Depends(get_db_conn),
):
    """
    Salvează un set generat de exerciții pentru utilizatorul curent.
    body: { exercise_ids: [uuid, ...], filters: {...}, name: str, linked_plan: str|null }
    Marchează automat exercițiile ca văzute.
    """
    import json as json_mod
    exercise_ids: list = body.get("exercise_ids", [])
    filters = body.get("filters", {})
    name = body.get("name", f"Set {__import__('datetime').datetime.now().strftime('%d.%m.%Y %H:%M')}")
    linked_plan = body.get("linked_plan", None)

    if not exercise_ids:
        raise HTTPException(status_code=400, detail="exercise_ids este obligatoriu")

    with conn.cursor(row_factory=dict_row) as cur:
        # Creează setul
        cur.execute(
            """
            INSERT INTO user_exercise_sets (user_id, name, linked_plan, filters)
            VALUES (%s, %s, %s, %s)
            RETURNING id, user_id, name, linked_plan, filters, created_at
            """,
            (str(current_user.id), name, linked_plan, json_mod.dumps(filters)),
        )
        new_set = cur.fetchone()
        set_id = new_set["id"]

        # Inserează itemii
        for idx, ex_id in enumerate(exercise_ids):
            cur.execute(
                "INSERT INTO user_exercise_set_items (set_id, exercise_id, sort_order) VALUES (%s, %s, %s)",
                (str(set_id), str(ex_id), idx),
            )

        # Marchează exercițiile ca văzute (INSERT OR IGNORE)
        for ex_id in exercise_ids:
            cur.execute(
                """
                INSERT INTO user_seen_exercises (user_id, exercise_id)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
                """,
                (str(current_user.id), str(ex_id)),
            )

        conn.commit()

    return {"id": str(set_id), "name": name, "exercise_count": len(exercise_ids)}


@app.get("/exercise-sets/", tags=["ExerciseSets"])
def list_exercise_sets(
    current_user: UserDB = Depends(get_current_user),
    conn: Connection = Depends(get_db_conn),
):
    """Listează seturile salvate ale utilizatorului curent, în ordine cronologică inversă."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT s.id, s.name, s.linked_plan, s.filters, s.created_at,
                   COUNT(i.id) AS exercise_count
            FROM user_exercise_sets s
            LEFT JOIN user_exercise_set_items i ON i.set_id = s.id
            WHERE s.user_id = %s
            GROUP BY s.id
            ORDER BY s.created_at DESC
            """,
            (str(current_user.id),),
        )
        rows = cur.fetchall()
    return [
        {
            "id": str(r["id"]),
            "name": r["name"],
            "linked_plan": r["linked_plan"],
            "filters": r["filters"],
            "exercise_count": r["exercise_count"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]


@app.get("/exercise-sets/{set_id}", tags=["ExerciseSets"])
def get_exercise_set(
    set_id: uuid.UUID,
    current_user: UserDB = Depends(get_current_user),
    conn: Connection = Depends(get_db_conn),
):
    """Returnează un set salvat cu exercițiile complete."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT id, name, linked_plan, filters, created_at FROM user_exercise_sets WHERE id = %s AND user_id = %s",
            (str(set_id), str(current_user.id)),
        )
        s = cur.fetchone()
    if not s:
        raise HTTPException(status_code=404, detail="Set negăsit")

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT e.id, e.exam_type, e.profile, e.subject_part, e.item_type,
                   e.statement_latex, e.statement_text,
                   e.answer_latex, e.solution_latex, e.scoring_guide_latex, e.scoring_guide_text,
                   e.difficulty, e.estimated_time_sec, e.points, e.metadata, e.status,
                   e.created_by_user_id, e.created_at, e.updated_at
            FROM user_exercise_set_items i
            JOIN exercises e ON e.id = i.exercise_id
            WHERE i.set_id = %s
            ORDER BY i.sort_order
            """,
            (str(set_id),),
        )
        exercises = cur.fetchall()

    return {
        "id": str(s["id"]),
        "name": s["name"],
        "linked_plan": s["linked_plan"],
        "filters": s["filters"],
        "created_at": s["created_at"].isoformat() if s["created_at"] else None,
        "exercises": exercises,
    }


@app.delete("/exercise-sets/{set_id}", tags=["ExerciseSets"])
def delete_exercise_set(
    set_id: uuid.UUID,
    current_user: UserDB = Depends(get_current_user),
    conn: Connection = Depends(get_db_conn),
):
    """Șterge un set salvat al utilizatorului curent și elimină exercițiile din seen."""
    with conn.cursor() as cur:
        # Obține exercițiile din set înainte de ștergere
        cur.execute(
            "SELECT exercise_id FROM user_exercise_set_items WHERE set_id = %s",
            (str(set_id),),
        )
        exercise_ids = [str(r[0]) for r in cur.fetchall()]

        cur.execute(
            "DELETE FROM user_exercise_sets WHERE id = %s AND user_id = %s RETURNING id",
            (str(set_id), str(current_user.id)),
        )
        deleted = cur.fetchone()
        if not deleted:
            raise HTTPException(status_code=404, detail="Set negăsit sau nu îți aparține")

        # Elimină exercițiile din seen doar dacă nu mai apar în alte seturi ale userului
        if exercise_ids:
            placeholders = ",".join(["%s"] * len(exercise_ids))
            cur.execute(f"""
                DELETE FROM user_seen_exercises
                WHERE user_id = %s
                  AND exercise_id IN ({placeholders})
                  AND exercise_id NOT IN (
                      SELECT si.exercise_id FROM user_exercise_set_items si
                      JOIN user_exercise_sets s ON s.id = si.set_id
                      WHERE s.user_id = %s AND s.id != %s
                  )
            """, (str(current_user.id), *exercise_ids, str(current_user.id), str(set_id)))

    conn.commit()
    return {"deleted": True}


@app.get("/auth/me/subscription", response_model=SubscriptionDB, tags=["Auth"])
def my_subscription(
    current_user: UserDB = Depends(get_current_user),
    conn: Connection = Depends(get_db_conn),
):
    """Returnează abonamentul activ al utilizatorului curent."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT id, user_id, plan_type, status, expires_at, created_at
            FROM subscriptions
            WHERE user_id = %s
            ORDER BY created_at DESC LIMIT 1
            """,
            (str(current_user.id),),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Niciun abonament găsit")
    return SubscriptionDB(**row)

# # ADMIN: GESTIONARE ABONAMENTE

@app.post("/admin/subscriptions/{user_id}/upgrade", response_model=SubscriptionDB, tags=["Admin"])
def upgrade_subscription(
    user_id: uuid.UUID,
    plan_type: str = "premium",
    expires_at: Optional[str] = None,
    _admin: UserDB = Depends(require_role(UserRole.ADMIN)),
    conn: Connection = Depends(get_db_conn),
):
    """Admin: activează abonament pentru un utilizator. plan_type: premium | premium_help | premium_pdf | premium_gen"""
    from datetime import datetime as dt
    valid_plans = ("premium", "premium_help", "premium_pdf", "premium_gen", "free")
    if plan_type not in valid_plans:
        raise HTTPException(status_code=400, detail=f"Plan invalid. Valori acceptate: {valid_plans}")
    exp = dt.fromisoformat(expires_at) if expires_at else None

    with conn.cursor(row_factory=dict_row) as cur:
        # Dacă se activează premium full, anulează toate celelalte (le include pe toate)
        # Dacă se activează un plan specific, anulează doar același plan (dacă există deja activ)
        if plan_type == "premium":
            cur.execute(
                "UPDATE subscriptions SET status = 'cancelled', updated_at = NOW() WHERE user_id = %s AND status = 'active'",
                (str(user_id),),
            )
        else:
            cur.execute(
                "UPDATE subscriptions SET status = 'cancelled', updated_at = NOW() WHERE user_id = %s AND plan_type = %s AND status = 'active'",
                (str(user_id), plan_type),
            )
        cur.execute(
            """
            INSERT INTO subscriptions (user_id, plan_type, status, expires_at)
            VALUES (%s, %s, 'active', %s)
            RETURNING id, user_id, plan_type, status, expires_at, created_at
            """,
            (str(user_id), plan_type, exp),
        )
        row = cur.fetchone()
        conn.commit()
    return SubscriptionDB(**row)

@app.delete("/admin/subscriptions/{user_id}", tags=["Admin"])
def cancel_subscription(
    user_id: uuid.UUID,
    _admin: UserDB = Depends(require_role(UserRole.ADMIN)),
    conn: Connection = Depends(get_db_conn),
):
    """Admin: dezactivează toate abonamentele active ale unui utilizator și șterge seturile asociate."""
    with conn.cursor(row_factory=dict_row) as cur:
        # Obține planurile active înainte de anulare (pentru a știi ce seturi să ștergem)
        cur.execute(
            "SELECT plan_type FROM subscriptions WHERE user_id = %s AND status = 'active'",
            (str(user_id),),
        )
        active_plans = [r["plan_type"] for r in cur.fetchall()]

        # Anulează toate abonamentele
        cur.execute(
            """
            UPDATE subscriptions
            SET status = 'cancelled', updated_at = NOW()
            WHERE user_id = %s AND status = 'active'
            RETURNING id
            """,
            (str(user_id),),
        )
        cancelled = cur.fetchall()

        # Șterge seturile de exerciții legate de planurile anulate
        if active_plans:
            cur.execute(
                "DELETE FROM user_exercise_sets WHERE user_id = %s AND linked_plan = ANY(%s)",
                (str(user_id), active_plans),
            )

        conn.commit()
    return {"cancelled": len(cancelled)}

@app.get("/admin/users", tags=["Admin"])
def list_users(
    _admin: UserDB = Depends(require_role(UserRole.ADMIN)),
    conn: Connection = Depends(get_db_conn),
):
    """Admin: listează toți utilizatorii cu abonamentul activ curent."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT u.id, u.email, u.full_name, u.role, u.is_active, u.created_at,
                   COALESCE(
                       (SELECT json_agg(plan_type ORDER BY created_at DESC)
                        FROM subscriptions
                        WHERE user_id = u.id
                          AND status = 'active'
                          AND (expires_at IS NULL OR expires_at > NOW())
                          AND plan_type != 'free'),
                       '[]'::json
                   ) AS active_plans
            FROM users u
            ORDER BY u.created_at DESC
            """
        )
        return cur.fetchall()

# # HELP REQUESTS (FLAG-URI)

@app.post("/help-requests/", response_model=HelpRequestDB, tags=["Help"])
def create_help_request(
    body: HelpRequestCreate,
    background_tasks: BackgroundTasks,
    current_user: UserDB = Depends(require_premium),
    conn: Connection = Depends(get_db_conn),
):
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT id FROM exercises WHERE id = %s", (str(body.exercise_id),))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Exercițiu negăsit")

        cur.execute(
            """
            INSERT INTO help_requests (student_id, exercise_id, flag_type, notes)
            VALUES (%s, %s, %s, %s)
            RETURNING id, student_id, exercise_id, flag_type, status, notes,
                      assigned_teacher_id, created_at, updated_at
            """,
            (str(current_user.id), str(body.exercise_id), body.flag_type.value, body.notes),
        )
        row = cur.fetchone()
        request_id = str(row["id"])

        flag_labels = {"WRITTEN": "Rezolvare scrisă", "VIDEO": "Rezolvare video", "LIVE": "Sesiune live"}
        flag_label = flag_labels.get(body.flag_type.value, body.flag_type.value)

        # Notificări în-platformă + email pentru toți profesorii activi
        cur.execute("SELECT id, full_name, email FROM users WHERE role = 'teacher' AND is_active = TRUE")
        teachers = cur.fetchall()
        for t in teachers:
            cur.execute(
                """
                INSERT INTO notifications (user_id, type, title, body, related_id)
                VALUES (%s, 'new_request', %s, %s, %s)
                """,
                (
                    str(t["id"]),
                    f"Cerere nouă: {flag_label}",
                    f"{current_user.full_name} a solicitat ajutor pentru un exercițiu.",
                    request_id,
                ),
            )
            background_tasks.add_task(
                send_new_request_to_teacher,
                t["email"], t["full_name"],
                current_user.full_name, body.flag_type.value, request_id,
            )

        conn.commit()
    return HelpRequestDB(**row)

@app.get("/help-requests/my", response_model=List[HelpRequestDB], tags=["Help"])
def my_help_requests(
    current_user: UserDB = Depends(get_current_user),
    conn: Connection = Depends(get_db_conn),
):
    """Student: vede propriile request-uri."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT id, student_id, exercise_id, flag_type, status, notes,
                   assigned_teacher_id, created_at, updated_at
            FROM help_requests WHERE student_id = %s ORDER BY created_at DESC
            """,
            (str(current_user.id),),
        )
        return [HelpRequestDB(**r) for r in cur.fetchall()]

@app.get("/help-requests/pending", response_model=List[dict], tags=["Help"])
def pending_help_requests(
    _teacher: UserDB = Depends(require_role(UserRole.TEACHER, UserRole.ADMIN)),
    conn: Connection = Depends(get_db_conn),
):
    """Profesor: vede toate request-urile nerezolvate, cu detalii exercițiu și student."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT
                hr.id, hr.flag_type, hr.status, hr.notes, hr.created_at, hr.updated_at,
                hr.assigned_teacher_id,
                u.full_name AS student_name, u.email AS student_email,
                e.statement_latex, e.difficulty, e.points,
                e.metadata->>'path' AS exercise_path,
                hr.exercise_id, hr.student_id
            FROM help_requests hr
            JOIN users u ON u.id = hr.student_id
            JOIN exercises e ON e.id = hr.exercise_id
            WHERE hr.status IN ('pending', 'assigned')
            ORDER BY hr.created_at ASC
            """
        )
        return cur.fetchall()

@app.put("/help-requests/{request_id}/assign", response_model=HelpRequestDB, tags=["Help"])
def assign_help_request(
    request_id: uuid.UUID,
    current_user: UserDB = Depends(require_role(UserRole.TEACHER, UserRole.ADMIN)),
    conn: Connection = Depends(get_db_conn),
):
    """Profesor: preia un request (îl asignează sie însuși)."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            UPDATE help_requests
            SET status = 'assigned', assigned_teacher_id = %s, updated_at = NOW()
            WHERE id = %s
            RETURNING id, student_id, exercise_id, flag_type, status, notes,
                      assigned_teacher_id, created_at, updated_at
            """,
            (str(current_user.id), str(request_id)),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Request negăsit")
        conn.commit()
    return HelpRequestDB(**row)

@app.post("/help-requests/{request_id}/respond", response_model=HelpResponseDB, tags=["Help"])
def respond_to_help_request(
    request_id: uuid.UUID,
    body: HelpResponseCreate,
    background_tasks: BackgroundTasks,
    current_user: UserDB = Depends(require_role(UserRole.TEACHER, UserRole.ADMIN)),
    conn: Connection = Depends(get_db_conn),
):
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT id, flag_type FROM help_requests WHERE id = %s", (str(request_id),))
        req = cur.fetchone()
        if not req:
            raise HTTPException(status_code=404, detail="Request negăsit")

        cur.execute(
            """
            INSERT INTO help_responses (request_id, teacher_id, content_text, zoom_link, scheduled_at)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, request_id, teacher_id, content_text, video_path, zoom_link, scheduled_at, created_at
            """,
            (str(request_id), str(current_user.id), body.content_text, body.zoom_link, body.scheduled_at),
        )
        response_row = cur.fetchone()

        cur.execute(
            "UPDATE help_requests SET status = 'resolved', updated_at = NOW() WHERE id = %s",
            (str(request_id),),
        )

        cur.execute(
            "SELECT hr.student_id, u.email, u.full_name FROM help_requests hr JOIN users u ON u.id = hr.student_id WHERE hr.id = %s",
            (str(request_id),),
        )
        student = cur.fetchone()

        flag_labels = {"WRITTEN": "Rezolvare scrisă", "VIDEO": "Rezolvare video", "LIVE": "Sesiune live"}
        flag_label = flag_labels.get(req["flag_type"], req["flag_type"])

        if student:
            cur.execute(
                """
                INSERT INTO notifications (user_id, type, title, body, related_id)
                VALUES (%s, 'help_response', %s, %s, %s)
                """,
                (
                    str(student["student_id"]),
                    f"Ai primit un răspuns: {flag_label}",
                    f"Profesorul {current_user.full_name} a răspuns la cererea ta.",
                    str(request_id),
                ),
            )
            background_tasks.add_task(
                send_response_to_student,
                student["email"], student["full_name"],
                current_user.full_name, req["flag_type"],
            )

        conn.commit()
    return HelpResponseDB(**response_row)

@app.post("/help-requests/{request_id}/upload-video", tags=["Help"])
def upload_help_video(
    request_id: uuid.UUID,
    file: UploadFile = File(...),
    current_user: UserDB = Depends(require_role(UserRole.TEACHER, UserRole.ADMIN)),
    conn: Connection = Depends(get_db_conn),
):
    """Profesor: uploadează video explicativ pentru un request VIDEO."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT id, flag_type FROM help_requests WHERE id = %s", (str(request_id),)
        )
        req = cur.fetchone()
        if not req:
            raise HTTPException(status_code=404, detail="Request negăsit")
        if req["flag_type"] != HelpFlagType.VIDEO.value:
            raise HTTPException(status_code=400, detail="Acest request nu este de tip VIDEO")

    # Salvează fișierul
    video_dir = os.path.join(UPLOAD_DIR, "help_videos")
    os.makedirs(video_dir, exist_ok=True)
    ext = os.path.splitext(file.filename or "video.mp4")[1] or ".mp4"
    filename = f"{request_id}{ext}"
    file_path = os.path.join(video_dir, filename)

    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            INSERT INTO help_responses (request_id, teacher_id, video_path)
            VALUES (%s, %s, %s)
            ON CONFLICT DO NOTHING
            RETURNING id
            """,
            (str(request_id), str(current_user.id), file_path),
        )
        cur.execute(
            "UPDATE help_requests SET status = 'resolved', updated_at = NOW() WHERE id = %s",
            (str(request_id),),
        )
        conn.commit()

    return {"status": "ok", "video_path": file_path}

@app.get("/help-requests/{request_id}/response", response_model=HelpResponseDB, tags=["Help"])
def get_help_response(
    request_id: uuid.UUID,
    current_user: UserDB = Depends(get_current_user),
    conn: Connection = Depends(get_db_conn),
):
    """Student: vede răspunsul la request-ul său."""
    with conn.cursor(row_factory=dict_row) as cur:
        # Verifică că requestul aparține studentului (sau e teacher/admin)
        cur.execute(
            "SELECT student_id FROM help_requests WHERE id = %s", (str(request_id),)
        )
        req = cur.fetchone()
        if not req:
            raise HTTPException(status_code=404, detail="Request negăsit")
        if (
            current_user.role == UserRole.STUDENT
            and str(req["student_id"]) != str(current_user.id)
        ):
            raise HTTPException(status_code=403, detail="Acces interzis")

        cur.execute(
            """
            SELECT id, request_id, teacher_id, content_text, video_path, zoom_link, scheduled_at, created_at
            FROM help_responses WHERE request_id = %s ORDER BY created_at DESC LIMIT 1
            """,
            (str(request_id),),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Niciun răspuns încă")
    return HelpResponseDB(**row)


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


# =============================================================================
# --- Parent-Student Endpoints ---
# =============================================================================

@app.post("/parent/link-student", response_model=ParentStudentDB, tags=["Parent"])
def link_parent_to_student(
    body: ParentLinkRequest,
    background_tasks: BackgroundTasks,
    conn: Connection = Depends(get_db_conn),
    current_user=Depends(get_current_user),
):
    """
    Elevul adaugă un părinte după email.
    Dacă emailul nu există → creăm cont parent + trimitem email cu parolă temporară.
    Dacă există deja → legăm direct.
    """
    if current_user.role not in (UserRole.STUDENT, UserRole.SCHOOL_TEACHER):
        raise HTTPException(status_code=403, detail="Doar elevii pot adăuga un părinte")

    import secrets, string
    parent_email = body.parent_email.strip().lower()

    with conn.cursor(row_factory=dict_row) as cur:
        # Verificăm dacă există deja legătura
        cur.execute(
            """SELECT ps.id, ps.parent_id, ps.student_id, ps.linked_at,
                      p.email as parent_email, p.full_name as parent_name,
                      s.full_name as student_name
               FROM parent_student ps
               JOIN users p ON p.id = ps.parent_id
               JOIN users s ON s.id = ps.student_id
               WHERE ps.student_id=%s AND p.email=%s""",
            (str(current_user.id), parent_email),
        )
        existing = cur.fetchone()
        if existing:
            return ParentStudentDB(**existing)

        # Căutăm contul de parent
        cur.execute("SELECT id, full_name, email FROM users WHERE email=%s", (parent_email,))
        parent_user = cur.fetchone()
        created_new = False

        if not parent_user:
            # Creăm cont nou
            alphabet = string.ascii_letters + string.digits
            temp_password = ''.join(secrets.choice(alphabet) for _ in range(10))
            parent_name = body.parent_name or parent_email.split("@")[0]
            from auth import hash_password as hp
            cur.execute(
                """INSERT INTO users (email, password_hash, full_name, role)
                   VALUES (%s, %s, %s, 'parent') RETURNING id, full_name, email""",
                (parent_email, hp(temp_password), parent_name),
            )
            parent_user = cur.fetchone()
            created_new = True
        elif parent_user.get("role") not in (None, "parent"):
            raise HTTPException(status_code=400, detail="Emailul aparține unui alt tip de cont")

        # Creăm legătura
        cur.execute(
            """INSERT INTO parent_student (parent_id, student_id)
               VALUES (%s, %s) RETURNING id, linked_at""",
            (str(parent_user["id"]), str(current_user.id)),
        )
        link_row = cur.fetchone()
        conn.commit()

        result = ParentStudentDB(
            id=link_row["id"],
            parent_id=parent_user["id"],
            student_id=current_user.id,
            parent_email=parent_email,
            parent_name=parent_user["full_name"],
            student_name=current_user.full_name,
            linked_at=link_row["linked_at"],
        )

    if created_new:
        background_tasks.add_task(
            send_parent_invite, parent_email, parent_user["full_name"],
            current_user.full_name, temp_password,
        )
    else:
        background_tasks.add_task(
            send_parent_linked, parent_email, parent_user["full_name"],
            current_user.full_name,
        )

    return result


@app.get("/student/my-parents", response_model=list[ParentStudentDB], tags=["Parent"])
def get_my_parents(
    conn: Connection = Depends(get_db_conn),
    current_user=Depends(get_current_user),
):
    """Elevul vede părinții legați la contul său."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """SELECT ps.id, ps.parent_id, ps.student_id, ps.linked_at,
                      p.email as parent_email, p.full_name as parent_name,
                      s.full_name as student_name
               FROM parent_student ps
               JOIN users p ON p.id = ps.parent_id
               JOIN users s ON s.id = ps.student_id
               WHERE ps.student_id=%s ORDER BY ps.linked_at DESC""",
            (str(current_user.id),),
        )
        rows = cur.fetchall()
    return [ParentStudentDB(**r) for r in rows]


@app.delete("/student/my-parents/{parent_id}", tags=["Parent"])
def remove_parent_link(
    parent_id: str,
    conn: Connection = Depends(get_db_conn),
    current_user=Depends(get_current_user),
):
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM parent_student WHERE student_id=%s AND parent_id=%s",
            (str(current_user.id), parent_id),
        )
        conn.commit()
    return {"ok": True}


@app.get("/parent/students", response_model=list[ParentStudentDB], tags=["Parent"])
def get_my_students(
    conn: Connection = Depends(get_db_conn),
    current_user=Depends(get_current_user),
):
    """Părintele vede elevii legați la contul său."""
    if current_user.role != UserRole.PARENT:
        raise HTTPException(status_code=403, detail="Doar părinții pot accesa această resursă")
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """SELECT ps.id, ps.parent_id, ps.student_id, ps.linked_at,
                      p.email as parent_email, p.full_name as parent_name,
                      s.full_name as student_name
               FROM parent_student ps
               JOIN users p ON p.id = ps.parent_id
               JOIN users s ON s.id = ps.student_id
               WHERE ps.parent_id=%s ORDER BY ps.linked_at DESC""",
            (str(current_user.id),),
        )
        rows = cur.fetchall()
    return [ParentStudentDB(**r) for r in rows]


@app.get("/parent/students/{student_id}/stats", response_model=ParentStudentStats, tags=["Parent"])
def get_student_stats(
    student_id: str,
    conn: Connection = Depends(get_db_conn),
    current_user=Depends(get_current_user),
):
    """Dashboard date pentru un elev — accesibil de părinte sau admin."""
    if current_user.role == UserRole.PARENT:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM parent_student WHERE parent_id=%s AND student_id=%s",
                (str(current_user.id), student_id),
            )
            if not cur.fetchone():
                raise HTTPException(status_code=403, detail="Nu ești legat de acest elev")
    elif current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Acces interzis")

    with conn.cursor(row_factory=dict_row) as cur:
        # Info elev
        cur.execute("SELECT full_name, email FROM users WHERE id=%s", (student_id,))
        student = cur.fetchone()
        if not student:
            raise HTTPException(status_code=404, detail="Elevul nu există")

        # Totale
        cur.execute(
            "SELECT COUNT(*) as cnt FROM student_progress WHERE student_id=%s",
            (student_id,),
        )
        total_seen = cur.fetchone()["cnt"]

        cur.execute(
            "SELECT COUNT(*) as cnt FROM student_progress WHERE student_id=%s AND completed=TRUE",
            (student_id,),
        )
        total_completed = cur.fetchone()["cnt"]

        cur.execute(
            "SELECT COUNT(*) as cnt FROM variants WHERE created_by_user_id=%s",
            (student_id,),
        )
        total_variants = cur.fetchone()["cnt"]

        cur.execute(
            "SELECT COUNT(*) as cnt FROM help_requests WHERE student_id=%s",
            (student_id,),
        )
        total_flags = cur.fetchone()["cnt"]

        cur.execute(
            "SELECT MAX(last_seen_at) as last_active FROM student_progress WHERE student_id=%s",
            (student_id,),
        )
        last_active_row = cur.fetchone()
        last_active = last_active_row["last_active"].isoformat() if last_active_row and last_active_row["last_active"] else None

        # Activitate pe zile (ultimele 30 zile)
        cur.execute(
            """
            SELECT
                DATE(last_seen_at) as day,
                COUNT(*) as exercises_seen,
                SUM(CASE WHEN completed THEN 1 ELSE 0 END) as exercises_completed
            FROM student_progress
            WHERE student_id=%s AND last_seen_at >= NOW() - INTERVAL '30 days'
            GROUP BY DATE(last_seen_at)
            ORDER BY day
            """,
            (student_id,),
        )
        seen_by_day = {str(r["day"]): r for r in cur.fetchall()}

        cur.execute(
            """
            SELECT DATE(created_at) as day, COUNT(*) as cnt
            FROM variants WHERE created_by_user_id=%s AND created_at >= NOW() - INTERVAL '30 days'
            GROUP BY DATE(created_at)
            """,
            (student_id,),
        )
        variants_by_day = {str(r["day"]): r["cnt"] for r in cur.fetchall()}

        cur.execute(
            """
            SELECT DATE(created_at) as day, COUNT(*) as cnt
            FROM help_requests WHERE student_id=%s AND created_at >= NOW() - INTERVAL '30 days'
            GROUP BY DATE(created_at)
            """,
            (student_id,),
        )
        flags_by_day = {str(r["day"]): r["cnt"] for r in cur.fetchall()}

        # Completări pe subiect (din metadata exercițiu)
        cur.execute(
            """
            SELECT e.metadata->>'subiect' as subiect, COUNT(*) as cnt
            FROM student_progress sp
            JOIN exercises e ON e.id = sp.exercise_id
            WHERE sp.student_id=%s AND sp.completed=TRUE AND e.metadata IS NOT NULL
            GROUP BY e.metadata->>'subiect'
            """,
            (student_id,),
        )
        completion_by_subiect = {str(r["subiect"]): r["cnt"] for r in cur.fetchall() if r["subiect"]}

    # Construim lista de zile
    from datetime import date, timedelta
    all_days = []
    today = date.today()
    for i in range(29, -1, -1):
        d = str(today - timedelta(days=i))
        sd = seen_by_day.get(d, {})
        all_days.append(StudentActivityDay(
            date=d,
            exercises_seen=sd.get("exercises_seen", 0),
            exercises_completed=sd.get("exercises_completed", 0),
            variants_generated=variants_by_day.get(d, 0),
            flags_sent=flags_by_day.get(d, 0),
        ))

    return ParentStudentStats(
        student_id=student_id,
        student_name=student["full_name"],
        student_email=student["email"],
        total_exercises_seen=total_seen,
        total_exercises_completed=total_completed,
        total_variants_generated=total_variants,
        total_flags_sent=total_flags,
        last_active_at=last_active,
        activity_last_30_days=all_days,
        completion_by_subiect=completion_by_subiect,
    )


# Admin: leagă manual un parinte de un elev
@app.post("/admin/parent-student", response_model=ParentStudentDB, tags=["Admin"])
def admin_link_parent_student(
    body: dict,
    background_tasks: BackgroundTasks,
    conn: Connection = Depends(get_db_conn),
    current_user=Depends(get_current_user),
):
    """Admin leagă manual un cont de parent de un cont de student."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Doar admin")

    parent_id = body.get("parent_id")
    student_id = body.get("student_id")
    if not parent_id or not student_id:
        raise HTTPException(status_code=400, detail="parent_id și student_id sunt obligatorii")

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT id, full_name, email, role FROM users WHERE id=%s", (parent_id,))
        parent = cur.fetchone()
        cur.execute("SELECT id, full_name, email FROM users WHERE id=%s", (student_id,))
        student = cur.fetchone()
        if not parent or not student:
            raise HTTPException(status_code=404, detail="Utilizator inexistent")

        cur.execute(
            """INSERT INTO parent_student (parent_id, student_id)
               VALUES (%s, %s)
               ON CONFLICT (parent_id, student_id) DO NOTHING
               RETURNING id, linked_at""",
            (parent_id, student_id),
        )
        row = cur.fetchone()
        conn.commit()

    if row:
        background_tasks.add_task(
            send_parent_linked, parent["email"], parent["full_name"], student["full_name"],
        )
        return ParentStudentDB(
            id=row["id"],
            parent_id=parent_id,
            student_id=student_id,
            parent_email=parent["email"],
            parent_name=parent["full_name"],
            student_name=student["full_name"],
            linked_at=row["linked_at"],
        )
    raise HTTPException(status_code=409, detail="Legătura există deja")


@app.get("/admin/parent-students", tags=["Admin"])
def admin_get_parent_students(
    conn: Connection = Depends(get_db_conn),
    current_user=Depends(get_current_user),
):
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Doar admin")
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """SELECT ps.id, ps.parent_id, ps.student_id, ps.linked_at,
                      p.email as parent_email, p.full_name as parent_name,
                      s.full_name as student_name, s.email as student_email
               FROM parent_student ps
               JOIN users p ON p.id = ps.parent_id
               JOIN users s ON s.id = ps.student_id
               ORDER BY ps.linked_at DESC"""
        )
        return cur.fetchall()


@app.delete("/admin/parent-student/{link_id}", tags=["Admin"])
def admin_remove_parent_student(
    link_id: str,
    conn: Connection = Depends(get_db_conn),
    current_user=Depends(get_current_user),
):
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Doar admin")
    with conn.cursor() as cur:
        cur.execute("DELETE FROM parent_student WHERE id=%s", (link_id,))
        conn.commit()
    return {"ok": True}


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

def _calc_base_xp(difficulty: float) -> int:
    """XP de bază recalibrat pe dificultate."""
    d = difficulty or 5
    if d <= 2:   return 10
    if d <= 4:   return 20
    if d <= 6:   return 35
    if d <= 8:   return 55
    return 80


def _award_xp(conn, user_id: str, xp: int, reason: str, ref_id: str = None):
    """Adaugă XP cu cap zilnic de 300. Returnează XP efectiv acordat."""
    if xp <= 0:
        return 0
    today = datetime.now().date()
    with conn.cursor(row_factory=dict_row) as cur:
        # XP câștigat azi
        cur.execute(
            "SELECT COALESCE(SUM(xp_gained),0) as total FROM xp_log WHERE user_id=%s AND DATE(created_at)=%s",
            (user_id, today),
        )
        xp_today = cur.fetchone()["total"]
        xp_allowed = min(xp, max(0, 300 - xp_today))
        if xp_allowed <= 0:
            return 0
        # Actualizează gamification
        cur.execute(
            """INSERT INTO student_gamification (user_id, xp_total, streak_current, streak_max, last_active_date)
               VALUES (%s, %s, 1, 1, %s)
               ON CONFLICT (user_id) DO UPDATE
               SET xp_total = student_gamification.xp_total + %s,
                   last_active_date = EXCLUDED.last_active_date,
                   updated_at = NOW()""",
            (user_id, xp_allowed, today, xp_allowed),
        )
        # Log
        cur.execute(
            "INSERT INTO xp_log (user_id, xp_gained, reason, reference_id) VALUES (%s, %s, %s, %s)",
            (user_id, xp_allowed, reason, ref_id),
        )
    return xp_allowed


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

        # Marchează și în student_progress
        cur.execute(
            """INSERT INTO student_progress (student_id, exercise_id, completed, completed_at, last_seen_at)
               VALUES (%s, %s, TRUE, NOW(), NOW())
               ON CONFLICT (student_id, exercise_id) DO UPDATE
               SET completed=TRUE, completed_at=NOW(), last_seen_at=NOW()""",
            (str(current_user.id), exercise_id),
        )
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
    if current_user.role not in (UserRole.TEACHER, UserRole.ADMIN):
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
        if status and status != "all":
            query += " WHERE es.teacher_status = %s"
            params.append(status)
        query += " ORDER BY es.created_at ASC"
        cur.execute(query, params)
        return cur.fetchall()


@app.post("/teacher/submissions/assign-pending", tags=["Teacher"])
def assign_pending_submissions(
    conn: Connection = Depends(get_db_conn),
    current_user=Depends(get_current_user),
):
    """Profesorul preia toate submisiile fără profesor atribuit."""
    if current_user.role not in (UserRole.TEACHER, UserRole.ADMIN):
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
    if current_user.role not in (UserRole.TEACHER, UserRole.ADMIN):
        raise HTTPException(status_code=403, detail="Acces interzis")

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT * FROM exercise_submissions WHERE id=%s",
            (submission_id,),
        )
        sub = cur.fetchone()
        if not sub:
            raise HTTPException(status_code=404, detail="Submisie inexistentă")

        xp_teacher = 0
        if body.status == TeacherReviewStatus.CORRECT and sub["xp_teacher"] == 0:
            cur.execute("SELECT difficulty FROM exercises WHERE id=%s", (str(sub["exercise_id"]),))
            ex = cur.fetchone()
            base_xp = _calc_base_xp((ex["difficulty"] or 5) if ex else 5)
            xp_teacher = max(1, round(base_xp * 0.50))
            _award_xp(conn, str(sub["user_id"]), xp_teacher, "teacher_correct", str(sub["exercise_id"]))

        cur.execute(
            """UPDATE exercise_submissions
               SET teacher_status=%s, reviewed_by=%s, reviewed_at=NOW(),
                   teacher_note=%s, xp_teacher=%s, updated_at=NOW()
               WHERE id=%s RETURNING *""",
            (body.status, str(current_user.id), body.note, xp_teacher, submission_id),
        )
        row = cur.fetchone()

        # Notifică studentul cu rezultatul corecției
        is_correct = body.status == TeacherReviewStatus.CORRECT
        notif_title = "Soluție corectată ✅" if is_correct else "Soluție incorectă ❌"
        notif_body = f"Profesorul a evaluat soluția ta: {'Corectă' if is_correct else 'Incorectă'}."
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
    if current_user.role not in (UserRole.TEACHER, UserRole.ADMIN):
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


@app.get("/teacher/submissions/stats", tags=["Teacher"])
def get_submission_stats(
    conn: Connection = Depends(get_db_conn),
    current_user=Depends(get_current_user),
):
    if current_user.role not in (UserRole.TEACHER, UserRole.ADMIN):
        raise HTTPException(status_code=403, detail="Acces interzis")
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("""
            SELECT
                COUNT(*) FILTER (WHERE teacher_status='pending') as pending,
                COUNT(*) FILTER (WHERE teacher_status='correct') as correct,
                COUNT(*) FILTER (WHERE teacher_status='incorrect') as incorrect,
                COUNT(*) as total
            FROM exercise_submissions WHERE photo_path IS NOT NULL
        """)
        return cur.fetchone()


# =============================================================================
# --- Study Sessions ---
# =============================================================================

@app.post("/study-sessions/start", tags=["Study"])
def start_study_session(
    body: dict,
    conn: Connection = Depends(get_db_conn),
    current_user: UserDB = Depends(get_current_user),
):
    """
    Elevul pornește o sesiune nouă.
    Body: { session_type, filters, exercise_ids }
    Creează study_session + user_exercise_set și returnează session_id.
    """
    if current_user.role not in (UserRole.STUDENT,):
        raise HTTPException(status_code=403, detail="Doar elevii pot porni sesiuni de studiu")

    session_type = body.get("session_type", "test_scurt")
    filters = body.get("filters", {})
    plan_day_id = body.get("plan_day_id")

    ex_count = 10 if session_type == "test_scurt" else 25

    with conn.cursor(row_factory=dict_row) as cur:
        # ── Generează exerciții din filters ──
        conditions = ["e.status = 'READY'",
                      "e.metadata::jsonb->>'parent_external_id' IS NULL",
                      "(e.metadata::jsonb->>'is_container' IS NULL OR (e.metadata::jsonb->>'is_container')::boolean = false)"]
        params: list = []

        subiect_tag = filters.get("subiect_tag")
        if subiect_tag:
            conditions.append("""
                EXISTS (
                    SELECT 1 FROM exercise_tags et2
                    JOIN tags t2 ON et2.tag_id = t2.id
                    WHERE et2.exercise_id = e.id
                      AND t2.namespace = 'subiect'
                      AND t2.key = %s
                )
            """)
            params.append(subiect_tag)

        where_clause = " WHERE " + " AND ".join(conditions)
        query = f"""
            SELECT DISTINCT e.id, e.statement_latex, e.statement_text,
                   e.answer_latex, e.solution_latex, e.difficulty, e.metadata
            FROM exercises e{where_clause}
            ORDER BY RANDOM() LIMIT {ex_count}
        """
        cur.execute(query, params)
        exercises = cur.fetchall()

        if not exercises:
            raise HTTPException(status_code=400, detail="Nu există exerciții disponibile pentru filtrele selectate")

        exercise_ids = [str(e["id"]) for e in exercises]

        # Creează exercise set
        cur.execute(
            """INSERT INTO user_exercise_sets (user_id, name, linked_plan, filters)
               VALUES (%s, %s, %s, %s) RETURNING id""",
            (str(current_user.id), f"Sesiune {session_type}", "study_session", json.dumps(filters)),
        )
        set_id = cur.fetchone()["id"]

        for ex_id in exercise_ids:
            cur.execute(
                "INSERT INTO user_exercise_set_items (set_id, exercise_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (str(set_id), ex_id),
            )

        avg_diff = sum(e["difficulty"] for e in exercises if e["difficulty"]) / max(1, sum(1 for e in exercises if e["difficulty"]))
        avg_diff = round(avg_diff, 2) if avg_diff else None

        cur.execute(
            """INSERT INTO study_sessions
               (user_id, session_type, filters, exercise_set_id, status,
                exercises_total, avg_difficulty)
               VALUES (%s, %s, %s, %s, 'active', %s, %s)
               RETURNING *""",
            (
                str(current_user.id),
                session_type,
                json.dumps(filters),
                str(set_id),
                len(exercise_ids),
                avg_diff,
            ),
        )
        session = dict(cur.fetchone())
        conn.commit()

    session["exercises"] = [dict(e) for e in exercises]
    return session


@app.post("/study-sessions/{session_id}/complete", tags=["Study"])
def complete_study_session(
    session_id: str,
    body: dict,
    conn: Connection = Depends(get_db_conn),
    current_user: UserDB = Depends(get_current_user),
):
    """
    Elevul finalizează sesiunea manual.
    Body: { exercises_completed, duration_sec }
    """
    if current_user.role not in (UserRole.STUDENT, UserRole.SCHOOL_TEACHER):
        raise HTTPException(status_code=403, detail="Acces interzis")

    exercises_completed = body.get("exercises_completed", 0)
    duration_sec = body.get("duration_sec", 0)

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT * FROM study_sessions WHERE id=%s AND user_id=%s",
            (session_id, str(current_user.id)),
        )
        session = cur.fetchone()
        if not session:
            raise HTTPException(status_code=404, detail="Sesiune inexistentă")
        if session["status"] != "active":
            raise HTTPException(status_code=400, detail="Sesiunea nu este activă")

        # XP bonus pentru sesiune completată
        completion_pct = exercises_completed / max(session["exercises_total"], 1)
        bonus_xp = 0
        if completion_pct >= 0.8:
            bonus_xp = 50 if session["session_type"] == "test_bac" else 20
            _award_xp(conn, str(current_user.id), bonus_xp, "session_complete", session_id)

        cur.execute(
            """UPDATE study_sessions
               SET status='completed', completed_at=NOW(),
                   duration_sec=%s, exercises_completed=%s, xp_gained=%s
               WHERE id=%s RETURNING *""",
            (duration_sec, exercises_completed, bonus_xp, session_id),
        )
        updated = cur.fetchone()

        # Dacă există un plan asociat, marchează ziua ca completată
        cur.execute(
            "UPDATE study_plan_days SET completed=TRUE, session_id=%s WHERE session_id IS NULL AND user_id=%s AND plan_date=CURRENT_DATE AND completed=FALSE",
            (session_id, str(current_user.id)),
        )

        conn.commit()

    return dict(updated)


@app.post("/study-sessions/{session_id}/abandon", tags=["Study"])
def abandon_study_session(
    session_id: str,
    conn: Connection = Depends(get_db_conn),
    current_user: UserDB = Depends(get_current_user),
):
    """Elevul abandonează sesiunea."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "UPDATE study_sessions SET status='abandoned', completed_at=NOW() WHERE id=%s AND user_id=%s RETURNING id",
            (session_id, str(current_user.id)),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Sesiune inexistentă")
        conn.commit()
    return {"status": "abandoned"}


@app.get("/study-sessions/", tags=["Study"])
def list_study_sessions(
    limit: int = 30,
    conn: Connection = Depends(get_db_conn),
    current_user: UserDB = Depends(get_current_user),
):
    """Istoricul sesiunilor elevului."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """SELECT * FROM study_sessions
               WHERE user_id=%s ORDER BY started_at DESC LIMIT %s""",
            (str(current_user.id), limit),
        )
        return cur.fetchall()


@app.get("/study-sessions/{session_id}", tags=["Study"])
def get_study_session(
    session_id: str,
    conn: Connection = Depends(get_db_conn),
    current_user: UserDB = Depends(get_current_user),
):
    """Detaliile unei sesiuni (inclusiv exercițiile)."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT * FROM study_sessions WHERE id=%s AND user_id=%s",
            (session_id, str(current_user.id)),
        )
        session = cur.fetchone()
        if not session:
            raise HTTPException(status_code=404, detail="Sesiune inexistentă")

        # Exercițiile din set
        if session["exercise_set_id"]:
            cur.execute(
                """SELECT e.id, e.statement_latex, e.statement_text, e.difficulty, e.points,
                          e.metadata, e.solution_latex, e.answer_latex
                   FROM user_exercise_set_items si
                   JOIN exercises e ON e.id = si.exercise_id
                   WHERE si.set_id=%s""",
                (str(session["exercise_set_id"]),),
            )
            exercises = cur.fetchall()
        else:
            exercises = []

        result = dict(session)
        result["exercises"] = exercises
        return result


@app.get("/student/study-stats", tags=["Study"])
def get_student_study_stats(
    conn: Connection = Depends(get_db_conn),
    current_user: UserDB = Depends(get_current_user),
):
    """Statistici sesiuni pentru elev (și parinte via student_id param)."""
    user_id = str(current_user.id)

    with conn.cursor(row_factory=dict_row) as cur:
        # Totale
        cur.execute(
            """SELECT
                COUNT(*) as total_sessions,
                COUNT(*) FILTER (WHERE status='completed') as completed_sessions,
                SUM(duration_sec) FILTER (WHERE status='completed') as total_time_sec,
                SUM(exercises_completed) FILTER (WHERE status='completed') as total_exercises,
                ROUND(AVG(avg_difficulty) FILTER (WHERE status='completed'), 1) as avg_difficulty,
                SUM(xp_gained) as total_xp
               FROM study_sessions WHERE user_id=%s""",
            (user_id,),
        )
        totals = cur.fetchone()

        # Sesiuni pe ultimele 30 de zile (pentru grafic)
        cur.execute(
            """SELECT
                DATE(started_at) as date,
                COUNT(*) as sessions,
                SUM(exercises_completed) as exercises,
                SUM(duration_sec) as time_sec
               FROM study_sessions
               WHERE user_id=%s AND started_at >= NOW() - INTERVAL '30 days'
               GROUP BY DATE(started_at)
               ORDER BY date""",
            (user_id,),
        )
        daily = cur.fetchall()

        # Progres per subiect (completate vs total disponibil)
        cur.execute(
            """SELECT
                e.metadata->>'subiect' as subiect,
                COUNT(*) as total_available
               FROM exercises e
               WHERE e.status='READY' AND e.metadata->>'subiect' IS NOT NULL
               AND e.metadata::jsonb->>'parent_external_id' IS NULL
               GROUP BY e.metadata->>'subiect'""",
        )
        available_by_subiect = {r["subiect"]: r["total_available"] for r in cur.fetchall()}

        cur.execute(
            """SELECT e.metadata->>'subiect' as subiect, COUNT(*) as completed
               FROM student_progress sp
               JOIN exercises e ON e.id = sp.exercise_id
               WHERE sp.student_id=%s AND sp.completed=TRUE
               AND e.metadata->>'subiect' IS NOT NULL
               GROUP BY e.metadata->>'subiect'""",
            (user_id,),
        )
        completed_by_subiect = {r["subiect"]: r["completed"] for r in cur.fetchall()}

        subiect_progress = []
        for s in ["1", "2", "3"]:
            total = available_by_subiect.get(s, 0)
            done = completed_by_subiect.get(s, 0)
            subiect_progress.append({
                "subiect": s,
                "label": f"Subiectul {s}",
                "total": total,
                "completed": done,
                "pct": round(done / total * 100) if total > 0 else 0,
            })

        # Recomandare: subiectul cu cel mai mic procent
        rec = min(subiect_progress, key=lambda x: x["pct"]) if subiect_progress else None

        return {
            "totals": dict(totals) if totals else {},
            "daily_last_30": [dict(d) for d in daily],
            "subiect_progress": subiect_progress,
            "recommendation": rec,
        }


@app.get("/parent/students/{student_id}/study-sessions", tags=["Parent"])
def get_student_study_sessions_for_parent(
    student_id: str,
    conn: Connection = Depends(get_db_conn),
    current_user: UserDB = Depends(get_current_user),
):
    """Părintele vede sesiunile de studiu ale elevului său."""
    if current_user.role not in (UserRole.PARENT, UserRole.ADMIN):
        raise HTTPException(status_code=403, detail="Acces interzis")

    # Verifică că e legat
    if current_user.role == UserRole.PARENT:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT id FROM parent_student WHERE parent_id=%s AND student_id=%s",
                (str(current_user.id), student_id),
            )
            if not cur.fetchone():
                raise HTTPException(status_code=403, detail="Nu ești legat de acest elev")

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """SELECT * FROM study_sessions
               WHERE user_id=%s ORDER BY started_at DESC LIMIT 60""",
            (student_id,),
        )
        sessions = cur.fetchall()

        # Statistici rapide
        cur.execute(
            """SELECT
                COUNT(*) FILTER (WHERE status='completed') as completed,
                SUM(exercises_completed) FILTER (WHERE status='completed') as total_exercises,
                SUM(duration_sec) FILTER (WHERE status='completed') as total_time_sec
               FROM study_sessions WHERE user_id=%s""",
            (student_id,),
        )
        stats = cur.fetchone()

        return {"sessions": [dict(s) for s in sessions], "stats": dict(stats) if stats else {}}


# =============================================================================
# --- Study Plan ---
# =============================================================================

@app.get("/study-plan/", tags=["Study"])
def get_study_plan(
    student_id: Optional[str] = None,
    conn: Connection = Depends(get_db_conn),
    current_user: UserDB = Depends(get_current_user),
):
    """
    Returnează planul săptămânal pentru un elev.
    Elevul vede propriul plan. Profesorul poate vedea planul oricărui elev.
    """
    # Dacă e profesor/admin și pasează student_id, vede planul elevului
    if student_id and current_user.role in (UserRole.TEACHER, UserRole.ADMIN):
        target_id = student_id
    else:
        target_id = str(current_user.id)

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """SELECT spd.*, u.full_name as teacher_name
               FROM study_plan_days spd
               LEFT JOIN users u ON u.id = spd.teacher_id
               WHERE spd.user_id=%s AND spd.plan_date >= CURRENT_DATE - INTERVAL '1 day'
               ORDER BY spd.plan_date, spd.created_at""",
            (target_id,),
        )
        return cur.fetchall()


@app.post("/study-plan/", tags=["Study"])
def create_study_plan_day(
    body: dict,
    conn: Connection = Depends(get_db_conn),
    current_user: UserDB = Depends(get_current_user),
):
    """
    Adaugă o intrare în planul săptămânal.
    Elevul adaugă pentru sine. Profesorul adaugă pentru un elev (trebuie student_id).
    """
    plan_date = body.get("plan_date")  # YYYY-MM-DD
    session_type = body.get("session_type", "test_scurt")
    filters = body.get("filters", {})
    note = body.get("note")
    # frontend trimite user_id pentru elevul țintă (folosit de profesor)
    target_student_id = body.get("user_id") or body.get("student_id")

    if not plan_date:
        raise HTTPException(status_code=400, detail="plan_date este obligatoriu")

    if current_user.role in (UserRole.TEACHER, UserRole.ADMIN) and target_student_id:
        # Profesor adaugă pentru un elev specific
        target_user_id = target_student_id
        created_by = "teacher"
        teacher_id = str(current_user.id)
    else:
        # Elev sau profesor care adaugă pentru sine
        target_user_id = str(current_user.id)
        created_by = "student"
        teacher_id = None

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """INSERT INTO study_plan_days
               (user_id, plan_date, session_type, filters, note, created_by, teacher_id)
               VALUES (%s, %s, %s, %s, %s, %s, %s)
               RETURNING *""",
            (
                target_user_id, plan_date, session_type,
                json.dumps(filters), note, created_by, teacher_id,
            ),
        )
        row = cur.fetchone()

        # Notifică elevul dacă planul a fost adăugat de profesor
        if created_by == "teacher":
            cur.execute(
                """INSERT INTO notifications (user_id, type, title, body, related_id)
                   VALUES (%s, 'study_plan', %s, %s, %s)""",
                (
                    target_user_id,
                    "Plan de studiu nou 📅",
                    f"Profesorul ți-a adăugat o sesiune în plan pentru {plan_date}.",
                    str(row["id"]),
                ),
            )

        conn.commit()
    return dict(row)


@app.delete("/study-plan/{plan_id}", tags=["Study"])
def delete_study_plan_day(
    plan_id: str,
    conn: Connection = Depends(get_db_conn),
    current_user: UserDB = Depends(get_current_user),
):
    """Șterge o intrare din plan. Elevul șterge propria intrare, profesorul poate șterge orice."""
    with conn.cursor(row_factory=dict_row) as cur:
        if current_user.role in (UserRole.TEACHER, UserRole.ADMIN):
            cur.execute("DELETE FROM study_plan_days WHERE id=%s RETURNING id", (plan_id,))
        else:
            cur.execute(
                "DELETE FROM study_plan_days WHERE id=%s AND user_id=%s RETURNING id",
                (plan_id, str(current_user.id)),
            )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Intrare inexistentă")
        conn.commit()
    return {"deleted": True}


@app.get("/teacher/students-list", tags=["Teacher"])
def get_students_list(
    conn: Connection = Depends(get_db_conn),
    current_user: UserDB = Depends(get_current_user),
):
    """Profesorul vede lista tuturor elevilor activi (pentru a le adăuga plan)."""
    if current_user.role not in (UserRole.TEACHER, UserRole.ADMIN):
        raise HTTPException(status_code=403, detail="Acces interzis")
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT id, full_name, email FROM users WHERE role='student' AND is_active=TRUE ORDER BY full_name"
        )
        return cur.fetchall()
