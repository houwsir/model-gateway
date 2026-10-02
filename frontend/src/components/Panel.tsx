import type { ReactNode } from 'react';

interface PanelProps {
  title?: string;
  sub?: string;
  actions?: ReactNode;
  children: ReactNode;
  bodyStyle?: React.CSSProperties;
}

export default function Panel({ title, sub, actions, children, bodyStyle }: PanelProps) {
  return (
    <div className="panel">
      {title && (
        <div className="panel-head">
          <div>
            <div className="panel-title">{title}</div>
            {sub && <div className="panel-sub">{sub}</div>}
          </div>
          {actions && <div className="spacer">{actions}</div>}
        </div>
      )}
      <div className="panel-body" style={bodyStyle}>
        {children}
      </div>
    </div>
  );
}
