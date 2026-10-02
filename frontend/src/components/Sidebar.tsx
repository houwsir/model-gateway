import { NavLink } from 'react-router-dom';
import type { ReactNode } from 'react';

interface NavEntry {
  to: string;
  label: string;
  section: string;
  icon: ReactNode;
  badge?: string;
}

const stroke = { fill: 'none', stroke: 'currentColor', strokeWidth: 1.8 } as const;

const NAV: NavEntry[] = [
  {
    to: '/overview',
    label: '监控大盘',
    section: '概览',
    icon: (
      <svg viewBox="0 0 24 24" {...stroke}>
        <rect x="3" y="3" width="7" height="9" rx="1.5" />
        <rect x="14" y="3" width="7" height="5" rx="1.5" />
        <rect x="14" y="12" width="7" height="9" rx="1.5" />
        <rect x="3" y="16" width="7" height="5" rx="1.5" />
      </svg>
    ),
  },
  {
    to: '/routing',
    label: '智能路由',
    section: '调度',
    icon: (
      <svg viewBox="0 0 24 24" {...stroke}>
        <circle cx="5" cy="12" r="2.5" />
        <circle cx="19" cy="5" r="2.5" />
        <circle cx="19" cy="19" r="2.5" />
        <path d="M7.3 10.8 16.7 6.2M7.3 13.2 16.7 17.8" />
      </svg>
    ),
  },
  {
    to: '/providers',
    label: '供应商管理',
    section: '调度',
    icon: (
      <svg viewBox="0 0 24 24" {...stroke}>
        <path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v14H6.5A2.5 2.5 0 0 0 4 19.5z" />
        <path d="M4 5.5A2.5 2.5 0 0 0 6.5 8H20" />
        <path d="M8 7h.01M8 11h6M8 14h4" />
      </svg>
    ),
  },
  {
    to: '/balancing',
    label: '负载均衡',
    section: '调度',
    icon: (
      <svg viewBox="0 0 24 24" {...stroke}>
        <path d="M12 3v18M5 7l7-4 7 4M5 17l7 4 7-4" />
        <path d="M5 7v10M19 7v10M12 3v.01" />
      </svg>
    ),
  },
  {
    to: '/traffic',
    label: '流量控制',
    section: '治理',
    icon: (
      <svg viewBox="0 0 24 24" {...stroke}>
        <path d="M4 5h16v5H4z" />
        <path d="M4 13h16v6H4z" />
        <path d="M8 8h.01M8 16h.01" />
      </svg>
    ),
  },
  {
    to: '/memory',
    label: '持久记忆',
    section: '治理',
    icon: (
      <svg viewBox="0 0 24 24" {...stroke}>
        <path d="M12 3a9 9 0 1 0 9 9" />
        <path d="M12 3a9 9 0 0 1 9 9" />
        <path d="M12 12l4-4" />
        <circle cx="12" cy="12" r="1.5" />
      </svg>
    ),
  },
  {
    to: '/resilience',
    label: '容灾策略',
    section: '稳定',
    icon: (
      <svg viewBox="0 0 24 24" {...stroke}>
        <path d="M12 3l8 3v6c0 4.5-3.2 7.8-8 9-4.8-1.2-8-4.5-8-9V6z" />
        <path d="M9 12l2 2 4-4" />
      </svg>
    ),
  },
  {
    to: '/alerts',
    label: '告警中心',
    section: '稳定',
    icon: (
      <svg viewBox="0 0 24 24" {...stroke}>
        <path d="M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
        <path d="M13.7 21a2 2 0 0 1-3.4 0" />
      </svg>
    ),
    badge: '3',
  },
  {
    to: '/settings',
    label: '系统设置',
    section: '系统',
    icon: (
      <svg viewBox="0 0 24 24" {...stroke}>
        <circle cx="12" cy="12" r="3" />
        <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
      </svg>
    ),
  },
];

export default function Sidebar() {
  let lastSection = '';
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M4 7h16M4 12h10M4 17h16" />
            <circle cx="18" cy="12" r="2.2" />
          </svg>
        </div>
        <div>
          <div className="brand-name">模型网关</div>
          <div className="brand-sub">Model Gateway Console</div>
        </div>
      </div>

      <nav>
        {NAV.map((item) => {
          const sectionHeader =
            item.section !== lastSection ? (
              <div className="nav-label" key={`sec-${item.section}`} style={{ marginTop: item.section !== '概览' ? 'var(--sp-3)' : 0 }}>
                {item.section}
              </div>
            ) : null;
          lastSection = item.section;
          return (
            <div key={item.to}>
              {sectionHeader}
              <NavLink to={item.to} className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}>
                {item.icon}
                {item.label}
                {item.badge && <span className="nav-badge">{item.badge}</span>}
              </NavLink>
            </div>
          );
        })}
      </nav>

      <div className="sidebar-foot">
        <div className="avatar">陈</div>
        <div className="foot-meta">
          <div className="foot-name">陈运营</div>
          <div className="foot-role">平台管理员</div>
        </div>
      </div>
    </aside>
  );
}
