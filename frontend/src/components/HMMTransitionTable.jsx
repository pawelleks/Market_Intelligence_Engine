import React from 'react';

const HMMTransitionTable = ({ metricsData, nStates, expectedDurations }) => {
    if (!metricsData || metricsData.length === 0) {
        return null;
    }

    // 1. Parse Transition Matrix from Metrics
    const matrix = Array(nStates).fill(0).map(() => Array(nStates).fill(0));

    // 2. Determine State Names dynamically from Mean Returns
    let stateNames = Array(nStates).fill('');
    const meanReturns = {};

    metricsData.forEach(item => {
        if (item.metric.startsWith('trans_')) {
            const parts = item.metric.split('_');
            const i = parseInt(parts[1]);
            const j = parseInt(parts[2]);
            if (!isNaN(i) && !isNaN(j) && i < nStates && j < nStates) {
                matrix[i][j] = item.value;
            }
        } else if (item.metric.match(/state_\d+_mean_ret/)) {
            const parts = item.metric.split('_');
            const i = parseInt(parts[1]);
            meanReturns[i] = item.value;
        }
    });

    // Sort indices by mean return to assign names
    const indices = Object.keys(meanReturns).map(Number).sort((a, b) => meanReturns[a] - meanReturns[b]);

    // Map sorted indices to names: Lowest -> Bear, Highest -> Bull
    if (indices.length === nStates) {
        // Create a map from Index -> Name
        const indexToName = {};
        indexToName[indices[0]] = 'Bear';
        indexToName[indices[indices.length - 1]] = 'Bull';
        if (nStates === 3) {
            indexToName[indices[1]] = 'Neutral';
        }

        // Fill stateNames array
        for (let i = 0; i < nStates; i++) {
            stateNames[i] = indexToName[i] || `State ${i}`;
        }
    } else {
        // Fallback if means not found
        if (nStates === 2) {
            stateNames = ['Bear', 'Bull'];
        } else {
            stateNames = ['Bear', 'Neutral', 'Bull'];
        }
    }

    // 3. Calculate Expected Duration or Use Provided
    let durationText = "";

    if (expectedDurations) {
        // Use backend provided durations (most accurate)
        // Sort by name for consistent display: Bear, Bull
        const sortedKeys = Object.keys(expectedDurations).sort();
        durationText = sortedKeys.map(name => `${name}: ~${Math.round(expectedDurations[name])} days`).join(', ');
    } else {
        // Fallback calculation
        const durations = stateNames.map((name, i) => {
            const p_ii = matrix[i][i];
            const days = 1 / (1 - p_ii);
            return { name, days: Math.round(days) };
        });
        durationText = durations.map(d => `${d.name}: ~${d.days} days`).join(', ');
    }

    const takeaway = `Regimes are persistent. Expected duration — ${durationText}.`;

    // 5. Render Table
    // We want to match the screenshot: "From -> To" | Bull | Bear
    // The screenshot shows Bull first. Let's reorder for display if needed.
    // If we want Bull first, we can just reverse the order of display.
    // Let's stick to the logical order (Bear -> Bull) or match the screenshot (Bull -> Bear).
    // Screenshot has Bull on top/left.
    // So let's use a display order.

    const displayOrder = nStates === 2 ? [1, 0] : [2, 1, 0]; // Bull, Bear OR Bull, Neutral, Bear
    const displayNames = displayOrder.map(i => stateNames[i]);

    return (
        <div style={{ marginTop: '20px', marginBottom: '20px' }}>
            <h4 style={{ margin: '0 0 15px 0', fontSize: '1.2rem', color: '#d7e3f3', fontWeight: 'bold' }}>
                HMM transition matrix (daily transition probabilities)
            </h4>

            <div style={{ overflowX: 'auto', border: '1px solid #203049', borderRadius: '8px' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px', backgroundColor: '#0e1525' }}>
                    <thead>
                        <tr>
                            <th style={{ padding: '10px 8px', textAlign: 'left', borderBottom: '1px solid #203049', color: '#9ec4ff', fontSize: '11px', textTransform: 'uppercase' }}>From &#8594; To</th>
                            {displayNames.map(name => (
                                <th key={name} style={{ padding: '10px 8px', textAlign: 'right', borderBottom: '1px solid #203049', color: '#9ec4ff', fontSize: '11px', textTransform: 'uppercase' }}>{name}</th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {displayOrder.map(rowIdx => (
                            <tr key={rowIdx}>
                                <td style={{ padding: '8px', borderBottom: '1px solid #203049', color: stateNames[rowIdx] === 'Bull' ? '#4caf50' : stateNames[rowIdx] === 'Bear' ? '#f44336' : '#9e9e9e', fontWeight: 'bold' }}>{stateNames[rowIdx]}</td>
                                {displayOrder.map(colIdx => (
                                    <td key={colIdx} style={{ padding: '8px', textAlign: 'right', borderBottom: '1px solid #203049', color: '#d7e3f3' }}>
                                        {(matrix[rowIdx][colIdx] * 100).toFixed(1)}%
                                    </td>
                                ))}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            <p style={{ marginTop: '15px', fontSize: '0.9rem', color: '#d7e3f3' }}>
                <strong>Transition takeaway:</strong> {takeaway}
            </p>
        </div>
    );
};

export default HMMTransitionTable;
