import React from 'react';

// Utility to map state codes to user-friendly names (Green/Red) and colors
const STATE_INFO_MAP = {
    'U': { name: 'Green', color: '#4caf50' },
    'N': { name: 'Neutral', color: '#9e9e9e' },
    'D': { name: 'Red', color: '#f44336' },
    'G': { name: 'Green', color: '#4caf50' }, // For Order > 1 context visualization
    'R': { name: 'Red', color: '#f44336' },
};

// Helper function to find the maximum probability and its state name in a row
const getPredictionDetails = (contextRow, settings) => {
    let maxProb = 0;
    let nextStateName = '';
    let continuationProb = 0;

    // Determine the continuation state name (e.g., 'Green' if the context ends in 'G')
    // Raw data context is like 'U' or 'U-D'.
    const contextCode = settings.markovOrder === 1 ? contextRow.context : contextRow.context.split('-').pop();
    // Map raw code (U/N/D) to display name (Green/Neutral/Red)
    const continuationState = STATE_INFO_MAP[contextCode] ? STATE_INFO_MAP[contextCode].name : '';

    // Construct the key for continuation probability in the raw data (e.g., mc_prob_up)
    // We need to map 'Green' -> 'mc_prob_up', 'Red' -> 'mc_prob_down'
    const nameToKeyMap = {
        'Green': 'mc_prob_up',
        'Neutral': 'mc_prob_neutral',
        'Red': 'mc_prob_down'
    };
    const continuationKey = nameToKeyMap[continuationState];

    // Filter keys that start with 'mc_prob_'
    const probKeys = Object.keys(contextRow).filter(key => key.startsWith('mc_prob_'));

    probKeys.forEach(key => {
        // Extract probability value (raw float)
        const prob = contextRow[key];

        // Map key 'mc_prob_up' -> 'Green'
        const rawState = key.split('_')[2]; // up, neutral, down
        const stateCodeMap = { 'up': 'U', 'neutral': 'N', 'down': 'D' };
        const stateName = STATE_INFO_MAP[stateCodeMap[rawState]].name;

        if (prob > maxProb) {
            maxProb = prob;
            nextStateName = stateName;
        }

        // Check if this is the continuation probability
        if (key === continuationKey) {
            continuationProb = prob;
        }
    });

    return {
        maxProb,
        nextStateName,
        continuationProb,
        continuationStateName: continuationState,
    };
};

const MarkovConclusion = ({ markovData, settings, latestMarkovState }) => {
    // NOTE: We prefer the calculated latestMarkovState from recent price data
    // because the matrix file might be slightly stale or the last row might not represent "today".

    if (!markovData || markovData.length === 0) {
        return null;
    }

    let contextRow = null;
    if (latestMarkovState) {
        // Find row matching current calculated state
        contextRow = markovData.find(d => d.context === latestMarkovState);
    }

    // Fallback: Use last row (old behavior) if state calculation failed
    if (!contextRow) {
        contextRow = markovData[markovData.length - 1];
    }

    if (!contextRow) {
        return <p style={{ fontSize: '13px', color: '#9e9e9e', paddingTop: '10px' }}>Current context data unavailable.</p>;
    }

    // Use the found row
    const lastContextRow = contextRow;

    const { maxProb, nextStateName, continuationProb, continuationStateName } = getPredictionDetails(lastContextRow, settings);

    // Calculate final probability values
    const switchProb = 1.0 - continuationProb;

    // Helper function to format state names with color coding
    const formatState = (code) => {
        const info = STATE_INFO_MAP[code.charAt(0)] || { name: code, color: '#d7e3f3' };
        return `<span style="color: ${info.color || '#d7e3f3'}; font-weight: bold;">${info.name}</span>`;
    };

    // Construct Context HTML based on order
    let contextHtml;
    if (settings.markovOrder === 1) {
        // Order 1: Context is just the state name (e.g., 'Red')
        contextHtml = formatState(lastContextRow.context);
    } else {
        // Order > 1: Context is a sequence (e.g., 'R-G-N')
        const rawContext = lastContextRow.context;
        contextHtml = rawContext.split('-').map(formatState).join('-');
    }

    return (
        <div style={{
            marginTop: '15px',
            padding: '15px',
            backgroundColor: '#0e1525',
            borderRadius: '8px',
            border: '1px solid #203049'
        }}>
            <h4 style={{ margin: '0 0 10px 0', color: '#9ec4ff', fontSize: '1rem' }}>Conclusion</h4>
            <p style={{ fontSize: '14px', margin: '0' }} dangerouslySetInnerHTML={{
                __html: `
                Given context is: ${contextHtml}, most likely next day is ${formatState(nextStateName)} (${(maxProb * 100).toFixed(1)}%).
            `}} />
            <p style={{ fontSize: '13px', margin: '5px 0 0 0', color: '#d7e3f3' }} dangerouslySetInnerHTML={{
                __html: `
                Continuation (stay ${formatState(continuationStateName)}) = ${(continuationProb * 100).toFixed(1)}%; Switch = ${(switchProb * 100).toFixed(1)}%.
            `}} />
        </div>
    );
};

export default MarkovConclusion;
