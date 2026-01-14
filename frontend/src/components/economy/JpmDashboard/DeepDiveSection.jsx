import React, { useState, useEffect } from 'react';
import axios from 'axios';

const DeepDiveSection = ({ category }) => {
    const [deepData, setDeepData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        fetchDeepDiveData();
    }, [category]);

    const fetchDeepDiveData = async () => {
        try {
            // NOTE: We don't have a specific deep-dive endpoint yet in the API spec.
            // However, the detail endpoint (/indicators/{category}) returns 'insights' 
            // which contains much of this info. 
            // For now, we will re-use the detail endpoint data or placeholder data 
            // until a specific deep-dive endpoint is expanded if needed.
            //
            // In a real scenario, we might have: /api/v1/jpm-dashboard/indicators/{category}/deep-dive
            // For now, let's reuse the detailed info we already have access to via props 
            // OR fetch again if we want to isolate it. 
            // To strictly follow the plan, I'll fetch the detail endpoint again but display the 'richer' properties.

            const response = await axios.get(
                `/api/v1/jpm-dashboard/indicators/${category}`
            );
            setDeepData(response.data);
            setLoading(false);
        } catch (error) {
            console.error('Deep dive data not available:', error);
            setError('Deep dive analysis currently unavailable.');
            setLoading(false);
        }
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center py-12">
                <div className="text-center">
                    <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-cyan-500 mx-auto mb-2"></div>
                    <div className="text-gray-400 text-sm">Generating deep analysis...</div>
                </div>
            </div>
        );
    }

    // Fallback if APIs don't return specific deep dive fields yet
    const insights = deepData?.insights || {};

    return (
        <div className="space-y-8 p-6 bg-gray-900/30 border border-gray-700 rounded-lg animate-fadeIn">
            {/* Header */}
            <div className="border-b border-gray-700 pb-4 mb-6">
                <h3 className="text-2xl font-bold text-white">Deep Dive Analysis: {deepData?.name || category}</h3>
                <p className="text-gray-400 mt-1">Comprehensive breakdown of underlying components and historical context.</p>
            </div>

            {/* Comprehensive Analysis */}
            <div>
                <h4 className="text-lg font-bold text-cyan-400 mb-3 flex items-center">
                    <span className="mr-2">📝</span> Comprehensive Analysis
                </h4>
                <div className="prose prose-invert max-w-none text-gray-300 leading-relaxed bg-gray-900/50 p-4 rounded-lg border border-gray-800 whitespace-pre-line">
                    {insights.comprehensive_insight || insights.detailed_insight || 'Deep analysis is being generated...'}
                </div>
            </div>

            {/* Component Breakdown */}
            <div>
                <h4 className="text-lg font-bold text-cyan-400 mb-3 flex items-center">
                    <span className="mr-2">🧩</span> Component Drivers
                </h4>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {insights.component_analysis && Object.keys(insights.component_analysis).length > 0 ? (
                        Object.entries(insights.component_analysis).map(([key, value]) => (
                            <div key={key} className="p-3 bg-gray-900/50 border border-gray-700 rounded border-l-4 border-l-cyan-500">
                                <span className="text-gray-400 text-xs block uppercase">Component</span>
                                <span className="text-white font-semibold">{key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}</span>
                                <p className="text-xs text-gray-400 mt-1">{value}</p>
                            </div>
                        ))
                    ) : (
                        // Fallback to secondary metrics if no AI component analysis
                        (deepData?.secondary_metrics || []).map(metric => (
                            <div key={metric.series_id} className="p-3 bg-gray-900/50 border border-gray-700 rounded border-l-4 border-l-gray-600">
                                <span className="text-gray-400 text-xs block uppercase">Driver</span>
                                <span className="text-white font-semibold">{metric.name}</span>
                                <p className="text-xs text-gray-500 mt-1">Key metric monitoring.</p>
                            </div>
                        ))
                    )}
                </div>
            </div>

            {/* Forward Looking Assessment (New) */}
            {insights.forward_looking && (
                <div>
                    <h4 className="text-lg font-bold text-cyan-400 mb-3 flex items-center">
                        <span className="mr-2">🔭</span> Forward Outlook
                    </h4>
                    <div className="text-gray-300 bg-gray-900/50 p-4 rounded-lg border border-gray-800 whitespace-pre-line">
                        {insights.forward_looking}
                    </div>
                </div>
            )}

            {/* Historical Context / Recessions */}
            <div>
                <h4 className="text-lg font-bold text-cyan-400 mb-3 flex items-center">
                    <span className="mr-2">📉</span> Historical Context
                </h4>
                <div className="text-gray-300 bg-gray-900/50 p-4 rounded-lg border border-gray-800">
                    <p className="mb-4 whitespace-pre-line">
                        {insights.historical_context || "This indicator places current values in the context of previous business cycles. Shaded areas on the main chart represent US Recessions as defined by NBER."}
                    </p>

                    {insights.recession_signal && (
                        <div className="mt-3 pt-3 border-t border-gray-700">
                            <span className="text-xs text-gray-400 uppercase tracking-wider block mb-1">Recession Signal</span>
                            <span className="font-semibold text-white">{insights.recession_signal}</span>
                        </div>
                    )}
                </div>
            </div>

            {/* Business Impact */}
            {insights.business_impact && (
                <div>
                    <h4 className="text-lg font-bold text-cyan-400 mb-3 flex items-center">
                        <span className="mr-2">💼</span> Business Owner Impact
                    </h4>
                    <div className="text-gray-300 italic border-l-4 border-yellow-500 pl-4 py-2 bg-yellow-900/10 rounded-r">
                        {insights.business_impact}
                    </div>
                </div>
            )}

        </div>
    );
};

export default DeepDiveSection;
