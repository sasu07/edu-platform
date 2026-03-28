import { useState, useEffect, useRef } from 'react';
import { Bell } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { getNotifications, markAllNotificationsRead } from '../api';
import './NotificationBell.css';

interface Notif {
  id: string;
  type: string;
  title: string;
  body?: string;
  is_read: boolean;
  related_id?: string;
  created_at: string;
}

const TYPE_ROUTES: Record<string, string> = {
  help_response: '/app/my-requests',
  new_request:   '/app/teacher/requests',
};

export default function NotificationBell() {
  const [notifs, setNotifs] = useState<Notif[]>([]);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  const unread = notifs.filter(n => !n.is_read).length;

  const load = async () => {
    try {
      const res = await getNotifications();
      setNotifs(Array.isArray(res.data) ? res.data : []);
    } catch {}
  };

  useEffect(() => {
    load();
    const id = setInterval(load, 30_000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const handleOpen = () => {
    setOpen(v => !v);
  };

  const handleMarkAll = async () => {
    await markAllNotificationsRead();
    setNotifs(notifs.map(n => ({ ...n, is_read: true })));
  };

  const handleClick = (n: Notif) => {
    setOpen(false);
    const route = TYPE_ROUTES[n.type];
    if (route) navigate(route);
  };

  return (
    <div className="notif-bell-wrap" ref={ref}>
      <button className="notif-bell-btn" onClick={handleOpen} aria-label="Notificări">
        <Bell size={20} />
        {unread > 0 && (
          <span className="notif-badge">{unread > 9 ? '9+' : unread}</span>
        )}
      </button>

      {open && (
        <div className="notif-dropdown">
          <div className="notif-dropdown-head">
            <span>Notificări</span>
            {unread > 0 && (
              <button className="notif-mark-all" onClick={handleMarkAll}>
                Marchează toate citite
              </button>
            )}
          </div>

          <div className="notif-list">
            {notifs.length === 0 ? (
              <div className="notif-empty">Nicio notificare.</div>
            ) : (
              notifs.slice(0, 20).map(n => (
                <button
                  key={n.id}
                  className={`notif-item ${n.is_read ? 'read' : 'unread'}`}
                  onClick={() => handleClick(n)}
                >
                  <div className="notif-item-title">{n.title}</div>
                  {n.body && <div className="notif-item-body">{n.body}</div>}
                  <div className="notif-item-time">
                    {new Date(n.created_at).toLocaleString('ro-RO', {
                      day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit',
                    })}
                  </div>
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
