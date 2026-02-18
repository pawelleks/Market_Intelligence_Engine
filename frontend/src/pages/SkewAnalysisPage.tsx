import React, { useState, useEffect } from 'react';
import Plot from 'react-plotly.js';
import { TrendingUp, BarChart2, Activity, Info, AlertTriangle } from 'lucide-react';

const SYMBOLS = ['SPX', 'SPY', 'QQQ', 'IWM'];

interface SmilePoint {
    strike: number;
    iv: number;
    right: string;
    volume: number;
    oi: number;
}

interface TenorData {
    expiration: string;
    dte: number;
    data: SmilePoint[];
}

interface SkewData {
    ticker: string;
    as_of: string;
    spot_price: number;
    pcr: {
        volume: number;
        oi: number;
        total_call_vol: number;
        total_put_vol: number;
        total_call_oi: number;
        total_put_oi: number;
    };
    smile: Record<string, TenorData>;
}

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444'];

const SkewPage: React.FC = () => {
    const [selectedSymbol, setSelectedSymbol] = useState('SPX');
    const [data, setData] = useState<SkewData | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const loadSkewData = async () => {
            setLoading(true);
            setError(null);
            try {
                const timestamp = new Date().getTime();
                const response = await fetch(`/data/skew_${selectedSymbol}.json?v=${timestamp}`);
                if (!response.ok) {
                    throw new Error(`Data not found for ${selectedSymbol}`);
                }
                const jsonData = await response.json();
                setData(jsonData);
            } catch (e) {
                console.error('Failed to load skew data:', e);
                setError(`No analysis data available for ${selectedSymbol}. The pipeline might be processing.`);
                setData(null);
            } finally {
                setLoading(false);
            }
        };

        loadSkewData();
    }, [selectedSymbol]);

    const renderSmileChart = () => {
        if (!data || !data.smile) return null;

        const traces = Object.entries(data.smile).map(([tenor, tenorData], idx) => {
            // Sort data by strike for a clean line
            const sortedData = [...tenorData.data].sort((a, b) => a.strike - b.strike);

            return {
                x: sortedData.map(p => p.strike),
                y: sortedData.map(p => p.iv * 100),
                name: `${tenor} (${tenorData.expiration})`,
                type: 'scatter',
                mode: 'lines+markers',
                line: { shape: 'spline', color: COLORS[idx % COLORS.length], width: 3 },
                marker: { size: 4, opacity: 0.6 },
                hovertemplate: `Strike: $%{x}<br>Implied Vol: %{y:.2f}%<extra></extra>`
            };
        });

        return (
            <Plot
                data={traces as any}
                layout={{
                    autosize: true,
                    height: 450,
                    paper_bgcolor: 'transparent',
                    plot_bgcolor: 'rgba(0,0,0,0)',
                    font: { color: '#94a3b8', family: 'Inter, sans-serif' },
                    margin: { t: 40, r: 40, b: 60, l: 60 },
                    xaxis: {
                        gridcolor: '#1e293b',
                        zeroline: false,
                        title: { text: 'Strike Price ($)', font: { size: 12 } },
                        tickfont: { size: 10 }
                    },
                    yaxis: {
                        gridcolor: '#1e293b',
                        zeroline: false,
                        title: { text: 'Implied Volatility (%)', font: { size: 12 } },
                        tickfont: { size: 10 }
                    },
                    legend: {
                        orientation: 'h',
                        y: -0.2,
                        x: 0.5,
                        xanchor: 'center',
                        font: { size: 11 }
                    },
                    hovermode: 'closest',
                    annotations: data.spot_price ? [{
                        x: data.spot_price,
                        y: 0,
                        yref: 'paper',
                        text: `Spot: $${data.spot_price}`,
                        showarrow: false,
                        font: { color: '#ffffff', size: 10 },
                        bgcolor: 'rgba(59, 130, 246, 0.5)',
                        borderpad: 4
                    }] : []
                }}
                config={{ responsive: true, displayModeBar: false }}
                style={{ width: '100%' }}
            />
        );
    };

    const PCRStat = ({ label, value, description }: { label: string, value: number, description: string }) => (
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-lg">
            <div className="flex items-center justify-between mb-2">
                <span className="text-slate-400 text-sm font-medium uppercase tracking-wider">{label}</span>
                <BarChart2 className="w-5 h-5 text-blue-400" />
            </div>
            <div className="text-3xl font-bold text-white mb-2">
                {value > 0 ? value.toFixed(2) : 'N/A'}
            </div>
            <p className="text-slate-500 text-xs leading-relaxed">
                {description}
            </p>
            <div className="mt-4 h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                <div
                    className={`h-full transition-all duration-500 rounded-full ${value > 1.2 ? 'bg-red-500' : value < 0.8 ? 'bg-green-500' : 'bg-blue-500'}`}
                    style={{ width: `${Math.min(100, (value / 2) * 100)}%` }}
                />
            </div>
        </div>
    );

    return (
        <div className="p-8 space-y-8 bg-slate-950 min-h-screen text-slate-200">
            {/* Header */}
            <header className="flex flex-col md:flex-row md:items-end justify-between gap-4 border-b border-slate-800 pb-8">
                <div>
                    <div className="flex items-center gap-3 mb-2">
                        <Activity className="w-8 h-8 text-blue-500" />
                        <h1 className="text-4xl font-extrabold text-white tracking-tight">
                            Skew Analysis
                        </h1>
                    </div>
                    <p className="text-slate-400 text-lg">
                        Volatility Smile & Put-Call Ratio Dashboard
                    </p>
                </div>

                <div className="flex bg-slate-900 p-1.5 rounded-xl border border-slate-800">
                    {SYMBOLS.map(sym => (
                        <button
                            key={sym}
                            onClick={() => setSelectedSymbol(sym)}
                            className={`px-6 py-2.5 rounded-lg font-bold text-sm transition-all duration-200 ${selectedSymbol === sym
                                ? 'bg-blue-600 text-white shadow-lg shadow-blue-900/40'
                                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
                                }`}
                        >
                            {sym}
                        </button>
                    ))}
                </div>
            </header>

            {error && (
                <div className="bg-red-900/20 border border-red-500/50 rounded-xl p-6 flex items-start gap-4">
                    <AlertTriangle className="w-6 h-6 text-red-400 flex-shrink-0 mt-0.5" />
                    <div>
                        <h3 className="text-red-400 font-bold mb-1">Data Unavailable</h3>
                        <p className="text-red-200/70 text-sm">{error}</p>
                    </div>
                </div>
            )}

            {loading ? (
                <div className="h-96 flex flex-col items-center justify-center space-y-4">
                    <div className="w-12 h-12 border-4 border-blue-600/30 border-t-blue-600 rounded-full animate-spin" />
                    <p className="text-slate-500 font-medium animate-pulse">Analyzing market skew...</p>
                </div>
            ) : data ? (
                <>
                    {/* Top Stats Grid */}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
                        <PCRStat
                            label="PCR (Volume)"
                            value={data.pcr.volume}
                            description="Real-time ratio of Put to Call volume. Higher values suggest bearish sentiment or increased hedging."
                        />
                        <PCRStat
                            label="PCR (Open Interest)"
                            value={data.pcr.oi}
                            description="Ratio of outstanding Put to Call contracts. Reflects structural positioning of market participants."
                        />
                        <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-lg flex flex-col justify-between">
                            <div className="flex items-center justify-between mb-2">
                                <span className="text-slate-400 text-sm font-medium uppercase tracking-wider">Spot Reference</span>
                                <Activity className="w-5 h-5 text-emerald-400" />
                            </div>
                            <div className="text-3xl font-bold text-white mb-2">
                                ${data.spot_price?.toLocaleString()}
                            </div>
                            <p className="text-slate-500 text-xs italic">
                                Last updated: {data.as_of}
                            </p>
                        </div>
                    </div>

                    {/* Main Charts */}
                    <div className="grid grid-cols-1 gap-8">
                        <section className="bg-slate-900 border border-slate-800 rounded-2xl p-8 shadow-xl">
                            <div className="flex items-center justify-between mb-8">
                                <div>
                                    <div className="flex items-center gap-2 mb-1">
                                        <TrendingUp className="w-5 h-5 text-blue-400" />
                                        <h2 className="text-2xl font-bold text-white">Volatility Smile</h2>
                                    </div>
                                    <p className="text-slate-500 text-sm">
                                        Implied Volatility (IV) across strike prices. Deep "smiles" indicate higher tail-risk pricing.
                                    </p>
                                </div>
                                <div className="hidden md:flex items-center gap-6">
                                    <div className="flex items-center gap-2">
                                        <div className="w-3 h-3 rounded-full bg-blue-500" />
                                        <span className="text-xs text-slate-400">30D Tenor</span>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <div className="w-3 h-3 rounded-full bg-emerald-500" />
                                        <span className="text-xs text-slate-400">60D Tenor</span>
                                    </div>
                                </div>
                            </div>
                            <div className="rounded-xl bg-slate-950/50 p-4 border border-slate-800/50">
                                {renderSmileChart()}
                            </div>
                        </section>
                    </div>

                    {/* Educational Footer */}
                    <div className="bg-blue-900/10 border border-blue-500/20 rounded-2xl p-8 flex gap-6">
                        <div className="bg-blue-500/20 p-3 rounded-xl h-fit">
                            <Info className="w-6 h-6 text-blue-400" />
                        </div>
                        <div className="space-y-4">
                            <h4 className="text-lg font-bold text-blue-200">How to interpret this data</h4>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-8 text-sm text-slate-400 leading-relaxed">
                                <p>
                                    <strong className="text-slate-200 block mb-1">Negative Skew (Smirk)</strong>
                                    When OTM Puts have higher IV than OTM Calls, the market is pricing in a "fear of the downside." This is typical for equity indices.
                                </p>
                                <p>
                                    <strong className="text-slate-200 block mb-1">Put-Call Ratio (PCR)</strong>
                                    A PCR {'>'} 1.0 indicates more Puts than Calls. Extremes (e.g. {'>'} 1.6) can be contrarian bullish signals as they represent peak fear.
                                </p>
                            </div>
                        </div>
                    </div>
                </>
            ) : (
                <div className="bg-slate-900/50 border border-dashed border-slate-800 rounded-2xl p-24 text-center">
                    <p className="text-slate-500 italic">Select a symbol to begin analysis</p>
                </div>
            )}
        </div>
    );
};

export default SkewPage;
