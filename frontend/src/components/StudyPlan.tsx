import { useState, useEffect } from 'react';
import { CalendarDays, Plus, Trash2, ChevronLeft, ChevronRight, Play, Users } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import {
  getStudyPlan,
  createStudyPlanDay,
  deleteStudyPlanDay,
  getTeacherStudentsList,
  type StudyPlanDay,
  type SessionType,
} from '../api';
import { useAuth } from '../AuthContext';
import './StudyPlan.css';

// ─── Constants ─────────────────────────────────────────────────────────────────

const BAC_DATE = new Date('2026-07-01');

const SESSION_LABELS: Record<SessionType, { label: string; icon: string }> = {
  test_scurt: { label: 'Test Scurt', icon: '⚡' },
  test_bac:   { label: 'Test BAC',   icon: '🏆' },
};

const DAYS_RO = ['Lun', 'Mar', 'Mie', 'Joi', 'Vin', 'Sâm', 'Dum'];

// ─── Helpers ──────────────────────────────────────────────────────────────────

function toISODate(d: Date) {
  return d.toISOString().split('T')[0];
}

function getWeekDates(weekOffset: number): Date[] {
  const now = new Date();
  const day = now.getDay(); // 0=Sun,1=Mon...
  const monday = new Date(now);
  monday.setDate(now.getDate() - ((day + 6) % 7) + weekOffset * 7);
  monday.setHours(0, 0, 0, 0);
  return Array.from({ length: 7 }, (_, i) => {
    const d = new Date(monday);
    d.setDate(monday.getDate() + i);
    return d;
  });
}

function daysUntilBAC(): number {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return Math.max(0, Math.floor((BAC_DATE.getTime() - today.getTime()) / 86400000));
}

// ─── Add Entry Modal ──────────────────────────────────────────────────────────

interface AddEntryProps {
  defaultDate: string;
  isTeacher: boolean;
  students: { id: string; full_name: string }[];
  onSave: (data: { user_id?: string; plan_date: string; session_type: SessionType; note?: string }) => Promise<void>;
  onClose: () => void;
}

function AddEntryModal({ defaultDate, isTeacher, students, onSave, onClose }: AddEntryProps) {
  const [date, setDate] = useState(defaultDate);
  const [sessionType, setSessionType] = useState<SessionType>('test_scurt');
  const [note, setNote] = useState('');
  const [studentId, setStudentId] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const handleSave = async () => {
    setSaving(true);
    setError('');
    try {
      await onSave({
        plan_date: date,
        session_type: sessionType,
        note: note.trim() || undefined,
        user_id: isTeacher && studentId ? studentId : undefined,
      });
      onClose();
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Eroare la salvare.');
      setSaving(false);
    }
  };

  return (
    <div className="sp-modal-overlay" onClick={onClose}>
      <div className="sp-modal" onClick={e => e.stopPropagation()}>
        <div className="sp-modal-header">
          <span>Adaugă sesiune în plan</span>
          <button className="sp-modal-close" onClick={onClose}>✕</button>
        </div>

        <div className="sp-modal-body">
          {isTeacher && students.length > 0 && (
            <label className="sp-modal-label">Elev
              <select className="sp-modal-select" value={studentId} onChange={e => setStudentId(e.target.value)}>
                <option value="">— Eu (plan personal) —</option>
                {students.map(s => (
                  <option key={s.id} value={s.id}>{s.full_name}</option>
                ))}
              </select>
            </label>
          )}

          <label className="sp-modal-label">Data
            <input
              type="date"
              className="sp-modal-input"
              value={date}
              min={toISODate(new Date())}
              onChange={e => setDate(e.target.value)}
            />
          </label>

          <label className="sp-modal-label">Tip sesiune
            <div className="sp-type-btns">
              {(Object.entries(SESSION_LABELS) as [SessionType, { label: string; icon: string }][]).map(([k, v]) => (
                <button
                  key={k}
                  className={`sp-type-btn${sessionType === k ? ' selected' : ''}`}
                  onClick={() => setSessionType(k)}
                >
                  {v.icon} {v.label}
                </button>
              ))}
            </div>
          </label>

          <label className="sp-modal-label">Notă (opțional)
            <input
              type="text"
              className="sp-modal-input"
              placeholder="ex: Focusează-te pe ecuații"
              value={note}
              onChange={e => setNote(e.target.value)}
              maxLength={200}
            />
          </label>

          {error && <div className="sp-modal-error">{error}</div>}
        </div>

        <div className="sp-modal-footer">
          <button className="sp-btn-cancel" onClick={onClose}>Anulează</button>
          <button className="sp-btn-save" onClick={handleSave} disabled={saving || !date}>
            {saving ? 'Se salvează…' : 'Adaugă'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Day Cell ─────────────────────────────────────────────────────────────────

interface DayCellProps {
  date: Date;
  entries: StudyPlanDay[];
  isToday: boolean;
  isPast: boolean;
  onAdd: (date: string) => void;
  onDelete: (id: string) => void;
  onStart: (entry: StudyPlanDay) => void;
}

function DayCell({ date, entries, isToday, isPast, onAdd, onDelete, onStart }: DayCellProps) {
  const dateStr = toISODate(date);
  const dayLabel = DAYS_RO[date.getDay() === 0 ? 6 : date.getDay() - 1];

  return (
    <div className={`sp-day-cell${isToday ? ' today' : ''}${isPast ? ' past' : ''}`}>
      <div className="sp-day-header">
        <span className="sp-day-name">{dayLabel}</span>
        <span className={`sp-day-num${isToday ? ' today-num' : ''}`}>{date.getDate()}</span>
        {!isPast && (
          <button className="sp-add-day-btn" title="Adaugă sesiune" onClick={() => onAdd(dateStr)}>
            <Plus size={12} />
          </button>
        )}
      </div>

      <div className="sp-day-entries">
        {entries.map(entry => {
          const cfg = SESSION_LABELS[entry.session_type];
          return (
            <div key={entry.id} className={`sp-entry${entry.completed ? ' done' : ''}${entry.created_by === 'teacher' ? ' by-teacher' : ''}`}>
              <div className="sp-entry-top">
                <span className="sp-entry-icon">{cfg.icon}</span>
                <span className="sp-entry-label">{cfg.label}</span>
                {!entry.completed && !isPast && (
                  <>
                    <button className="sp-entry-start" title="Pornește sesiunea" onClick={() => onStart(entry)}>
                      <Play size={11} />
                    </button>
                    <button className="sp-entry-del" title="Șterge" onClick={() => onDelete(entry.id)}>
                      <Trash2 size={11} />
                    </button>
                  </>
                )}
                {entry.completed && <span className="sp-entry-done-mark">✓</span>}
              </div>
              {entry.created_by === 'teacher' && entry.teacher_name && (
                <div className="sp-entry-teacher">👨‍🏫 {entry.teacher_name}</div>
              )}
              {entry.note && <div className="sp-entry-note">{entry.note}</div>}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

export default function StudyPlan() {
  const { isTeacher } = useAuth();
  const navigate = useNavigate();

  const [weekOffset, setWeekOffset] = useState(0);
  const [planDays, setPlanDays] = useState<StudyPlanDay[]>([]);
  const [students, setStudents] = useState<{ id: string; full_name: string; email: string }[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [modalDefaultDate, setModalDefaultDate] = useState('');

  const weekDates = getWeekDates(weekOffset);
  const bacDays = daysUntilBAC();

  const loadPlan = () => {
    setLoading(true);
    getStudyPlan()
      .then(r => setPlanDays(Array.isArray(r.data) ? r.data : []))
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadPlan();
    if (isTeacher) {
      getTeacherStudentsList()
        .then(r => setStudents(Array.isArray(r.data) ? r.data : []))
        .catch(() => {});
    }
  }, [isTeacher]);

  const handleAddEntry = async (data: { user_id?: string; plan_date: string; session_type: SessionType; note?: string }) => {
    await createStudyPlanDay(data);
    loadPlan();
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteStudyPlanDay(id);
      setPlanDays(prev => prev.filter(d => d.id !== id));
    } catch {}
  };

  const handleStart = (entry: StudyPlanDay) => {
    const params = new URLSearchParams({
      plan: entry.id,
      type: entry.session_type,
    });
    if (entry.filters?.subiect_tag) {
      params.set('subiect', String(entry.filters.subiect_tag));
    }
    if (entry.filters?.exercise_set_id) {
      params.set('set', String(entry.filters.exercise_set_id));
    }
    navigate(`/app/study-session?${params.toString()}`);
  };

  const openModal = (date: string) => {
    setModalDefaultDate(date);
    setShowModal(true);
  };

  const today = toISODate(new Date());

  return (
    <div className="study-plan-wrap">
      <div className="sp-page-header">
        <CalendarDays size={22} />
        <h2>Plan de studiu săptămânal</h2>
        {isTeacher && (
          <span className="sp-teacher-badge"><Users size={13} /> Profesor</span>
        )}
      </div>

      {/* BAC countdown strip */}
      <div className="sp-bac-strip">
        <span className="sp-bac-label">📅 BAC 2026</span>
        <span className="sp-bac-days">
          {bacDays > 0 ? <><strong>{bacDays}</strong> zile rămase</> : 'Succes la BAC!'}
        </span>
        <div className="sp-bac-bar">
          <div
            className="sp-bac-fill"
            style={{ width: `${Math.max(0, Math.min(100, 100 - (bacDays / 300) * 100))}%` }}
          />
        </div>
      </div>

      {/* Week navigation */}
      <div className="sp-week-nav">
        <button className="sp-nav-btn" onClick={() => setWeekOffset(w => w - 1)}>
          <ChevronLeft size={18} />
        </button>
        <div className="sp-week-label">
          {weekOffset === 0 ? 'Săptămâna curentă' : weekOffset > 0 ? `+${weekOffset} săptămâni` : `${weekOffset} săptămâni`}
          {' · '}
          {weekDates[0].toLocaleDateString('ro-RO', { day: 'numeric', month: 'short' })}
          {' – '}
          {weekDates[6].toLocaleDateString('ro-RO', { day: 'numeric', month: 'short', year: 'numeric' })}
        </div>
        <button className="sp-nav-btn" onClick={() => setWeekOffset(w => w + 1)}>
          <ChevronRight size={18} />
        </button>
        {weekOffset !== 0 && (
          <button className="sp-today-btn" onClick={() => setWeekOffset(0)}>Azi</button>
        )}
        <button className="sp-add-btn" onClick={() => openModal(today)}>
          <Plus size={15} /> Adaugă sesiune
        </button>
      </div>

      {/* Calendar grid */}
      {loading ? (
        <div className="sp-loading">Se încarcă planul...</div>
      ) : (
        <div className="sp-grid">
          {weekDates.map(date => {
            const dateStr = toISODate(date);
            const dayEntries = planDays.filter(p => p.plan_date === dateStr);
            const isToday = dateStr === today;
            const isPast = dateStr < today;
            return (
              <DayCell
                key={dateStr}
                date={date}
                entries={dayEntries}
                isToday={isToday}
                isPast={isPast}
                onAdd={openModal}
                onDelete={handleDelete}
                onStart={handleStart}
              />
            );
          })}
        </div>
      )}

      {/* Upcoming entries list (next 14 days) */}
      {!loading && (() => {
        const upcoming = planDays.filter(p => p.plan_date >= today && !p.completed).slice(0, 5);
        if (upcoming.length === 0) return null;
        return (
          <div className="sp-upcoming">
            <div className="sp-upcoming-title">Următoarele sesiuni planificate</div>
            {upcoming.map(entry => {
              const cfg = SESSION_LABELS[entry.session_type];
              const d = new Date(entry.plan_date);
              return (
                <div key={entry.id} className={`sp-upcoming-row${entry.created_by === 'teacher' ? ' by-teacher' : ''}`}>
                  <span className="sp-upcoming-icon">{cfg.icon}</span>
                  <div className="sp-upcoming-info">
                    <span className="sp-upcoming-type">{cfg.label}</span>
                    <span className="sp-upcoming-date">
                      {d.toLocaleDateString('ro-RO', { weekday: 'long', day: 'numeric', month: 'long' })}
                    </span>
                    {entry.teacher_name && <span className="sp-upcoming-teacher">Programat de {entry.teacher_name}</span>}
                    {entry.note && <span className="sp-upcoming-note">{entry.note}</span>}
                  </div>
                  <div className="sp-upcoming-actions">
                    <button className="sp-upcoming-start" onClick={() => handleStart(entry)}>
                      <Play size={13} /> Start
                    </button>
                    <button className="sp-upcoming-del" onClick={() => handleDelete(entry.id)}>
                      <Trash2 size={13} />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        );
      })()}

      {showModal && (
        <AddEntryModal
          defaultDate={modalDefaultDate}
          isTeacher={isTeacher}
          students={students}
          onSave={handleAddEntry}
          onClose={() => setShowModal(false)}
        />
      )}
    </div>
  );
}
