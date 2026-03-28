"""
HTML Generator — generează pagini HTML cu KaTeX pentru Rezolvare / Barem.
Randarea matematică este identică cu Previzualizarea Live din editor.
"""
import json
import uuid
import logging
from html import escape
from datetime import datetime
from typing import Optional

from psycopg import Connection
from psycopg.rows import dict_row

logger = logging.getLogger(__name__)

EXAM_TYPE_LABELS = {
    'bacalaureat': 'BACALAUREAT',
    'evaluare_nationala': 'EVALUARE NAȚIONALĂ',
    'simulare': 'SIMULARE',
    'olimpiada': 'OLIMPIADĂ',
    'alta': 'TEST',
}

SECTION_ORDER = {'Subiectul I': 0, 'Subiectul II': 1, 'Subiectul III': 2}

CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: 'Times New Roman', serif;
    font-size: 11pt;
    color: #111;
    background: #fff;
    max-width: 800px;
    margin: 0 auto;
    padding: 24px 32px 40px;
}
.print-bar {
    position: fixed; top: 0; left: 0; right: 0;
    background: #1c1c1c; color: #fff;
    padding: 10px 24px;
    display: flex; align-items: center; justify-content: space-between;
    z-index: 100; font-family: sans-serif; font-size: 13px;
}
.print-bar span { opacity: 0.7; }
.btn-print {
    background: #2980b9; color: #fff; border: none;
    padding: 7px 20px; border-radius: 5px; cursor: pointer;
    font-size: 13px; font-weight: bold;
}
.btn-print:hover { background: #1a6fa0; }
.btn-print:disabled { background: #666; cursor: not-allowed; opacity: 0.7; }
.content { margin-top: 52px; }
.doc-header {
    border-bottom: 2px solid #111;
    padding-bottom: 10px;
    margin-bottom: 14px;
    text-align: center;
}
.doc-title { font-size: 18pt; font-weight: bold; }
.doc-subtitle { font-size: 11pt; margin-top: 3px; color: #333; }
.doc-meta { font-size: 10pt; color: #666; margin-top: 2px; font-style: italic; }
.mode-badge {
    display: inline-block;
    background: #1a5276; color: #fff;
    padding: 3px 12px; border-radius: 12px;
    font-size: 10pt; font-weight: bold; margin-top: 6px;
    font-family: sans-serif;
}
.mode-badge.barem { background: #1e8449; }
.section-header {
    background: #1c1c1c; color: #fff;
    padding: 7px 14px; margin: 22px 0 12px;
    font-weight: bold; font-size: 12pt; text-align: center;
    font-family: sans-serif;
}
.exercise { margin-bottom: 18px; }
.exercise-header {
    display: flex; justify-content: space-between;
    align-items: baseline;
    border-bottom: 1px solid #ddd; padding-bottom: 3px;
    margin-bottom: 6px;
}
.exercise-num { font-weight: bold; font-size: 11pt; }
.exercise-pts { font-size: 9.5pt; color: #666; font-style: italic; font-family: sans-serif; }
.statement { margin: 4px 0 8px 8px; line-height: 1.6; }
.solution-block {
    margin: 8px 0 4px 8px;
    border-left: 3px solid #2980b9;
    padding: 6px 10px;
    background: #eaf4fb;
    border-radius: 0 6px 6px 0;
}
.solution-block.barem {
    border-left-color: #27ae60;
    background: #eafaf1;
}
.solution-label {
    font-weight: bold; font-size: 9.5pt;
    color: #1a5276; margin-bottom: 4px;
    font-family: sans-serif;
}
.solution-label.barem { color: #1e8449; }
.solution-content { line-height: 1.65; }
.subpoint { margin: 8px 0 6px 16px; }
.subpoint-header {
    display: flex; justify-content: space-between; align-items: baseline;
}
.subpoint-label { font-weight: bold; font-size: 10.5pt; }
.subpoint-pts { font-size: 9pt; color: #666; font-style: italic; font-family: sans-serif; }
.subpoint-stmt { margin: 3px 0 5px 10px; line-height: 1.6; }
.instructions {
    background: #f7f7f7; border: 1px solid #ccc;
    border-radius: 5px; padding: 8px 14px;
    margin-bottom: 14px; font-family: sans-serif; font-size: 9.5pt;
}
.instr-row { margin: 3px 0; color: #222; }
.footer {
    margin-top: 32px; border-top: 1px solid #ccc;
    padding-top: 8px; text-align: center;
    font-size: 8.5pt; color: #999; font-style: italic; font-family: sans-serif;
}
@media print {
    .print-bar { display: none !important; }
    .content { margin-top: 0 !important; }
    body { padding: 10mm 15mm; max-width: 100%; font-size: 10.5pt; }
    .section-header {
        background: #fff !important;
        color: #000 !important;
        border: 2px solid #000;
        border-radius: 0;
    }
    .solution-block {
        background: #fff !important;
        -webkit-print-color-adjust: exact;
        print-color-adjust: exact;
    }
    .solution-block.barem {
        background: #fff !important;
    }
    .mode-badge {
        background: #fff !important;
        color: #000 !important;
        border: 1px solid #000;
        -webkit-print-color-adjust: exact;
        print-color-adjust: exact;
    }
    a { text-decoration: none; color: #000; }
}
"""

KATEX_HEAD = """
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css">
<script src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
<script>
  document.addEventListener('DOMContentLoaded', function() {
    renderMathInElement(document.body, {
      delimiters: [
        {left: '$$', right: '$$', display: true},
        {left: '$', right: '$', display: false}
      ],
      throwOnError: false
    });
    var btn = document.getElementById('btn-print');
    btn.disabled = false;
    btn.textContent = '⬇️ Descarcă PDF';

    btn.addEventListener('click', function() {
      btn.disabled = true;
      btn.textContent = 'Se generează...';
      var filename = document.title.replace(/[^a-zA-Z0-9_\-\.]/g, '_') + '.pdf';
      var opt = {
        margin: [10, 12, 10, 12],
        filename: filename,
        image: { type: 'jpeg', quality: 0.98 },
        html2canvas: { scale: 2, useCORS: true, logging: false },
        jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' }
      };
      html2pdf().set(opt).from(document.getElementById('printable')).save()
        .then(function() {
          btn.disabled = false;
          btn.textContent = '⬇️ Descarcă PDF';
        });
    });
  });
</script>
"""


class VariantHTMLGenerator:

    def __init__(self, conn: Connection):
        self.conn = conn

    def generate(self, variant_id: uuid.UUID, mode: str = 'exam') -> str:
        variant = self._get_variant(variant_id)
        exercises = self._get_exercises(variant_id)
        groups_by_section = self._group_by_section(exercises)

        if mode == 'solutions':
            mode_label = 'REZOLVARE'
            badge_class = ''
        elif mode == 'barem':
            mode_label = 'BAREM DE CORECTARE'
            badge_class = 'barem'
        else:
            mode_label = ''
            badge_class = ''

        exam_label = EXAM_TYPE_LABELS.get(variant.get('exam_type', ''), 'EXAMEN')
        year = variant.get('year') or ''
        profile = variant.get('profile') or ''
        name = escape(variant.get('name') or '')
        duration = variant.get('duration_minutes') or 0
        total_pts = variant.get('total_points') or 0
        now = datetime.now().strftime('%d.%m.%Y %H:%M')

        body_parts = []

        # Header
        badge_html = f'<div><span class="mode-badge {badge_class}">{escape(mode_label)}</span></div>' if mode_label else ''
        body_parts.append(f'''
<div class="doc-header">
  <div class="doc-title">{escape(exam_label)}{" " + str(year) if year else ""}</div>
  {"<div class='doc-subtitle'>Matematică — Profil " + escape(profile.title()) + "</div>" if profile else ""}
  <div class="doc-meta">Proba E.c &nbsp;|&nbsp; {name}</div>
  {badge_html}
</div>
''')

        # Instructions (only for exam mode)
        if mode == 'exam':
            instr_items = ['Toate subiectele sunt obligatorii.', 'Se acordă 10 puncte din oficiu.']
            if duration:
                h, m = duration // 60, duration % 60
                instr_items.append(f'Timp efectiv de lucru: {h} ore{"" if m == 0 else f" {m} min"}.')
            if total_pts:
                instr_items.append(f'Punctaj total: {total_pts} puncte (plus 10 puncte din oficiu).')
            rows = ''.join(f'<div class="instr-row">• &nbsp;{escape(i)}</div>' for i in instr_items)
            body_parts.append(f'<div class="instructions">{rows}</div>')

        sorted_sections = sorted(
            groups_by_section.items(),
            key=lambda x: SECTION_ORDER.get(x[0], 99)
        )

        for section_name, groups in sorted_sections:
            section_points = sum(
                (c.get('points') or 0)
                for g in groups
                for c in (g['children'] if g['type'] == 'problem' else [g['exercise']])
            )
            pts_text = f' — {section_points} de puncte' if section_points else ''
            body_parts.append(
                f'<div class="section-header">{escape(section_name.upper())}{escape(pts_text)}</div>'
            )

            simple_counter = 0
            problem_counter = 0
            for group in groups:
                if group['type'] == 'simple':
                    simple_counter += 1
                    body_parts.append(self._render_exercise(simple_counter, group['exercise'], mode))
                else:
                    problem_counter += 1
                    parent_stmt = self._get_parent_statement(group['parent_id'])
                    body_parts.append(self._render_problem(problem_counter, group['children'], parent_stmt, mode))

        body_parts.append(f'<div class="footer">© {datetime.now().year} EtoX Academy &nbsp;·&nbsp; Generat: {now} &nbsp;·&nbsp; uz educațional</div>')

        html = f"""<!DOCTYPE html>
<html lang="ro">
<head>
<meta charset="UTF-8">
<title>{escape(name)} — {escape(mode_label)}</title>
{KATEX_HEAD}
<style>{CSS}</style>
</head>
<body>
<div class="print-bar">
  <span>EtoX Academy — {escape(mode_label) if mode_label else "Subiect"}</span>
  <button id="btn-print" class="btn-print" disabled>Se încarcă...</button>
</div>
<div id="printable" class="content">
{"".join(body_parts)}
</div>
</body>
</html>"""
        return html

    # ── Renderers ─────────────────────────────────────────────

    def _render_exercise(self, number: int, exercise: dict, mode: str) -> str:
        pts = exercise.get('points') or 0
        pts_str = f'{pts} puncte' if pts else ''
        stmt = exercise.get('statement_latex') or exercise.get('statement_text') or ''

        solution_html = self._solution_block(exercise, mode)

        return f"""
<div class="exercise">
  <div class="exercise-header">
    <span class="exercise-num">{number}.</span>
    <span class="exercise-pts">{escape(pts_str)}</span>
  </div>
  <div class="statement">{self._render_text(stmt)}</div>
  {solution_html}
</div>"""

    def _render_problem(self, number: int, children: list, parent_stmt: str, mode: str) -> str:
        total_pts = sum(c.get('points') or 0 for c in children)
        pts_str = f'{total_pts} puncte' if total_pts else ''

        parts = [f"""
<div class="exercise">
  <div class="exercise-header">
    <span class="exercise-num">{number}.</span>
    <span class="exercise-pts">{escape(pts_str)}</span>
  </div>"""]

        if parent_stmt:
            parts.append(f'  <div class="statement">{self._render_text(parent_stmt)}</div>')

        for child in children:
            meta = child.get('metadata') or {}
            if isinstance(meta, str):
                meta = json.loads(meta)
            subpoint = meta.get('subpoint', '')
            pts = child.get('points') or 0
            pts_str_sub = f'{pts} puncte' if pts else ''
            stmt = child.get('statement_latex') or child.get('statement_text') or ''

            solution_html = self._solution_block(child, mode)
            parts.append(f"""
  <div class="subpoint">
    <div class="subpoint-header">
      <span class="subpoint-label">{escape(subpoint)})</span>
      <span class="subpoint-pts">{escape(pts_str_sub)}</span>
    </div>
    <div class="subpoint-stmt">{self._render_text(stmt)}</div>
    {solution_html}
  </div>""")

        parts.append('</div>')
        return ''.join(parts)

    def _solution_block(self, exercise: dict, mode: str) -> str:
        if mode == 'exam':
            return ''
        if mode == 'solutions':
            content = exercise.get('solution_latex') or exercise.get('answer_latex') or ''
            if not content:
                return ''
            label = 'Rezolvare:'
            cls = ''
        else:  # barem
            content = exercise.get('scoring_guide_latex') or exercise.get('scoring_guide_text') or exercise.get('answer_latex') or ''
            if not content:
                return ''
            pts = exercise.get('points') or 0
            label = f'Barem ({pts}p):' if pts else 'Barem:'
            cls = 'barem'

        return f"""
<div class="solution-block {cls}">
  <div class="solution-label {cls}">{escape(label)}</div>
  <div class="solution-content">{self._render_text(content)}</div>
</div>"""

    def _render_text(self, text: str) -> str:
        """Escape HTML but preserve LaTeX delimiters for KaTeX auto-render."""
        if not text:
            return ''
        # Preserve $...$ and $$...$$ — KaTeX will handle them
        # Split on math delimiters, escape only text parts
        import re
        parts = re.split(r'(\$\$[\s\S]*?\$\$|\$[^\$]+\$)', text)
        result = []
        for part in parts:
            if part.startswith('$$') or (part.startswith('$') and part.endswith('$') and len(part) > 1):
                result.append(part)  # raw LaTeX — KaTeX renders this
            else:
                # escape HTML, convert newlines
                escaped = escape(part).replace('\n', '<br>')
                result.append(escaped)
        return ''.join(result)

    # ── Data ──────────────────────────────────────────────────

    def _get_variant(self, variant_id: uuid.UUID) -> dict:
        query = """
        SELECT id, name, exam_type, profile, year, session,
               total_points, duration_minutes, instructions
        FROM variants WHERE id = %s;
        """
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, (variant_id,))
            return cur.fetchone() or {}

    def _get_exercises(self, variant_id: uuid.UUID) -> list:
        query = """
        SELECT ve.order_index, ve.section_name,
               e.statement_latex, e.statement_text, e.points,
               e.answer_latex, e.solution_latex,
               e.scoring_guide_latex, e.scoring_guide_text, e.metadata
        FROM variant_exercises ve
        JOIN exercises e ON ve.exercise_id = e.id
        WHERE ve.variant_id = %s
        ORDER BY ve.order_index;
        """
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, (variant_id,))
            return cur.fetchall()

    def _group_by_section(self, exercises: list) -> dict:
        sections: dict = {}
        for ex in exercises:
            section = ex.get('section_name') or 'Exerciții'
            if section not in sections:
                sections[section] = []
            meta = ex.get('metadata') or {}
            if isinstance(meta, str):
                meta = json.loads(meta)
            parent_id = meta.get('parent_external_id')
            groups = sections[section]
            if parent_id:
                if groups and groups[-1].get('type') == 'problem' and groups[-1].get('parent_id') == parent_id:
                    groups[-1]['children'].append(ex)
                else:
                    groups.append({'type': 'problem', 'parent_id': parent_id, 'children': [ex]})
            else:
                groups.append({'type': 'simple', 'exercise': ex})
        return sections

    def _get_parent_statement(self, parent_external_id: str) -> str:
        query = """
        SELECT statement_latex, statement_text
        FROM exercises
        WHERE metadata::jsonb->>'external_id' = %s
          AND (metadata::jsonb->>'is_container')::boolean IS TRUE
        LIMIT 1;
        """
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, (parent_external_id,))
            row = cur.fetchone()
        if row:
            return row['statement_latex'] or row['statement_text'] or ''
        return ''


def get_html_generator(conn: Connection) -> VariantHTMLGenerator:
    return VariantHTMLGenerator(conn)
