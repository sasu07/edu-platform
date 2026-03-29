
import uuid
import os
import shutil
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, BackgroundTasks, Depends, HTTPException, status, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
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
)
from pix2text_processor import get_pix2text_processor
from ai_tagger import get_ai_tagger
from exercise_extractor import get_exercise_extractor
from import_json import JSONImporter
from variant_generator import get_variant_generator
from pdf_generator import get_pdf_generator
from html_generator import get_html_generator
from email_service import send_new_request_to_teacher, send_response_to_student
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
    INSERT INTO sources (name, type, year, session, url_file_path, notes)
    VALUES (%s, %s, %s, %s, %s, %s)
    RETURNING id, name, type, year, session, url_file_path, notes, created_at;
    """
    with conn.cursor(row_factory=dict_row) as cur:
        # Convert SourceType enum to its value for database
        type_value = source.type.value if isinstance(source.type, SourceType) else source.type
        cur.execute(query, (
            source.name, type_value, source.year, source.session,
            source.url_file_path, source.notes
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
    query = "SELECT id, name, type, year, session, url_file_path, notes, created_at FROM sources ORDER BY created_at DESC;"
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query)
        sources = cur.fetchall()
        return sources

@app.get("/sources/{source_id}", response_model=SourceDB)
def read_source(source_id: uuid.UUID, conn: Connection = Depends(get_db_conn)):
    """Retrieve a single source by ID."""
    query = "SELECT id, name, type, year, session, url_file_path, notes, created_at FROM sources WHERE id = %s;"
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query, (source_id,))
        source = cur.fetchone()
        if source is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
        return source

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
    RETURNING id, name, type, year, session, url_file_path, notes, created_at;
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
    source_notes: Optional[str] = Form(None),
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

    # 2. Convert source_type string to SourceType enum
    try:
        type_enum = SourceType(source_type)
    except ValueError:
        type_enum = SourceType.PDF  # Default to PDF if invalid

    # 3. Create Source entry in DB with all fields
    source_data = SourceCreate(
        name=source_name,
        type=type_enum,
        year=source_year,
        session=source_session,
        notes=source_notes,
        url_file_path=file_path
    )

    try:
        source_entry = _create_source_in_db(source_data, conn)
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

    # 4. Process PDF with pix2text
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
    source_notes: Optional[str] = Form(None),
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
        notes=source_notes,
        url_file_path=file_path
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
    difficulty_min: Optional[int] = None,
    difficulty_max: Optional[int] = None,
    has_solution: Optional[bool] = None,      # True = doar cu soluție
    subject_part: Optional[str] = None,       # S1, S2, S3
    only_roots: Optional[bool] = None,        # True = nu include copii (parent_external_id IS NULL)
    exclude_seen: Optional[bool] = None,      # True = exclude exercises already seen by user
    conn: Connection = Depends(get_db_conn),
    current_user: Optional[UserDB] = Depends(get_optional_user),
):
    """Retrieve exercises, optionally filtered by multiple criteria."""
    conditions = []
    params: list = []

    # Tag join needed if filtering by subiect or topic tag
    use_tag_join = bool(subiect_tag or topic_tag)

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

    if difficulty_min is not None:
        conditions.append("(e.difficulty >= %s OR e.difficulty IS NULL)")
        params.append(difficulty_min)

    if difficulty_max is not None:
        conditions.append("(e.difficulty <= %s OR e.difficulty IS NULL)")
        params.append(difficulty_max)

    if has_solution:
        conditions.append("(e.solution_latex IS NOT NULL OR e.answer_latex IS NOT NULL)")

    if only_roots:
        conditions.append("e.metadata::jsonb->>'parent_external_id' IS NULL")

    if exclude_seen and current_user:
        conditions.append("""
            e.id NOT IN (
                SELECT exercise_id FROM user_seen_exercises WHERE user_id = %s
            )
        """)
        params.append(str(current_user.id))

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

    if topic_tag:
        conditions.append("""
            EXISTS (
                SELECT 1 FROM exercise_tags et3
                JOIN tags t3 ON et3.tag_id = t3.id
                WHERE et3.exercise_id = e.id
                  AND t3.namespace = 'topic'
                  AND t3.key = %s
            )
        """)
        params.append(topic_tag)

    where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

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
        return exercises

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
    conn: Connection = Depends(get_db_conn)
):
    """
    Upload și procesare fișier JSON cu exerciții.

    Suportă automat două formate:
    - LEGACY: exercises[] plate cu tag_catalog[]
    - IERARHIC: exercises[] grupate cu subpoints[] nested

    Detectarea formatului e automată.
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

        # Folosește noul importer unificat (detectează automat formatul)
        importer = JSONImporter(json_data=data, include_containers=include_containers, conn=conn)

        try:
            stats = importer.run()
            conn.commit()
            return {
                "status": "success",
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
    """Șterge un set salvat al utilizatorului curent."""
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM user_exercise_sets WHERE id = %s AND user_id = %s RETURNING id",
            (str(set_id), str(current_user.id)),
        )
        deleted = cur.fetchone()
    if not deleted:
        raise HTTPException(status_code=404, detail="Set negăsit sau nu îți aparține")
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
