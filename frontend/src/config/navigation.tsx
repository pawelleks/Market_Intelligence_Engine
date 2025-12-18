import {
    LayoutDashboard,
    Activity,
    History,
    Radio,
    Network,
    TrendingDown,
    TrendingUp,
    BarChart2,
    Zap,
    Search,
    Target,
    ShieldCheck,
    Layers,
    Calendar,
    Brain,
    LineChart,
    Eye,
    Database,
    Cloud
} from 'lucide-react';

export const NAV_DATA = {
    // Items that sit at the top, outside of any accordion
    start: [
        { label: 'Dashboard Home', to: '/', icon: LayoutDashboard }
    ],
    // Collapsible sections
    sections: [
        {
            title: 'Long Term Investing',
            id: 'long_term',
            items: [
                { label: 'Trend Command Center', to: '/investing/trend-matrix', icon: TrendingUp },
                { label: 'HMM Regimes', to: '/analysis/hmm', icon: Activity },
                { label: 'HMM Backtest', to: '/hmm-backtest', icon: History },
                { label: 'HMM Signals', to: '/hmm-signals', icon: Radio },
                { label: 'Markov Analysis', to: '/analysis/markov', icon: Network },
                { label: 'Downtrend Score', to: '/analysis/dcs', icon: TrendingDown },
                { label: 'Downtrend History', to: '/analysis/downtrend', icon: TrendingDown },
                { label: 'Time Series Momentum', to: '/analysis/tsmom', icon: BarChart2 },
                { label: 'Minervini Template', to: '/theory/minervini', icon: Zap },
                { label: 'Minervini Scanner', to: '/analysis/scanner/minervini', icon: Search },
                { label: 'EMA Stack Report', to: '/analysis/ema-stack', icon: Layers },
                { label: 'ADX Strength Report', to: '/analysis/adx', icon: Activity },
                { label: 'PSAR Momentum Report', to: '/analysis/psar', icon: Target },
                { label: 'Ichimoku Cloud Report', to: '/investing/ichimoku', icon: Cloud },
            ]
        },
        {
            title: 'Trading',
            id: 'trading',
            items: [
                { label: 'Expected Moves', to: '/analysis/expected-moves', icon: Target },
                { label: 'EM Reliability', to: '/analysis/reliability', icon: ShieldCheck },
                { label: 'Gamma Exposure (GEX)', to: '/analysis/gex', icon: Layers },
                { label: 'Seasonality & Time', to: '/market/seasonality', icon: Calendar },
            ]
        },
        {
            title: 'Pure Quant',
            id: 'pure_quant',
            items: [
                { label: 'GAF Neural Net', to: '/analysis/neural/gaf', icon: Brain },
            ]
        },
        {
            title: 'Market',
            id: 'market',
            items: [
                { label: 'Market Performance', to: '/analysis/performance', icon: LineChart },
                { label: 'Price & Returns Viewer', to: '/utility/price-viewer', icon: Eye },
            ]
        },
        {
            title: 'Settings & Utilities',
            id: 'settings',
            items: [
                { label: 'Data Pipelines', to: '/system/pipelines', icon: Database },
            ]
        }
    ]
};
