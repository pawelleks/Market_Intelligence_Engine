import React, { useState, useEffect } from 'react';
import TradingViewCandleChart from '../components/TradingViewCandleChart';
import PriceViewerSettings from '../components/PriceViewerSettings';

const formatPrice = (value) => {
    if (value === null || value === undefined) return 'N/A';
    // Ensures prices are displayed as dollars and cents (2 decimal places)
    return parseFloat(value).toFixed(2);
};

// Utility component to render the styled data table
const StyledDataTable = ({ data }) => {
    // Define styles for color coding
    const getChangeColor = (value) => {
        if (value === null || value === undefined) return '#d7e3f3';
        const strVal = String(value);
        if (strVal === "") return '#d7e3f3';
        const num = parseFloat(strVal.replace('%', ''));
        if (num > 0) return '#4caf50'; // Green
        if (num < 0) return '#f44336'; // Red
        return '#d7e3f3';
    };

    const getStateColor = (state) => {
        if (state === 'Green') return '#4caf50'; // Green
        if (state === 'Red') return '#f44336'; // Red
        if (state === 'Neutral') return '#9e9e9e'; // Gray/Neutral
        return '#d7e3f3';
    };

    const getRowClass = (state) => {
        // Row background remains subtle
        if (state === 'Green') return { backgroundColor: 'rgba(76, 175, 80, 0.1)' };
        if (state === 'Red') return { backgroundColor: 'rgba(244, 67, 54, 0.1)' };
        return {};
    };

    const tableStyle = { width: '100%', borderCollapse: 'collapse', fontSize: '13px' };
    const headerStyle = { padding: '10px 8px', textAlign: 'right', borderBottom: '1px solid #203049', color: '#9ec4ff', fontSize: '11px', textTransform: 'uppercase' };
    const cellStyle = { padding: '8px', borderBottom: '1px solid #203049', color: '#d7e3f3', textAlign: 'right' };
    const dateCellStyle = { ...cellStyle, textAlign: 'left', width: '150px' };

    if (!data || data.length === 0) return <p style={{ color: '#9e9e9e', padding: '20px' }}>No price data available. Check CLI data pipeline.</p>;

    const headers = Object.keys(data[0]);
    // Manually insert Volume after Close for correct ordering in the table display
    const closeIndex = headers.indexOf('Close');
    if (closeIndex !== -1 && headers.indexOf('Volume') === -1) {
        headers.splice(closeIndex + 1, 0, 'Volume');
    }

    return (
        <div style={{ overflowX: 'auto', border: '1px solid #203049', borderRadius: '8px', marginTop: '20px' }}>
            <table style={tableStyle}>
                <thead>
                    <tr>
                        {headers.map(header => (
                            <th key={header} style={{ ...headerStyle, textAlign: (header === 'Date' || header === 'State') ? 'left' : 'right' }}>{header}</th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    {data.map((row, index) => (
                        <tr key={index} style={getRowClass(row.State)}>
                            {headers.map(header => (
                                <td
                                    key={header}
                                    style={{
                                        ...(header === 'Date' ? dateCellStyle : cellStyle),
                                        // Color logic: Green/Red for Change %, and Green/Red/Neutral for State
                                        color: header === 'Daily Change (%)' ? getChangeColor(row[header]) :
                                            (header === 'State' ? getStateColor(row[header]) : cellStyle.color),
                                        fontWeight: header === 'Daily Change (%)' ? 'bold' : 'normal'
                                    }}
                                >
                                    {/* Apply rounding to OHLC columns */}
                                    {(header === 'Open' || header === 'High' || header === 'Low' || header === 'Close') ? formatPrice(row[header]) : row[header]}
                                </td>
                            ))}
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
};


// --- Main Page Component ---
import { usePageTitle } from '../hooks/usePageTitle';

// Error Boundary Component
class ErrorBoundary extends React.Component {
    constructor(props) {
        super(props);
        this.state = { hasError: false, error: null, errorInfo: null };
    }

    static getDerivedStateFromError(error) {
        return { hasError: true, error };
    }

    componentDidCatch(error, errorInfo) {
        console.error("PriceViewer Error:", error, errorInfo);
        this.state.errorInfo = errorInfo;
    }

    render() {
        if (this.state.hasError) {
            return (
                <div style={{ padding: '20px', color: '#f44336', backgroundColor: '#0e1525', minHeight: '100vh' }}>
                    <h2>Something went wrong in Price Viewer.</h2>
                    <pre style={{ whiteSpace: 'pre-wrap', backgroundColor: '#000', padding: '10px' }}>
                        {this.state.error && this.state.error.toString()}
                        <br />
                        {this.state.errorInfo && this.state.errorInfo.componentStack}
                    </pre>
                </div>
            );
        }
        return this.props.children;
    }
}

const PriceReturnsViewerPage = ({ settings, onSettingsChange, data, loading, error, freshnessStatus }) => {
    usePageTitle(`Price Analysis: ${settings.ticker}`);

    return (
        <ErrorBoundary>
            <PriceReturnsViewerPageContent
                settings={settings}
                onSettingsChange={onSettingsChange}
                data={data}
                loading={loading}
                error={error}
                freshnessStatus={freshnessStatus}
            />
        </ErrorBoundary>
    );
};

const PriceReturnsViewerPageContent = ({ settings, onSettingsChange, data, loading, error, freshnessStatus }) => {
    const summaryText = `Ticker: ${settings.ticker} • Mode: ${settings.stateMode} • Threshold: ${settings.thresholdBPS} BPS (${(settings.thresholdBPS / 100).toFixed(2)}%) • Table Rows: ${settings.rows}`;

    // Extract chart and table data from the new API structure
    const chartData = data?.chartData || [];
    const tableData = data?.tableData || [];

    return (
        <div style={{ display: 'flex', gap: '20px', padding: '20px', minHeight: '100vh', width: '100%' }}>

            {/* Left Panel: Configuration (Sticky) */}
            <div style={{
                width: '270px',
                flexShrink: 0,
                position: 'sticky',
                top: '20px',
                maxHeight: 'calc(100vh - 40px)',
                overflowY: 'auto'
            }}>
                <PriceViewerSettings settings={settings} onSettingsChange={onSettingsChange} />

                {/* Data Status/Debug */}
                <div style={{ padding: '15px', border: '1px solid #203049', borderRadius: '8px', marginTop: '20px', backgroundColor: '#0e1525' }}>
                    <h3 style={{ color: '#4caf50', paddingTop: '0' }}>Data Status</h3>
                    <p style={{ fontSize: '13px' }}>Proxy Status: Active</p>

                    {/* NEW FRESHNESS DISPLAY */}
                    {freshnessStatus && (
                        <p style={{ fontSize: '14px', color: freshnessStatus.is_fresh ? '#4caf50' : '#f44336', fontWeight: 'bold' }}>
                            Data: {freshnessStatus.ticker} last OHLC day {freshnessStatus.last_date}.
                        </p>
                    )}
                    {freshnessStatus && (
                        <p style={{ fontSize: '13px', color: freshnessStatus.is_fresh ? '#4caf50' : '#f44336' }}>
                            {freshnessStatus.status_text}
                        </p>
                    )}
                    {/* END NEW FRESHNESS DISPLAY */}

                    <p style={{ fontSize: '14px', color: '#9ec4ff' }}>Chart Records: {chartData.length}</p>
                    <p style={{ fontSize: '14px', color: '#9ec4ff' }}>Table Records: {tableData.length}</p>
                    <p style={{ fontSize: '13px', color: error ? '#f44336' : 'inherit' }}>{error ? `API Error: ${error}` : ''}</p>
                </div>
            </div>

            {/* Right Panel: Data Viewer */}
            <div style={{ flexGrow: 1, padding: '0 10px', textAlign: 'left', minWidth: 0 }}>
                <h2 style={{ fontSize: '1.5rem', marginBottom: '0' }}>Price & Daily Returns Viewer: {settings.ticker}</h2>
                <p style={{ color: '#9e9e9e', fontSize: '0.85rem', borderBottom: '1px solid #203049', paddingBottom: '10px', marginBottom: '20px' }}>
                    {summaryText}
                </p>

                {loading ? <p>Loading chart data...</p> : <TradingViewCandleChart data={chartData} />}

                <h3 style={{ fontSize: '1.2rem', marginTop: '30px', marginBottom: '10px', color: '#9ec4ff' }}>Recent Price Data Table</h3>
                {loading ? <p>Loading table data...</p> : <StyledDataTable data={tableData} />}
            </div>
        </div>
    );
};

export default PriceReturnsViewerPage;
