import React, { useState, useEffect } from 'react';
import Plot from 'react-plotly.js';
import PriceViewerSettings from '../components/PriceViewerSettings';

// Component to render the Candlestick and Volume Chart
const CandlestickChart = ({ data, settings }) => {
    if (!data || data.length === 0) return null;

    // Sort data ascending for charting
    const chartData = [...data].reverse();
    const dates = chartData.map(d => d.Date);

    // Candle colors: White/Light Gray for up, Dark Gray for down (matching traditional style)
    const candleTrace = {
        x: dates,
        open: chartData.map(d => parseFloat(d.Open)),
        high: chartData.map(d => parseFloat(d.High)),
        low: chartData.map(d => parseFloat(d.Low)),
        close: chartData.map(d => parseFloat(d.Close)),
        type: 'candlestick',
        xaxis: 'x',
        yaxis: 'y',
        name: settings.ticker,
        increasing: { line: { color: '#d7e3f3', width: 1 }, fillcolor: '#d7e3f3' }, // White/Light Gray for up
        decreasing: { line: { color: '#9e9e9e', width: 1 }, fillcolor: '#0b1220' }  // Dark Gray/Black for down
    };

    // Volume colors: Green for up day, Red for down day
    const volumeTrace = {
        x: dates,
        y: chartData.map(d => d.Volume),
        type: 'bar',
        xaxis: 'x',
        yaxis: 'y2', // Secondary Y-axis for Volume
        name: 'Volume',
        marker: {
            // Match candlestick colors: Light Gray for up, Dark Gray for down
            color: chartData.map(d => parseFloat(d['Daily Change (%)'].replace('%', '')) > 0 ? '#d7e3f3' : '#9e9e9e'),
            opacity: 0.5
        },
    };

    const layout = {
        title: { text: `OHLC & Volume: ${settings.ticker}`, font: { color: '#d7e3f3', size: 16 } },
        height: 500,
        autosize: true,
        margin: { t: 50, b: 50, l: 50, r: 20 },
        plot_bgcolor: '#0e1525',
        paper_bgcolor: '#0b1220',
        font: { color: '#d7e3f3' },
        xaxis: {
            rangeslider: { visible: false },
            type: 'date',
            domain: [0, 1],
            gridcolor: '#203049',
            rangebreaks: [
                { bounds: ["sat", "mon"] } // Hide weekends
            ]
        },
        yaxis: { title: 'Price (USD)', domain: [0.3, 1], gridcolor: '#203049' }, // Main Price Axis
        yaxis2: { title: 'Volume', domain: [0, 0.25], showgrid: false, gridcolor: '#203049' }, // Volume Axis
        legend: { orientation: 'h', y: 1.05, x: 0.1, bgcolor: 'rgba(0,0,0,0)' }
    };

    return (
        <div style={{ marginTop: '20px', border: '1px solid #203049', borderRadius: '8px', overflow: 'hidden' }}>
            <Plot
                data={[candleTrace, volumeTrace]}
                layout={layout}
                config={{ responsive: true, displayModeBar: true, scrollZoom: true }}
                style={{ width: '100%', height: '100%' }}
            />
        </div>
    );
};

const formatPrice = (value) => {
    if (value === null || value === undefined) return 'N/A';
    // Ensures prices are displayed as dollars and cents (2 decimal places)
    return parseFloat(value).toFixed(2);
};

// Utility component to render the styled data table
const StyledDataTable = ({ data }) => {
    // Define styles for color coding
    const getChangeColor = (value) => {
        if (!value || value === "") return '#d7e3f3';
        const num = parseFloat(value.replace('%', ''));
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

const PriceReturnsViewerPage = ({ settings, onSettingsChange, data, loading, error, freshnessStatus }) => {
    usePageTitle(`Price Analysis: ${settings.ticker}`);
    const summaryText = `Ticker: ${settings.ticker} • Mode: ${settings.stateMode} • Threshold: ${settings.thresholdBPS} BPS (${(settings.thresholdBPS / 100).toFixed(2)}%) • Rows: ${settings.rows}`;

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

                    <p style={{ fontSize: '14px', color: '#9ec4ff' }}>Records: {data ? data.length : 'N/A'}</p>
                    <p style={{ fontSize: '13px', color: error ? '#f44336' : 'inherit' }}>{error ? `API Error: ${error}` : ''}</p>
                </div>
            </div>

            {/* Right Panel: Data Viewer */}
            <div style={{ flexGrow: 1, padding: '0 10px', textAlign: 'left', minWidth: 0 }}>
                <h2 style={{ fontSize: '1.5rem', marginBottom: '0' }}>Price & Daily Returns Viewer: {settings.ticker}</h2>
                <p style={{ color: '#9e9e9e', fontSize: '0.85rem', borderBottom: '1px solid #203049', paddingBottom: '10px', marginBottom: '20px' }}>
                    {summaryText}
                </p>

                {loading ? <p>Loading chart data...</p> : <CandlestickChart data={data} settings={settings} />}

                <h3 style={{ fontSize: '1.2rem', marginTop: '30px', marginBottom: '10px', color: '#9ec4ff' }}>Recent Price Data Table</h3>
                {loading ? <p>Loading table data...</p> : <StyledDataTable data={data} />}
            </div>
        </div>
    );
};

export default PriceReturnsViewerPage;
