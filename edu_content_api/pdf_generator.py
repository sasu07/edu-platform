"""
PDF Generator - Generare PDF stil oficial BAC cu LaTeX rendering via matplotlib.
Logo + copyright EtoX Academy.
Font: DejaVu Sans (suport complet diacritice românești).
"""
import os
import re
import uuid
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from io import BytesIO

import json

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image,
    Table, TableStyle, KeepTogether
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.lib import colors
from reportlab.platypus.flowables import HRFlowable
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from psycopg import Connection
from psycopg.rows import dict_row

logger = logging.getLogger(__name__)

# ─── Register DejaVu Sans fonts (Romanian diacritics support) ─────
import matplotlib as _mpl
_FONT_DIR = os.path.join(os.path.dirname(_mpl.__file__), 'mpl-data', 'fonts', 'ttf')
_FONTS_REGISTERED = False

def _register_fonts():
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return
    font_map = {
        'DejaVuSans': 'DejaVuSans.ttf',
        'DejaVuSans-Bold': 'DejaVuSans-Bold.ttf',
        'DejaVuSans-Oblique': 'DejaVuSans-Oblique.ttf',
        'DejaVuSans-BoldOblique': 'DejaVuSans-BoldOblique.ttf',
    }
    for name, filename in font_map.items():
        path = os.path.join(_FONT_DIR, filename)
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont(name, path))
            except Exception:
                pass
    # Register font family for <b> and <i> tags in Paragraph
    from reportlab.pdfbase.pdfmetrics import registerFontFamily
    registerFontFamily(
        'DejaVuSans',
        normal='DejaVuSans',
        bold='DejaVuSans-Bold',
        italic='DejaVuSans-Oblique',
        boldItalic='DejaVuSans-BoldOblique',
    )
    _FONTS_REGISTERED = True

# Path to logo
ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets')
LOGO_PATH = os.path.join(ASSETS_DIR, 'logo_etox.png')

EXAM_TYPE_LABELS = {
    'bacalaureat': 'BACALAUREAT',
    'evaluare_nationala': 'EVALUARE NAȚIONALĂ',
    'simulare': 'SIMULARE',
    'olimpiada': 'OLIMPIADĂ',
    'alta': 'TEST',
}

SECTION_ORDER = {
    'Subiectul I': 0,
    'Subiectul II': 1,
    'Subiectul III': 2,
}

# Font names
FONT = 'DejaVuSans'
FONT_BOLD = 'DejaVuSans-Bold'
FONT_ITALIC = 'DejaVuSans-Oblique'
FONT_BOLD_ITALIC = 'DejaVuSans-BoldOblique'


# ─── LaTeX rendering helpers ───────────────────────────────────

def _render_math_to_image(latex_str, fontsize=13, dpi=150):
    """Render a LaTeX math expression to PNG via matplotlib mathtext."""
    clean = latex_str.strip().strip('$')
    if not clean:
        return None
    # matplotlib mathtext cannot handle environments
    if '\\begin{' in clean or '\\end{' in clean:
        return None

    # Clean up for matplotlib mathtext compatibility
    clean = clean.replace('\\dfrac', '\\frac')
    clean = clean.replace('\\displaystyle', '')
    clean = clean.replace('\\newline', ' ')
    clean = clean.replace('\\,', '\\;')
    clean = clean.replace('\\!', '')
    clean = clean.replace('\\text{', '\\mathrm{')
    clean = clean.replace('\\circ', '{^{\\circ}}')
    clean = clean.replace('\\ge ', '\\geq ')
    clean = clean.replace('\\ge\\', '\\geq\\')
    clean = clean.replace('\\le ', '\\leq ')
    clean = clean.replace('\\le\\', '\\leq\\')
    # Handle \ge at end of string
    if clean.endswith('\\ge'):
        clean = clean[:-3] + '\\geq'
    if clean.endswith('\\le'):
        clean = clean[:-3] + '\\leq'
    clean = clean.replace('\\bigl', '')
    clean = clean.replace('\\bigr', '')
    clean = clean.replace('\\Bigl', '')
    clean = clean.replace('\\Bigr', '')
    clean = clean.replace('\\left(', '(')
    clean = clean.replace('\\right)', ')')
    clean = clean.replace('\\left[', '[')
    clean = clean.replace('\\right]', ']')
    clean = clean.replace('\\left\\{', '\\{')
    clean = clean.replace('\\right\\}', '\\}')
    clean = clean.replace('\\left|', '|')
    clean = clean.replace('\\right|', '|')
    # Remove any remaining \ge or \le without space
    clean = re.sub(r'\\ge(?=[^a-zA-Z]|$)', r'\\geq', clean)
    clean = re.sub(r'\\le(?=[^a-zA-Z]|$)', r'\\leq', clean)

    try:
        fig = plt.figure(figsize=(0.01, 0.01))
        fig.text(0, 0, f'${clean}$', fontsize=fontsize, math_fontfamily='dejavuserif')
        buf = BytesIO()
        fig.savefig(buf, format='png', dpi=dpi, bbox_inches='tight',
                    pad_inches=0.02, transparent=True)
        plt.close(fig)
        buf.seek(0)
        return buf
    except Exception as e:
        logger.warning(f"Math render failed for: {clean[:60]}... -> {e}")
        plt.close('all')
        return None


def _clean_latex_to_unicode(text):
    """Convert LaTeX to readable Unicode as fallback."""
    if not text:
        return ""

    replacements = {
        '\\mathbb{R}': '\u211d', '\\mathbb{N}': '\u2115',
        '\\mathbb{Z}': '\u2124', '\\mathbb{Q}': '\u211a',
        '\\mathbb{C}': '\u2102',
        '\\in': '\u2208', '\\notin': '\u2209',
        '\\subset': '\u2282', '\\subseteq': '\u2286',
        '\\cup': '\u222a', '\\cap': '\u2229',
        '\\forall': '\u2200', '\\exists': '\u2203',
        '\\to': '\u2192', '\\rightarrow': '\u2192',
        '\\leftarrow': '\u2190', '\\Rightarrow': '\u21d2',
        '\\Leftarrow': '\u21d0', '\\Leftrightarrow': '\u21d4',
        '\\infty': '\u221e', '\\int': '\u222b',
        '\\sum': '\u2211', '\\prod': '\u220f',
        '\\sqrt': '\u221a', '\\circ': '\u00b0',
        '\\leq': '\u2264', '\\geq': '\u2265',
        '\\neq': '\u2260', '\\approx': '\u2248',
        '\\equiv': '\u2261', '\\times': '\u00d7',
        '\\cdot': '\u00b7', '\\pm': '\u00b1',
        '\\alpha': '\u03b1', '\\beta': '\u03b2',
        '\\gamma': '\u03b3', '\\delta': '\u03b4',
        '\\epsilon': '\u03b5', '\\varepsilon': '\u03b5',
        '\\theta': '\u03b8', '\\lambda': '\u03bb',
        '\\mu': '\u03bc', '\\pi': '\u03c0',
        '\\sigma': '\u03c3', '\\omega': '\u03c9',
        '\\phi': '\u03c6', '\\Delta': '\u0394',
        '\\Sigma': '\u03a3', '\\Omega': '\u03a9',
        '\\emptyset': '\u2205', '\\ldots': '\u2026',
        '\\cdots': '\u22ef', '\\langle': '\u27e8',
        '\\rangle': '\u27e9',
        '\\newline': '\n', '\\\\': '\n',
        '\\,': ' ', '\\;': ' ', '\\!': '',
        '\\quad': '  ', '\\qquad': '    ',
        '\\left(': '(', '\\right)': ')',
        '\\left[': '[', '\\right]': ']',
        '\\left\\{': '{', '\\right\\}': '}',
        '\\left|': '|', '\\right|': '|',
    }

    # Sort by longest key first to avoid prefix conflicts (e.g. \in vs \infty)
    for latex_cmd, unicode_char in sorted(replacements.items(), key=lambda x: -len(x[0])):
        text = text.replace(latex_cmd, unicode_char)

    text = re.sub(r'\\d?frac\{([^}]+)\}\{([^}]+)\}', r'(\1)/(\2)', text)
    text = re.sub(r'\\sqrt\{([^}]+)\}', '√(\\1)', text)
    text = re.sub(r'\\log_\{([^}]+)\}', r'log_\1', text)
    text = text.replace('\\ln', 'ln')
    text = re.sub(r'\^{([^}]+)}', r'^\1', text)
    text = re.sub(r'_\{([^}]+)\}', r'_\1', text)
    text = re.sub(r'\\(?:text|mathrm)\{([^}]+)\}', r'\1', text)
    text = re.sub(r'\\overline\{([^}]+)\}', r'\1', text)

    # Handle \begin{cases} as text fallback
    def format_cases(match):
        content = match.group(1)
        rows = [r.strip() for r in content.split('\\\\')]
        formatted = []
        for row in rows:
            if row.strip():
                formatted.append('  ' + row.strip())
        return '{ ' + ' ; '.join(formatted)

    text = re.sub(r'\\begin\{cases\}(.+?)\\end\{cases\}', format_cases, text, flags=re.DOTALL)

    # Remove \ge \le leftovers
    text = text.replace('\\ge', '\u2265')
    text = text.replace('\\le', '\u2264')

    text = re.sub(r'\$([^\$]+)\$', r'\1', text)
    text = re.sub(r'\\[a-zA-Z]+', '', text)
    text = text.replace('{', '').replace('}', '')
    text = re.sub(r'  +', ' ', text)
    return text.strip()


def _render_environment_table(latex_str):
    """Render \begin{pmatrix}, \begin{bmatrix}, or \begin{cases} as a ReportLab Table."""
    # Try matrix first
    m = re.search(r'\\begin\{(pmatrix|bmatrix)\}(.+?)\\end\{(?:pmatrix|bmatrix)\}', latex_str, re.DOTALL)
    if m:
        return _build_matrix_table(m.group(1), m.group(2))

    # Try cases (system of equations)
    m = re.search(r'\\begin\{cases\}(.+?)\\end\{cases\}', latex_str, re.DOTALL)
    if m:
        return _build_cases_table(m.group(1))

    return None


def _build_matrix_table(matrix_type, content):
    """Build a ReportLab Table for a matrix."""
    rows = [r.strip() for r in content.split('\\\\') if r.strip()]
    table_data = []
    for row in rows:
        cells = [c.strip() for c in row.split('&')]
        clean_cells = [_clean_latex_to_unicode(cell) for cell in cells]
        table_data.append(clean_cells)

    if not table_data:
        return None

    left_bracket = '(' if matrix_type == 'pmatrix' else '['
    right_bracket = ')' if matrix_type == 'pmatrix' else ']'

    num_rows = len(table_data)
    styled_data = []
    for i, row in enumerate(table_data):
        left = left_bracket if i == num_rows // 2 else ''
        right = right_bracket if i == num_rows // 2 else ''
        styled_data.append([left] + row + [right])

    num_cols = max(len(r) for r in styled_data)
    col_widths = [0.4 * cm] + [1.5 * cm] * (num_cols - 2) + [0.4 * cm]
    for i, row in enumerate(styled_data):
        while len(row) < num_cols:
            row.insert(-1, '')

    style_commands = [
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, -1), FONT),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 0), (-1, -1), 1),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ('FONTSIZE', (0, 0), (0, -1), 14 + num_rows * 2),
        ('FONTSIZE', (-1, 0), (-1, -1), 14 + num_rows * 2),
    ]

    table = Table(styled_data, colWidths=col_widths,
                  style=TableStyle(style_commands))
    table.hAlign = 'CENTER'
    return table


def _build_cases_table(content):
    """Build a ReportLab Table for a system of equations (\begin{cases})."""
    rows = [r.strip() for r in content.split('\\\\') if r.strip()]
    if not rows:
        return None

    num_rows = len(rows)
    styled_data = []
    for i, row in enumerate(rows):
        clean = _clean_latex_to_unicode(row)
        # Use curly brace only on middle row
        brace = '{' if i == num_rows // 2 else ''
        styled_data.append([brace, clean])

    style_commands = [
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, -1), FONT),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('FONTSIZE', (0, 0), (0, -1), 12 + num_rows * 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]

    col_widths = [0.5 * cm, 8 * cm]
    table = Table(styled_data, colWidths=col_widths,
                  style=TableStyle(style_commands))
    table.hAlign = 'CENTER'
    return table


def _safe_xml(text):
    """Escape text for XML/HTML in ReportLab Paragraphs."""
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


# ─── Main generator class ──────────────────────────────────────

class VariantPDFGenerator:
    """Generator de PDF-uri stil oficial BAC cu logo EtoX Academy"""

    def __init__(self, conn):
        _register_fonts()
        self.conn = conn
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        self.styles.add(ParagraphStyle(
            name='MainTitle',
            fontSize=16, textColor=colors.black, spaceAfter=2,
            spaceBefore=0, alignment=TA_CENTER, fontName=FONT_BOLD, leading=20,
        ))
        self.styles.add(ParagraphStyle(
            name='SubTitle',
            fontSize=11, textColor=colors.HexColor('#222222'), spaceAfter=1,
            spaceBefore=0, alignment=TA_CENTER, fontName=FONT, leading=14,
        ))
        self.styles.add(ParagraphStyle(
            name='ExamMeta',
            fontSize=10, textColor=colors.HexColor('#555555'), spaceAfter=2,
            spaceBefore=1, alignment=TA_CENTER, fontName=FONT_ITALIC, leading=13,
        ))
        # Used inside dark background table cell
        self.styles.add(ParagraphStyle(
            name='SectionTitle',
            fontSize=12, textColor=colors.white, spaceAfter=0,
            spaceBefore=0, fontName=FONT_BOLD, leading=16, alignment=TA_CENTER,
        ))
        self.styles.add(ParagraphStyle(
            name='ExerciseText',
            fontSize=10.5, textColor=colors.black, spaceAfter=2,
            spaceBefore=1, leading=15, fontName=FONT, alignment=TA_JUSTIFY,
            leftIndent=10,
        ))
        self.styles.add(ParagraphStyle(
            name='SubpointText',
            fontSize=10.5, textColor=colors.black, spaceAfter=2,
            spaceBefore=1, leading=15, fontName=FONT, alignment=TA_JUSTIFY,
            leftIndent=22,
        ))
        self.styles.add(ParagraphStyle(
            name='ExerciseHeader',
            fontSize=10.5, textColor=colors.black, spaceAfter=1,
            spaceBefore=6, fontName=FONT_BOLD, leading=14,
        ))
        self.styles.add(ParagraphStyle(
            name='SubpointHeader',
            fontSize=10.5, textColor=colors.black, spaceAfter=1,
            spaceBefore=4, fontName=FONT_BOLD, leading=14, leftIndent=10,
        ))
        self.styles.add(ParagraphStyle(
            name='PointsLabel',
            fontSize=9, textColor=colors.HexColor('#666666'), spaceAfter=0,
            spaceBefore=0, fontName=FONT_ITALIC, alignment=TA_RIGHT, leading=14,
        ))
        self.styles.add(ParagraphStyle(
            name='DiffStyle',
            fontSize=8, textColor=colors.HexColor('#aaaaaa'), spaceAfter=2,
            fontName=FONT, alignment=TA_RIGHT,
        ))
        self.styles.add(ParagraphStyle(
            name='FooterStyle',
            fontSize=8, textColor=colors.HexColor('#999999'), spaceBefore=4,
            alignment=TA_CENTER, fontName=FONT_ITALIC, leading=11,
        ))
        self.styles.add(ParagraphStyle(
            name='Instructions',
            fontSize=9.5, textColor=colors.HexColor('#222222'), spaceAfter=3,
            spaceBefore=2, fontName=FONT, leading=14,
            alignment=TA_LEFT, leftIndent=4,
        ))
        self.styles.add(ParagraphStyle(
            name='SolutionLabel',
            fontSize=9, textColor=colors.HexColor('#1a5276'), spaceAfter=2,
            spaceBefore=4, fontName=FONT_BOLD, leading=13,
            leftIndent=10,
        ))
        self.styles.add(ParagraphStyle(
            name='SolutionText',
            fontSize=9.5, textColor=colors.HexColor('#1a1a2e'), spaceAfter=2,
            spaceBefore=1, leading=14, fontName=FONT, alignment=TA_JUSTIFY,
            leftIndent=20,
        ))
        self.styles.add(ParagraphStyle(
            name='BaremLabel',
            fontSize=9, textColor=colors.HexColor('#1e8449'), spaceAfter=2,
            spaceBefore=4, fontName=FONT_BOLD, leading=13,
            leftIndent=10,
        ))
        self.styles.add(ParagraphStyle(
            name='BaremText',
            fontSize=9.5, textColor=colors.HexColor('#1a2e1a'), spaceAfter=2,
            spaceBefore=1, leading=14, fontName=FONT, alignment=TA_JUSTIFY,
            leftIndent=20,
        ))

    def generate_variant_pdf(self, variant_id, mode: str = 'exam'):
        """
        mode: 'exam' = subiect normal, 'solutions' = cu rezolvare, 'barem' = cu barem de corectare
        """
        variant_data = self._get_variant_data(variant_id)
        exercises = self._get_variant_exercises(variant_id)
        exercises_by_section = self._group_exercises_by_section(exercises)

        difficulties = [ex.get('difficulty', 5) for ex in exercises if ex.get('difficulty')]
        avg_difficulty = round(sum(difficulties) / len(difficulties)) if difficulties else 5

        mode_labels = {
            'exam': '',
            'solutions': ' — REZOLVARE',
            'barem': ' — BAREM DE CORECTARE',
        }
        mode_label = mode_labels.get(mode, '')

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=A4,
            rightMargin=2 * cm, leftMargin=2 * cm,
            topMargin=1.5 * cm, bottomMargin=1.5 * cm,
            title=variant_data['name'] + mode_label
        )

        story = []
        story.extend(self._build_header(variant_data, avg_difficulty, mode_label=mode_label))
        if mode == 'exam':
            story.extend(self._build_instructions(variant_data))

        sorted_sections = sorted(
            exercises_by_section.items(),
            key=lambda x: SECTION_ORDER.get(x[0], 99)
        )
        for section_name, section_exercises in sorted_sections:
            section_points = sum(ex.get('points', 0) or 0 for ex in section_exercises)
            story.extend(self._build_section(
                section_name, section_exercises, section_points, mode=mode))

        story.extend(self._build_footer())

        doc.build(story)
        buffer.seek(0)
        return buffer

    # ─── Data ───────────────────────────────────────────────────

    def _get_variant_data(self, variant_id):
        query = """
        SELECT id, name, exam_type, profile, year, session,
               total_points, duration_minutes, instructions, status, created_at
        FROM variants WHERE id = %s;
        """
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, (variant_id,))
            return cur.fetchone()

    def _get_variant_exercises(self, variant_id):
        query = """
        SELECT ve.id, ve.order_index, ve.section_name,
               e.statement_latex, e.statement_text, e.points, e.item_type,
               e.subject_part, e.difficulty, e.answer_latex, e.solution_latex,
               e.scoring_guide_latex, e.scoring_guide_text, e.metadata
        FROM variant_exercises ve
        JOIN exercises e ON ve.exercise_id = e.id
        WHERE ve.variant_id = %s
        ORDER BY ve.order_index;
        """
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, (variant_id,))
            return cur.fetchall()

    def _group_exercises_by_section(self, exercises):
        sections = {}
        for ex in exercises:
            section = ex.get('section_name') or 'Exerciții'
            if section not in sections:
                sections[section] = []
            sections[section].append(ex)
        return sections

    # ─── Header ─────────────────────────────────────────────────

    def _build_header(self, variant_data, avg_difficulty, mode_label: str = ''):
        story = []

        exam_type = variant_data.get('exam_type', 'bacalaureat')
        exam_label = EXAM_TYPE_LABELS.get(exam_type, exam_type.upper())
        year = variant_data.get('year', '')
        profile = variant_data.get('profile', '')
        variant_name = variant_data.get('name', '')

        # Logo
        if os.path.exists(LOGO_PATH):
            logo = Image(LOGO_PATH, width=1.6 * cm, height=1.6 * cm)
        else:
            logo = Paragraph('', self.styles['Normal'])

        # Center: title + subtitle
        title_items = [
            Paragraph(f'<b>{exam_label}{(" " + str(year)) if year else ""}{mode_label}</b>', self.styles['MainTitle']),
        ]
        if profile:
            title_items.append(Paragraph(f'Matematică — Profil {profile.title()}', self.styles['SubTitle']))
        title_items.append(Paragraph('Proba E.c', self.styles['ExamMeta']))

        # Right: variant name + difficulty
        star_count = max(1, round(min(avg_difficulty, 10) / 2))
        stars = '\u2605' * star_count + '\u2606' * (5 - star_count)
        right_items = []
        if variant_name:
            right_items.append(Paragraph(f'<b>{variant_name}</b>', self.styles['ExamMeta']))
        right_items.append(Paragraph(f'Dificultate: {avg_difficulty}/10', self.styles['DiffStyle']))
        right_items.append(Paragraph(stars, self.styles['DiffStyle']))

        header_tbl = Table(
            [[logo, title_items, right_items]],
            colWidths=[2 * cm, 12 * cm, 3 * cm],
            style=TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ALIGN', (0, 0), (0, 0), 'LEFT'),
                ('ALIGN', (1, 0), (1, 0), 'CENTER'),
                ('ALIGN', (2, 0), (2, 0), 'RIGHT'),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ])
        )
        story.append(header_tbl)
        story.append(Spacer(1, 3 * mm))
        story.append(HRFlowable(width='100%', thickness=2, color=colors.black, spaceAfter=5, spaceBefore=2))
        return story

    # ─── Instructions ───────────────────────────────────────────

    def _build_instructions(self, variant_data):
        story = []
        items = []

        items.append('Toate subiectele sunt obligatorii.')
        items.append('Se acordă 10 puncte din oficiu.')

        duration = variant_data.get('duration_minutes')
        if duration:
            hours = duration // 60
            mins = duration % 60
            time_str = f'{hours} ore' if mins == 0 else f'{hours}h {mins}min'
            items.append(f'Timp efectiv de lucru: {time_str}.')

        total_pts = variant_data.get('total_points')
        if total_pts:
            items.append(f'Punctaj total: {total_pts} puncte (plus 10 puncte din oficiu).')

        custom = variant_data.get('instructions')
        if custom:
            items.append(custom)

        rows = [[Paragraph(f'\u2022  {item}', self.styles['Instructions'])] for item in items]
        instr_tbl = Table(
            rows,
            colWidths=[16.6 * cm],
            style=TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f7f7f7')),
                ('BOX', (0, 0), (-1, -1), 0.75, colors.HexColor('#bbbbbb')),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                ('LEFTPADDING', (0, 0), (-1, -1), 10),
                ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ])
        )
        story.append(instr_tbl)
        story.append(Spacer(1, 5 * mm))
        return story

    # ─── Section ────────────────────────────────────────────────

    def _build_section(self, section_name, exercises, section_points, mode: str = 'exam'):
        story = []
        pts_text = f' — {section_points} de puncte' if section_points > 0 else ''
        sec_tbl = Table(
            [[Paragraph(f'<b>{section_name.upper()}{pts_text}</b>', self.styles['SectionTitle'])]],
            colWidths=[17 * cm],
            style=TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#1c1c1c')),
                ('TOPPADDING', (0, 0), (-1, -1), 7),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ])
        )
        story.append(sec_tbl)
        story.append(Spacer(1, 4 * mm))

        # Group exercises by parent_external_id (subpoints) vs simple
        groups = []
        for exercise in exercises:
            meta = exercise.get('metadata') or {}
            if isinstance(meta, str):
                meta = json.loads(meta)
            parent_id = meta.get('parent_external_id')
            if parent_id:
                if groups and groups[-1].get('type') == 'problem' and groups[-1].get('parent_id') == parent_id:
                    groups[-1]['children'].append(exercise)
                else:
                    groups.append({'type': 'problem', 'parent_id': parent_id, 'children': [exercise]})
            else:
                groups.append({'type': 'simple', 'exercise': exercise})

        problem_counter = 0
        simple_counter = 0
        for group in groups:
            if group['type'] == 'simple':
                simple_counter += 1
                story.extend(self._build_exercise(simple_counter, group['exercise'], mode=mode))
            else:
                problem_counter += 1
                parent_statement = self._get_parent_statement(group['parent_id'])
                story.extend(self._build_problem(problem_counter, group['children'], parent_statement, mode=mode))

        return story

    def _get_parent_statement(self, parent_external_id):
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

    def _build_problem(self, number, children, parent_statement, mode: str = 'exam'):
        """Render a container problem with subpoints (a, b, c)."""
        flowables = []
        total_points = sum(c.get('points', 0) or 0 for c in children)
        pts_label = f'{total_points} puncte' if total_points else ''

        # Problem number + total points row
        num_p = Paragraph(f'<b>{number}.</b>', self.styles['ExerciseHeader'])
        pts_p = Paragraph(pts_label, self.styles['PointsLabel'])
        hdr_tbl = Table(
            [[num_p, pts_p]],
            colWidths=[14.7 * cm, 2.3 * cm],
            style=TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
                ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ('TOPPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ])
        )
        flowables.append(hdr_tbl)

        if parent_statement:
            flowables.extend(self._render_statement(parent_statement))
            flowables.append(Spacer(1, 3 * mm))

        for child in children:
            meta = child.get('metadata') or {}
            if isinstance(meta, str):
                meta = json.loads(meta)
            subpoint = meta.get('subpoint', '')
            pts = child.get('points', 0) or 0
            pts_label_sub = f'{pts} puncte' if pts else ''

            sub_p = Paragraph(f'<b>{subpoint})</b>', self.styles['SubpointHeader'])
            sub_pts_p = Paragraph(pts_label_sub, self.styles['PointsLabel'])
            sub_hdr_tbl = Table(
                [[sub_p, sub_pts_p]],
                colWidths=[13.7 * cm, 2.3 * cm],
                style=TableStyle([
                    ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
                    ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
                    ('LEFTPADDING', (0, 0), (0, 0), 10),
                    ('LEFTPADDING', (1, 0), (1, 0), 0),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                    ('TOPPADDING', (0, 0), (-1, -1), 0),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                ])
            )
            flowables.append(sub_hdr_tbl)

            statement = child.get('statement_latex') or child.get('statement_text', '')
            if statement:
                flowables.extend(self._render_statement(statement, text_style='SubpointText'))

            if mode in ('solutions', 'barem'):
                flowables.extend(self._render_solution_block(child, mode))

            flowables.append(Spacer(1, 3 * mm))

        flowables.append(Spacer(1, 5 * mm))
        return flowables

    # ─── Exercise ───────────────────────────────────────────────

    def _build_exercise(self, number, exercise, mode: str = 'exam'):
        flowables = []
        points = exercise.get('points', 0) or 0
        pts_label = f'{points} puncte' if points else ''

        num_p = Paragraph(f'<b>{number}.</b>', self.styles['ExerciseHeader'])
        pts_p = Paragraph(pts_label, self.styles['PointsLabel'])
        hdr_tbl = Table(
            [[num_p, pts_p]],
            colWidths=[14.7 * cm, 2.3 * cm],
            style=TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
                ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ('TOPPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ])
        )
        flowables.append(hdr_tbl)

        statement = exercise.get('statement_latex') or exercise.get('statement_text', '')
        if statement:
            flowables.extend(self._render_statement(statement))

        if mode in ('solutions', 'barem'):
            flowables.extend(self._render_solution_block(exercise, mode))

        flowables.append(Spacer(1, 5 * mm))
        return flowables

    def _render_solution_block(self, exercise, mode: str):
        """Render solution or barem block after an exercise."""
        flowables = []
        if mode == 'solutions':
            content = exercise.get('solution_latex') or exercise.get('answer_latex') or ''
            if content:
                flowables.append(HRFlowable(width='90%', thickness=0.5,
                                            color=colors.HexColor('#aed6f1'),
                                            spaceAfter=2, spaceBefore=3))
                flowables.append(Paragraph('Rezolvare:', self.styles['SolutionLabel']))
                flowables.extend(self._render_statement(content, text_style='SolutionText'))
        elif mode == 'barem':
            content = exercise.get('scoring_guide_latex') or exercise.get('scoring_guide_text') or ''
            if not content:
                content = exercise.get('answer_latex') or ''
            if content:
                flowables.append(HRFlowable(width='90%', thickness=0.5,
                                            color=colors.HexColor('#a9dfbf'),
                                            spaceAfter=2, spaceBefore=3))
                pts = exercise.get('points', 0) or 0
                pts_str = f' ({pts}p)' if pts else ''
                flowables.append(Paragraph(f'Barem{pts_str}:', self.styles['BaremLabel']))
                flowables.extend(self._render_statement(content, text_style='BaremText'))
        return flowables

    def _render_statement(self, statement, text_style='ExerciseText'):
        """
        Render mixed text+LaTeX statement.
        Strategy:
          - For each line, split into text and $...$ math parts
          - Simple math (no frac/sqrt/int/env) → convert to Unicode inline with text
          - Complex math → render as image via matplotlib
          - Environments (matrix, cases) → render as ReportLab Table
          - Accumulate adjacent text+simple-math into single paragraphs for flow
          - Ensure spaces between text and math fragments
        """
        flowables = []

        statement = statement.replace('\\newline', '\n').replace('\n\n', '\n')
        lines = statement.split('\n')

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Split into text and math parts, preserving delimiters
            parts = re.split(r'(\$[^\$]+\$)', line)

            # Classify each part
            classified = []
            for p in parts:
                if p.startswith('$') and p.endswith('$'):
                    inner = p[1:-1]
                    has_env = '\\begin{' in inner
                    is_complex = has_env or any(cmd in inner for cmd in [
                        '\\frac', '\\dfrac', '\\sqrt', '\\int', '\\sum',
                        '\\prod', '\\lim', '^', '_',
                    ])
                    classified.append({
                        'raw': p, 'is_math': True,
                        'is_complex': is_complex, 'has_env': has_env,
                    })
                else:
                    classified.append({
                        'raw': p, 'is_math': False,
                        'is_complex': False, 'has_env': False,
                    })

            has_any_block = any(c['is_complex'] for c in classified)

            if not has_any_block:
                # All simple: convert everything to Unicode in one paragraph
                combined = self._combine_text_and_simple_math(classified)
                safe = _safe_xml(combined)
                if safe.strip():
                    flowables.append(Paragraph(safe, self.styles[text_style]))
            else:
                # Mix of text, simple math, complex math, environments
                text_buffer = ""

                for item in classified:
                    raw = item['raw']
                    if not raw or not raw.strip():
                        continue

                    if not item['is_math']:
                        # Plain text - accumulate as-is (preserve original whitespace)
                        text_buffer += raw
                        continue

                    # It's a math part ($...$)
                    raw_stripped = raw.strip()
                    if not item['is_complex']:
                        # Simple math - convert to Unicode and accumulate inline
                        unicode_math = _clean_latex_to_unicode(raw_stripped)
                        if not unicode_math:
                            continue
                        # Ensure proper spacing
                        if text_buffer and text_buffer[-1] not in ' \t\n({[':
                            if unicode_math[0] not in ',.:;!?)}\n':
                                text_buffer += ' '
                        text_buffer += unicode_math
                    elif item['has_env']:
                        # Environment (matrix/cases) - flush buffer, render as table
                        if text_buffer.strip():
                            flowables.append(Paragraph(
                                _safe_xml(text_buffer), self.styles[text_style]))
                            text_buffer = ""

                        inner = raw_stripped[1:-1]  # strip $...$
                        tbl = _render_environment_table(inner)
                        if tbl:
                            flowables.append(tbl)
                        else:
                            clean = _clean_latex_to_unicode(raw_stripped)
                            if clean:
                                flowables.append(Paragraph(
                                    _safe_xml(clean), self.styles[text_style]))
                    else:
                        # Complex math (frac, sqrt, etc.) - flush buffer, render as image
                        if text_buffer.strip():
                            flowables.append(Paragraph(
                                _safe_xml(text_buffer), self.styles[text_style]))
                            text_buffer = ""

                        img_buf = _render_math_to_image(raw_stripped)
                        if img_buf:
                            try:
                                from PIL import Image as PILImage
                                pil_img = PILImage.open(img_buf)
                                img_w, img_h = pil_img.size
                                img_buf.seek(0)

                                display_w = img_w * 72.0 / 150
                                display_h = img_h * 72.0 / 150

                                max_w = 15 * cm
                                if display_w > max_w:
                                    ratio = max_w / display_w
                                    display_w = max_w
                                    display_h *= ratio

                                img = Image(img_buf, width=display_w, height=display_h)
                                img.hAlign = 'CENTER'
                                flowables.append(img)
                            except Exception:
                                clean = _clean_latex_to_unicode(raw_stripped)
                                if clean:
                                    flowables.append(Paragraph(
                                        _safe_xml(clean), self.styles[text_style]))
                        else:
                            clean = _clean_latex_to_unicode(raw_stripped)
                            if clean:
                                flowables.append(Paragraph(
                                    _safe_xml(clean), self.styles[text_style]))

                # Flush remaining text
                if text_buffer.strip():
                    flowables.append(Paragraph(
                        _safe_xml(text_buffer), self.styles[text_style]))

        return flowables

    def _combine_text_and_simple_math(self, classified):
        """Combine text and simple math parts into a single Unicode string with proper spacing."""
        result = ""
        prev_was_math = False

        for item in classified:
            raw = item['raw']
            if not raw:
                continue

            if item['is_math']:
                piece = _clean_latex_to_unicode(raw)
                if not piece:
                    continue
                # Before math: ensure space if result doesn't end with space/punctuation
                if result and result[-1] not in ' \t\n({[':
                    first = piece[0]
                    if first not in ',.:;!?)}\n':
                        result += ' '
                result += piece
                prev_was_math = True
            else:
                piece = raw
                if not piece:
                    continue
                # After math: ensure space if text doesn't start with space/punctuation
                if prev_was_math and result and piece[0] not in ' \t\n,.:;!?)}':
                    if result[-1] not in ' \t\n':
                        result += ' '
                result += piece
                prev_was_math = False

        return result

    # ─── Footer ─────────────────────────────────────────────────

    def _build_footer(self):
        story = []
        story.append(Spacer(1, 8 * mm))
        story.append(HRFlowable(width='100%', thickness=1, color=colors.HexColor('#cccccc'), spaceAfter=4, spaceBefore=4))

        now = datetime.now().strftime('%d.%m.%Y %H:%M')
        footer_text = f'\u00a9 {datetime.now().year} EtoX Academy  \u00b7  Generat: {now}  \u00b7  uz educațional'
        story.append(Paragraph(footer_text, self.styles['FooterStyle']))

        return story


def get_pdf_generator(conn):
    """Factory function for VariantPDFGenerator"""
    return VariantPDFGenerator(conn)
