"""
Variant Generator v2 — Generare automată de variante BAC/EN.

Strategia de selecție (pe tag-ul `subiect`):
  ┌──────────────┬────────┬────────────┬──────────────────────────────┐
  │ Subiect      │ Count  │ Tip        │ Selecție                     │
  ├──────────────┼────────┼────────────┼──────────────────────────────┤
  │ Subiectul I  │ 6      │ simple     │ tag subiect:1, !container    │
  │ Subiectul II │ 2      │ container  │ tag subiect:2, container     │
  │              │        │ + 3 copii  │ + toți copiii (a,b,c)        │
  │ Subiectul III│ 2      │ container  │ tag subiect:3, container     │
  │              │        │ + 3 copii  │ + toți copiii (a,b,c)        │
  └──────────────┴────────┴────────────┴──────────────────────────────┘

Validare parent-coherentă:
  - Când selectăm un container, includem TOȚI copiii (a,b,c)
  - Dacă un container nu are toți copiii → skip
  - Nu se permit subpuncte orfane

Returnare detaliată:
  - Fiecare subiect cu exercițiile selectate
  - Pentru containere: enunțul comun + subpunctele ordonate
  - Punctaj per exercițiu, total per subiect, total general
"""
from typing import List, Dict, Optional, Any, Set, Tuple
from dataclasses import dataclass, field
import uuid
import json
import logging
from psycopg import Connection
from psycopg.rows import dict_row

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
#  Structura examenului
# ═══════════════════════════════════════════════════════════════

@dataclass
class SubjectSpec:
    """Specificația unui subiect din examen."""
    name: str                      # "Subiectul I"
    subiect_key: str               # "1", "2", "3" — valoarea tag-ului subiect
    count: int                     # Nr de exerciții/probleme de selectat
    has_subpoints: bool            # Are subpuncte (a,b,c)?
    expected_subpoints: List[str] = field(default_factory=list)
    points_per_exercise: int = 5   # Puncte per exercițiu simplu
    points_per_problem: int = 15   # Puncte per problemă cu subpuncte

@dataclass
class ExamStructure:
    """Structura completă a unui examen."""
    exam_type: str
    subjects: List[SubjectSpec]
    total_points: int = 90
    oficiu_points: int = 10
    duration_minutes: int = 180

    @staticmethod
    def bacalaureat(profile: str = "mate-info") -> 'ExamStructure':
        return ExamStructure(
            exam_type="bacalaureat",
            subjects=[
                SubjectSpec(
                    name="Subiectul I",
                    subiect_key="1",
                    count=6,
                    has_subpoints=False,
                    points_per_exercise=5,
                ),
                SubjectSpec(
                    name="Subiectul II",
                    subiect_key="2",
                    count=2,
                    has_subpoints=True,
                    expected_subpoints=["a", "b", "c"],
                    points_per_problem=15,
                ),
                SubjectSpec(
                    name="Subiectul III",
                    subiect_key="3",
                    count=2,
                    has_subpoints=True,
                    expected_subpoints=["a", "b", "c"],
                    points_per_problem=15,
                ),
            ],
            total_points=90,
            oficiu_points=10,
            duration_minutes=180,
        )

    @staticmethod
    def evaluare_nationala() -> 'ExamStructure':
        return ExamStructure(
            exam_type="evaluare_nationala",
            subjects=[
                SubjectSpec(
                    name="Subiectul I",
                    subiect_key="1",
                    count=6,
                    has_subpoints=False,
                    points_per_exercise=5,
                ),
                SubjectSpec(
                    name="Subiectul II",
                    subiect_key="2",
                    count=3,
                    has_subpoints=False,
                    points_per_exercise=10,
                ),
            ],
            total_points=60,
            oficiu_points=10,
            duration_minutes=120,
        )

# ═══════════════════════════════════════════════════════════════
#  Generator
# ═══════════════════════════════════════════════════════════════

class VariantGenerator:
    """Generator automat de variante cu selecție pe tag-ul `subiect`."""

    def __init__(self, conn: Connection):
        self.conn = conn

    #  PUBLIC: generate_variant

    def generate_variant(
        self,
        name: str,
        exam_type: str,
        profile: Optional[str] = None,
        year: Optional[int] = None,
        session: Optional[str] = None,
        difficulty_range: Optional[Tuple[int, int]] = None,
        exclude_exercise_ids: Optional[List[uuid.UUID]] = None,
        duration_minutes: int = 180,
    ) -> Dict[str, Any]:
        """
        Generează o variantă completă.

        Algoritm:
        1. Determină structura examenului
        2. Pentru fiecare subiect:
           - Subiect simplu: selectează N exerciții cu tag subiect:X, fără container
           - Subiect cu subpuncte: selectează N containere cu tag subiect:X,
             validează copiii compleți (a,b,c), adaugă copiii
        3. Inserează totul în DB
        4. Returnează structura detaliată

        Args:
            difficulty_range: Opțional (min, max). Dacă None, acceptă orice dificultate.
        """
        # 1. Structura examenului
        if exam_type == "bacalaureat":
            structure = ExamStructure.bacalaureat(profile or "mate-info")
        elif exam_type == "evaluare_nationala":
            structure = ExamStructure.evaluare_nationala()
        else:
            raise ValueError(f"Tip examen necunoscut: {exam_type}")

        # Override duration dacă e specificat
        if duration_minutes:
            structure.duration_minutes = duration_minutes

        # 2. Creează varianta în DB
        variant_id = self._create_variant(
            name=name, exam_type=exam_type, profile=profile,
            year=year, session=session,
            duration_minutes=structure.duration_minutes,
        )

        # 3. Selectează exerciții pentru fiecare subiect
        exclude_ids = set(exclude_exercise_ids or [])
        used_container_ext_ids: Set[str] = set()
        warnings: List[str] = []
        subject_results: List[Dict[str, Any]] = []
        all_variant_entries: List[Tuple[uuid.UUID, str]] = []  # (exercise_id, section_name)
        computed_total_points = 0

        for spec in structure.subjects:
            if spec.has_subpoints:
                result = self._select_problems_with_subpoints(
                    spec=spec,
                    difficulty_range=difficulty_range,
                    exclude_ids=exclude_ids,
                    used_container_ext_ids=used_container_ext_ids,
                )
            else:
                result = self._select_simple_exercises(
                    spec=spec,
                    difficulty_range=difficulty_range,
                    exclude_ids=exclude_ids,
                )

            subject_results.append(result)
            warnings.extend(result.get('warnings', []))

            # Adaugă la lista globală + exclude
            for entry in result['entries']:
                all_variant_entries.append((entry['exercise_id'], spec.name))
                exclude_ids.add(entry['exercise_id'])

            computed_total_points += result['total_points']

        # 4. Inserează exercițiile în variantă (ordonate)
        for order_idx, (exercise_id, section_name) in enumerate(all_variant_entries):
            self._add_exercise_to_variant(variant_id, exercise_id, order_idx, section_name)

        # 5. Actualizează punctajul total
        self._update_variant_points(variant_id, structure.total_points)

        # 6. Construiește răspunsul detaliat
        return {
            "variant_id": str(variant_id),
            "name": name,
            "exam_type": exam_type,
            "profile": profile,
            "duration_minutes": structure.duration_minutes,
            "total_points": structure.total_points,
            "oficiu_points": structure.oficiu_points,
            "exercise_count": len(all_variant_entries),
            "warnings": warnings,
            "subjects": [
                self._format_subject_result(spec, result)
                for spec, result in zip(structure.subjects, subject_results)
            ],
        }

    #  PUBLIC: generate_for_existing_variant

    def generate_for_existing_variant(
        self,
        variant_id: uuid.UUID,
        difficulty_range: Optional[Tuple[int, int]] = None,
    ) -> Dict[str, Any]:
        """
        Generează exerciții pentru o variantă deja existentă în DB.

        1. Citește varianta din DB (name, exam_type, profile, year, session)
        2. Șterge exercițiile vechi din variantă
        3. Selectează exerciții noi
        4. Le inserează în variantă
        5. Returnează structura detaliată
        """
        # 1. Citește varianta
        query = """
            SELECT id, name, exam_type, profile, year, session, duration_minutes
            FROM variants WHERE id = %s
        """
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, (variant_id,))
            variant = cur.fetchone()

        if not variant:
            raise ValueError(f"Varianta {variant_id} nu există")

        name = variant['name']
        exam_type = variant['exam_type'] or 'bacalaureat'
        profile = variant['profile']
        year = variant['year']
        duration_minutes = variant['duration_minutes'] or 180

        # Structura examenului
        if exam_type == "bacalaureat":
            structure = ExamStructure.bacalaureat(profile or "mate-info")
        elif exam_type == "evaluare_nationala":
            structure = ExamStructure.evaluare_nationala()
        else:
            raise ValueError(f"Tip examen necunoscut: {exam_type}")

        structure.duration_minutes = duration_minutes

        # 2. Șterge exercițiile vechi din această variantă
        with self.conn.cursor() as cur:
            cur.execute("DELETE FROM variant_exercises WHERE variant_id = %s", (variant_id,))
            self.conn.commit()

        # 3. Selectează exerciții noi
        exclude_ids: Set[uuid.UUID] = set()
        used_container_ext_ids: Set[str] = set()
        warnings: List[str] = []
        subject_results: List[Dict[str, Any]] = []
        all_variant_entries: List[Tuple[uuid.UUID, str]] = []
        computed_total_points = 0

        for spec in structure.subjects:
            if spec.has_subpoints:
                result = self._select_problems_with_subpoints(
                    spec=spec,
                    difficulty_range=difficulty_range,
                    exclude_ids=exclude_ids,
                    used_container_ext_ids=used_container_ext_ids,
                )
            else:
                result = self._select_simple_exercises(
                    spec=spec,
                    difficulty_range=difficulty_range,
                    exclude_ids=exclude_ids,
                )

            subject_results.append(result)
            warnings.extend(result.get('warnings', []))

            for entry in result['entries']:
                all_variant_entries.append((entry['exercise_id'], spec.name))
                exclude_ids.add(entry['exercise_id'])

            computed_total_points += result['total_points']

        # 4. Inserează exercițiile în variantă
        for order_idx, (exercise_id, section_name) in enumerate(all_variant_entries):
            self._add_exercise_to_variant(variant_id, exercise_id, order_idx, section_name)

        # 5. Actualizează punctajul total
        self._update_variant_points(variant_id, structure.total_points)

        # 6. Construiește răspunsul detaliat
        return {
            "variant_id": str(variant_id),
            "name": name,
            "exam_type": exam_type,
            "profile": profile,
            "duration_minutes": structure.duration_minutes,
            "total_points": structure.total_points,
            "oficiu_points": structure.oficiu_points,
            "exercise_count": len(all_variant_entries),
            "warnings": warnings,
            "subjects": [
                self._format_subject_result(spec, result)
                for spec, result in zip(structure.subjects, subject_results)
            ],
        }

    #  SELECȚIE: Exerciții simple (Subiectul I)

    def _select_simple_exercises(
        self,
        spec: SubjectSpec,
        difficulty_range: Optional[Tuple[int, int]],
        exclude_ids: Set[uuid.UUID],
    ) -> Dict[str, Any]:
        """
        Selectează exerciții simple cu tag subiect:{key}, fără containere.

        Returnează dict cu:
          entries: [{exercise_id, external_id, statement, difficulty, points}]
          total_points, selected_count, warnings
        """
        params: List[Any] = [spec.subiect_key]
        conditions = [
            "t.namespace = 'subiect'",
            "t.key = %s",
            "(e.metadata::jsonb->>'is_container')::boolean IS NOT TRUE",
            "e.metadata::jsonb->>'parent_external_id' IS NULL",  # Nu copii de container
            "(e.status != 'ARCHIVED' OR e.status IS NULL)",
        ]

        if difficulty_range:
            conditions.append("(e.difficulty >= %s OR e.difficulty IS NULL)")
            params.append(difficulty_range[0])
            conditions.append("(e.difficulty <= %s OR e.difficulty IS NULL)")
            params.append(difficulty_range[1])

        if exclude_ids:
            placeholders = ','.join(['%s'] * len(exclude_ids))
            conditions.append(f"e.id NOT IN ({placeholders})")
            params.extend(exclude_ids)

        where = " AND ".join(conditions)
        params.append(spec.count)

        query = f"""
            SELECT id, metadata, difficulty, points, statement_latex, statement_text
            FROM (
                SELECT DISTINCT e.id, e.metadata, e.difficulty, e.points,
                       e.statement_latex, e.statement_text
                FROM exercises e
                JOIN exercise_tags et ON e.id = et.exercise_id
                JOIN tags t ON et.tag_id = t.id
                WHERE {where}
            ) sub
            ORDER BY RANDOM()
            LIMIT %s
        """

        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, params)
            rows = cur.fetchall()

        entries = []
        total_points = 0
        for row in rows:
            meta = row['metadata']
            if isinstance(meta, str):
                meta = json.loads(meta)

            pts = row['points'] or spec.points_per_exercise
            total_points += pts

            entries.append({
                'exercise_id': row['id'],
                'external_id': meta.get('external_id', ''),
                'statement_latex': row['statement_latex'] or '',
                'statement_text': row['statement_text'] or '',
                'difficulty': row['difficulty'],
                'points': pts,
                'type': 'simple',
            })

        warnings = []
        if len(entries) < spec.count:
            warnings.append(
                f"{spec.name}: doar {len(entries)}/{spec.count} exerciții simple "
                f"găsite cu tag subiect:{spec.subiect_key}"
            )

        return {
            'entries': entries,
            'total_points': total_points,
            'selected_count': len(entries),
            'expected_count': spec.count,
            'warnings': warnings,
        }

    #  SELECȚIE: Probleme cu subpuncte (Subiectul II/III)

    def _select_problems_with_subpoints(
        self,
        spec: SubjectSpec,
        difficulty_range: Optional[Tuple[int, int]],
        exclude_ids: Set[uuid.UUID],
        used_container_ext_ids: Set[str],
    ) -> Dict[str, Any]:
        """
        Selectează containere complete cu tag subiect:{key}.

        Algoritm:
        1. Găsește containerele (is_container=true) cu tag subiect:{key}
        2. Pentru fiecare, verifică dacă are TOȚI copiii (a,b,c)
        3. Dacă da → adaugă copiii la variantă (NU containerul)
        4. Returnează structura detaliată

        Returnează dict cu:
          entries: [{exercise_id, external_id, statement, difficulty, points, subpoint, parent_external_id}]
          problems: [{container_external_id, statement_latex, subpoints: [...]}]
          total_points, selected_count, warnings
        """
        # 1. Găsește containere cu tag subiect:{key}
        params: List[Any] = [spec.subiect_key]
        conditions = [
            "t.namespace = 'subiect'",
            "t.key = %s",
            "(e.metadata::jsonb->>'is_container')::boolean IS TRUE",
            "(e.status != 'ARCHIVED' OR e.status IS NULL)",
        ]

        if exclude_ids:
            placeholders = ','.join(['%s'] * len(exclude_ids))
            conditions.append(f"e.id NOT IN ({placeholders})")
            params.extend(exclude_ids)

        where = " AND ".join(conditions)

        query = f"""
            SELECT id, metadata, difficulty, points, statement_latex
            FROM (
                SELECT DISTINCT e.id, e.metadata, e.difficulty, e.points, e.statement_latex
                FROM exercises e
                JOIN exercise_tags et ON e.id = et.exercise_id
                JOIN tags t ON et.tag_id = t.id
                WHERE {where}
            ) sub
            ORDER BY RANDOM()
        """

        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, params)
            containers = cur.fetchall()

        # 2. Validează fiecare container
        entries = []       # Flat list of children to insert
        problems = []      # Structured problems for response
        selected_count = 0
        total_points = 0
        warnings = []

        for container in containers:
            if selected_count >= spec.count:
                break

            meta = container['metadata']
            if isinstance(meta, str):
                meta = json.loads(meta)

            ext_id = meta.get('external_id', '')

            # Skip dacă deja folosit
            if ext_id in used_container_ext_ids:
                continue

            # 3. Verifică copiii
            children = self._get_complete_children(ext_id, spec.expected_subpoints)
            if children is None:
                logger.debug(f"Container {ext_id}: copii incompleti, skip")
                continue

            # Filtrare dificultate (pe media copiilor)
            if difficulty_range:
                child_diffs = [c['difficulty'] for c in children if c.get('difficulty') is not None]
                if child_diffs:
                    avg_diff = sum(child_diffs) / len(child_diffs)
                    if avg_diff < difficulty_range[0] - 1 or avg_diff > difficulty_range[1] + 1:
                        continue

            # Acceptat!
            used_container_ext_ids.add(ext_id)
            selected_count += 1

            problem_subpoints = []
            for child in children:
                child_meta = child['metadata']
                if isinstance(child_meta, str):
                    child_meta = json.loads(child_meta)

                pts = child['points'] or 5
                total_points += pts

                entry = {
                    'exercise_id': child['id'],
                    'external_id': child_meta.get('external_id', ''),
                    'parent_external_id': ext_id,
                    'subpoint': child_meta.get('subpoint', ''),
                    'statement_latex': child['statement_latex'] or '',
                    'difficulty': child['difficulty'],
                    'points': pts,
                    'type': 'subpoint',
                }
                entries.append(entry)

                problem_subpoints.append({
                    'subpoint': child_meta.get('subpoint', ''),
                    'statement_latex': child['statement_latex'] or '',
                    'solution_latex': child.get('solution_latex', ''),
                    'scoring_guide_latex': child.get('scoring_guide_latex', ''),
                    'difficulty': child['difficulty'],
                    'points': pts,
                })

            problems.append({
                'container_external_id': ext_id,
                'statement_latex': container['statement_latex'] or '',
                'difficulty': container['difficulty'],
                'total_points': sum(sp['points'] for sp in problem_subpoints),
                'subpoints': problem_subpoints,
            })

        if selected_count < spec.count:
            warnings.append(
                f"{spec.name}: doar {selected_count}/{spec.count} probleme complete "
                f"găsite cu tag subiect:{spec.subiect_key} "
                f"(necesită subpuncte {spec.expected_subpoints})"
            )

        return {
            'entries': entries,
            'problems': problems,
            'total_points': total_points,
            'selected_count': selected_count,
            'expected_count': spec.count,
            'warnings': warnings,
        }

    #  HELPER: Validare copii completi

    def _get_complete_children(
        self,
        parent_external_id: str,
        expected_subpoints: List[str],
    ) -> Optional[List[Dict]]:
        """
        Returnează copiii unui container, DOAR dacă sunt TOȚI prezenți.

        Returns:
            Lista de copii sortați pe subpoint (a, b, c) dacă complet,
            None dacă lipsesc subpuncte.
        """
        query = """
            SELECT id, metadata, difficulty, points, statement_latex,
                   solution_latex, scoring_guide_latex
            FROM exercises
            WHERE metadata::jsonb->>'parent_external_id' = %s
              AND (status != 'ARCHIVED' OR status IS NULL)
            ORDER BY metadata::jsonb->>'subpoint' ASC
        """

        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, (parent_external_id,))
            children = cur.fetchall()

        if not children:
            return None

        # Parsează metadata
        for child in children:
            if isinstance(child['metadata'], str):
                child['metadata'] = json.loads(child['metadata'])

        # Verifică completitudinea
        found_subpoints = {
            child['metadata'].get('subpoint')
            for child in children
            if child.get('metadata', {}).get('subpoint')
        }

        missing = set(expected_subpoints) - found_subpoints
        if missing:
            return None

        # Returnează în ordinea așteptată (a, b, c)
        ordered = []
        for sp in expected_subpoints:
            match = next(
                (c for c in children if c.get('metadata', {}).get('subpoint') == sp),
                None
            )
            if match:
                ordered.append(match)
            else:
                return None

        return ordered

    #  FORMAT: Construiește răspunsul detaliat per subiect

    def _format_subject_result(
        self,
        spec: SubjectSpec,
        result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Formatează rezultatul unui subiect pentru răspunsul API."""

        if spec.has_subpoints:
            # Subiect cu probleme
            exercises_detail = []
            for problem in result.get('problems', []):
                exercises_detail.append({
                    'container_external_id': problem['container_external_id'],
                    'statement_latex': problem['statement_latex'],
                    'difficulty': problem['difficulty'],
                    'total_points': problem['total_points'],
                    'subpoints': [
                        {
                            'subpoint': sp['subpoint'],
                            'statement_latex': sp['statement_latex'],
                            'difficulty': sp['difficulty'],
                            'points': sp['points'],
                        }
                        for sp in problem['subpoints']
                    ],
                })

            return {
                'name': spec.name,
                'subiect_key': spec.subiect_key,
                'type': 'problems_with_subpoints',
                'expected_problems': spec.count,
                'selected_problems': result['selected_count'],
                'expected_subpoints': spec.expected_subpoints,
                'total_points': result['total_points'],
                'total_exercises': len(result['entries']),
                'exercises': exercises_detail,
            }
        else:
            # Subiect simplu
            exercises_detail = [
                {
                    'external_id': e['external_id'],
                    'statement_latex': e['statement_latex'],
                    'difficulty': e['difficulty'],
                    'points': e['points'],
                }
                for e in result['entries']
            ]

            return {
                'name': spec.name,
                'subiect_key': spec.subiect_key,
                'type': 'simple_exercises',
                'expected_count': spec.count,
                'selected_count': result['selected_count'],
                'total_points': result['total_points'],
                'exercises': exercises_detail,
            }

    #  DB helpers

    def _create_variant(
        self, name, exam_type, profile, year, session, duration_minutes
    ) -> uuid.UUID:
        query = """
        INSERT INTO variants (name, exam_type, profile, year, session, duration_minutes, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id;
        """
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, (
                name, exam_type, profile, year, session, duration_minutes, 'DRAFT'
            ))
            result = cur.fetchone()
            self.conn.commit()
            return result['id']

    def _add_exercise_to_variant(
        self, variant_id, exercise_id, order_index, section_name
    ):
        query = """
        INSERT INTO variant_exercises (variant_id, exercise_id, order_index, section_name)
        VALUES (%s, %s, %s, %s) ON CONFLICT (variant_id, exercise_id) DO NOTHING;
        """
        with self.conn.cursor() as cur:
            cur.execute(query, (variant_id, exercise_id, order_index, section_name))
        self.conn.commit()

    def _update_variant_points(self, variant_id, total_points):
        query = "UPDATE variants SET total_points = %s WHERE id = %s;"
        with self.conn.cursor() as cur:
            cur.execute(query, (total_points, variant_id))
        self.conn.commit()

# ═══════════════════════════════════════════════════════════════
#  Factory
# ═══════════════════════════════════════════════════════════════

def get_variant_generator(conn: Connection) -> VariantGenerator:
    """Factory function."""
    return VariantGenerator(conn)
