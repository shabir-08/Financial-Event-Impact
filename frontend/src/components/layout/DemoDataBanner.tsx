import React from 'react';
import { FlaskConical } from 'lucide-react';

/** Visible label for views that render fictional demo constants instead of backend responses. */
export const DemoDataBanner: React.FC<{ reason?: string }> = ({ reason }) => (
  <div className="mx-6 mt-4 p-2.5 rounded-lg border border-amber-300 bg-amber-50 text-amber-900 text-xs flex items-center gap-2">
    <FlaskConical size={14} className="flex-shrink-0" />
    <span>
      <span className="font-bold">DEMO DATA</span> — fictional events, values and sources for layout only; not backend results.
      {reason ? ` ${reason}` : ''}
    </span>
  </div>
);
