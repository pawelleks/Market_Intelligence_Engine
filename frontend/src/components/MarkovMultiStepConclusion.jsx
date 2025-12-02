import React from 'react';

// Utility to map state codes to user-friendly names (Green/Red) and colors
const STATE_INFO_MAP = {
    'Green': { name: 'Green', color: '#4caf50' },
    'Neutral': { name: 'Neutral', color: '#9e9e9e' },
    'Red': { name: 'Red', color: '#f44336' },
};

// Helper function to format percentages
const fmtPct = (value) => (value * 100).toFixed(1) + '%';
const fmtPctDec = (value) => (value * 100).toFixed(2);


const MarkovMultiStepConclusion = ({ forecastData }) => {
    if (!forecastData || forecastData.length < 2) {
        return <p style={{ fontSize: '13px', color: '#9e9e9e' }}>Insufficient data to analyze multi-step trend (requires at least 2 horizons).</p>;
    }

    // 1. Prepare Data for Analysis
    const horizons = forecastData.map(d => d.horizon);

    // Determine keys based on data format (raw API data vs formatted table data)
    let probKeys;
    let isRawData = false;

    if (Object.keys(forecastData[0]).some(k => k.startsWith('mc_prob_'))) {
        // Raw API Data (mc_prob_up, mc_prob_down, etc.)
        probKeys = Object.keys(forecastData[0]).filter(key => key.startsWith('mc_prob_'));
        isRawData = true;
    } else {
        // Formatted Table Data (Green Prob (%), etc.)
        probKeys = Object.keys(forecastData[0]).filter(key => key.includes('Prob (%)'));
    }

    // Map raw keys to standard keys for internal logic
    const keyMap = {
        'mc_prob_up': 'Green',
        'mc_prob_neutral': 'Neutral',
        'mc_prob_down': 'Red',
        'Green Prob (%)': 'Green',
        'Neutral Prob (%)': 'Neutral',
        'Red Prob (%)': 'Red'
    };

    // Convert data to decimals for math
    const dataDecimals = forecastData.map(d => {
        const obj = {};
        probKeys.forEach(key => {
            const standardKey = keyMap[key]; // Green, Neutral, Red
            if (isRawData) {
                obj[standardKey] = d[key]; // Already a float
            } else {
                obj[standardKey] = parseFloat(d[key].replace('%', '')) / 100;
            }
        });
        return obj;
    });

    const hasNeutral = probKeys.some(key => keyMap[key] === 'Neutral');

    // 2. Calculate Averages and Bias
    let sumGreen = 0, sumRed = 0;
    let greenFavoredCount = 0;
    let redFavoredCount = 0;
    const totalHorizons = dataDecimals.length;

    dataDecimals.forEach(d => {
        sumGreen += d.Green || 0;
        sumRed += d.Red || 0;

        if ((d.Green || 0) > (d.Red || 0)) {
            greenFavoredCount++;
        } else if ((d.Red || 0) > (d.Green || 0)) {
            redFavoredCount++;
        }
    });

    const avgGreen = sumGreen / totalHorizons;
    const avgRed = sumRed / totalHorizons;

    // Calculate neutral average if it exists
    let avgNeutral = 0;
    if (hasNeutral) {
        const sumNeutral = dataDecimals.reduce((acc, d) => acc + (d.Neutral || 0), 0);
        avgNeutral = sumNeutral / totalHorizons;
    }

    // Determine overall bias
    let biasText, biasColor;
    if (avgGreen > avgRed && avgGreen > avgNeutral) {
        biasText = 'bullish';
        biasColor = STATE_INFO_MAP.Green.color;
    } else if (avgRed > avgGreen && avgRed > avgNeutral) {
        biasText = 'bearish';
        biasColor = STATE_INFO_MAP.Red.color;
    } else {
        biasText = 'neutral';
        biasColor = STATE_INFO_MAP.Neutral.color;
    }

    // 3. Calculate Trend/Drift
    const startGreenProb = dataDecimals[0].Green;
    const endGreenProb = dataDecimals[totalHorizons - 1].Green;

    let driftText;
    if (endGreenProb > startGreenProb) {
        driftText = 'rises';
    } else if (endGreenProb < startGreenProb) {
        driftText = 'declines';
    } else {
        driftText = 'stays flat';
    }

    // 4. Construct Final HTML Output
    const htmlOutput = `
        <h4 style="margin: 0 0 8px 0; color: #9ec4ff; font-size: 1rem;">Conclusion: Multi-Step Forecast</h4>
        <p style="font-size: 14px; margin: 5px 0;">
            <span style="color: ${biasColor}; font-weight: bold;">Overall ${biasText} bias</span> 
            (${STATE_INFO_MAP.Red.name} ≈ ${fmtPctDec(avgRed)}% vs. ${STATE_INFO_MAP.Green.name} ≈ ${fmtPctDec(avgGreen)}%).
        </p>
        <p style="font-size: 13px; margin: 5px 0; color: #d7e3f3;">
            ${STATE_INFO_MAP.Green.name} probability ${driftText} from 
            <span style="font-weight: bold;">${fmtPct(startGreenProb)}</span> to 
            <span style="font-weight: bold;">${fmtPct(endGreenProb)}</span> over ${horizons[0]}→${horizons[totalHorizons - 1]} days.
        </p>
        <p style="font-size: 13px; margin: 5px 0; color: #d7e3f3;">
            <span style="color: ${STATE_INFO_MAP.Green.color};">Green</span> favored in 
            <span style="font-weight: bold;">${greenFavoredCount}/${totalHorizons}</span> horizons, 
            <span style="color: ${STATE_INFO_MAP.Red.color};">Red</span> favored in 
            <span style="font-weight: bold;">${redFavoredCount}/${totalHorizons}</span>.
        </p>
    `;

    return (
        <div style={{ padding: '15px', backgroundColor: '#0e1525', borderRadius: '8px', border: '1px solid #203049', marginTop: '20px' }}
            dangerouslySetInnerHTML={{ __html: htmlOutput }}
        />
    );
};

export default MarkovMultiStepConclusion;
