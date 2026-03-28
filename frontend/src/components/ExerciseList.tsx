import React, { useState, useEffect, useRef } from 'react';
import {
  getExercises, getTags, getExerciseTags, addTagToExercise, removeTagFromExercise, tagExercise,
  type Exercise, type Tag, type ExerciseTag
} from '../api';
import { Edit2, Tag as TagIcon, BookOpen, ChevronRight, X, Plus, Search } from 'lucide-react';
import { Link } from 'react-router-dom';
import './ExerciseList.css';

interface ExerciseListProps {
  refreshKey?: number;
}

const NAMESPACE_COLORS: Record<string, { bg: string; color: string; border: string }> = {
  topic:           { bg: '#ebf5ff', color: '#1e429f', border: '#bfdbfe' },
  subtopic:        { bg: '#f3e8ff', color: '#6b21a8', border: '#d8b4fe' },
  skill:           { bg: '#fdf4ff', color: '#86198f', border: '#e879f9' },
  method:          { bg: '#fef3c7', color: '#92400e', border: '#fcd34d' },
  exam:            { bg: '#fef9c3', color: '#854d0e', border: '#fde047' },
  subject:         { bg: '#dcfce7', color: '#166534', border: '#86efac' },
  subiect:         { bg: '#dcfce7', color: '#166534', border: '#86efac' },
  exercise:        { bg: '#dbeafe', color: '#1e40af', border: '#93c5fd' },
  subpoint:        { bg: '#e0e7ff', color: '#3730a3', border: '#a5b4fc' },
  path:            { bg: '#f0f9ff', color: '#0c4a6e', border: '#7dd3fc' },
  difficulty:      { bg: '#fee2e2', color: '#991b1b', border: '#fca5a5' },
  difficulty_math: { bg: '#fef2f2', color: '#b91c1c', border: '#fecaca' },
  difficulty_time: { bg: '#fff1f2', color: '#9f1239', border: '#fda4af' },
  profile:         { bg: '#e0f2fe', color: '#075985', border: '#7dd3fc' },
  item_type:       { bg: '#fce7f3', color: '#9d174d', border: '#f9a8d4' },
  variant:         { bg: '#fff7ed', color: '#9a3412', border: '#fdba74' },
  year:            { bg: '#f0fdf4', color: '#15803d', border: '#86efac' },
  session:         { bg: '#ecfdf5', color: '#065f46', border: '#6ee7b7' },
};

const DEFAULT_TAG_COLOR = { bg: '#f3f4f6', color: '#374151', border: '#d1d5db' };

const ExerciseList: React.FC<ExerciseListProps> = ({ refreshKey }) => {
  const [exercises, setExercises] = useState<Exercise[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [exerciseTags, setExerciseTags] = useState<Record<string, ExerciseTag[]>>({});
  const [allTags, setAllTags] = useState<Tag[]>([]);
  const [tagPickerExerciseId, setTagPickerExerciseId] = useState<string | null>(null);
  const [tagSearch, setTagSearch] = useState('');
  const tagPickerRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);

  const fetchExercises = async () => {
    setLoading(true);
    try {
      const response = await getExercises();
      const data = Array.isArray(response.data) ? response.data : [];
      setExercises(data);
      setError(null);

      // Fetch tags for all exercises in parallel
      const tagPromises = data.map(ex =>
        getExerciseTags(ex.id).then(res => ({ id: ex.id, tags: res.data })).catch(() => ({ id: ex.id, tags: [] }))
      );
      const tagResults = await Promise.all(tagPromises);
      const tagsMap: Record<string, ExerciseTag[]> = {};
      tagResults.forEach(({ id, tags }) => {
        tagsMap[id] = Array.isArray(tags) ? tags : [];
      });
      setExerciseTags(tagsMap);

    } catch (err) {
      setError('Nu s-au putut încărca exercițiile');
    } finally {
      setLoading(false);
    }
  };

  const fetchTags = async () => {
    try {
      const response = await getTags();
      setAllTags(Array.isArray(response.data) ? response.data : []);
    } catch {
      // ignore
    }
  };

  useEffect(() => {
    fetchExercises();
    fetchTags();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshKey]);

  // close tag picker on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (tagPickerRef.current && !tagPickerRef.current.contains(e.target as Node)) {
        setTagPickerExerciseId(null);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    if (tagPickerExerciseId) {
      setTimeout(() => searchInputRef.current?.focus(), 0);
    }
  }, [tagPickerExerciseId]);

  const handleAddTag = async (exerciseId: string, tagId: string) => {
    try {
      await addTagToExercise(exerciseId, tagId);
      const res = await getExerciseTags(exerciseId);
      setExerciseTags(prev => ({ ...prev, [exerciseId]: res.data }));
      setTagSearch('');
      setTagPickerExerciseId(null);
    } catch {
      // ignore
    }
  };

  const handleRemoveTag = async (exerciseId: string, tagId: string) => {
    try {
      await removeTagFromExercise(exerciseId, tagId);
      const res = await getExerciseTags(exerciseId);
      setExerciseTags(prev => ({ ...prev, [exerciseId]: res.data }));
    } catch {
      // ignore
    }
  };

  const handleAutoTag = async (exerciseId: string) => {
    try {
      await tagExercise(exerciseId);
      const res = await getExerciseTags(exerciseId);
      setExerciseTags(prev => ({ ...prev, [exerciseId]: res.data }));
    } catch {
      // ignore
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'READY':
        return 'badge-success';
      case 'REVIEW':
        return 'badge-warning';
      case 'ARCHIVED':
        return 'badge-secondary';
      default:
        return 'badge-danger';
    }
  };

  const truncateText = (text: string, max = 220) => {
    const t = (text || '').trim();
    return t.length > max ? `${t.slice(0, max)}…` : t;
  };

  const filteredTags = (exerciseId: string) => {
    const current = new Set((exerciseTags[exerciseId] || []).map(t => t.id));
    const q = tagSearch.trim().toLowerCase();
    return allTags
      .filter(t => !current.has(t.id))
      .filter(t => {
        if (!q) return true;
        return (
          (t.namespace || '').toLowerCase().includes(q) ||
          (t.key || '').toLowerCase().includes(q) ||
          (t.label || '').toLowerCase().includes(q)
        );
      })
      .slice(0, 80);
  };

  if (loading) return <div className="exercise-list-container">Se încarcă…</div>;
  if (error) return <div className="exercise-list-container">{error}</div>;

  return (
    <div className="exercise-list-container">
      <div className="list-header">
        <h2>📘 Exerciții</h2>
        <button className="btn-refresh" onClick={fetchExercises}>Refresh</button>
      </div>

      <div className="exercise-grid">
        {exercises.length === 0 ? (
          <div className="empty-state">
            <p>Nu există exerciții.</p>
          </div>
        ) : (
          exercises.map((exercise) => {
            const tags = exerciseTags[exercise.id] || [];
            return (
              <div className="exercise-card" key={exercise.id}>
                <div className="exercise-card-header">
                  <span className={`status-badge ${getStatusBadge(exercise.status)}`}>{exercise.status}</span>
                  <span className="exam-type-tag">{exercise.exam_type}</span>
                </div>

                <div className="exercise-content-preview">
                  <div className="statement-preview">
                    {truncateText(exercise.statement_text || exercise.statement_latex || '')}
                  </div>
                </div>

                <div className="exercise-tags-section">
                  <div className="tags-list">
                    {tags.map((t) => {
                      const color = NAMESPACE_COLORS[t.namespace] || DEFAULT_TAG_COLOR;
                      return (
                        <span
                          key={t.id}
                          className="tag-chip"
                          style={{ background: color.bg, color: color.color, borderColor: color.border }}
                          title={`${t.namespace}:${t.key}`}
                        >
                          <span className="tag-namespace">{t.namespace}</span>
                          <span className="tag-label">{t.label || t.key}</span>
                          <button
                            className="tag-remove-btn"
                            onClick={() => handleRemoveTag(exercise.id, t.id)}
                            title="Șterge tag"
                          >
                            <X size={12} />
                          </button>
                        </span>
                      );
                    })}

                    <div className="tag-picker-wrapper" ref={tagPickerRef}>
                      <button
                        className="tag-add-btn"
                        onClick={() => setTagPickerExerciseId(prev => (prev === exercise.id ? null : exercise.id))}
                        title="Adaugă tag"
                      >
                        <Plus size={14} />
                      </button>

                      {tagPickerExerciseId === exercise.id && (
                        <div className="tag-picker-dropdown">
                          <div className="tag-picker-search">
                            <Search size={14} />
                            <input
                              ref={searchInputRef}
                              value={tagSearch}
                              onChange={(e) => setTagSearch(e.target.value)}
                              placeholder="Caută tag…"
                            />
                          </div>

                          <div className="tag-picker-list">
                            {filteredTags(exercise.id).length === 0 ? (
                              <div className="tag-picker-empty">Niciun tag disponibil</div>
                            ) : (
                              filteredTags(exercise.id).map((t) => {
                                const color = NAMESPACE_COLORS[t.namespace] || DEFAULT_TAG_COLOR;
                                return (
                                  <button
                                    key={t.id}
                                    className="tag-picker-item"
                                    onClick={() => handleAddTag(exercise.id, t.id)}
                                  >
                                    <span className="tag-picker-dot" style={{ background: color.border }} />
                                    <span className="tag-picker-namespace">{t.namespace}</span>
                                    <span className="tag-picker-key">{t.label || t.key}</span>
                                  </button>
                                );
                              })
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                <div className="exercise-meta">
                  <span className="meta-item">
                    <BookOpen size={16} /> {exercise.item_type}
                  </span>
                  <span className="meta-item">
                    Puncte: {exercise.points}
                  </span>
                  {exercise.difficulty != null && (
                    <span className="meta-item">
                      Dificultate: {exercise.difficulty}/10
                    </span>
                  )}
                </div>

                <div className="exercise-actions">
                  {/* FIX: link relativ (merge la /app/content/exercises/:id) */}
                  <Link to={exercise.id} className="btn-action btn-edit" title="Editează">
                    <Edit2 size={18} />
                  </Link>

                  <button
                    onClick={() => handleAutoTag(exercise.id)}
                    className="btn-action btn-tag"
                    title="Tag AI"
                  >
                    <TagIcon size={18} />
                  </button>

                  {/* FIX: link relativ */}
                  <Link to={exercise.id} className="btn-view-more">
                    Detalii <ChevronRight size={16} />
                  </Link>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};

export default ExerciseList;