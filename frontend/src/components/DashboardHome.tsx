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
    TrendingUp
} from 'lucide-react';

const DashboardHome = () => {
    return (
        <div style={{ padding: '40px', color: '#e0e0e0', backgroundColor: '#0b1220', minHeight: '100vh', display: 'flex', flexDirection: 'column', gap: '40px' }}>

            {/* Header Section */}
            <div style={{ textAlign: 'center', marginBottom: '20px' }}>
                <h1 style={{ fontSize: '36px', fontWeight: 'bold', color: '#fff', marginBottom: '10px' }}>
                    Welcome to the Quant Terminal
                </h1>
                <p style={{ fontSize: '18px', color: '#94a3b8' }}>
                    Select a module below to begin your analysis.
                </p>
            </div>

            {/* Grid Layout */}
            <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
                gap: '30px',
                maxWidth: '1400px',
                margin: '0 auto',
                width: '100%'
            }}>
                {/* Column 1: Long Term Investing */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                    <h2 style={{ fontSize: '20px', fontWeight: 'bold', color: '#4ade80', borderBottom: '1px solid #1e293b', paddingBottom: '10px' }}>
                        Long Term Investing
                    </h2>

                    <InfoCard
                        title="Trend Command Center"
                        description="Aggregated trend scoring using SMA Stack, ADX, PSAR, and Ichimoku Cloud."
                        to="/investing/trend-matrix"
                        icon={TrendingUp}
                        color="#4ade80"
                    />
                    <InfoCard
                        title="Ichimoku Cloud Report"
                        description="Comprehensive trend confirmation using the Ichimoku Kinko Hyo system."
                        to="/investing/ichimoku"
                        icon={Cloud}
                        color="#4ade80"
                    />
                    <InfoCard
                        title="HMM Regimes"
                        description="Hidden Markov Model analysis to detect latent market regimes (Bull/Bear)."
                        to="/analysis/hmm"
                        icon={Activity}
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
                        description="Verify trend strength by analyzing exponential moving average alignment."
                        to="/analysis/ema-stack"
                        icon={Layers}
                        color="#4ade80"
                    />
                </div>

                {/* Column 2: Trading */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                    <h2 style={{ fontSize: '20px', fontWeight: 'bold', color: '#60a5fa', borderBottom: '1px solid #1e293b', paddingBottom: '10px' }}>
                        Trading
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
                        title="Seasonality & Time"
                        description="Analyze historical returns across monthly and intraday timeframes."
                        to="/market/seasonality"
                        icon={Calendar}
                        color="#60a5fa"
                    />
                </div>

                {/* Column 3: Advanced Analytics */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                    <h2 style={{ fontSize: '20px', fontWeight: 'bold', color: '#a78bfa', borderBottom: '1px solid #1e293b', paddingBottom: '10px' }}>
                        Advanced Analytics
                    </h2>

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
