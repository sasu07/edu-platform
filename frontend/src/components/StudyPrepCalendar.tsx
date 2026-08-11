import { useMemo, useState } from "react";
import type { GamificationProfile, StudyPlanDay, StudySession } from "../api";
import "./StudyPrepCalendar.css";

const MONTHS_RO = [
  "Ianuarie",
  "Februarie",
  "Martie",
  "Aprilie",
  "Mai",
  "Iunie",
  "Iulie",
  "August",
  "Septembrie",
  "Octombrie",
  "Noiembrie",
  "Decembrie",
];

const WEEKDAYS_RO = ["L", "Ma", "Mi", "J", "V", "S", "D"];

function toDateKey(date: Date): string {
  return date.toISOString().slice(0, 10);
}

function fromIsoDate(value: string): Date {
  return new Date(`${value}T12:00:00`);
}

function normalizeSubiectTag(value: string | null | undefined): string | null {
  if (!value) return null;
  const normalized = String(value).trim().toUpperCase();
  const mapping: Record<string, string> = { S1: "1", S2: "2", S3: "3", "1": "1", "2": "2", "3": "3" };
  return mapping[normalized] || null;
}

function startOfMonth(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), 1, 12);
}

function buildCalendarDays(monthDate: Date): Date[] {
  const first = startOfMonth(monthDate);
  const startWeekday = (first.getDay() + 6) % 7;
  const start = new Date(first);
  start.setDate(first.getDate() - startWeekday);
  return Array.from({ length: 42 }, (_, index) => {
    const day = new Date(start);
    day.setDate(start.getDate() + index);
    return day;
  });
}

function buildCurrentStreakKeys(gamification?: GamificationProfile | null): Set<string> {
  if (!gamification?.last_active_date || !gamification.streak_current) {
    return new Set();
  }
  const keys = new Set<string>();
  const end = fromIsoDate(gamification.last_active_date);
  for (let offset = 0; offset < gamification.streak_current; offset += 1) {
    const day = new Date(end);
    day.setDate(end.getDate() - offset);
    keys.add(toDateKey(day));
  }
  return keys;
}

function getPlanLabel(entry: StudyPlanDay): string {
  const subiect = normalizeSubiectTag(entry.filters?.subiect_tag);
  if (subiect) return `S${subiect}`;
  if (entry.note) return entry.note.trim().slice(0, 14);
  return entry.session_type === "test_bac" ? "BAC" : "Scurt";
}

export default function StudyPrepCalendar({
  title,
  subtitle,
  sessions,
  planDays,
  gamification,
  className = "",
}: {
  title: string;
  subtitle: string;
  sessions: StudySession[];
  planDays: StudyPlanDay[];
  gamification?: GamificationProfile | null;
  className?: string;
}) {
  const [monthCursor, setMonthCursor] = useState(() => startOfMonth(new Date()));

  const activeDates = useMemo(() => {
    const counts = new Map<string, number>();
    sessions.forEach((session) => {
      const key = toDateKey(new Date(session.started_at));
      counts.set(key, (counts.get(key) || 0) + 1);
    });
    return counts;
  }, [sessions]);

  const plannedDates = useMemo(() => {
    const plans = new Map<string, StudyPlanDay[]>();
    planDays.forEach((entry) => {
      const items = plans.get(entry.plan_date) || [];
      items.push(entry);
      plans.set(entry.plan_date, items);
    });
    return plans;
  }, [planDays]);

  const streakKeys = useMemo(() => buildCurrentStreakKeys(gamification), [gamification]);
  const calendarDays = useMemo(() => buildCalendarDays(monthCursor), [monthCursor]);
  const todayKey = toDateKey(new Date());

  const activeDaysThisMonth = calendarDays.filter((day) => activeDates.has(toDateKey(day)) && day.getMonth() === monthCursor.getMonth()).length;
  const plannedDaysThisMonth = calendarDays.filter((day) => plannedDates.has(toDateKey(day)) && day.getMonth() === monthCursor.getMonth()).length;

  return (
    <section className={`spc ${className}`.trim()}>
      <div className="spc-head">
        <div>
          <div className="spc-title">{title}</div>
          <div className="spc-subtitle">{subtitle}</div>
        </div>
        <div className="spc-summary">
          <span>{activeDaysThisMonth} zile active</span>
          <span>{plannedDaysThisMonth} zile planificate</span>
          {gamification && <span>Streak {gamification.streak_current}</span>}
        </div>
      </div>

      <div className="spc-toolbar">
        <button type="button" className="spc-nav" aria-label="Luna precedentă" onClick={() => setMonthCursor(new Date(monthCursor.getFullYear(), monthCursor.getMonth() - 1, 1, 12))}>
          ←
        </button>
        <div className="spc-month-label">
          {MONTHS_RO[monthCursor.getMonth()]} {monthCursor.getFullYear()}
        </div>
        <button type="button" className="spc-nav" aria-label="Luna următoare" onClick={() => setMonthCursor(new Date(monthCursor.getFullYear(), monthCursor.getMonth() + 1, 1, 12))}>
          →
        </button>
      </div>

      <div className="spc-grid spc-grid-head">
        {WEEKDAYS_RO.map((day) => (
          <div key={day} className="spc-weekday">{day}</div>
        ))}
      </div>

      <div className="spc-grid">
        {calendarDays.map((day) => {
          const key = toDateKey(day);
          const isCurrentMonth = day.getMonth() === monthCursor.getMonth();
          const activeCount = activeDates.get(key) || 0;
          const dayPlans = plannedDates.get(key) || [];
          const isToday = key === todayKey;
          const isStreak = streakKeys.has(key);
          const titleParts = [
            dayPlans.length ? `Planificat: ${dayPlans.map(getPlanLabel).join(", ")}` : "",
            activeCount ? `Sesiuni începute: ${activeCount}` : "",
            isStreak ? "Face parte din streak-ul curent" : "",
          ].filter(Boolean);

          return (
            <div
              key={key}
              className={`spc-cell${isCurrentMonth ? "" : " is-outside"}${isToday ? " is-today" : ""}${activeCount ? " has-active" : ""}${dayPlans.length ? " has-plan" : ""}${isStreak ? " has-streak" : ""}`}
              title={titleParts.join("\n")}
            >
              <div className="spc-cell-top">
                <span className="spc-mobile-date">
                  {day.toLocaleDateString('ro-RO', { weekday: 'long', day: 'numeric', month: 'short' })}
                </span>
                <span className="spc-day-num">{day.getDate()}</span>
                <span className="spc-markers">
                  {activeCount > 0 && <span className="spc-dot active" />}
                  {dayPlans.length > 0 && <span className="spc-dot planned" />}
                </span>
              </div>

              <div className="spc-cell-body">
                {dayPlans.slice(0, 2).map((entry) => (
                  <span key={entry.id} className={`spc-chip${entry.completed ? " done" : ""}`}>
                    {getPlanLabel(entry)}
                  </span>
                ))}
                {activeCount > 0 && (
                  <span className="spc-chip active">{activeCount} sesiune{activeCount > 1 ? "e" : ""}</span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {activeDaysThisMonth === 0 && plannedDaysThisMonth === 0 && (
        <div className="spc-mobile-empty">Nu există activitate sau sesiuni planificate în această lună.</div>
      )}

      <div className="spc-legend">
        <span><i className="spc-dot active" /> zi de studiu</span>
        <span><i className="spc-dot planned" /> zi planificată</span>
        <span><i className="spc-dot streak" /> streak curent</span>
      </div>
    </section>
  );
}
