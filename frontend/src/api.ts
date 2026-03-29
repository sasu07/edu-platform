import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000'; // FastAPI default port

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
  role: 'student' | 'teacher' | 'school_teacher' | 'admin';
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
export const getAdminUsers = () => api.get<any[]>('/admin/users');
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
export const deleteExerciseSet = (id: string) => api.delete(`/exercise-sets/${id}`);

export const getSources = () => api.get<Source[]>('/sources/');
export const getExercises = (params?: {
  exam_type?: string;
  status?: string;
  subiect_tag?: string;
  topic_tag?: string;
  difficulty_min?: number;
  difficulty_max?: number;
  has_solution?: boolean;
  subject_part?: string;
  only_roots?: boolean;
  exclude_seen?: boolean;
}) => api.get<Exercise[]>('/exercises/', { params });
export const getExercise = (id: string) => api.get<Exercise>(`/exercises/${id}`);
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

export default api;
