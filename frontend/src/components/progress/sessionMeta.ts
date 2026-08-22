import type { SessionStatus, SessionType } from '../../api';

/* Etichete/iconițe prietenoase pentru tipurile și statusurile de sesiune,
   ca să nu expunem elevului valori tehnice (Epic 3 §6.3). */

export const SESSION_META: Record<string, { label: string; icon: string }> = {
  test_scurt: { label: 'Test scurt', icon: '⚡' },
  test_bac: { label: 'Test BAC', icon: '🏆' },
  _default: { label: 'Sesiune', icon: '📘' },
};

export function statusLabel(status: SessionStatus | string): string {
  if (status === 'completed') return 'Finalizat';
  if (status === 'abandoned') return 'Abandonat';
  return 'Activ';
}

export function sessionMeta(type: SessionType | string) {
  return SESSION_META[type] || SESSION_META._default;
}
