import React, { useState } from 'react';
import SectorPerformance from '../components/SectorPerformance';
import SectorTrends from '../components/SectorTrends';
import SectorCorrelations from '../components/SectorCorrelations';
import SectorTreemap from '../components/SectorTreemap';

const SectorAnalysisPage = () => {
    // Tab State
    const [activeTab, setActiveTab] = useState('performance');

    // Tab Definitions
    // Placeholder for future tabs (5 expected)
    const tabs = [
        { id: 'performance', label: 'Sector Performance' },
        { id: 'tab2', label: 'Performance Trends' },
        { id: 'tab3', label: 'Correlation Matrix' },
        { id: 'tab4', label: 'Heatmap Analysis' },
        { id: 'tab5', label: 'Tab 5' },
    ];

    const containerStyle = {
        padding: '20px',
        color: '#d7e3f3',
        fontFamily: 'Inter, sans-serif'
    };

    const headerStyle = {
        marginBottom: '30px',
        borderBottom: '1px solid #203049',
        paddingBottom: '15px'
    };

    const tabContainerStyle = {
        display: 'flex',
        gap: '2px',
        borderBottom: '1px solid #203049',
        marginBottom: '30px'
    };

    const tabStyle = (isActive) => ({
        padding: '10px 20px',
        cursor: 'pointer',
        backgroundColor: isActive ? '#203049' : 'transparent',
        color: isActive ? '#fff' : '#888',
        border: 'none',
        borderTopLeftRadius: '4px',
        borderTopRightRadius: '4px',
        fontSize: '14px',
        fontWeight: '500',
        transition: 'background-color 0.2s',
        marginBottom: '-1px', // Sit on the line
        borderBottom: isActive ? '2px solid #4CAF50' : 'none'
    });

    return (
        <div style={containerStyle}>
            {/* Header */}
            <div style={headerStyle}>
                <h1 style={{ margin: 0, fontSize: '24px', fontWeight: '600', color: '#fff' }}>
                    Sector Analysis
                </h1>
                <p style={{ margin: '5px 0 0', color: '#9ec4ff', fontSize: '14px' }}>
                    Deep dive into sector performance and rotation.
                </p>
            </div>

            {/* Tabs */}
            <div style={tabContainerStyle}>
                {tabs.map(tab => (
                    <button
                        key={tab.id}
                        style={tabStyle(activeTab === tab.id)}
                        onClick={() => setActiveTab(tab.id)}
                    >
                        {tab.label}
                    </button>
                ))}
            </div>

            {/* Content */}
            <div>
                {activeTab === 'performance' && <SectorPerformance />}
                {activeTab === 'tab2' && <SectorTrends />}
                {activeTab === 'tab3' && <SectorCorrelations />}
                {activeTab === 'tab4' && <SectorTreemap />}
                {activeTab === 'tab5' && <div style={{ padding: '40px', textAlign: 'center', color: '#666' }}>Tab 5 Content Coming Soon</div>}
            </div>
        </div>
    );
};

export default SectorAnalysisPage;
