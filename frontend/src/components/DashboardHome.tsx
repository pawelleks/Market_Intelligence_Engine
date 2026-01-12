import React from 'react';
import { Link } from 'react-router-dom';
import {
    Activity,
    Search,
    Layers,
    Target,
    ShieldCheck,
    Calendar,
    Brain,
    LineChart,
    ArrowRight,
    Cloud,
    TrendingUp,
    Gauge,
    AlertTriangle,
    Droplets,
    Briefcase,
    History,
    Globe,
    BarChart3,
    Sparkles,
    Zap
} from 'lucide-react';

const DashboardHome = () => {
    return (
        <div style={{ padding: '40px', color: '#e0e0e0', backgroundColor: '#0b1220', minHeight: '100vh', display: 'flex', flexDirection: 'column', gap: '40px' }}>

            {/* Header Section */}
            <div style={{ textAlign: 'center', marginBottom: '20px' }}>
                <h1 style={{ fontSize: '36px', fontWeight: 'bold', color: '#fff', marginBottom: '10px' }}>
                    Welcome to the Market Intelligence Engine
                </h1>
                <p style={{ fontSize: '18px', color: '#94a3b8' }}>
                    Comprehensive analysis tools for long-term investing, trading, and economic forecasting.
                </p>
            </div>

            {/* Grid Layout */}
            <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
                gap: '30px',
                maxWidth: '1600px',
                margin: '0 auto',
                width: '100%'
            }}>
                {/* Column 1: Economy & Macro */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                    <h2 style={{ fontSize: '20px', fontWeight: 'bold', color: '#f59e0b', borderBottom: '1px solid #1e293b', paddingBottom: '10px' }}>
                        📊 Economy & Macro
                    </h2>

                    <InfoCard
                        title="Prediction Analysis"
                        description="Comprehensive forecasting framework comparing 9 recession models with SPX returns."
                        to="/analysis/prediction"
                        icon={Sparkles}
                        color="#f59e0b"
                    />
                    <InfoCard
                        title="LEI Index"
                        description="Leading Economic Indicators - early warning signals for economic turning points."
                        to="/analysis/lei"
                        icon={Gauge}
                        color="#f59e0b"
                    />
                    <InfoCard
                        title="COI Index"
                        description="Coincident Indicators - real-time snapshot of current economic conditions."
                        to="/analysis/coi"
                        icon={Activity}
                        color="#f59e0b"
                    />
                    <InfoCard
                        title="LAG Index"
                        description="Lagging Indicators - confirms cycle peaks and validates recession signals."
                        to="/analysis/lag"
                        icon={History}
                        color="#f59e0b"
                    />
                    <InfoCard
                        title="Minsky Model"
                        description="Financial instability hypothesis tracking credit cycles and systemic risk."
                        to="/analysis/minsky"
                        icon={Brain}
                        color="#f59e0b"
                    />
                    <InfoCard
                        title="Austrian Cycle (ABCT)"
                        description="Austrian Business Cycle Theory monitoring credit-driven boom-bust patterns."
                        to="/analysis/abct"
                        icon={TrendingUp}
                        color="#f59e0b"
                    />
                    <InfoCard
                        title="HP Filter (Cycles)"
                        description="Hodrick-Prescott filter isolating business cycle components from trend."
                        to="/analysis/hp-filter"
                        icon={LineChart}
                        color="#f59e0b"
                    />
                    <InfoCard
                        title="Hamilton (Recession)"
                        description="Markov-switching model for recession probability forecasting."
                        to="/analysis/hamilton"
                        icon={AlertTriangle}
                        color="#f59e0b"
                    />
                    <InfoCard
                        title="Global Liquidity"
                        description="Central bank balance sheets and global liquidity impulse tracking."
                        to="/analysis/liquidity"
                        icon={Droplets}
                        color="#f59e0b"
                    />
                    <InfoCard
                        title="NFP Momentum"
                        description="Nonfarm payrolls momentum and labor market cycle analysis."
                        to="/analysis/nfp-momentum"
                        icon={Briefcase}
                        color="#f59e0b"
                    />
                    <InfoCard
                        title="Economic Data"
                        description="Browse weekly releases, FRED data, and economic calendar."
                        to="/economy/weekly"
                        icon={Globe}
                        color="#f59e0b"
                    />
                </div>

                {/* Column 2: Long Term Investing */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                    <h2 style={{ fontSize: '20px', fontWeight: 'bold', color: '#4ade80', borderBottom: '1px solid #1e293b', paddingBottom: '10px' }}>
                        📈 Long Term Investing
                    </h2>

                    <InfoCard
                        title="Trend Command Center"
                        description="Aggregated trend scoring using SMA Stack, ADX, PSAR, and Ichimoku Cloud."
                        to="/investing/trend-matrix"
                        icon={TrendingUp}
                        color="#4ade80"
                    />
                    <InfoCard
                        title="HMM Regimes"
                        description="Hidden Markov Model detecting latent market states (Bull/Bear/Neutral)."
                        to="/analysis/hmm"
                        icon={Activity}
                        color="#4ade80"
                    />
                    <InfoCard
                        title="HMM Signals"
                        description="Real-time HMM regime signals and backtested performance metrics."
                        to="/analysis/hmm-signals"
                        icon={Zap}
                        color="#4ade80"
                    />
                    <InfoCard
                        title="HMM Backtest"
                        description="Strategy performance analysis across different HMM configurations."
                        to="/analysis/hmm-backtest"
                        icon={BarChart3}
                        color="#4ade80"
                    />
                    <InfoCard
                        title="Minervini Scanner"
                        description="Screen for high-growth stocks meeting the Minervini Trend Template."
                        to="/analysis/scanner/minervini"
                        icon={Search}
                        color="#4ade80"
                    />
                    <InfoCard
                        title="EMA Stack Report"
                        description="Verify trend strength through exponential moving average alignment."
                        to="/analysis/ema-stack"
                        icon={Layers}
                        color="#4ade80"
                    />
                    <InfoCard
                        title="Ichimoku Cloud"
                        description="Comprehensive trend confirmation using Ichimoku Kinko Hyo system."
                        to="/investing/ichimoku"
                        icon={Cloud}
                        color="#4ade80"
                    />
                    <InfoCard
                        title="TSMOM Dashboard"
                        description="Time series momentum strategy across multiple timeframes."
                        to="/analysis/tsmom"
                        icon={TrendingUp}
                        color="#4ade80"
                    />
                    <InfoCard
                        title="Downtrend Score"
                        description="Multi-factor analysis quantifying downtrend severity and duration."
                        to="/analysis/downtrend-score"
                        icon={LineChart}
                        color="#4ade80"
                    />
                    <InfoCard
                        title="Downtrend History"
                        description="Historical downtrend patterns and recovery timelines."
                        to="/analysis/downtrend-history"
                        icon={History}
                        color="#4ade80"
                    />
                </div>

                {/* Column 3: Trading & Options */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                    <h2 style={{ fontSize: '20px', fontWeight: 'bold', color: '#60a5fa', borderBottom: '1px solid #1e293b', paddingBottom: '10px' }}>
                        🎯 Trading & Options
                    </h2>

                    <InfoCard
                        title="Expected Moves"
                        description="Options-implied volatility ranges for forecasting price boundaries."
                        to="/analysis/expected-moves"
                        icon={Target}
                        color="#60a5fa"
                    />
                    <InfoCard
                        title="EM Reliability"
                        description="Historical backtest of Expected Moves accuracy and breach rates."
                        to="/analysis/reliability"
                        icon={ShieldCheck}
                        color="#60a5fa"
                    />
                    <InfoCard
                        title="Gamma Exposure (GEX)"
                        description="Visualize dealer gamma positioning to anticipate volatility pinning."
                        to="/analysis/gex"
                        icon={Layers}
                        color="#60a5fa"
                    />
                    <InfoCard
                        title="Skew Analysis"
                        description="Options skew patterns revealing market fear and tail risk."
                        to="/analysis/skew"
                        icon={BarChart3}
                        color="#60a5fa"
                    />
                    <InfoCard
                        title="Volatility Term Structure"
                        description="VIX futures curve analysis for volatility regime forecasting."
                        to="/analysis/vol-term-structure"
                        icon={LineChart}
                        color="#60a5fa"
                    />
                    <InfoCard
                        title="Volume Regime"
                        description="Detect volume anomalies and accumulation/distribution patterns."
                        to="/analysis/volume"
                        icon={BarChart3}
                        color="#60a5fa"
                    />
                    <InfoCard
                        title="Seasonality & Time"
                        description="Historical returns across monthly and intraday timeframes."
                        to="/market/seasonality"
                        icon={Calendar}
                        color="#60a5fa"
                    />
                </div>

                {/* Column 4: AI & Advanced */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                    <h2 style={{ fontSize: '20px', fontWeight: 'bold', color: '#a78bfa', borderBottom: '1px solid #1e293b', paddingBottom: '10px' }}>
                        🤖 AI & Advanced Analytics
                    </h2>

                    <InfoCard
                        title="Daily Intelligence (AI)"
                        description="AI-driven market analysis synthesizing technical regimes and options data."
                        to="/analysis/daily"
                        icon={Brain}
                        color="#a78bfa"
                    />
                    <InfoCard
                        title="GAF Neural Net"
                        description="Gramian Angular Field computer vision for deep learning trend forecasting."
                        to="/analysis/neural/gaf"
                        icon={Brain}
                        color="#a78bfa"
                    />
                    <InfoCard
                        title="Market Performance"
                        description="Real-time heatmap of index and sector returns."
                        to="/analysis/performance"
                        icon={LineChart}
                        color="#a78bfa"
                    />
                    <InfoCard
                        title="DCS Dashboard"
                        description="Digital Currency Signal tracking crypto market conditions."
                        to="/analysis/dcs"
                        icon={Activity}
                        color="#a78bfa"
                    />
                </div>

            </div>
        </div>
    );
};

// Sub-component for individual cards
const InfoCard = ({ title, description, to, icon: Icon, color }) => {
    return (
        <div style={{
            backgroundColor: '#162032',
            border: '1px solid #1e293b',
            borderRadius: '8px',
            padding: '20px',
            display: 'flex',
            flexDirection: 'column',
            gap: '10px',
            transition: 'transform 0.2s, border-color 0.2s',
            cursor: 'pointer'
        }}
            onMouseEnter={(e) => {
                e.currentTarget.style.transform = 'translateY(-2px)';
                e.currentTarget.style.borderColor = color;
            }}
            onMouseLeave={(e) => {
                e.currentTarget.style.transform = 'translateY(0)';
                e.currentTarget.style.borderColor = '#1e293b';
            }}
        >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <div style={{
                        padding: '8px',
                        borderRadius: '6px',
                        backgroundColor: `${color}20`,
                        color: color
                    }}>
                        <Icon size={20} />
                    </div>
                    <h3 style={{ margin: 0, fontSize: '16px', fontWeight: '600', color: '#e2e8f0' }}>{title}</h3>
                </div>
            </div>

            <p style={{ margin: 0, fontSize: '13px', color: '#94a3b8', lineHeight: '1.5' }}>
                {description}
            </p>

            <Link to={to} style={{
                marginTop: '5px',
                display: 'flex',
                alignItems: 'center',
                gap: '5px',
                fontSize: '13px',
                fontWeight: 'bold',
                color: color,
                textDecoration: 'none'
            }}>
                Go to Module <ArrowRight size={14} />
            </Link>
        </div>
    );
};

export default DashboardHome;
