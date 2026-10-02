import { Outlet, useLocation } from 'react-router-dom';
import Sidebar from './Sidebar';

const TITLES: Record<string, string> = {
  '/overview': '监控大盘',
  '/routing': '智能路由',
  '/providers': '供应商管理',
  '/balancing': '负载均衡',
  '/traffic': '流量控制',
  '/memory': '持久记忆',
  '/resilience': '容灾策略',
  '/alerts': '告警中心',
  '/settings': '系统设置',
};

export default function Layout() {
  const location = useLocation();
  const title = TITLES[location.pathname] || '监控大盘';

  return (
    <div className="app">
      <Sidebar />
      <main className="main">
        <div className="topbar">
          <div className="crumb">
            模型网关 <span>/</span> <b>{title}</b>
          </div>
          <div className="topbar-right">
            <div className="env-pill">
              <span className="dot" />
              生产环境正常
            </div>
          </div>
        </div>
        <Outlet />
        <div className="foot">模型网关控制台 v2.4 · 所有示例数据均为演示用途</div>
      </main>
    </div>
  );
}
