#!/usr/bin/env python3
"""
Import ierarhic de exerciții din JSON în baza de date PostgreSQL.

Suportă două formate:
  1. LEGACY  — format vechi cu tag_catalog[] + exercises[] plate
  2. IERARHIC — format nou cu exercises[] grupate cu subpoints[] nested

Ordinea de import:
  1. SOURCES         — inserează sursa (PDF-ul)
  2. SOURCE_SEGMENTS — creează câte un segment per pagină
  3. FLATTEN         — (doar ierarhic) desfac exerciții grupate → rânduri plate
  4. AUTO-TAGS       — (doar ierarhic) generez tag catalog din exerciții + meta
  5. TAGS            — upsert tag-uri
  6. EXERCISES       — upsert exerciții
  7. EXERCISE_TAGS   — leagă exerciții de tag-uri
  8. EXERCISE_SOURCE_SEGMENTS — leagă exerciții de segmente pagini
"""

import json
import sys
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from pathlib import Path
from copy import deepcopy

from answer_numeric import evaluate_numeric_answer
from database import get_db_conn
from psycopg.rows import dict_row


# Namespace stabil pentru UUID5 (NU schimba după ce ai date în DB)
EXERCISE_UUID_NS = uuid.UUID("3f2f3bd1-6cf8-4a68-9d33-8c1d4d7f7c3a")


class JSONImporter:
    def __init__(self, json_path: str = None, include_containers: bool = True,
                 json_data: dict = None, conn=None):
        """
        Args:
            json_path: Calea către fișierul JSON (opțional dacă json_data e dat)
            include_containers: Dacă True, importă și exercițiile container
            json_data: Date JSON direct (pentru apel din endpoint)
            conn: Conexiune DB existentă (pentru apel din endpoint)
        """
        self.json_path = json_path
        self.include_containers = include_containers
        self._json_data = json_data
        self.conn = conn

        # Cache pentru maparea id-urilor
        self.source_uuid_cache: Dict[str, uuid.UUID] = {}
        self.tag_uuid_cache: Dict[tuple, uuid.UUID] = {}  # (namespace, key) -> UUID
        self.exercise_uuid_cache: Dict[str, uuid.UUID] = {}
        self.segment_cache: Dict[tuple, uuid.UUID] = {}  # (source_id, page_start, page_end) -> UUID

        # Statistici
        self.stats = {
            'sources': 0,
            'segments': 0,
            'tags': 0,
            'exercises': 0,
            'exercise_tags': 0,
            'exercise_source_segments': 0,
            'containers': 0,
            'subpoints': 0,
        }

    # ──────────────────────────────────────────────────────
    #  Helper static methods
    # ──────────────────────────────────────────────────────

    @staticmethod
    def _first_non_empty(*values: Any) -> Optional[Any]:
        for v in values:
            if v is None:
                continue
            if isinstance(v, str) and v.strip() == "":
                continue
            return v
        return None

    @classmethod
    def _pick(cls, data: Dict[str, Any], keys: List[str]) -> Optional[Any]:
        return cls._first_non_empty(*[data.get(k) for k in keys])

    @staticmethod
    def _detect_format(data: Dict[str, Any]) -> str:
        """Detectează formatul JSON: 'hierarchical' sau 'legacy'."""
        exercises = data.get('exercises', [])
        if not exercises:
            return 'legacy'

        first = exercises[0]
        # Dacă are 'subiect' și 'exercise_num' → ierarhic
        if 'subiect' in first and 'exercise_num' in first:
            return 'hierarchical'
        return 'legacy'

    # ──────────────────────────────────────────────────────
    #  FLATTEN: exerciții grupate → rânduri plate
    # ──────────────────────────────────────────────────────

    def _flatten_exercises(self, exercises: List[Dict[str, Any]],
                           source_data: Dict[str, Any]) -> tuple:
        """
        Transformă exercițiile grupate (cu subpoints) în rânduri plate.

        Returns:
            (flat_exercises, auto_tag_catalog)
            - flat_exercises: lista de exerciții individuale cu metadata completă
            - auto_tag_catalog: lista de tag-uri auto-generate
        """
        flat_exercises = []
        tag_set = {}  # (namespace, key) -> label

        year = source_data.get('year')
        session = source_data.get('session')

        # Tag-uri globale din source
        if year:
            tag_set[('year', str(year))] = str(year)
        if session:
            tag_set[('session', session.lower())] = session.capitalize()

        for ex in exercises:
            subiect = ex.get('subiect', 1)
            exercise_num = ex.get('exercise_num', 1)
            external_id = ex.get('external_id')
            subpoints = ex.get('subpoints') or []
            parent_tags = ex.get('tags') or []

            # Construiește exercise_key: "S{subiect}-{num}"
            exercise_key = f"S{subiect}-{exercise_num}"

            # Tag-uri de poziție auto-generate
            tag_set[('subiect', str(subiect))] = f"Subiectul {subiect}"
            tag_set[('exercise', exercise_key)] = f"Exercițiul {exercise_key}"

            # Colectează tag-urile explicite din JSON
            for t in parent_tags:
                tag_set[(t['namespace'], t['key'])] = t.get('label', t['key'])

            # Tag-uri year/session per exercițiu
            year_session_tags = []
            if year:
                year_session_tags.append({'namespace': 'year', 'key': str(year), 'weight': 1.0})
            if session:
                year_session_tags.append({'namespace': 'session', 'key': session.lower(), 'weight': 1.0})

            if not subpoints:
                # ── Exercițiu simplu (fără subpuncte) ──
                path = f"S{subiect}/{exercise_num}"
                tag_set[('path', path)] = path

                auto_tags = [
                    {'namespace': 'subiect', 'key': str(subiect), 'weight': 1.0},
                    {'namespace': 'exercise', 'key': exercise_key, 'weight': 1.0},
                    {'namespace': 'path', 'key': path, 'weight': 1.0},
                ] + year_session_tags

                flat_ex = {
                    'external_id': external_id,
                    'exam_type': ex.get('exam_type', 'BAC'),
                    'profile': ex.get('profile'),
                    'item_type': ex.get('item_type', 'item'),
                    'statement_latex': ex.get('statement_latex', ''),
                    'statement_text': ex.get('statement_text'),
                    'answer_latex': ex.get('answer_latex'),
                    'solution_latex': self._pick(ex, ['solution_latex', 'rezolvare_latex']),
                    'scoring_guide_latex': self._pick(ex, ['scoring_guide_latex', 'barem_latex']),
                    'scoring_guide_text': self._pick(ex, ['scoring_guide_text', 'barem_text', 'barem']),
                    'difficulty': ex.get('difficulty'),
                    'estimated_time_sec': ex.get('estimated_time_sec'),
                    'points': ex.get('points', 5),
                    'status': ex.get('status', 'DRAFT'),
                    'source_ref': ex.get('source_ref'),
                    'metadata': {
                        'external_id': external_id,
                        'subiect': subiect,
                        'exercise_num': exercise_num,
                        'path': path,
                        'is_container': False,
                    },
                    'tags': parent_tags + auto_tags,
                }
                flat_exercises.append(flat_ex)

            else:
                # ── Exercițiu cu subpuncte → container + copii ──
                path_parent = f"S{subiect}/{exercise_num}"
                tag_set[('path', path_parent)] = path_parent

                # Container (parent)
                total_points = sum(sp.get('points', 5) for sp in subpoints)
                auto_tags_parent = [
                    {'namespace': 'subiect', 'key': str(subiect), 'weight': 1.0},
                    {'namespace': 'exercise', 'key': exercise_key, 'weight': 1.0},
                    {'namespace': 'path', 'key': path_parent, 'weight': 1.0},
                ] + year_session_tags

                container = {
                    'external_id': external_id,
                    'exam_type': ex.get('exam_type', 'BAC'),
                    'profile': ex.get('profile'),
                    'item_type': ex.get('item_type', 'problem'),
                    'statement_latex': ex.get('statement_latex', ''),
                    'statement_text': ex.get('statement_text'),
                    'answer_latex': ex.get('answer_latex'),
                    'solution_latex': self._pick(ex, ['solution_latex', 'rezolvare_latex']),
                    'scoring_guide_latex': self._pick(ex, ['scoring_guide_latex', 'barem_latex']),
                    'scoring_guide_text': self._pick(ex, ['scoring_guide_text', 'barem_text', 'barem']),
                    'difficulty': ex.get('difficulty'),
                    'estimated_time_sec': ex.get('estimated_time_sec'),
                    'points': total_points,
                    'status': ex.get('status', 'DRAFT'),
                    'source_ref': ex.get('source_ref'),
                    'metadata': {
                        'external_id': external_id,
                        'subiect': subiect,
                        'exercise_num': exercise_num,
                        'path': path_parent,
                        'is_container': True,
                        'subpoint_count': len(subpoints),
                        'subpoints': [sp['subpoint'] for sp in subpoints],
                    },
                    'tags': parent_tags + auto_tags_parent,
                }
                flat_exercises.append(container)
                self.stats['containers'] += 1

                # Copii (subpuncte)
                for sp in subpoints:
                    subpoint_letter = sp['subpoint']
                    child_ext_id = f"{external_id}-{subpoint_letter}"
                    path_child = f"S{subiect}/{exercise_num}/{subpoint_letter}"

                    tag_set[('subpoint', subpoint_letter)] = f"Punctul {subpoint_letter})"
                    tag_set[('path', path_child)] = path_child

                    auto_tags_child = [
                        {'namespace': 'subiect', 'key': str(subiect), 'weight': 1.0},
                        {'namespace': 'exercise', 'key': exercise_key, 'weight': 1.0},
                        {'namespace': 'subpoint', 'key': subpoint_letter, 'weight': 1.0},
                        {'namespace': 'path', 'key': path_child, 'weight': 1.0},
                    ] + year_session_tags

                    child = {
                        'external_id': child_ext_id,
                        'parent_external_id': external_id,
                        'exam_type': ex.get('exam_type', 'BAC'),
                        'profile': ex.get('profile'),
                        'item_type': ex.get('item_type', 'problem'),
                        'statement_latex': sp.get('statement_latex', ''),
                        'statement_text': sp.get('statement_text'),
                        'answer_latex': sp.get('answer_latex'),
                        'solution_latex': self._pick(sp, ['solution_latex', 'rezolvare_latex']),
                        'scoring_guide_latex': self._pick(sp, ['scoring_guide_latex', 'barem_latex']),
                        'scoring_guide_text': self._pick(sp, ['scoring_guide_text', 'barem_text', 'barem']),
                        'difficulty': sp.get('difficulty') or ex.get('difficulty'),
                        'estimated_time_sec': sp.get('estimated_time_sec'),
                        'points': sp.get('points', 5),
                        'status': ex.get('status', 'DRAFT'),
                        'source_ref': ex.get('source_ref'),
                        'metadata': {
                            'external_id': child_ext_id,
                            'parent_external_id': external_id,
                            'subiect': subiect,
                            'exercise_num': exercise_num,
                            'subpoint': subpoint_letter,
                            'path': path_child,
                            'is_container': False,
                        },
                        # Copilul moștenește tag-urile parentului + auto-tags proprii
                        'tags': parent_tags + auto_tags_child,
                    }
                    flat_exercises.append(child)
                    self.stats['subpoints'] += 1

        # Construiește tag catalog din tag_set
        auto_tag_catalog = [
            {'namespace': ns, 'key': key, 'label': label}
            for (ns, key), label in tag_set.items()
        ]

        return flat_exercises, auto_tag_catalog

    # ──────────────────────────────────────────────────────
    #  ENRICH LEGACY: adaugă position tags + parent metadata
    # ──────────────────────────────────────────────────────

    def _enrich_legacy_exercises(self, exercises: List[Dict[str, Any]],
                                  source_data: Dict[str, Any]) -> tuple:
        """
        Enrichează exercițiile legacy cu:
        1. Tag-uri de poziție (subiect, exercise, subpoint, path)
        2. Tag-uri year/session
        3. Metadata parent/child (is_container, parent_external_id)
        4. source_ref din metadata.page_start/page_end

        Detectează structura din:
        - external_id pattern: B2023-MI-V01-S{subiect}-{num}{subpoint?}
        - metadata.group pentru gruparea subpunctelor
        - item_type: subiect_1 / subiect_2 / subiect_3

        Returns: (enriched_exercises, extra_tag_catalog)
        """
        import re
        enriched = []
        tag_set = {}  # (namespace, key) -> label

        year = source_data.get('year')
        session = source_data.get('session')

        # Tag-uri globale
        if year:
            tag_set[('year', str(year))] = str(year)
        if session:
            tag_set[('session', session.lower())] = session.capitalize()

        # Primul pas: identificăm grupurile (containerele)
        # Grupăm exercițiile care au metadata.group
        groups: Dict[str, List[Dict]] = {}
        standalone: List[Dict] = []

        for ex in exercises:
            meta = ex.get('metadata', {})
            group_id = meta.get('group')
            if group_id:
                groups.setdefault(group_id, []).append(ex)
            else:
                standalone.append(ex)

        # Parsăm subiect/exercise_num din external_id
        # Pattern: ...-S{subiect}-{num}{letter?}  (ex: B2023-MI-V01-S1-3 sau B2023-MI-V01-S2-1a)
        ext_id_pattern = re.compile(r'S(\d+)-(\d+)([a-z])?$')

        def parse_ext_id(ext_id: str):
            m = ext_id_pattern.search(ext_id or '')
            if m:
                return int(m.group(1)), int(m.group(2)), m.group(3)
            return None, None, None

        # Procesăm exerciții standalone (Subiectul I)
        for ex in standalone:
            ext_id = ex.get('external_id', '')
            subiect, exercise_num, subpoint_letter = parse_ext_id(ext_id)

            if subiect is None:
                # Fallback: detectăm din item_type
                item_type = ex.get('item_type', '')
                if 'subiect_1' in item_type:
                    subiect = 1
                elif 'subiect_2' in item_type:
                    subiect = 2
                elif 'subiect_3' in item_type:
                    subiect = 3
                else:
                    subiect = 1
                exercise_num = 1

            path = f"S{subiect}/{exercise_num}"
            exercise_key = f"S{subiect}-{exercise_num}"

            tag_set[('subiect', str(subiect))] = f"Subiectul {subiect}"
            tag_set[('exercise', exercise_key)] = f"Exercițiul {exercise_key}"
            tag_set[('path', path)] = path

            # Construim auto-tags
            auto_tags = [
                {'namespace': 'subiect', 'key': str(subiect), 'weight': 1.0},
                {'namespace': 'exercise', 'key': exercise_key, 'weight': 1.0},
                {'namespace': 'path', 'key': path, 'weight': 1.0},
            ]
            if year:
                auto_tags.append({'namespace': 'year', 'key': str(year), 'weight': 1.0})
            if session:
                auto_tags.append({'namespace': 'session', 'key': session.lower(), 'weight': 1.0})

            enriched_ex = deepcopy(ex)
            existing_tags = enriched_ex.get('tags', [])
            enriched_ex['tags'] = existing_tags + auto_tags

            # Enrichim metadata
            meta = enriched_ex.get('metadata', {})
            meta['subiect'] = subiect
            meta['exercise_num'] = exercise_num
            meta['path'] = path
            meta['is_container'] = False
            enriched_ex['metadata'] = meta

            # source_ref din metadata dacă lipsește
            if not enriched_ex.get('source_ref'):
                page_start = meta.get('page_start')
                page_end = meta.get('page_end')
                if page_start:
                    enriched_ex['source_ref'] = {
                        'page_start': page_start,
                        'page_end': page_end or page_start
                    }

            enriched.append(enriched_ex)

        # Procesăm grupurile (Subiectul II/III cu subpuncte)
        for group_id, group_exs in groups.items():
            # Parsăm group_id: B2023-MI-V01-S2-1
            subiect, exercise_num, _ = parse_ext_id(group_id)
            if subiect is None:
                # Fallback: detectăm din item_type
                item_type = group_exs[0].get('item_type', '') if group_exs else ''
                if 'subiect_2' in item_type:
                    subiect = 2
                elif 'subiect_3' in item_type:
                    subiect = 3
                else:
                    subiect = 2
                exercise_num = 1

            path_parent = f"S{subiect}/{exercise_num}"
            exercise_key = f"S{subiect}-{exercise_num}"

            tag_set[('subiect', str(subiect))] = f"Subiectul {subiect}"
            tag_set[('exercise', exercise_key)] = f"Exercițiul {exercise_key}"
            tag_set[('path', path_parent)] = path_parent

            # Creăm exercițiul container
            first_ex = group_exs[0]
            subpoint_letters = []
            for gex in sorted(group_exs, key=lambda x: x.get('external_id', '')):
                _, _, sp = parse_ext_id(gex.get('external_id', ''))
                if sp:
                    subpoint_letters.append(sp)

            total_points = sum(gex.get('points', 5) for gex in group_exs)
            avg_difficulty = None
            diffs = [gex.get('difficulty') for gex in group_exs if gex.get('difficulty') is not None]
            if diffs:
                avg_difficulty = round(sum(diffs) / len(diffs))

            auto_tags_parent = [
                {'namespace': 'subiect', 'key': str(subiect), 'weight': 1.0},
                {'namespace': 'exercise', 'key': exercise_key, 'weight': 1.0},
                {'namespace': 'path', 'key': path_parent, 'weight': 1.0},
            ]
            if year:
                auto_tags_parent.append({'namespace': 'year', 'key': str(year), 'weight': 1.0})
            if session:
                auto_tags_parent.append({'namespace': 'session', 'key': session.lower(), 'weight': 1.0})

            # Refolosim tag-urile de conținut din primul exercițiu
            content_tags = [t for t in (first_ex.get('tags', []))
                          if t.get('namespace') not in ('subiect', 'exercise', 'path', 'subpoint', 'year', 'session')]

            container = {
                'external_id': group_id,
                'exam_type': first_ex.get('exam_type', 'bacalaureat'),
                'profile': first_ex.get('profile'),
                'item_type': first_ex.get('item_type', 'subiect_2'),
                'statement_latex': first_ex.get('statement_latex', '').split('\\newline')[0].strip(),
                'statement_text': None,
                'answer_latex': None,
                'solution_latex': None,
                'scoring_guide_latex': None,
                'scoring_guide_text': None,
                'difficulty': avg_difficulty,
                'estimated_time_sec': None,
                'points': total_points,
                'status': first_ex.get('status', 'DRAFT'),
                'metadata': {
                    'external_id': group_id,
                    'subiect': subiect,
                    'exercise_num': exercise_num,
                    'path': path_parent,
                    'is_container': True,
                    'subpoint_count': len(subpoint_letters),
                    'subpoints': subpoint_letters,
                },
                'tags': content_tags + auto_tags_parent,
            }

            # source_ref din primul exercițiu
            first_meta = first_ex.get('metadata', {})
            ps = first_meta.get('page_start')
            pe = first_meta.get('page_end')
            if ps:
                container['source_ref'] = {'page_start': ps, 'page_end': pe or ps}

            enriched.append(container)
            self.stats['containers'] += 1

            # Procesăm copiii
            for gex in sorted(group_exs, key=lambda x: x.get('external_id', '')):
                ext_id = gex.get('external_id', '')
                _, _, sp_letter = parse_ext_id(ext_id)
                if not sp_letter:
                    sp_letter = ext_id[-1] if ext_id else '?'

                path_child = f"S{subiect}/{exercise_num}/{sp_letter}"
                tag_set[('subpoint', sp_letter)] = f"Punctul {sp_letter})"
                tag_set[('path', path_child)] = path_child

                auto_tags_child = [
                    {'namespace': 'subiect', 'key': str(subiect), 'weight': 1.0},
                    {'namespace': 'exercise', 'key': exercise_key, 'weight': 1.0},
                    {'namespace': 'subpoint', 'key': sp_letter, 'weight': 1.0},
                    {'namespace': 'path', 'key': path_child, 'weight': 1.0},
                ]
                if year:
                    auto_tags_child.append({'namespace': 'year', 'key': str(year), 'weight': 1.0})
                if session:
                    auto_tags_child.append({'namespace': 'session', 'key': session.lower(), 'weight': 1.0})

                enriched_child = deepcopy(gex)
                child_content_tags = [t for t in (enriched_child.get('tags', []))
                                     if t.get('namespace') not in ('subiect', 'exercise', 'path', 'subpoint', 'year', 'session')]
                enriched_child['tags'] = child_content_tags + auto_tags_child

                # Enrichim metadata
                child_meta = enriched_child.get('metadata', {})
                child_meta['parent_external_id'] = group_id
                child_meta['subiect'] = subiect
                child_meta['exercise_num'] = exercise_num
                child_meta['subpoint'] = sp_letter
                child_meta['path'] = path_child
                child_meta['is_container'] = False
                enriched_child['metadata'] = child_meta
                enriched_child['parent_external_id'] = group_id

                # source_ref
                if not enriched_child.get('source_ref'):
                    cps = child_meta.get('page_start')
                    cpe = child_meta.get('page_end')
                    if cps:
                        enriched_child['source_ref'] = {
                            'page_start': cps,
                            'page_end': cpe or cps
                        }

                enriched.append(enriched_child)
                self.stats['subpoints'] += 1

        # Construiește tag catalog extra
        extra_tags = [
            {'namespace': ns, 'key': key, 'label': label}
            for (ns, key), label in tag_set.items()
        ]

        print(f"  [enrich-legacy] {len(enriched)} exerciții "
              f"({self.stats['containers']} containere, {self.stats['subpoints']} subpuncte)")

        return enriched, extra_tags

    # ──────────────────────────────────────────────────────
    #  LOAD
    # ──────────────────────────────────────────────────────

    def load_json(self) -> Dict[str, Any]:
        if self._json_data:
            return self._json_data

        with open(self.json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Validare minimă
        if 'exercises' not in data:
            raise ValueError("JSON-ul lipsește cheia obligatorie: exercises")
        if 'source' not in data:
            raise ValueError("JSON-ul lipsește cheia obligatorie: source")

        return data

    # ──────────────────────────────────────────────────────
    #  PAS 1: SOURCES
    # ──────────────────────────────────────────────────────

    def import_source(self, source_data: Dict[str, Any]) -> uuid.UUID:
        external_id = source_data.get('external_id')

        existing = self._find_source_by_external_id(external_id)
        if existing:
            print(f"  [source] deja există: {external_id} -> {existing}")
            self.source_uuid_cache[external_id] = existing

            # Dacă importul curent aduce fișiere noi (variantă / barem), suprascrie-le
            new_varianta = source_data.get('url_file_path')
            new_barem    = source_data.get('url_barem_path')
            if new_varianta or new_barem:
                parts = []
                vals  = []
                if new_varianta:
                    parts.append("url_file_path = %s")
                    vals.append(new_varianta)
                if new_barem:
                    parts.append("url_barem_path = %s")
                    vals.append(new_barem)
                vals.append(existing)
                with self.conn.cursor() as cur:
                    cur.execute(
                        f"UPDATE sources SET {', '.join(parts)} WHERE id = %s",
                        vals,
                    )
                print(f"  [source] actualizat fișiere: varianta={new_varianta} barem={new_barem}")

            return existing

        source_id = uuid.uuid4()
        year = source_data.get('year', '')
        type_val = source_data.get('type', 'BAC')
        profile = source_data.get('profile', '')
        file_name = source_data.get('file_name', '')

        file_path = f"{year}/{type_val}/{profile}/{file_name}" if all([year, type_val, profile, file_name]) else file_name

        notes = json.dumps({
            'external_id': external_id,
            'page_count': source_data.get('page_count'),
            'imported_at': datetime.now(timezone.utc).isoformat()
        })

        query = """
        INSERT INTO sources (id, name, type, year, session, profile, url_file_path, url_barem_path, notes, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
        """
        with self.conn.cursor() as cur:
            cur.execute(query, (
                source_id,
                source_data.get('name', f"Source {external_id}"),
                'pdf',
                source_data.get('year'),
                source_data.get('session'),
                source_data.get('profile') or None,
                source_data.get('url_file_path') or file_path or None,
                source_data.get('url_barem_path') or None,
                notes,
                datetime.now(timezone.utc)
            ))
            self.conn.commit()

        self.source_uuid_cache[external_id] = source_id
        self.stats['sources'] += 1
        print(f"  [source] creat: {external_id} -> {source_id}")
        return source_id

    # ──────────────────────────────────────────────────────
    #  PAS 2: SOURCE SEGMENTS
    # ──────────────────────────────────────────────────────

    def import_source_segments(self, source_id: uuid.UUID, page_count: int) -> List[uuid.UUID]:
        segment_ids = []
        query = """
        INSERT INTO source_segments (id, source_id, page_start, page_end, status, extraction_method, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
        """
        with self.conn.cursor() as cur:
            for page in range(1, page_count + 1):
                seg_id = uuid.uuid4()
                cur.execute(query, (seg_id, source_id, page, page, 'EXTRACTED', 'MANUAL', datetime.now(timezone.utc)))
                self.segment_cache[(source_id, page, page)] = seg_id
                segment_ids.append(seg_id)
            self.conn.commit()

        self.stats['segments'] += len(segment_ids)
        print(f"  [segments] creat {len(segment_ids)} segmente")
        return segment_ids

    # ──────────────────────────────────────────────────────
    #  PAS 3: TAGS
    # ──────────────────────────────────────────────────────

    def import_tags(self, tag_catalog: List[Dict[str, Any]]) -> Dict[tuple, uuid.UUID]:
        query_check = "SELECT id FROM tags WHERE namespace = %s AND key = %s"
        query_insert = """
        INSERT INTO tags (id, namespace, key, label, parent_id, created_at)
        VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
        """

        with self.conn.cursor() as cur:
            for tag in tag_catalog:
                namespace = tag['namespace']
                key = tag['key']
                label = tag.get('label', key)

                cur.execute(query_check, (namespace, key))
                row = cur.fetchone()

                if row:
                    self.tag_uuid_cache[(namespace, key)] = row[0]
                else:
                    tag_id = uuid.uuid4()
                    cur.execute(query_insert, (tag_id, namespace, key, label, None, datetime.now(timezone.utc)))
                    self.tag_uuid_cache[(namespace, key)] = tag_id
                    self.stats['tags'] += 1

            self.conn.commit()

        print(f"  [tags] procesat {len(tag_catalog)} tag-uri ({self.stats['tags']} noi)")
        return self.tag_uuid_cache

    # ──────────────────────────────────────────────────────
    #  PAS 4: EXERCISES
    # ──────────────────────────────────────────────────────

    def import_exercises(self, exercises: List[Dict[str, Any]]) -> Dict[str, uuid.UUID]:
        upsert_query = """
        INSERT INTO exercises (
            id, exam_type, profile, subject_part, item_type,
            statement_latex, statement_text, answer_latex, answer_numeric_value, answer_numeric_expression, solution_latex,
            scoring_guide_latex, scoring_guide_text,
            difficulty, estimated_time_sec, points, metadata, status,
            created_at, updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET
            exam_type = EXCLUDED.exam_type,
            profile = EXCLUDED.profile,
            subject_part = EXCLUDED.subject_part,
            item_type = EXCLUDED.item_type,
            statement_latex = EXCLUDED.statement_latex,
            statement_text = EXCLUDED.statement_text,
            answer_latex = EXCLUDED.answer_latex,
            answer_numeric_value = EXCLUDED.answer_numeric_value,
            answer_numeric_expression = EXCLUDED.answer_numeric_expression,
            solution_latex = EXCLUDED.solution_latex,
            scoring_guide_latex = EXCLUDED.scoring_guide_latex,
            scoring_guide_text = EXCLUDED.scoring_guide_text,
            difficulty = EXCLUDED.difficulty,
            estimated_time_sec = EXCLUDED.estimated_time_sec,
            points = EXCLUDED.points,
            metadata = EXCLUDED.metadata,
            status = EXCLUDED.status,
            updated_at = EXCLUDED.updated_at
        RETURNING id
        """

        item_type_map = {"item": "exercitiu", "problem": "problema"}
        exam_type_map = {"BAC": "bacalaureat", "EN": "evaluare_nationala"}

        with self.conn.cursor() as cur:
            for ex in exercises:
                external_id = ex.get('external_id')
                points = ex.get('points', 0)

                if not self.include_containers and points == 0:
                    continue

                if external_id:
                    exercise_id = uuid.uuid5(EXERCISE_UUID_NS, str(external_id))
                else:
                    exercise_id = uuid.uuid4()

                # Metadata — fie deja construită (ierarhic), fie construim (legacy)
                metadata = ex.get('metadata')
                if not metadata:
                    metadata = {
                        'external_id': external_id,
                        'parent_external_id': ex.get('parent_external_id'),
                        'imported_at': datetime.now(timezone.utc).isoformat(),
                    }

                metadata['imported_at'] = datetime.now(timezone.utc).isoformat()

                item_type = item_type_map.get(ex.get('item_type'), ex.get('item_type', 'exercitiu'))
                exam_type = exam_type_map.get(ex.get('exam_type'), ex.get('exam_type', 'bacalaureat'))

                solution_latex = ex.get('solution_latex') or self._pick(ex, ['rezolvare_latex', 'solution', 'rezolvare'])
                scoring_guide_latex = ex.get('scoring_guide_latex') or self._pick(ex, ['barem_latex', 'scoring_latex'])
                scoring_guide_text = ex.get('scoring_guide_text') or self._pick(ex, ['barem_text', 'barem'])
                if scoring_guide_text and not isinstance(scoring_guide_text, str):
                    scoring_guide_text = json.dumps(scoring_guide_text, ensure_ascii=False)
                answer_numeric_value, answer_numeric_expression = evaluate_numeric_answer(ex.get('answer_latex'))

                cur.execute(upsert_query, (
                    exercise_id,
                    exam_type,
                    ex.get('profile'),
                    None,  # subject_part
                    item_type,
                    ex.get('statement_latex', ''),
                    ex.get('statement_text'),
                    ex.get('answer_latex'),
                    answer_numeric_value,
                    answer_numeric_expression,
                    solution_latex,
                    scoring_guide_latex,
                    scoring_guide_text,
                    ex.get('difficulty'),
                    ex.get('estimated_time_sec'),
                    points,
                    json.dumps(metadata),
                    ex.get('status', 'DRAFT'),
                    datetime.now(timezone.utc),
                    datetime.now(timezone.utc),
                ))

                self.exercise_uuid_cache[external_id] = cur.fetchone()[0]
                self.stats['exercises'] += 1

            self.conn.commit()

        print(f"  [exercises] upsert {self.stats['exercises']} exerciții")
        return self.exercise_uuid_cache

    # ──────────────────────────────────────────────────────
    #  PAS 5: EXERCISE_TAGS
    # ──────────────────────────────────────────────────────

    def import_exercise_tags(self, exercises: List[Dict[str, Any]]):
        query = """
        INSERT INTO exercise_tags (exercise_id, tag_id, weight, confidence, created_by)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (exercise_id, tag_id) DO UPDATE
        SET weight = EXCLUDED.weight, confidence = EXCLUDED.confidence
        """

        with self.conn.cursor() as cur:
            for ex in exercises:
                external_id = ex.get('external_id')
                exercise_id = self.exercise_uuid_cache.get(external_id)
                if not exercise_id:
                    continue

                # Overwrite: ștergem legături vechi, punem noi
                cur.execute("DELETE FROM exercise_tags WHERE exercise_id = %s", (exercise_id,))

                for tag in (ex.get('tags') or []):
                    tag_id = self.tag_uuid_cache.get((tag['namespace'], tag['key']))
                    if not tag_id:
                        continue

                    cur.execute(query, (
                        exercise_id,
                        tag_id,
                        tag.get('weight', 1.0),
                        tag.get('confidence', 1.0),
                        'import_script'
                    ))
                    self.stats['exercise_tags'] += 1

            self.conn.commit()

        print(f"  [exercise_tags] creat {self.stats['exercise_tags']} legături")

    # ──────────────────────────────────────────────────────
    #  PAS 6: EXERCISE_SOURCE_SEGMENTS
    # ──────────────────────────────────────────────────────

    def import_exercise_source_segments(self, exercises: List[Dict[str, Any]], source_id: uuid.UUID):
        query = """
        INSERT INTO exercise_source_segments (exercise_id, source_segment_id, role)
        VALUES (%s, %s, %s)
        ON CONFLICT (exercise_id, source_segment_id) DO NOTHING
        """

        with self.conn.cursor() as cur:
            for ex in exercises:
                external_id = ex.get('external_id')
                exercise_id = self.exercise_uuid_cache.get(external_id)
                if not exercise_id:
                    continue

                cur.execute("DELETE FROM exercise_source_segments WHERE exercise_id = %s", (exercise_id,))

                source_ref = ex.get('source_ref') or {}
                page_start = source_ref.get('page_start')
                page_end = source_ref.get('page_end')
                if not (page_start and page_end):
                    continue

                for page in range(page_start, page_end + 1):
                    seg_id = self.segment_cache.get((source_id, page, page))
                    if seg_id:
                        cur.execute(query, (exercise_id, seg_id, 'statement'))
                        self.stats['exercise_source_segments'] += 1

            self.conn.commit()

        print(f"  [exercise_source_segments] creat {self.stats['exercise_source_segments']} legături")

    # ──────────────────────────────────────────────────────
    #  RUN — orchestrator principal
    # ──────────────────────────────────────────────────────

    def run(self) -> Dict[str, Any]:
        """Rulează importul complet. Returnează statisticile."""
        print("═══ Import JSON în baza de date ═══\n")

        # 1. Încarcă JSON
        data = self.load_json()
        fmt = self._detect_format(data)
        print(f"  Format detectat: {fmt}")
        print(f"  Exerciții în JSON: {len(data.get('exercises', []))}\n")

        # Obține conexiune la DB
        own_conn = False
        if self.conn is None:
            conn_gen = get_db_conn()
            self.conn = next(conn_gen)
            own_conn = True

        try:
            # PAS 1: SOURCES
            print("─── Pas 1: SOURCES ───")
            source_data = data['source']
            source_id = self.import_source(source_data)

            # PAS 2: SOURCE SEGMENTS
            print("─── Pas 2: SOURCE_SEGMENTS ───")
            page_count = source_data.get('page_count', 0)
            if page_count > 0:
                self.import_source_segments(source_id, page_count)
            else:
                print("  [segments] skip (page_count=0)")

            # PAS 3: FLATTEN + AUTO-TAGS (doar ierarhic)
            if fmt == 'hierarchical':
                print("─── Pas 3: FLATTEN + AUTO-TAGS ───")
                flat_exercises, auto_tag_catalog = self._flatten_exercises(
                    data['exercises'], source_data
                )
                print(f"  [flatten] {len(flat_exercises)} exerciții plate "
                      f"({self.stats['containers']} containere, {self.stats['subpoints']} subpuncte)")

                # PAS 4: TAGS (auto-generate)
                print("─── Pas 4: TAGS ───")
                self.import_tags(auto_tag_catalog)

            else:
                # Legacy: enrichim exercițiile cu position tags + parent metadata
                print("─── Pas 3: ENRICH LEGACY + TAGS ───")
                flat_exercises, extra_tags = self._enrich_legacy_exercises(
                    data['exercises'], source_data
                )
                # Combinăm tag_catalog din JSON + tag-urile extra generate
                all_tags = data.get('tag_catalog', data.get('tags', [])) + extra_tags
                self.import_tags(all_tags)

            # PAS 5: EXERCISES
            print("─── Pas 5: EXERCISES ───")
            self.import_exercises(flat_exercises)

            # PAS 6: EXERCISE_TAGS
            print("─── Pas 6: EXERCISE_TAGS ───")
            self.import_exercise_tags(flat_exercises)

            # PAS 7: EXERCISE_SOURCE_SEGMENTS
            print("─── Pas 7: EXERCISE_SOURCE_SEGMENTS ───")
            self.import_exercise_source_segments(flat_exercises, source_id)

            # Raport
            print("\n═══ SUMAR ═══")
            for key, value in self.stats.items():
                if value > 0:
                    print(f"  {key}: {value}")
            print("\n✓ Import finalizat!")

            return self.stats

        except Exception as e:
            print(f"\n✗ Eroare la import: {e}")
            if self.conn:
                self.conn.rollback()
            raise
        finally:
            if own_conn:
                try:
                    next(conn_gen)
                except StopIteration:
                    pass

    # ──────────────────────────────────────────────────────
    #  Helpers
    # ──────────────────────────────────────────────────────

    def _find_source_by_external_id(self, external_id: str) -> Optional[uuid.UUID]:
        query = "SELECT id FROM sources WHERE notes LIKE %s LIMIT 1"
        with self.conn.cursor() as cur:
            cur.execute(query, (f'%"external_id": "{external_id}"%',))
            row = cur.fetchone()
            return row[0] if row else None

    def _find_exercise_by_external_id(self, external_id: str) -> Optional[uuid.UUID]:
        query = "SELECT id FROM exercises WHERE metadata::jsonb->>'external_id' = %s LIMIT 1"
        with self.conn.cursor() as cur:
            cur.execute(query, (external_id,))
            row = cur.fetchone()
            return row[0] if row else None


# ──────────────────────────────────────────────────────
#  CLI
# ──────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: python import_json.py <path-to-json> [--include-containers]")
        sys.exit(1)

    json_path = sys.argv[1]
    include_containers = '--include-containers' in sys.argv

    if not Path(json_path).exists():
        print(f"Eroare: Fișierul {json_path} nu există!")
        sys.exit(1)

    importer = JSONImporter(json_path, include_containers=include_containers)
    importer.run()


if __name__ == '__main__':
    main()
