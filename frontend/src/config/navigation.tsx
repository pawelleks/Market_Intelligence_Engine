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
    Cloud,
    PieChart,
    Globe,
    AlertTriangle,
    Droplets,
    Briefcase,
    Gauge
} from 'lucide-react';

export const NAV_DATA = {
    // Items that sit at the top, outside of any accordion
    start: [
        { label: 'Dashboard Home', to: '/', icon: LayoutDashboard },
        { label: 'Daily Intelligence (AI)', to: '/analysis/daily', icon: Brain }
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
                { label: 'Volume Regime', to: '/analysis/volume', icon: BarChart2 },
                { label: 'Volatility & Risk (ATR)', to: '/analysis/volatility', icon: Activity },
            ]
        },
        {
            title: 'Trading',
            id: 'trading',
            items: [
                { label: 'Expected Moves', to: '/analysis/expected-moves', icon: Target },
                { label: 'Expected Moves V2', to: '/analysis/expected-moves-v2', icon: Zap },
                { label: 'Implied Probability', to: '/analysis/implied-probability', icon: TrendingUp },
                { label: 'Real-Time Option Flow', to: '/option-flow', icon: Zap },
                { label: 'Real-Time Dealer Flow', to: '/analysis/realtime-flow', icon: Zap },

                { label: 'EM Reliability', to: '/analysis/reliability', icon: ShieldCheck },
                { label: 'Gamma Exposure (GEX)', to: '/analysis/gex', icon: Layers },
                { label: 'Option Skew & PCR', to: '/analysis/skew', icon: Activity },
                { label: 'Volatility Term Structure', to: '/analysis/volatility-term-structure', icon: Activity },
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
                { label: 'Sector Analysis', to: '/analysis/sector', icon: PieChart },
                { label: 'Price & Returns Viewer', to: '/utility/price-viewer', icon: Eye },
            ]
        },
        {
            title: 'Economy',
            id: 'economy',
            items: [
                { label: 'JPM Economic Dashboard', to: '/economy/jpm-dashboard', icon: LayoutDashboard },
                { label: 'Prediction Analysis', to: '/analysis/prediction', icon: Target },
                { label: 'Weekly Economic data', to: '/economy/weekly', icon: Globe },
                { label: 'Calendar & Releases', to: '/economy/calendar', icon: Calendar },
                { label: 'Data Viewer', to: '/economy', icon: Globe },
                { label: 'Minsky Model', to: '/analysis/minsky', icon: Brain },
                { label: 'Austrian Cycle (ABCT)', to: '/analysis/abct', icon: Activity },
                { label: 'HP Filter (Cycles)', to: '/analysis/hp-filter', icon: TrendingUp },
                { label: 'Hamilton (Recession)', to: '/analysis/hamilton', icon: AlertTriangle },
                { label: 'Global Liquidity', to: '/analysis/liquidity', icon: Droplets },
                { label: 'NFP Momentum', to: '/analysis/nfp-momentum', icon: Briefcase },
                { label: 'LEI Index', to: '/analysis/lei', icon: Gauge },
                { label: 'COI Index', to: '/analysis/coi', icon: Activity },
                { label: 'LAG Index', to: '/analysis/lag', icon: History },
                { label: 'Business Cycle', to: '/analysis/business-cycle', icon: Activity },
            ]
        },
        {
            title: 'Tools',
            id: 'tools',
            items: [
                { label: 'EMA Respect Calculator', to: '/tools/ema-respect', icon: Target },
            ]
        },
        {
            title: 'Settings & Utilities',
            id: 'settings',
            items: [
                { label: 'Data Pipelines', to: '/system/pipelines', icon: Database },
                { label: 'User Management', to: '/admin', icon: ShieldCheck },
            ]
        }
    ]
};
