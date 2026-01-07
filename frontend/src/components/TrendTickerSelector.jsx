import React from 'react';
import { Search, ArrowDownRight } from 'lucide-react';

/**
 * Reusable Ticker Selector Component
 * Styles matched to TrendMatrix.
 * 
 * Props:
 * - value: string (currently selected ticker)
 * - onChange: (value: string) => void
 * - tickers: string[] (flat list of tickers)
 * - groups: { [groupName: string]: string[] } (optional grouped tickers)
 * - placeholder: string (default "All Tickers")
 * - className: string (optional)
 */
const TrendTickerSelector = ({
    value,
    onChange,
    tickers = [],
    groups = null,
    placeholder = "All Tickers",
    className = ""
}) => {
    return (
        <div className={className} style={{ position: 'relative', display: 'inline-block' }}>
            <Search
                size={14}
                color="#64748b"
                style={{
                    position: 'absolute',
                    left: '10px',
                    top: '50%',
                    transform: 'translateY(-50%)',
                    pointerEvents: 'none'
                }}
            />
            <select
                value={value}
                onChange={(e) => onChange(e.target.value)}
                style={{
                    appearance: 'none',
                    padding: '6px 35px 6px 35px', // Adjusted padding
                    backgroundColor: '#0f172a',
                    border: '1px solid #334155',
                    borderRadius: '4px',
                    color: '#e2e8f0',
                    fontSize: '0.8rem',
                    minWidth: '200px',
                    width: '100%',
                    outline: 'none',
                    cursor: 'pointer'
                }}
            >
                {/* 
                   Bug Fix Note: 
                   Ensure the placeholder/default value is handled correctly. 
                   Consumers should handle empty string as "Reset/All".
                */}
                <option value="">{placeholder}</option>

                {/* Render Groups if provided */}
                {groups && Object.keys(groups).length > 0 ? (
                    Object.keys(groups).map(g => (
                        <optgroup key={g} label={g.replace(/_/g, ' ')}>
                            {groups[g].map((t) => (
                                <option key={t} value={t}>{t}</option>
                            ))}
                        </optgroup>
                    ))
                ) : (
                    /* Render Flat List if no groups */
                    tickers.map(t => (
                        <option key={t} value={t}>{t}</option>
                    ))
                )}
            </select>

            {/* Custom Arrow */}
            <div style={{
                position: 'absolute',
                right: '10px',
                top: '50%',
                transform: 'translateY(-50%)',
                pointerEvents: 'none'
            }}>
                <ArrowDownRight size={14} color="#64748b" />
            </div>
        </div>
    );
};

export default TrendTickerSelector;
