import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';

const API_BASE = "/api/v1/admin/data";

const AdminDataDashboard = () => {
    const { user, token } = useAuth();
    const [activeTab, setActiveTab] = useState('ohlc');
    const [ohlcData, setOhlcData] = useState([]);
    const [optionsData, setOptionsData] = useState([]);
    const [gexData, setGexData] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        fetchAllData();
    }, []);

    const fetchAllData = async () => {
        setLoading(true);
        try {
            const headers = {};
            if (token) {
                headers["Authorization"] = `Bearer ${token}`;
            }

            // Fetch OHLC
            const resOhlc = await fetch(`${API_BASE}/ohlc`, { headers });
            const jsonOhlc = await resOhlc.json();
            if (jsonOhlc.status === 'ok') setOhlcData(jsonOhlc.data);

            // Fetch Options
            const resOpt = await fetch(`${API_BASE}/options`, { headers });
            const jsonOpt = await resOpt.json();
            if (jsonOpt.status === 'ok') setOptionsData(jsonOpt.data);

            // Fetch GEX
            const resGex = await fetch(`${API_BASE}/gex`, { headers });
            const jsonGex = await resGex.json();
            if (jsonGex.status === 'ok') setGexData(jsonGex.data);

        } catch (err) {
            console.error("Failed to fetch admin data", err);
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const renderOhlcTable = () => (
        <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: '20px' }}>
            <thead>
                <tr style={{ borderBottom: '1px solid #444', textAlign: 'left' }}>
                    <th style={{ padding: '10px' }}>Ticker</th>
                    <th style={{ padding: '10px' }}>Rows</th>
                    <th style={{ padding: '10px' }}>Range</th>
                    <th style={{ padding: '10px' }}>Last Update (UTC)</th>
                    <th style={{ padding: '10px' }}>Source</th>
                    <th style={{ padding: '10px' }}>Features?</th>
                </tr>
            </thead>
            <tbody>
                {ohlcData.map((row) => (
                    <tr key={row.ticker} style={{ borderBottom: '1px solid #222' }}>
                        <td style={{ padding: '10px', fontWeight: 'bold', color: '#4caf50' }}>{row.ticker}</td>
                        <td style={{ padding: '10px' }}>{row.rows}</td>
                        <td style={{ padding: '10px' }}>{row.data_range.join(' → ')}</td>
                        <td style={{ padding: '10px' }}>{row.last_update ? new Date(row.last_update).toLocaleString() : '-'}</td>
                        <td style={{ padding: '10px' }}>
                            <span style={{
                                padding: '2px 6px',
                                borderRadius: '4px',
                                backgroundColor: row.source === 'polygon' ? '#2e7d32' : (row.source === 'yfinance' ? '#f57c00' : '#444'),
                                fontSize: '0.8rem'
                            }}>
                                {row.source}
                            </span>
                        </td>
                        <td style={{ padding: '10px', color: row.has_features ? '#4caf50' : '#f44336' }}>
                            {row.has_features ? '✅' : '❌'}
                        </td>
                    </tr>
                ))}
            </tbody>
        </table>
    );

    const renderOptionsTable = () => (
        <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: '20px' }}>
            <thead>
                <tr style={{ borderBottom: '1px solid #444', textAlign: 'left' }}>
                    <th style={{ padding: '10px' }}>Ticker</th>
                    <th style={{ padding: '10px' }}>History File</th>
                    <th style={{ padding: '10px' }}>Last Validated (UTC)</th>
                    <th style={{ padding: '10px' }}>In Latest JSON?</th>
                </tr>
            </thead>
            <tbody>
                {optionsData.map((row) => (
                    <tr key={row.ticker} style={{ borderBottom: '1px solid #222' }}>
                        <td style={{ padding: '10px', fontWeight: 'bold', color: '#2196f3' }}>{row.ticker}</td>
                        <td style={{ padding: '10px' }}>{row.has_em_history ? '✅' : '❌'}</td>
                        <td style={{ padding: '10px' }}>{row.history_last_mod ? new Date(row.history_last_mod).toLocaleString() : '-'}</td>
                        <td style={{ padding: '10px', color: row.in_latest_json ? '#4caf50' : '#f44336' }}>
                            {row.in_latest_json ? 'Active' : 'Missing'}
                        </td>
                    </tr>
                ))}
            </tbody>
        </table>
    );

    const renderGexTable = () => (
        <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: '20px' }}>
            <thead>
                <tr style={{ borderBottom: '1px solid #444', textAlign: 'left' }}>
                    <th style={{ padding: '10px' }}>Ticker</th>
                    <th style={{ padding: '10px' }}>Timestamp (UTC)</th>
                    <th style={{ padding: '10px' }}>Spot Price</th>
                    <th style={{ padding: '10px' }}>Algo</th>
                    <th style={{ padding: '10px' }}>Profile?</th>
                </tr>
            </thead>
            <tbody>
                {gexData.map((row) => (
                    <tr key={row.ticker} style={{ borderBottom: '1px solid #222' }}>
                        <td style={{ padding: '10px', fontWeight: 'bold', color: '#9c27b0' }}>{row.ticker}</td>
                        <td style={{ padding: '10px' }}>{row.timestamp ? new Date(row.timestamp).toLocaleString() : '-'}</td>
                        <td style={{ padding: '10px' }}>{row.spot_price}</td>
                        <td style={{ padding: '10px' }}>{row.algo}</td>
                        <td style={{ padding: '10px' }}>{row.has_profile ? '✅' : '❌'}</td>
                    </tr>
                ))}
            </tbody>
        </table>
    );

    return (
        <div style={{ padding: '20px', color: '#d7e3f3', minHeight: '100vh', backgroundColor: '#0b1220' }}>
            <h1>Admin Data Dashboard</h1>
            <p style={{ color: '#888' }}>System Data Status Overview</p>

            {/* TABS */}
            <div style={{ display: 'flex', gap: '10px', borderBottom: '1px solid #444', paddingBottom: '10px' }}>
                <button
                    onClick={() => setActiveTab('ohlc')}
                    style={{
                        background: activeTab === 'ohlc' ? '#4caf50' : '#222',
                        color: 'white', border: 'none', padding: '10px 20px', cursor: 'pointer', borderRadius: '4px'
                    }}>
                    OHLC & Features
                </button>
                <button
                    onClick={() => setActiveTab('options')}
                    style={{
                        background: activeTab === 'options' ? '#2196f3' : '#222',
                        color: 'white', border: 'none', padding: '10px 20px', cursor: 'pointer', borderRadius: '4px'
                    }}>
                    Options & EM
                </button>
                <button
                    onClick={() => setActiveTab('gex')}
                    style={{
                        background: activeTab === 'gex' ? '#9c27b0' : '#222',
                        color: 'white', border: 'none', padding: '10px 20px', cursor: 'pointer', borderRadius: '4px'
                    }}>
                    Gamma Exposure (GEX)
                </button>
                <button
                    onClick={fetchAllData}
                    style={{
                        background: '#444',
                        marginLeft: 'auto',
                        color: 'white', border: 'none', padding: '10px 20px', cursor: 'pointer', borderRadius: '4px'
                    }}>
                    🔄 Refresh
                </button>
            </div>

            {loading && <p>Loading data...</p>}
            {error && <p style={{ color: '#f44336' }}>Error: {error}</p>}

            {!loading && !error && (
                <div>
                    {activeTab === 'ohlc' && renderOhlcTable()}
                    {activeTab === 'options' && renderOptionsTable()}
                    {activeTab === 'gex' && renderGexTable()}
                </div>
            )}
        </div>
    );
};

export default AdminDataDashboard;
