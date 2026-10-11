import React, { useState, useEffect, useRef } from 'react';
import { Search } from 'lucide-react';
import { GraphNodeData } from '../../types/graph';

interface FindEntityBarProps {
  nodes: GraphNodeData[];
  onSelectEntity: (nodeId: string) => void;
  onHoverEntity?: (nodeId: string | null) => void;
}

export const FindEntityBar: React.FC<FindEntityBarProps> = ({
  nodes,
  onSelectEntity,
  onHoverEntity,
}) => {
  const [query, setQuery] = useState('');
  const [isOpen, setIsOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  // Keyboard shortcut '/' to focus
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === '/' && document.activeElement !== inputRef.current) {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const filtered = query.trim()
    ? nodes.filter(
        (n) =>
          n.label.toLowerCase().includes(query.toLowerCase()) ||
          n.tag.toLowerCase().includes(query.toLowerCase())
      )
    : [];

  return (
    <div className="relative w-full">
      <div className="relative flex items-center bg-white border border-gray-200 rounded-xl shadow-2xs overflow-hidden focus-within:ring-2 focus-within:ring-blue-500 focus-within:border-blue-500 transition-all">
        <Search size={16} className="absolute left-3.5 text-gray-400" />
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setIsOpen(true);
          }}
          onFocus={() => setIsOpen(true)}
          placeholder="Find Entity"
          className="w-full pl-10 pr-4 py-2 text-xs text-gray-900 bg-transparent outline-none placeholder:text-gray-400 font-medium"
        />
      </div>

      {isOpen && filtered.length > 0 && (
        <div className="absolute left-0 right-0 mt-1 bg-white border border-gray-200 rounded-xl shadow-lg z-30 py-1.5 max-h-56 overflow-y-auto">
          {filtered.map((item) => (
            <button
              key={item.id}
              onClick={() => {
                onSelectEntity(item.id);
                setQuery('');
                setIsOpen(false);
              }}
              onMouseEnter={() => onHoverEntity && onHoverEntity(item.id)}
              onMouseLeave={() => onHoverEntity && onHoverEntity(null)}
              className="w-full px-4 py-2 text-left hover:bg-blue-50 flex items-center justify-between transition-colors group"
            >
              <div>
                <span className="text-xs font-bold text-gray-900 group-hover:text-blue-600 block">
                  {item.label}
                </span>
                <span className="text-[10px] font-medium text-gray-400 uppercase tracking-wider">
                  {item.tag}
                </span>
              </div>
              {item.metric && (
                <span className="text-[11px] font-mono font-semibold text-gray-600">
                  {item.metric}
                </span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};
