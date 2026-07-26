import axios from 'axios';

const DEFAULT_API_BASE_URL = 'http://localhost:8000';

export const API_BASE_URL =
  (import.meta as ImportMeta & { env?: { VITE_API_URL?: string } }).env?.VITE_API_URL?.replace(/\/$/, '') ||
  DEFAULT_API_BASE_URL;

export function buildApiUrl(path?: string | null): string {
  if (!path) return '';
  if (/^https?:\/\//i.test(path)) return path;
  return `${API_BASE_URL}${path.startsWith('/') ? path : `/${path}`}`;
}

/**
 * Ia un fișier protejat din /uploads ca object URL (pentru <img src>).
 * Fișierele necesită acum header Authorization; <img>/<a> nu-l trimit,
 * deci le luăm ca blob cu token. Apelantul e responsabil să revoce URL-ul.
 */
export async function fetchAuthedObjectUrl(path: string): Promise<string> {
  const token = localStorage.getItem('access_token');
  const res = await fetch(buildApiUrl(path), {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error('Fișier indisponibil');
  const blob = await res.blob();
  return URL.createObjectURL(blob);
}

/** Descarcă un fișier protejat (cu token) și îl deschide într-un tab nou. */
export async function openAuthedFile(path?: string | null): Promise<void> {
  if (!path) return;
  try {
    const url = await fetchAuthedObjectUrl(path);
    window.open(url, '_blank', 'noopener');
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
  } catch {
    alert('Fișierul nu este disponibil.');
  }
}

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Injectează automat token-ul JWT la fiecare request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// La 401 pe /auth/me — token expirat, logout automat
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && error.config?.url?.includes('/auth/me')) {
      localStorage.removeItem('access_token');
      if (!window.location.pathname.includes('/login')) {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

export interface Source {
  id: string;
  name: string;
  type: string;
  year?: number;
  session?: string;
  url_file_path?: string;
  notes?: string;
  created_at: string;
}

export interface Exercise {
  id: string;
  exam_type: string;
  profile?: string;
  subject_part?: string;
  item_type?: string;
  statement_latex: string;
  statement_text?: string;
  answer_latex?: string;
  answer_numeric_value?: number | null;
  answer_numeric_expression?: string | null;
  solution_latex?: string;
  scoring_guide_latex?: string;
  scoring_guide_text?: string;
  difficulty?: number;
  estimated_time_sec?: number;
  points?: number;
  metadata?: any;
  status: 'DRAFT' | 'REVIEW' | 'READY' | 'ARCHIVED';
  created_at: string;
  updated_at: string;
}

export interface Tag {
  id: string;
  namespace: string;
  key: string;
  label?: string;
  parent_id?: string;
  created_at?: string;
}

export interface ExerciseTag {
  id: string;
  namespace: string;
  key: string;
  label?: string;
  weight?: number;
}

// --- Auth types & calls ---
export interface User {
  id: string;
  email: string;
  full_name: string;
  role: 'student' | 'teacher' | 'school_teacher' | 'admin' | 'parent';
  is_active: boolean;
  created_at: string;
}

export interface Subscription {
  id: string;
  user_id: string;
  plan_type: 'free' | 'premium';
  status: 'active' | 'expired' | 'cancelled';
  expires_at?: string;
  created_at: string;
}

export interface AuthToken {
  access_token: string;
  token_type: string;
  user: User;
}

export interface HelpRequest {
  id: string;
  student_id: string;
  exercise_id: string;
  flag_type: 'WRITTEN' | 'VIDEO' | 'LIVE';
  status: 'pending' | 'assigned' | 'resolved';
  notes?: string;
  assigned_teacher_id?: string;
  created_at: string;
  updated_at: string;
}

export interface HelpResponse {
  id: string;
  request_id: string;
  teacher_id: string;
  content_text?: string;
  video_path?: string;
  zoom_link?: string;
  scheduled_at?: string;
  created_at: string;
}

export const authRegister = (data: { email: string; password: string; full_name: string; role: string; school_name?: string }) =>
  api.post<AuthToken>('/auth/register', data);
export const getMyVariants = () => api.get<any[]>('/variants/my');
export const getVariants = () => api.get<any[]>('/variants/');
export const getVariantExercises = (variantId: string) => api.get<any[]>(`/variants/${variantId}/exercises/`);
export const createVariant = (data: {
  name: string;
  exam_type: string;
  profile: string;
  year: number;
  session: string;
  duration_minutes: number;
  instructions: string;
}) => api.post<any>('/variants/', data);
export const addExercisesToVariant = (variantId: string, exerciseIds: string[]) =>
  api.post(`/variants/${variantId}/exercises/`, exerciseIds);
export const removeExerciseFromVariant = (variantId: string, exerciseId: string) =>
  api.delete(`/variants/${variantId}/exercises/${exerciseId}`);
export const generateVariant = (variantId: string) =>
  api.post('/variants/generate', { variant_id: variantId });
export const getVariantDocument = (variantId: string, endpoint: 'preview-exam' | 'preview-solutions' | 'preview-barem' | 'download-pdf') =>
  api.get(`/variants/${variantId}/${endpoint}`, { responseType: 'blob' });
export const getNotifications = () => api.get<any[]>('/notifications/');
export const markNotificationRead = (id: string) => api.put(`/notifications/${id}/read`);
export const markAllNotificationsRead = () => api.put('/notifications/read-all');
export const authLogin = (data: { email: string; password: string }) =>
  api.post<AuthToken>('/auth/login', data);
export const authMe = () => api.get<User>('/auth/me');
export const authMySubscription = () => api.get<Subscription>('/auth/me/subscription');

export const createHelpRequest = (data: { exercise_id: string; flag_type: string; notes?: string }) =>
  api.post<HelpRequest>('/help-requests/', data);
export const myHelpRequests = () => api.get<HelpRequest[]>('/help-requests/my');
export const pendingHelpRequests = () => api.get<any[]>('/help-requests/pending');
export const assignHelpRequest = (id: string) => api.put<HelpRequest>(`/help-requests/${id}/assign`);
export const respondToHelpRequest = (id: string, data: { content_text?: string; zoom_link?: string; scheduled_at?: string }) =>
  api.post<HelpResponse>(`/help-requests/${id}/respond`, data);
export const getHelpResponse = (requestId: string) =>
  api.get<HelpResponse>(`/help-requests/${requestId}/response`);

export const getExerciseChildren = (id: string) => api.get<Exercise[]>(`/exercises/${id}/children`);

export const getExerciseHints = (id: string) =>
  api.get<{ exercise_id: string; hints: string[]; source: string }>(`/exercises/${id}/hints`);
export const getAdminUsers = () => api.get<any[]>('/admin/users');

export const getAuditLog = (params?: {
  action?: string; method?: string; status_code?: number;
  resource_type?: string; q?: string; since_hours?: number;
  limit?: number; offset?: number;
}) =>
  api.get<{ total: number; limit: number; offset: number; items: any[] }>('/admin/audit', { params });
export const upgradeSubscription = (userId: string, planType: string = 'premium', expiresAt?: string) =>
  api.post(`/admin/subscriptions/${userId}/upgrade`, null, {
    params: { plan_type: planType, ...(expiresAt ? { expires_at: expiresAt } : {}) },
  });
export const cancelSubscription = (userId: string) =>
  api.delete(`/admin/subscriptions/${userId}`);
export const createTeacher = (data: { email: string; password: string; full_name: string }) =>
  api.post('/admin/teachers', { ...data, role: 'teacher' });
export const getMyAccess = () => api.get<{ can_help_requests: boolean; can_download_pdf: boolean; can_unlimited_gen: boolean }>('/auth/me/access');

export interface GenLimits {
  exercise_gen_used: number;
  exercise_gen_limit: number | null;
  variant_gen_used: number;
  variant_gen_limit: number | null;
  has_unlimited_gen: boolean;
}
export const getMyLimits = () => api.get<GenLimits>('/auth/me/limits');
export const logExerciseGeneration = () => api.post('/exercise-generations/log');

export interface ExerciseSet {
  id: string;
  name: string;
  linked_plan: string | null;
  filters: Record<string, any> | null;
  exercise_count: number;
  created_at: string;
}

export interface ExerciseSetDetail extends Omit<ExerciseSet, 'exercise_count'> {
  exercises: Exercise[];
}

export const saveExerciseSet = (data: {
  exercise_ids: string[];
  filters: Record<string, any>;
  name?: string;
  linked_plan?: string | null;
}) => api.post<{ id: string; name: string; exercise_count: number }>('/exercise-sets/', data);

export const getExerciseSets = () => api.get<ExerciseSet[]>('/exercise-sets/');
export const getExerciseSet = (id: string) => api.get<ExerciseSetDetail>(`/exercise-sets/${id}`);
export const updateExerciseSet = (id: string, data: { name?: string; linked_plan?: string | null }) =>
  api.put<ExerciseSet>(`/exercise-sets/${id}`, data);
export const deleteExerciseSet = (id: string) => api.delete(`/exercise-sets/${id}`);

export const getSources = () => api.get<Source[]>('/sources/');
export interface FilterOptions {
  profiles: string[];
  years: number[];
  topics: { key: string; label: string; count: number }[];
  methods: { key: string; label: string; count: number }[];
}

export const getExerciseFilterOptions = (params?: {
  subiect_tag?: string;
  profile?: string;
  year?: number;
  topic_tag?: string;
}) => api.get<FilterOptions>('/exercises/filter-options', { params });

export const getExercises = (params?: {
  exam_type?: string;
  status?: string;
  subiect_tag?: string;
  topic_tag?: string;
  method_tag?: string;
  difficulty_min?: number;
  difficulty_max?: number;
  has_solution?: boolean;
  has_scoring_guide?: boolean;
  subject_part?: string;
  profile?: string;
  year?: number;
  only_roots?: boolean;
  exclude_seen?: boolean;
  is_container?: boolean;
  limit?: number;
}) => api.get<Exercise[]>('/exercises/', { params });
export const getExercise = (id: string) => api.get<Exercise>(`/exercises/${id}`);
export const getBatchChildren = (ids: string[]) =>
  api.get<Record<string, Exercise[]>>('/exercises/batch-children', { params: { ids: ids.join(',') } });
export const updateExercise = (id: string, data: Partial<Exercise>) => api.put<Exercise>(`/exercises/${id}`, data);
export const deleteExercise = (id: string) => api.delete(`/exercises/${id}`);

export const getTags = (namespace?: string) => api.get<Tag[]>('/tags/', { params: { namespace } });
export const tagExercise = (id: string) => api.post(`/exercises/${id}/tag`);
export const getExerciseTags = (exerciseId: string) => api.get<ExerciseTag[]>(`/exercises/${exerciseId}/tags`);
export const addTagToExercise = (exerciseId: string, tagId: string) => api.post(`/exercises/${exerciseId}/tags/${tagId}`);
export const removeTagFromExercise = (exerciseId: string, tagId: string) => api.delete(`/exercises/${exerciseId}/tags/${tagId}`);

export interface TeacherStats {
  total_requests: number;
  pending: number;
  assigned: number;
  resolved: number;
  by_type: Record<string, number>;
  avg_response_hours?: number;
}

export const getTeacherStats = (params?: { teacher_id?: string }) =>
  api.get<TeacherStats>('/teacher/stats', { params });

// --- Exercise completion ---
export const markExerciseComplete = (exerciseId: string) =>
  api.post<{ exercise_id: string; completed: boolean; xp_gained: number; new_badges: string[] }>(`/exercises/${exerciseId}/complete`);
export const getExerciseCompleteStatus = (exerciseId: string) =>
  api.get<{ exercise_id: string; completed: boolean }>(`/exercises/${exerciseId}/complete`);
export const getCompletedExerciseIds = () =>
  api.get<string[]>('/student/completed-exercise-ids');

// --- Gamification ---
export interface GamificationLevel {
  name: string;
  icon: string;
  xp_total: number;
  xp_in_level: number;
  xp_for_next: number;
  progress_pct: number;
  is_max: boolean;
}

export interface GamificationBadge {
  key: string;
  label: string;
  icon: string;
  desc: string;
  earned_at: string;
}

export interface GamificationProfile {
  xp_total: number;
  streak_current: number;
  streak_max: number;
  last_active_date: string | null;
  level: GamificationLevel;
  badges: GamificationBadge[];
}

export const getMyGamification = () =>
  api.get<GamificationProfile>('/student/gamification');
export const getStudentGamification = (studentId: string) =>
  api.get<GamificationProfile>(`/student/gamification/${studentId}`);

// --- Liga BAC ---
export interface LeagueClass {
  id: string;
  name: string;
  class_code: string;
  allow_anonymous: boolean;
  created_at: string;
  teacher_name?: string;
  member_count?: number;
  membership_id?: string;
  pseudonym?: string | null;
  is_anonymous?: boolean;
  joined_at?: string;
}

export interface LeagueMembership {
  id: string;
  class_id: string;
  student_id: string;
  pseudonym?: string | null;
  is_anonymous: boolean;
  joined_at: string;
}

export interface LeagueLeaderboardEntry {
  student_id: string;
  display_name: string;
  xp_week: number;
  rank: number;
  is_you: boolean;
  is_anonymous: boolean;
}

export interface LeagueChallengeProgress {
  student_id: string;
  display_name: string;
  progress_count: number;
  completed: boolean;
  is_you: boolean;
}

export interface LeagueChallenge {
  id: string;
  title: string;
  description?: string | null;
  target_count: number;
  filters: Record<string, any>;
  week_start: string;
  week_end: string;
  participant_progress: LeagueChallengeProgress[];
}

export interface LeagueOverview {
  class_info: {
    id: string;
    name: string;
    class_code: string;
    allow_anonymous: boolean;
    teacher_name: string;
    member_count: number;
  };
  week: { start: string; end: string };
  my_membership?: {
    id: string;
    class_id: string;
    student_id: string;
    pseudonym?: string | null;
    is_anonymous: boolean;
    allow_anonymous?: boolean;
  } | null;
  leaderboard: LeagueLeaderboardEntry[];
  challenges: LeagueChallenge[];
}

export const createTeacherClass = (data: { name: string; allow_anonymous?: boolean }) =>
  api.post<LeagueClass>('/teacher/classes', data);
export const getTeacherClasses = () =>
  api.get<LeagueClass[]>('/teacher/classes');
export const createWeeklyClassChallenge = (classId: string, data: { title: string; description?: string; target_count: number; subiect_tag?: string }) =>
  api.post<LeagueChallenge>(`/teacher/classes/${classId}/challenges`, data);
export const joinLeagueClass = (data: { class_code: string; pseudonym?: string; is_anonymous?: boolean }) =>
  api.post<{ class: LeagueClass; membership: LeagueMembership }>('/student/classes/join', data);
export const getStudentLeagueClasses = () =>
  api.get<LeagueClass[]>('/student/classes');
export const updateLeagueMembership = (classId: string, data: { pseudonym?: string; is_anonymous?: boolean }) =>
  api.put<LeagueMembership>(`/student/classes/${classId}/membership`, data);
export const getLeagueOverview = (classId: string, params?: { week_start?: string }) =>
  api.get<LeagueOverview>(`/league/classes/${classId}/overview`, { params });

// --- Exercise Submissions ---
export type SelfEval = 'failed' | 'partial' | 'complete';
export type TeacherStatus = 'pending' | 'correct' | 'incorrect';

export interface ExerciseSubmission {
  id: string;
  user_id: string;
  exercise_id: string;
  self_eval: SelfEval;
  photo_path: string | null;
  photo_uploaded_at: string | null;
  teacher_status: TeacherStatus | null;
  teacher_note: string | null;
  teacher_file_path: string | null;
  xp_self_eval: number;
  xp_photo: number;
  xp_teacher: number;
  created_at: string;
}

export interface ReviewItem extends Exercise {
  source_reason: 'failed' | 'partial' | 'marked_unresolved';
  fail_count: number;
  revisit_count: number;
  first_flagged_at: string;
  last_flagged_at: string;
}

export const submitExercise = (exerciseId: string, self_eval: SelfEval) =>
  api.post<ExerciseSubmission>(`/exercises/${exerciseId}/submit`, { self_eval });
export const uploadSubmissionPhoto = (exerciseId: string, photo: File) => {
  const fd = new FormData();
  fd.append('photo', photo);
  return api.post<{ status: string; xp_awarded: number }>(`/exercises/${exerciseId}/submit-photo`, fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
};
export const getMySubmission = (exerciseId: string) =>
  api.get<ExerciseSubmission | null>(`/exercises/${exerciseId}/submission`);
export const getMySubmissions = () =>
  api.get<any[]>('/student/submissions');
export const getReviewItems = () =>
  api.get<ReviewItem[]>('/student/review-items');
export const openReviewItem = (exerciseId: string, reason: string = 'blocked') =>
  api.post(`/exercises/${exerciseId}/review/open`, null, { params: { reason } });
export const resolveReviewItem = (exerciseId: string) =>
  api.post(`/exercises/${exerciseId}/review/resolve`);

// Teacher
export const getTeacherSubmissions = (status = 'pending') =>
  api.get<any[]>('/teacher/submissions', { params: { status } });
export const reviewSubmission = (submissionId: string, data: { status: TeacherStatus; note?: string }) =>
  api.post(`/teacher/submissions/${submissionId}/review`, data);
export const uploadTeacherFile = (submissionId: string, file: File) => {
  const fd = new FormData();
  fd.append('file', file);
  return api.post<{ status: string; file_url: string }>(`/teacher/submissions/${submissionId}/upload-file`, fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
};
export const assignPendingSubmissions = () =>
  api.post<{ assigned: number }>('/teacher/submissions/assign-pending');
export const getSubmissionStats = () =>
  api.get<{ pending: number; correct: number; incorrect: number; total: number }>('/teacher/submissions/stats');
export const getPendingExerciseIds = () =>
  api.get<string[]>('/student/pending-exercise-ids');
export const getLiveHelpRequests = () =>
  api.get<any[]>('/teacher/help-requests/live');
export const scheduleLiveHelp = (requestId: string, data: { scheduled_at: string; zoom_link?: string }) =>
  api.post(`/teacher/help-requests/${requestId}/schedule`, data);

// --- Parent-Student ---
export interface ParentStudentLink {
  id: string;
  parent_id: string;
  student_id: string;
  parent_email: string;
  parent_name: string;
  student_name: string;
  linked_at: string;
}

export interface StudentActivityDay {
  date: string;
  exercises_seen: number;
  exercises_completed: number;
  variants_generated: number;
  flags_sent: number;
}

export interface ParentStudentStats {
  student_id: string;
  student_name: string;
  student_email: string;
  total_exercises_seen: number;
  total_exercises_completed: number;
  total_variants_generated: number;
  total_flags_sent: number;
  total_review_items_open: number;
  last_active_at?: string;
  activity_last_30_days: StudentActivityDay[];
  completion_by_subiect: Record<string, number>;
}

export const linkParent = (data: { parent_email: string; parent_name?: string }) =>
  api.post<ParentStudentLink>('/parent/link-student', data);
export const getMyParents = () => api.get<ParentStudentLink[]>('/student/my-parents');
export const removeParentLink = (parentId: string) =>
  api.delete(`/student/my-parents/${parentId}`);
export const getMyStudents = () => api.get<ParentStudentLink[]>('/parent/students');
export const getStudentStats = (studentId: string) =>
  api.get<ParentStudentStats>(`/parent/students/${studentId}/stats`);

// Admin parent management
export const adminGetParentStudents = () => api.get<any[]>('/admin/parent-students');
export const adminLinkParentStudent = (data: { parent_id: string; student_id: string }) =>
  api.post<ParentStudentLink>('/admin/parent-student', data);
export const adminRemoveParentStudentLink = (linkId: string) =>
  api.delete(`/admin/parent-student/${linkId}`);

// --- Study Sessions ---
export type SessionType = 'test_scurt' | 'test_bac';
export type SessionStatus = 'active' | 'completed' | 'abandoned';

export interface StudySession {
  id: string;
  user_id: string;
  session_type: SessionType;
  filters: Record<string, any>;
  exercise_set_id: string | null;
  status: SessionStatus;
  started_at: string;
  completed_at: string | null;
  duration_sec: number | null;
  exercises_total: number;
  exercises_completed: number;
  avg_difficulty: number | null;
  xp_gained: number;
  created_at: string;
  exercises?: any[];
}

export interface StudyPlanDay {
  id: string;
  user_id: string;
  plan_date: string;
  session_type: SessionType;
  filters: Record<string, any>;
  note: string | null;
  created_by: 'student' | 'teacher';
  teacher_id: string | null;
  teacher_name: string | null;
  session_id: string | null;
  completed: boolean;
  created_at: string;
}

export interface StudyStats {
  total_sessions: number;
  total_exercises: number;
  total_xp: number;
  avg_completion_pct: number;
  daily_last_30: { date: string; sessions: number; exercises: number }[];
  subiect_progress: { subiect: string; total: number; completed: number; pct: number }[];
  recommendation: string | null;
}

export interface ParentStudySessionsResponse {
  sessions: StudySession[];
  stats: Record<string, number | null>;
}

export const startStudySession = (data: { session_type: SessionType; filters: Record<string, any>; plan_day_id?: string }) =>
  api.post<StudySession>('/study-sessions/start', data);
export const completeStudySession = (sessionId: string, data: { duration_sec: number; exercises_completed: number }) =>
  api.post<StudySession>(`/study-sessions/${sessionId}/complete`, data);
export const abandonStudySession = (sessionId: string) =>
  api.post(`/study-sessions/${sessionId}/abandon`);
export const getStudySessions = () =>
  api.get<StudySession[]>('/study-sessions/');
export const getStudySession = (sessionId: string) =>
  api.get<StudySession>(`/study-sessions/${sessionId}`);
export const getStudyStats = () =>
  api.get<StudyStats>('/student/study-stats');
export const getParentStudentSessions = (studentId: string) =>
  api.get<ParentStudySessionsResponse>(`/parent/students/${studentId}/study-sessions`);
export const getParentStudentStudyPlan = (studentId: string) =>
  api.get<StudyPlanDay[]>(`/parent/students/${studentId}/study-plan`);

// Study Plan
export const getStudyPlan = () =>
  api.get<StudyPlanDay[]>('/study-plan/');
export const createStudyPlanDay = (data: { user_id?: string; plan_date: string; session_type: SessionType; filters?: Record<string, any>; note?: string }) =>
  api.post<StudyPlanDay>('/study-plan/', data);
export const deleteStudyPlanDay = (planId: string) =>
  api.delete(`/study-plan/${planId}`);
export const getTeacherStudentsList = () =>
  api.get<{ id: string; full_name: string; email: string }[]>('/teacher/students-list');

// ─── Learning Path ───────────────────────────────────────────────────────────

export interface DiagnosticExercise {
  id: string;
  statement_latex: string;
  statement_text?: string;
  difficulty?: number;
  topic_key?: string;
  topic_label?: string;
  has_auto_check?: boolean;
  options: string[] | null;  // null = exercițiu cu răspuns deschis
}

export interface DiagnosticWeakTopic {
  topic_key: string;
  topic_label: string;
  subiect: number | null;
  score_pct: number;
  seen: number;
  correct: number;
}

export interface DiagnosticResult {
  test_id: string;
  score_pct: number;
  correct_count: number;
  total: number;
  weak_topics: DiagnosticWeakTopic[];
}

export interface LearningPathNode {
  id: string;
  topic_key: string;
  topic_label: string;
  subiect_num: number;
  priority: number;
  status: 'pending' | 'in_progress' | 'mastered';
  exercises_seen: number;
  exercises_correct: number;
  target_exercises: number;
  score_pct: number;
  diagnostic_score_pct: number | null;
  sort_order: number;
}

export interface LearningPath {
  id: string;
  user_id: string;
  diagnostic_test_id: string | null;
  status: string;
  total_nodes: number;
  completed_nodes: number;
  generated_at: string;
  updated_at: string;
}

export interface AIPlanWeek {
  numar: number;
  titlu: string;
  focus_principal: string;
  obiective: string[];
  topicuri_recomandate: string[];
  timp_zilnic_minute: number;
  strategie: string;
}

export interface AIPlan {
  rezumat: string;
  nivel_general: 'incepator' | 'mediu' | 'avansat';
  saptamani: AIPlanWeek[];
  prioritati_urgente: string[];
  sfaturi_practice: string[];
  motivatie: string;
  _source?: 'claude' | 'fallback';
}

export interface LearningPathResponse {
  path: LearningPath | null;
  nodes: LearningPathNode[];
  total_nodes: number;
  preview_only: boolean;
  is_premium: boolean;
  ai_plan: AIPlan | null;
}

export interface TodayRecommendation {
  id: string;
  statement_latex: string;
  statement_text?: string;
  answer_latex?: string;
  answer_numeric_value?: number;
  difficulty?: number;
  source: 'spaced_repetition' | 'learning_path';
  topic_key?: string;
  topic_label?: string;
  node_id?: string;
}

export interface SkillTreeSubiect {
  subiect: number;
  label: string;
  topics: LearningPathNode[];
  mastered: number;
  total: number;
}

export interface DiagnosticHistoryEntry {
  id: string;
  status: 'active' | 'completed' | 'abandoned';
  total_exercises: number;
  correct_count: number;
  score_pct: number;
  weak_topics: DiagnosticWeakTopic[];
  solution_file_path: string | null;
  created_at: string;
  completed_at: string | null;
}

// Diagnostic
export const getDiagnosticHistory = () =>
  api.get<DiagnosticHistoryEntry[]>('/diagnostic/history');

export const startDiagnostic = () =>
  api.post<{ test_id: string; exercises: DiagnosticExercise[]; total: number }>('/diagnostic/start');

export const getCurrentDiagnostic = () =>
  api.get<{ test: any | null; exercises?: any[] }>('/diagnostic/current');

export const submitDiagnostic = (
  testId: string,
  answers: { exercise_id: string; selected_option?: number; answer?: string }[],
) => api.post<DiagnosticResult>(`/diagnostic/${testId}/submit`, { answers });

export const uploadDiagnosticSolution = (testId: string, file: File) => {
  const fd = new FormData();
  fd.append('file', file);
  return api.post<{ filename: string; url: string }>(
    `/diagnostic/${testId}/upload-solution`,
    fd,
    { headers: { 'Content-Type': 'multipart/form-data' } },
  );
};

// Learning Path
export const generateLearningPath = (diagnosticTestId: string) =>
  api.post<{ path_id: string; total_nodes: number }>('/learning-path/generate', {
    diagnostic_test_id: diagnosticTestId,
  });

export const getLearningPath = () =>
  api.get<LearningPathResponse>('/learning-path/');

export const getTodayRecommendations = () =>
  api.get<{ date: string; recommendations: TodayRecommendation[]; sr_count: number; new_count: number }>(
    '/learning-path/today',
  );

export const updateNodeProgress = (nodeId: string, exerciseId: string, isCorrect: boolean) =>
  api.post(`/learning-path/node/${nodeId}/progress`, { exercise_id: exerciseId, is_correct: isCorrect });

export const getSkillTree = () =>
  api.get<{ subiects: SkillTreeSubiect[] }>('/learning-path/skill-tree');

export const submitSRReview = (exerciseId: string, quality: number) =>
  api.post('/spaced-repetition/review', { exercise_id: exerciseId, quality });

export default api;
