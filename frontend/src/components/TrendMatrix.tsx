import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
    Search,
    Circle,
    Cloud,
    TrendingUp,
    TrendingDown,
    Construction,
    Activity,
    ArrowUpRight,
    ArrowDownRight
} from 'lucide-react';
import TrendTickerSelector from './TrendTickerSelector';

const TrendMatrix = () => {
    const [trendData, setTrendData] = useState<any[]>([]);
    const [groups, setGroups] = useState<any>(null); // { groups: { "Group Name": ["TICKER", ...] } }
    const [loading, setLoading] = useState(true);
    // Fetch Data
    useEffect(() => {
        const fetchData = async () => {
            try {
                // Parallel Fetch
                const [trendRes, groupsRes] = await Promise.all([
                    fetch("/api/v1/analytics/trend/summary-table"),
                    fetch("/api/v1/system/config/ticker-groups")
                ]);

                if (!trendRes.ok) throw new Error("Failed to fetch trend summary");
                if (!groupsRes.ok) throw new Error("Failed to fetch ticker groups");

                const trendJson = await trendRes.json();
                const groupsJson = await groupsRes.json();

                setTrendData(trendJson);
                setGroups(groupsJson.groups);
                setLoading(false);

            } catch (err) {
                console.error("Error loading trend dashboard:", err);
                setLoading(false);
            }
        };

        fetchData();
    }, []);

    // Sort Config
    const [sortConfig, setSortConfig] = useState<{ key: string | null, direction: 'asc' | 'desc' }>({ key: null, direction: 'desc' });

    // Filter
    const [searchTerm, setSearchTerm] = useState("");


    const sortData = (data: any[]) => {
        if (!sortConfig.key) return data;

        return [...data].sort((a, b) => {
            let aVal = a[sortConfig.key as string];
            let bVal = b[sortConfig.key as string];

            // Normalize
            if (sortConfig.key === 'pct_change' || sortConfig.key === 'price' || sortConfig.key === 'ema_age' || sortConfig.key === 'cloud_age') {
                aVal = Number(aVal || 0);
                bVal = Number(bVal || 0);
            }

            if (aVal < bVal) return sortConfig.direction === 'asc' ? -1 : 1;
            if (aVal > bVal) return sortConfig.direction === 'asc' ? 1 : -1;
            return 0;
        });
    };

    const handleSort = (key: string) => {
        let direction: 'asc' | 'desc' = 'desc';
        if (sortConfig.key === key && sortConfig.direction === 'desc') {
            direction = 'asc';
        }
        setSortConfig({ key, direction });
    };

    const getSortIcon = (key: string) => {
        if (sortConfig.key !== key) return null;
        return sortConfig.direction === 'asc' ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />;
    };

    const renderAgeBadge = (age: number, type: 'ema' | 'cloud') => {
        let color = '#94a3b8'; // default grey

        if (type === 'ema') {
            if (age <= 15) color = '#4ade80'; // Fresh
            else if (age > 200) color = '#facc15'; // Mature
            else color = '#94a3b8'; // Established
        } else {
            if (age <= 15) color = '#4ade80';
            else if (age > 200) color = '#facc15';
            else color = '#94a3b8';
        }

        return (
            <span style={{
                color: color,
                fontWeight: 'bold',
                fontSize: '0.85rem'
            }}>
                {age}d
            </span>
        );
    };
    const getScoreColor = (score: number) => {
        if (score === 4) return '#4caf50'; // Perfect
        if (score === 3) return '#81c784'; // Good
        if (score === 2) return '#ffb74d'; // Neutral/Warning
        if (score === 1) return '#e57373'; // Weak
        return '#ef5350'; // Bearish
    };

    if (loading) return <div style={{ color: '#d7e3f3', padding: '20px' }}>Loading Command Center...</div>;

    // --- DATA PROCESSING ---

    // 1. Create a map of Ticker -> TrendRow for easy lookup
    const trendMap: Record<string, any> = {};
    trendData.forEach(row => {
        trendMap[row.ticker] = row;
    });

    // 2. Build Display List (Grouped)
    // Structure: Array of { type: 'header' | 'row', data: ... }
    let displayRows: any[] = [];
    let processedTickers = new Set<string>();

    if (groups) {
        Object.keys(groups).forEach(groupName => {
            const tickersInGroup = groups[groupName];

            // Check if any ticker in this group matches search (or if search is empty)
            // If filtering, we only show groups that have matching tickers
            // Ensure inputs are strings and filter by search
            const matchingTickers = tickersInGroup
                .filter((t: any) => typeof t === 'string')
                .filter((t: string) => t.toLowerCase().includes(searchTerm.toLowerCase()));

            if (matchingTickers.length > 0) {
                // Add Header
                displayRows.push({
                    type: 'header',
                    title: groupName.replace(/_/g, ' '), // Clean name
                    count: matchingTickers.length
                });

                // Add Rows
                matchingTickers.forEach((ticker: string) => {
                    processedTickers.add(ticker);
                    const rowData = trendMap[ticker];

                    // If no data exists for a configured ticker, create a dummy placeholder OR skip?
                    // Better to show it with "N/A" to indicate missing data but configured intent
                    displayRows.push({
                        type: 'row',
                        ticker: ticker,
                        data: rowData || null
                    });
                });
            }
        });
    }

    // 3. Handle Ungrouped items (if they exist in data but not config)
    // Only if search allows
    const ungrouped = trendData.filter(row =>
        !processedTickers.has(row.ticker) &&
        row.ticker.toLowerCase().includes(searchTerm.toLowerCase())
    );

    if (ungrouped.length > 0) {
        displayRows.push({
            type: 'header',
            title: 'Ungrouped / Other',
            count: ungrouped.length
        });
        ungrouped.forEach(row => {
            displayRows.push({
                type: 'row',
                ticker: row.ticker,
                data: row
            });
        });
    }

    // --- STYLES ---
    const tableStyle = {
        width: '100%',
        borderCollapse: 'collapse' as const,
        fontSize: '0.85rem', // Compact Font
    };

    const headerCellStyle = {
        padding: '8px 12px',
        textAlign: 'center' as const,
        borderBottom: '1px solid #334155',
        color: '#94a3b8',
        fontWeight: '600',
        fontSize: '0.75rem',
        textTransform: 'uppercase' as const,
        letterSpacing: '0.05em'
    };

    // Group Header Style
    const groupRowStyle = {
        backgroundColor: '#1e293b',
        color: '#e2e8f0',
        fontWeight: 'bold',
        fontSize: '0.9rem',
        borderTop: '1px solid #334155',
        borderBottom: '1px solid #334155'
    };

    // Calculate Last Updated Date
    const lastDate = trendData.length > 0
        ? trendData.reduce((latest, row) => (row.date > latest ? row.date : latest), "")
        : "";

    return (
        <div style={{ padding: '20px', width: '100%', maxWidth: '1600px', margin: '0 auto', fontFamily: 'Inter, sans-serif' }}>

            {/* Page Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: '15px' }}>
                    <h2 style={{ fontSize: '1.5rem', color: '#e2e8f0', margin: 0, display: 'flex', alignItems: 'center', gap: '10px', fontWeight: 'bold' }}>
                        <Activity size={24} color="#4caf50" />
                        Trend Command Center
                    </h2>
                    {lastDate && (
                        <span style={{ color: '#64748b', fontSize: '0.9rem', fontWeight: '500' }}>
                            As of: <span style={{ color: '#94a3b8' }}>{lastDate}</span>
                        </span>
                    )}
                </div>

                <div style={{ position: 'relative' }}>
                    <TrendTickerSelector
                        value={searchTerm}
                        onChange={setSearchTerm}
                        groups={groups}
                        tickers={[]} // When groups are present, flat list is unused within optgroups logic in component
                        placeholder="All Tickers"
                    />
                </div>
            </div>

            {/* Main Table */}
            <div style={{
                border: '1px solid #334155',
                borderRadius: '6px',
                backgroundColor: '#0f172a',
                overflow: 'hidden'
            }}>
                <table style={tableStyle}>
                    <thead>
                        <tr style={{ backgroundColor: '#162032' }}>
                            <th style={{ ...headerCellStyle, textAlign: 'left' }}>Ticker</th>
                            <th style={headerCellStyle}>Total Score</th>
                            <th style={headerCellStyle}>Verdict</th>
                            <th style={headerCellStyle}>ADX Trend</th>
                            <th style={headerCellStyle}>PSAR</th>
                            <th style={headerCellStyle}>Ichimoku</th>
                            <th style={{ ...headerCellStyle, cursor: 'pointer' }} onClick={() => handleSort('cloud_age')}>
                                Cloud Age {getSortIcon('cloud_age')}
                            </th>
                            <th style={headerCellStyle}>EMA Stack</th>
                            <th style={{ ...headerCellStyle, cursor: 'pointer' }} onClick={() => handleSort('ema_age')}>
                                EMA Age {getSortIcon('ema_age')}
                            </th>
                            <th style={headerCellStyle}>Dow Theory</th>
                        </tr>
                    </thead>
                    <tbody>
                        {displayRows.map((row, idx) => {
                            // RENDER HEADER ROW
                            if (row.type === 'header') {
                                return (
                                    <tr key={`group-${idx}`} style={groupRowStyle}>
                                        <td colSpan={8} style={{ padding: '8px 12px' }}>
                                            {row.title} <span style={{ color: '#64748b', marginLeft: '5px', fontSize: '0.8rem' }}>({row.count})</span>
                                        </td>
                                    </tr>
                                );
                            }

                            // RENDER DATA ROW
                            const d = row.data;
                            if (!d) {
                                // Missing Data Placeholder
                                return (
                                    <tr key={row.ticker} style={{ borderBottom: '1px solid #1e293b' }}>
                                        <td style={{ padding: '8px 12px', color: '#64748b' }}>{row.ticker}</td>
                                        <td colSpan={7} style={{ padding: '8px 12px', color: '#64748b', fontStyle: 'italic', textAlign: 'center' }}>No Data Available</td>
                                    </tr>
                                );
                            }

                            // Active Row
                            return (
                                <tr key={row.ticker} style={{ borderBottom: '1px solid #1e293b', height: '40px' }} className="hover-row">
                                    {/* Ticker */}
                                    <td style={{ padding: '0 12px', color: '#e2e8f0', fontWeight: '600' }}>
                                        {d.ticker}
                                    </td>

                                    {/* Score Pill */}
                                    <td style={{ padding: '0 12px', textAlign: 'center' }}>
                                        <span style={{
                                            backgroundColor: getScoreColor(d.trend_score),
                                            color: '#0f172a',
                                            padding: '2px 10px',
                                            borderRadius: '999px',
                                            fontWeight: 'bold',
                                            fontSize: '0.75rem',
                                            display: 'inline-block',
                                            boxShadow: '0 1px 2px rgba(0,0,0,0.2)'
                                        }}>
                                            {d.trend_score} / 4
                                        </span>
                                    </td>

                                    {/* Text Status Summary (Inferred) */}
                                    <td style={{ padding: '0 12px', textAlign: 'center' }}>
                                        {d.trend_score === 4 ?
                                            <span style={{ color: '#4caf50', fontWeight: 'bold' }}>STRONG BULL</span> :
                                            d.trend_score === 0 ?
                                                <span style={{ color: '#ef5350', fontWeight: 'bold' }}>STRONG BEAR</span> :
                                                <span style={{ color: '#94a3b8' }}>Mixed / Neutral</span>
                                        }
                                    </td>



                                    {/* ADX Text */}
                                    <td style={{ padding: '0 12px', textAlign: 'center', fontSize: '0.75rem', fontWeight: 'bold' }}>
                                        <Link to={`/analysis/adx/${d.ticker}`} style={{ textDecoration: 'none', color: 'inherit', display: 'block' }}>
                                            {d.is_adx_strong_trend ?
                                                <span style={{ color: '#4caf50' }}>STRONG UP</span> :
                                                <span style={{ color: '#64748b' }}>NEUTRAL/BEAR</span>
                                            }
                                        </Link>
                                    </td>

                                    {/* PSAR */}
                                    <td style={{ padding: '0 12px', textAlign: 'center' }}>
                                        <Link to={`/analysis/psar/${d.ticker}`} style={{ textDecoration: 'none', color: 'inherit', display: 'block' }}>
                                            {d.is_psar_bullish ?
                                                <Circle size={14} fill="#4caf50" color="#4caf50" style={{ display: 'inline-block' }} /> :
                                                <Circle size={14} fill="#ef5350" color="#ef5350" style={{ display: 'inline-block' }} />
                                            }
                                        </Link>
                                    </td>

                                    {/* Ichimoku Icon */}
                                    <td style={{ padding: '0 12px', textAlign: 'center' }}>
                                        <Link to={`/investing/ichimoku/${d.ticker}`} style={{ textDecoration: 'none', color: 'inherit', display: 'block' }}>
                                            {(() => {
                                                // Green: Above Cloud + Green Cloud
                                                // Orange: Above Cloud + Red Cloud
                                                // Red: Below Cloud
                                                let color = '#ef5350';
                                                if (d.is_above_cloud) {
                                                    color = d.is_cloud_green ? '#4ade80' : '#facc15';
                                                }
                                                return <Cloud size={18} color={color} fill={color} fillOpacity={0.2} />;
                                            })()}
                                        </Link>
                                    </td>

                                    {/* Cloud Age */}
                                    <td style={{ padding: '0 12px', textAlign: 'center' }}>
                                        {renderAgeBadge(d.cloud_age, 'cloud')}
                                    </td>

                                    {/* EMA Stack */}
                                    <td style={{ padding: '0 12px', textAlign: 'center' }}>
                                        <Link to={`/analysis/ema-stack/${d.ticker}`} style={{ textDecoration: 'none', color: 'inherit', display: 'block' }}>
                                            {d.is_ema_stacked_up ?
                                                <Circle size={14} fill="#4caf50" color="#4caf50" style={{ display: 'inline-block' }} /> :
                                                <Circle size={14} fill="#ef5350" color="#ef5350" style={{ display: 'inline-block' }} />
                                            }
                                        </Link>
                                    </td>

                                    {/* EMA Age */}
                                    <td style={{ padding: '0 12px', textAlign: 'center' }}>
                                        {renderAgeBadge(d.ema_age, 'ema')}
                                    </td>

                                    {/* Dow Theory Placeholder */}
                                    <td style={{ padding: '0 12px', textAlign: 'center' }}>
                                        <div style={{
                                            display: 'inline-flex',
                                            alignItems: 'center',
                                            gap: '4px',
                                            backgroundColor: '#1e293b',
                                            padding: '2px 8px',
                                            borderRadius: '4px',
                                            fontSize: '0.7rem',
                                            color: '#94a3b8',
                                            border: '1px solid #334155'
                                        }}>
                                            <Construction size={10} />
                                            STAGING
                                        </div>
                                    </td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>

            <style>{`
                .hover-row:hover {
                    background-color: #1e293b !important;
                }
            `}</style>
        </div>
    );
};

export default TrendMatrix;
