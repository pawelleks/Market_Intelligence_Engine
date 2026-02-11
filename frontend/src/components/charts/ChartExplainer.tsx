import React, { useState } from 'react';
import { ChevronDown, ChevronRight, BookOpen } from 'lucide-react';

interface ChartExplainerProps {
    children: React.ReactNode;
}

export const ChartExplainer: React.FC<ChartExplainerProps> = ({ children }) => {
    const [isOpen, setIsOpen] = useState(false);

    return (
        <div className="mt-3 border border-slate-700/50 rounded-lg overflow-hidden">
            <button
                onClick={() => setIsOpen(!isOpen)}
                className="w-full flex items-center gap-2 px-3 py-2 text-xs font-medium text-slate-400 hover:text-slate-300 hover:bg-slate-800/30 transition-colors"
            >
                <BookOpen className="w-3.5 h-3.5" />
                <span>How to Read This Chart</span>
                {isOpen ? (
                    <ChevronDown className="w-3.5 h-3.5 ml-auto" />
                ) : (
                    <ChevronRight className="w-3.5 h-3.5 ml-auto" />
                )}
            </button>
            {isOpen && (
                <div className="px-4 pb-3 text-xs text-slate-400 leading-relaxed space-y-2 border-t border-slate-700/30">
                    {children}
                </div>
            )}
        </div>
    );
};
