import React, { useState, useEffect, useMemo } from 'react';
import { ProbabilitySurface3D } from '../components/charts/ProbabilitySurface3D';
import { ProbabilityBellCurve } from '../components/charts/ProbabilityBellCurve';
import { PriceHistoryHeatmap } from '../components/charts/PriceHistoryHeatmap';
import { ProbabilityLayeredChart } from '../components/charts/ProbabilityLayeredChart';
import { ProbabilityEducationModal } from '../components/modals/ProbabilityEducationModal';
import { SentimentGauge } from '../components/charts/SentimentGauge';
import { HelpCircle, Clock } from 'lucide-react';

// Available assets for probability analysis
const AVAILABLE_ASSETS = ['SPX', 'SPY', 'QQQ', 'IWM'] as const;
type AssetSymbol = typeof AVAILABLE_ASSETS[number];

export const ImpliedProbabilityPage = () => {
    // Asset Selection State
    const [selectedAsset, setSelectedAsset] = useState<AssetSymbol>('SPX');

    // State for static data (loaded from pre-computed JSON)
    const [surfaceData, setSurfaceData] = useState<any>(null);
    const [coneData, setConeData] = useState<any>(null);
    const [heatmapData, setHeatmapData] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // Live price state
    const [livePrice, setLivePrice] = useState<number>(0);
    const [priceLoading, setPriceLoading] = useState(false);

    // UI State
    const [erp, setErp] = useState(0.04);
    const [isEducationOpen, setIsEducationOpen] = useState(false);

    // Load Static Data when selectedAsset changes
    useEffect(() => {
        const loadStaticData = async () => {
            setLoading(true);
            setError(null);

            try {
                // Fetch static files in parallel for the selected asset
                const timestamp = new Date().getTime();
                const [surfaceRes, coneRes, heatmapRes] = await Promise.all([
                    fetch(`/data/probability_surface_${selectedAsset}.json?v=${timestamp}`),
                    fetch(`/data/forward_cone_${selectedAsset}.json?v=${timestamp}`),
                    fetch(`/data/projection_heatmap_${selectedAsset}.json?v=${timestamp}`).catch(() => null)
                ]);

                if (!surfaceRes.ok || !coneRes.ok) {
                    throw new Error(`No data for ${selectedAsset}. Run the daily pipeline first.`);
                }

                const [surfaceJson, coneJson] = await Promise.all([
                    surfaceRes.json(),
                    coneRes.json()
                ]);

                // Heatmap is optional — don't fail if missing
                let heatmapJson = null;
                if (heatmapRes && heatmapRes.ok) {
                    heatmapJson = await heatmapRes.json();
                }

                setSurfaceData(surfaceJson);
                setConeData(coneJson);
                setHeatmapData(heatmapJson);

                // Update ERP from data if available
                if (surfaceJson.erp) {
                    setErp(surfaceJson.erp);
                }

            } catch (e: any) {
                console.error(`Failed to load ${selectedAsset} probability data:`, e);
                setError(e.message || 'Failed to load data');
            } finally {
                setLoading(false);
            }
        };

        loadStaticData();
    }, [selectedAsset]);

    // Fetch Live Price for selected asset
    useEffect(() => {
        const fetchLivePrice = async () => {
            setPriceLoading(true);
            try {
                // Primary: use static EM endpoint (correct EOD close from ThetaData)
                const emRes = await fetch('/api/v1/expected_moves/static/latest');
                if (emRes.ok) {
                    const emData = await emRes.json();
                    const tickerEm = emData?.[selectedAsset];
                    if (tickerEm?.close && tickerEm.close > 0) {
                        setLivePrice(tickerEm.close);
                        return;
                    }
                }
                // Fallback: candles API
                const res = await fetch(`/api/v1/market/candles/${selectedAsset}?interval=1d&range=1d`);
                if (res.ok) {
                    const data = await res.json();
                    if (data?.length > 0) {
                        setLivePrice(data[data.length - 1].Close || 0);
                        return;
                    }
                }
                // Last resort: ref_price from static data
                if (surfaceData?.ref_price) setLivePrice(surfaceData.ref_price);
            } catch (e) {
                console.error('Failed to fetch live price:', e);
                if (surfaceData?.ref_price) setLivePrice(surfaceData.ref_price);
            } finally {
                setPriceLoading(false);
            }
        };

        fetchLivePrice();
        const interval = setInterval(fetchLivePrice, 60000);
        return () => clearInterval(interval);
    }, [selectedAsset, surfaceData]);

    // Process data with ERP drift adjustment
    const processedData = useMemo(() => {
        if (!surfaceData?.results) return [];

        return surfaceData.results.map((item: any) => {
            const T = item.dte / 365.0;
            const driftFactor = Math.exp(erp * T);

            const dist = { ...item.distribution };
            if (dist.strikes) {
                dist.strikes = dist.strikes.map((k: number) => k * driftFactor);
            }

            return {
                ...item,
                distribution: dist
            };
        });
    }, [surfaceData, erp]);

    // Target date for single expiration view
    const [targetDate, setTargetDate] = useState<string>('');

    useEffect(() => {
        if (processedData.length > 0 && !targetDate) {
            const defaultIndex = Math.min(processedData.length - 1, 4);
            setTargetDate(processedData[defaultIndex].expiration);
        }
    }, [processedData, targetDate]);

    // Reset targetDate when asset changes
    useEffect(() => {
        setTargetDate('');
    }, [selectedAsset]);

    // Get peak price (mode of distribution) for target date
    const getPeakPrice = (dStr: string) => {
        const row = processedData.find((d: any) => d.expiration === dStr);
        if (!row?.distribution) return livePrice || surfaceData?.ref_price || 0;

        const { pdf, strikes } = row.distribution;
        if (!pdf || !strikes) return livePrice || 0;

        let maxP = -1;
        let maxK = 0;
        pdf.forEach((p: number, i: number) => {
            if (p > maxP) {
                maxP = p;
                maxK = strikes[i];
            }
        });
        return maxK || livePrice;
    };

    const currentFwd = getPeakPrice(targetDate);

    // Prefer live price (from static EM endpoint) over stale JSON ref_price
    const safeRefPrice = useMemo(() => {
        if (livePrice && livePrice > 0) {
            return livePrice;
        }
        if (surfaceData?.ticker === selectedAsset && surfaceData?.ref_price > 0) {
            return surfaceData.ref_price;
        }
        return 0;
    }, [surfaceData, selectedAsset, livePrice]);

    const displayPrice = safeRefPrice;

    // Format date for display
    const formatAsOf = (dateStr: string) => {
        if (!dateStr) return '';
        const d = new Date(dateStr);
        return d.toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric'
        });
    };

    return (
        <div className="p-6 space-y-6 bg-slate-950 min-h-screen flex flex-col font-inter text-slate-200">
            {/* Construction Banner */}
            <div className="bg-amber-900/40 border border-amber-600/50 rounded-lg px-4 py-2.5 text-center text-sm text-amber-200">
                Under Construction — This page may not work properly as it is still under development. Do not use the data presented to make any trading or investment decisions.
            </div>

            {/* Header */}
            <header className="mb-4 flex flex-col md:flex-row justify-between items-start md:items-center gap-4 border-b border-slate-800 pb-4">
                <div>
                    <h1 className="text-3xl font-bold text-slate-100 mb-1">Implied Probability (ThetaData Pure)</h1>
                    <p className="text-slate-400">Option Chain Analysis & Breeden-Litzenberger PDF.</p>

                    {/* Data Timestamp */}
                    {surfaceData?.as_of && (
                        <div className="flex items-center gap-2 mt-2 text-xs text-slate-500">
                            <Clock className="w-3 h-3" />
                            <span>Map Generated: {formatAsOf(surfaceData.as_of)} (EOD Data)</span>
                            {safeRefPrice > 0 && (
                                <span className="text-green-400 ml-2">
                                    • {selectedAsset} Spot: ${safeRefPrice.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                                </span>
                            )}
                        </div>
                    )}
                </div>

                {/* Controls */}
                <div className="flex flex-wrap items-center gap-4">

                    {/* Asset Selector */}
                    <div className="flex items-center gap-1 bg-slate-900 border border-slate-700 rounded-lg p-1">
                        {AVAILABLE_ASSETS.map((asset) => (
                            <button
                                key={asset}
                                onClick={() => setSelectedAsset(asset)}
                                className={`px-3 py-1.5 text-sm font-medium rounded-md transition-all ${selectedAsset === asset
                                    ? 'bg-cyan-600 text-white shadow-md'
                                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
                                    }`}
                            >
                                {asset}
                            </button>
                        ))}
                    </div>

                    {/* Education Button */}
                    <button
                        onClick={() => setIsEducationOpen(true)}
                        className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-blue-400 bg-blue-500/10 hover:bg-blue-500/20 border border-blue-500/20 rounded-lg transition-colors"
                    >
                        <HelpCircle className="w-4 h-4" />
                        How to Read
                    </button>

                    {/* ERP Control */}
                    <div className="bg-slate-900 border border-slate-700 rounded-lg p-2 flex items-center gap-3 shadow-sm">
                        <label className="text-sm font-medium text-slate-400">ERP</label>
                        <input
                            type="range"
                            min="0" max="0.10" step="0.01"
                            value={erp}
                            onChange={(e) => setErp(parseFloat(e.target.value))}
                            className="w-24 cursor-pointer accent-cyan-500"
                        />
                        <span className="text-sm font-mono text-cyan-400 w-10 text-right">
                            {(erp * 100).toFixed(0)}%
                        </span>
                    </div>

                    {/* Expiration Selector */}
                    {processedData.length > 0 && (
                        <div className="bg-slate-900 border border-slate-700 rounded-lg p-2 flex items-center gap-3 shadow-sm">
                            <label className="text-sm font-medium text-slate-400">Exp</label>
                            <select
                                value={targetDate}
                                onChange={(e) => setTargetDate(e.target.value)}
                                className="bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-200 focus:ring-1 focus:ring-cyan-500 outline-none text-sm cursor-pointer"
                            >
                                {processedData.map((d: any) => (
                                    <option key={d.expiration} value={d.expiration}>
                                        {d.expiration} ({d.dte}d)
                                    </option>
                                ))}
                            </select>
                        </div>
                    )}
                </div>
            </header>

            {/* Error State */}
            {error && !loading && (
                <div className="flex-grow flex flex-col items-center justify-center text-slate-500 py-20">
                    <p className="text-red-400 mb-2">{error}</p>
                    <p className="text-sm">Run the daily pipeline to generate data:</p>
                    <code className="mt-2 bg-slate-900 px-3 py-1 rounded text-xs text-cyan-400">
                        python jobs/process_implied_probabilities.py
                    </code>
                </div>
            )}

            {/* Loading State */}
            {loading && (
                <div className="flex-grow flex items-center justify-center text-slate-500 animate-pulse py-20">
                    Loading {selectedAsset} Probability Maps...
                </div>
            )}

            {/* Charts Grid */}
            {!loading && processedData.length > 0 && (
                <div className="space-y-8 animate-in fade-in duration-500">

                    {/* 0. Sentiment Gauge */}
                    <SentimentGauge
                        sentiment={coneData?.sentiment || null}
                        ticker={selectedAsset}
                    />

                    {/* 1. Price History + Probability Heatmap (Full Width) */}
                    <PriceHistoryHeatmap
                        data={heatmapData}
                        ticker={selectedAsset}
                    />

                    {/* 2. Middle Row: Surface 3D + Layered Bell Curves */}
                    <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
                        {/* 3D Surface */}
                        <ProbabilitySurface3D
                            data={processedData}
                            forwardPrice={safeRefPrice}
                            ticker={selectedAsset}
                        />

                        {/* Layered Bell Curves (Multi-Exp) */}
                        <ProbabilityLayeredChart
                            data={processedData}
                            currentPrice={safeRefPrice}
                            ticker={selectedAsset}
                            hardAnchor={safeRefPrice}
                        />
                    </div>

                    {/* 3. Bottom: Single Exp Bell Curve */}
                    <ProbabilityBellCurve
                        data={processedData}
                        targetDate={targetDate}
                        currentPrice={safeRefPrice}
                        ticker={selectedAsset}
                        hardAnchor={safeRefPrice}
                    />
                </div>
            )}

            {/* Education Modal */}
            <ProbabilityEducationModal
                isOpen={isEducationOpen}
                onClose={() => setIsEducationOpen(false)}
            />
        </div>
    );
};

export default ImpliedProbabilityPage;
