import React, { useState, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { format } from 'date-fns';
import { FaCheckCircle, FaTimesCircle } from 'react-icons/fa';

// Define API URL
const API_BASE = "/api/v1";
const ANALYSIS_KEY = "Minervini_Template";

const checkLabels = {
    P_GT_MA: "1. Current Price > 150-day SMA AND Price > 200-day SMA",
    MA_150_GT_200: "2. 150-day SMA > 200-day SMA",
    MA_200_RISING: "3. 200-day SMA is trending up",
    MA_50_GT_LONG: "4. 50-day SMA > 150-day SMA AND 50-day SMA > 200-day SMA",
    P_GT_MA_50: "5. Current Price > 50-day SMA",
    CLOSE_TO_HIGH: "6. Current Price is within 25% of 52-week High",
    FAR_FROM_LOW: "7. Current Price is at least 30% above 52-week Low",
};

const ChecklistItem = ({ checkKey, status }) => {
    const isPassing = status === true;
    const color = isPassing ? '#4caf50' : '#f44336';
    const Icon = isPassing ? FaCheckCircle : FaTimesCircle;

    return (
        <li style={{ display: 'flex', alignItems: 'center', marginBottom: '10px', fontSize: '15px' }}>
            <Icon style={{ color: color, marginRight: '10px' }} />
            <span>{checkLabels[checkKey]}</span>
        </li>
    );
};

const MinerviniPage = ({ settings, priceData, loading, error, onSettingsChange }) => {
    const [templateResults, setTemplateResults] = useState(null);
    const [templateLoading, setTemplateLoading] = useState(false);
    const [templateError, setTemplateError] = useState(null);
    const [availableTickers, setAvailableTickers] = useState([]);
    const [loadingTickers, setLoadingTickers] = useState(true);

    const location = useLocation();

    const TEMPLATE_URL = `${API_BASE}/template/minervini/${settings.ticker}`;

    // Ticker Fetching Logic
    useEffect(() => {
        async function fetchTickers() {
            setLoadingTickers(true);
            try {
                const response = await fetch(`${API_BASE}/tickers/${ANALYSIS_KEY}`);
                const json = await response.json();
                if (response.ok) {
                    setAvailableTickers(json.tickers);
                    if (!settings.ticker || !json.tickers.includes(settings.ticker)) {
                        onSettingsChange({ ...settings, ticker: json.tickers[0] || 'SPY' });
                    }
                }
            } catch (error) {
                console.error("Failed to fetch available tickers:", error);
                setAvailableTickers(['SPY', 'QQQ']); // Fallback list
            } finally {
                setLoadingTickers(false);
            }
        }
        fetchTickers();
    }, [location.pathname]);

    // Main Template Run Logic
    const runCheck = async () => {
        setTemplateLoading(true);
        setTemplateError(null);
        setTemplateResults(null);

        try {
            const response = await fetch(TEMPLATE_URL);
            const json = await response.json();

            if (!response.ok) {
                throw new Error(json.detail || "Failed to run template check.");
            }
            setTemplateResults(json.results);

        } catch (err) {
            setTemplateError(err.message);
        } finally {
            setTemplateLoading(false);
        }
    };

    // Auto-run check on initial load (only if Ticker is set)
    useEffect(() => {
        if (settings.ticker) {
            runCheck();
        }
    }, [settings.ticker]);

    const checklistKeys = Object.keys(checkLabels);
    const results = templateResults?.data_status || {};
    const overallStatus = templateResults?.status || 'N/A';
    const totalPassed = templateResults?.total_passed || 0;
    const requiredPasses = templateResults?.required_passes || 6;
    const checkDate = templateResults?.check_date ? format(new Date(templateResults.check_date), 'MMMM d, yyyy') : 'N/A';
    const assetPrice = templateResults?.current_price ? `$${templateResults.current_price.toFixed(2)}` : 'N/A';
    const statusColor = overallStatus === 'PASS' ? '#4caf50' : '#f44336';


    return (
        <div style={{ display: 'flex', gap: '20px', padding: '20px', width: '100%' }}>

            {/* Left Panel: Configuration */}
            <div style={{ width: '300px', flexShrink: 0, textAlign: 'left', position: 'sticky', top: '20px', maxHeight: 'calc(100vh - 40px)', overflowY: 'auto' }}>
                <div style={{ padding: '10px', backgroundColor: '#0e1525', borderRadius: '8px', marginBottom: '25px', border: '1px solid #203049' }}>
                    <h4 style={{ color: '#9ec4ff', marginTop: '0', fontSize: '1.0rem', marginBottom: '10px', borderBottom: '1px solid #203049', paddingBottom: '5px' }}>
                        Trend Template Filters
                    </h4>

                    <div style={{ marginBottom: '15px' }}>
                        <label style={{ display: 'block', fontSize: '0.8rem', color: '#8899a6', marginBottom: '5px' }}>
                            Select Ticker
                        </label>
                        <select
                            value={settings.ticker}
                            onChange={(e) => onSettingsChange({ ...settings, ticker: e.target.value })}
                            disabled={loadingTickers}
                            style={{
                                width: '100%',
                                padding: '8px',
                                backgroundColor: '#162032',
                                color: '#fff',
                                border: '1px solid #2c3e50',
                                borderRadius: '4px',
                                fontSize: '0.9rem'
                            }}
                        >
                            {loadingTickers ? (
                                <option>Loading...</option>
                            ) : (
                                availableTickers.map(t => (
                                    <option key={t} value={t}>{t}</option>
                                ))
                            )}
                        </select>
                    </div>
                </div>
            </div>

            {/* Right Panel: Results */}
            <div style={{ flex: 1, backgroundColor: '#0e1525', borderRadius: '8px', padding: '20px', border: '1px solid #203049', minHeight: '400px' }}>
                <h2 style={{ marginTop: 0, borderBottom: '1px solid #2c3e50', paddingBottom: '15px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span>Minervini Trend Template: <span style={{ color: '#2196f3' }}>{settings.ticker}</span></span>
                    {templateResults && (
                        <span style={{
                            fontSize: '1rem',
                            padding: '5px 12px',
                            borderRadius: '15px',
                            backgroundColor: overallStatus === 'PASS' ? 'rgba(76, 175, 80, 0.2)' : 'rgba(244, 67, 54, 0.2)',
                            color: statusColor,
                            border: `1px solid ${statusColor}`
                        }}>
                            {overallStatus} ({totalPassed}/{checklistKeys.length})
                        </span>
                    )}
                </h2>

                {templateError && (
                    <div style={{ color: '#f44336', padding: '20px', textAlign: 'center', backgroundColor: 'rgba(244, 67, 54, 0.1)', borderRadius: '8px' }}>
                        Error: {templateError}
                    </div>
                )}

                {templateLoading && (
                    <div style={{ color: '#8899a6', padding: '40px', textAlign: 'center' }}>
                        Running technical checks...
                    </div>
                )}

                {!templateLoading && !templateError && !templateResults && (
                    <div style={{ color: '#8899a6', padding: '40px', textAlign: 'center' }}>
                        Select a ticker and run the analysis to see results.
                    </div>
                )}

                {!templateLoading && templateResults && (
                    <div>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '15px', marginBottom: '30px' }}>
                            <div style={{ backgroundColor: '#162032', padding: '15px', borderRadius: '6px' }}>
                                <div style={{ fontSize: '0.8rem', color: '#8899a6' }}>Check Date</div>
                                <div style={{ fontSize: '1.1rem', fontWeight: 'bold' }}>{checkDate}</div>
                            </div>
                            <div style={{ backgroundColor: '#162032', padding: '15px', borderRadius: '6px' }}>
                                <div style={{ fontSize: '0.8rem', color: '#8899a6' }}>Current Price</div>
                                <div style={{ fontSize: '1.1rem', fontWeight: 'bold' }}>{assetPrice}</div>
                            </div>
                        </div>

                        <h3 style={{ color: '#9ec4ff', marginBottom: '15px' }}>Technical Checklist</h3>
                        <ul style={{ listStyle: 'none', padding: 0 }}>
                            {checklistKeys.map(key => (
                                <ChecklistItem
                                    key={key}
                                    checkKey={key}
                                    status={results[key]}
                                />
                            ))}
                        </ul>

                        <div style={{ marginTop: '30px', padding: '15px', backgroundColor: '#162032', borderRadius: '6px', fontSize: '0.9rem', color: '#8899a6' }}>
                            <strong>Note:</strong> This template requires at least {requiredPasses} out of 7 technical criteria to pass. It is adapted for ETF trend following but applies to individual stocks as well.
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default MinerviniPage;
