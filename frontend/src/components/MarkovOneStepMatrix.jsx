import React from 'react';

// Utility to map state codes to user-friendly names (Green/Red) and colors
const STATE_INFO_MAP = {
    'U': { name: 'Green', color: '#4caf50' },
    'N': { name: 'Neutral', color: '#9e9e9e' },
    'D': { name: 'Red', color: '#f44336' },
    'Green': { name: 'Green', color: '#4caf50' },
    'Neutral': { name: 'Neutral', color: '#9e9e9e' },
    'Red': { name: 'Red', color: '#f44336' },
};

// Utility to parse the value (which is a raw float from the API)
const parseRawValue = (value) => {
    return isNaN(value) ? 0.0 : value;
};

// Helper function to get the user-friendly header name
const getHeaderName = (key) => {
    const code = key.split('_').pop(); // 'up', 'neutral', 'down'
    // Handle 'up' -> 'Green', 'down' -> 'Red' mapping explicitly if needed, or just capitalize
    // Based on previous files, it seems 'Up' maps to 'Green' and 'Down' maps to 'Red' visually
    let name = code.charAt(0).toUpperCase() + code.slice(1);
    if (name === 'Up') name = 'Green';
    if (name === 'Down') name = 'Red';
    return `${name} Prob (%)`;
};


const MarkovOneStepMatrix = ({ markovData, settings, latestMarkovState }) => {
    if (!markovData || markovData.length === 0) {
        return <p style={{ color: '#9e9e9e', padding: '10px' }}>Matrix data required for One-Step analysis.</p>;
    }

    // 1. Identify Raw Probability Keys (Technical API Keys)
    // NOTE: This assumes the API returns raw float values (not percentages) for the matrix.
    const rawProbKeys = Object.keys(markovData[0]).filter(key => key.startsWith('mc_prob_'));

    // 2. Calculate Aggregated Probabilities (Average of all Contexts)
    let aggregatedProbs = {};
    const numContexts = markovData.length;

    rawProbKeys.forEach(key => {
        let sumProb = 0;
        markovData.forEach(row => {
            // Use the row value directly (as a float, assuming it was fixed in the API)
            const probValue = parseRawValue(row[key]);
            sumProb += probValue;
        });
        // Aggregation is the simple average of probabilities (0.0 to 1.0)
        aggregatedProbs[key] = sumProb / numContexts;
    });

    // 3. Generate Table Data
    const tableHeaders = rawProbKeys.map(getHeaderName);

    // Convert aggregated float results to display percentage (0.0 to 1.0 -> 0.00 to 100.00%)
    const tableRows = [{
        'P(next, %)': rawProbKeys.map(key => (aggregatedProbs[key] * 100).toFixed(2))
    }];

    // 4. Generate Conclusion (Based on aggregated probabilities - Find Max)
    let maxProb = 0;
    let nextStateName = '';

    rawProbKeys.forEach(key => {
        const prob = aggregatedProbs[key];
        if (prob > maxProb) {
            maxProb = prob;
            nextStateName = getHeaderName(key).split(' ')[0]; // e.g., 'Green'
        }
    });

    // Format the Conclusion using color-coded HTML
    // Get the current context code (e.g., 'U') and map it to a color/name
    const contextCode = latestMarkovState?.context ? latestMarkovState.context.charAt(0) : 'U';
    const contextInfo = STATE_INFO_MAP[contextCode] || { name: 'N/A', color: '#9e9e9e' };
    const nextStateInfo = STATE_INFO_MAP[nextStateName] || { name: nextStateName, color: '#d7e3f3' };

    const conclusionHtml = `
        <h4 style="margin: 0 0 5px 0; color: #9ec4ff; font-size: 1rem;">Conclusion</h4>
        <p style="font-size: 13px; margin: 0;">
            Given context is: 
            <span style="font-weight: bold; color: ${contextInfo.color};">
                ${contextInfo.name}
            </span>, 
            most likely next day is 
            <span style="font-weight: bold; color: ${nextStateInfo.color};">
                ${nextStateInfo.name}
            </span> 
            (${(maxProb * 100).toFixed(1)}%).
        </p>
    `;

    // 5. Final Render
    return (
        <div style={{ padding: '0 10px', marginTop: '20px' }}>
            <h3 style={{ fontSize: '1.2rem', color: '#9ec4ff', borderBottom: '1px solid #203049', paddingBottom: '5px' }}>
                One-Step Next-State Probabilities
            </h3>

            {/* Probability Table */}
            <div style={{ marginTop: '15px' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                    <thead>
                        <tr>
                            <th style={{ padding: '8px', textAlign: 'left', color: '#9ec4ff', borderBottom: '1px solid #203049', width: '150px' }}>Metric</th>
                            {tableHeaders.map(header => (
                                <th key={header} style={{ padding: '8px', textAlign: 'right', color: '#9ec4ff', borderBottom: '1px solid #203049' }}>{header}</th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td style={{ padding: '8px', textAlign: 'left', color: '#d7e3f3', borderBottom: '1px solid #203049' }}>P(next, %)</td>
                            {tableHeaders.map((header, i) => (
                                <td key={header} style={{ padding: '8px', textAlign: 'right', color: '#d7e3f3', borderBottom: '1px solid #203049' }}>
                                    {tableRows[0]['P(next, %)'][i]}%
                                </td>
                            ))}
                        </tr>
                    </tbody>
                </table>
            </div>

            {/* Conclusion Section */}
            <div dangerouslySetInnerHTML={{ __html: conclusionHtml }} style={{ marginTop: '20px', padding: '10px', backgroundColor: '#0e1525', borderRadius: '8px' }} />
        </div>
    );
};

export default MarkovOneStepMatrix;
