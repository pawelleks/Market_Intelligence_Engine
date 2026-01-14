
import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { GoogleOAuthProvider } from '@react-oauth/google';
import { AuthProvider, useAuth } from './context/AuthContext';
// Icons removed (moved to Sidebar)
import PerformancePage from './pages/PerformancePage';
import './App.css';
import HMMRegimeChart from './components/HMMRegimeChart';
import HMMChartSettings from './components/HMMChartSettings';
import HMMStatsTable from './components/HMMStatsTable';
import HMMTransitionTable from './components/HMMTransitionTable';

import MarkovTransitionMatrix from './components/MarkovTransitionMatrix';
import MarkovSettings from './components/MarkovSettings';
import MarkovMultiStepForecast from './components/MarkovMultiStepForecast';
import MarkovConclusion from './components/MarkovConclusion';
import MarkovMultiStepConclusion from './components/MarkovMultiStepConclusion';
import DowntrendPage from './components/DowntrendPage';
import MarkovOneStepMatrix from './components/MarkovOneStepMatrix';
import PriceReturnsViewerPage from './pages/PriceReturnsViewerPage';
import MinerviniPage from './pages/MinerviniPage';
import MinerviniScannerPage from './pages/MinerviniScannerPage';
import SeasonalityPage from './pages/SeasonalityPage';
import DCSDashboardPage from './pages/DCSDashboardPage';
import ExpectedMovesPage from './pages/ExpectedMovesPage';
import ExpectedMovesPageMassive from './pages/ExpectedMovesPageMassive';
import EMReliabilityPage from './pages/EMReliabilityPage';
import GammaExposurePage from './pages/GammaExposurePage';
import GAFAnalysisPage from './pages/GAFAnalysisPage';
import HMMBacktestPage from './pages/HMMBacktestPage';
import HmmSignalsPage from './pages/HmmSignalsPage';
import DataPipelines from './pages/DataPipelines';
import Sidebar from './components/Sidebar';
import TsmomDashboardPage from './pages/TsmomDashboardPage';
import EmaStackReport from './components/EmaStackReport';
import AdxReport from './components/AdxReport';
import PsarReport from './components/PsarReport';
import IchimokuReport from './components/IchimokuReport';
import TrendMatrix from './components/TrendMatrix';
import VolatilityTermStructurePage from './pages/VolatilityTermStructurePage';
import SkewAnalysisPage from './pages/SkewAnalysisPage';
import SectorAnalysisPage from './pages/SectorAnalysisPage';
import AbctPage from './pages/AbctPage';
import HPFilterPage from './pages/HPFilterPage';
import HamiltonPage from './pages/HamiltonPage';
import LiquidityImpulsePage from './pages/LiquidityImpulsePage';
import NfpRecessionPage from './pages/NfpRecessionPage';
import LeiPage from './pages/LeiPage';
import CoiPage from './pages/CoiPage';
import LagPage from './pages/LagPage';
import BusinessCyclePage from './pages/BusinessCyclePage';
import MinskyPage from './pages/MinskyPage';
import EconomyDataViewer from './pages/EconomyDataViewer';
import DataReleasesCalendar from './pages/DataReleasesCalendar';
import EmaRespectCalculator from './pages/EmaRespectCalculator';
import PredictionAnalysisDashboard from './pages/PredictionAnalysisDashboard';
import JpmDashboardOverview from './components/economy/JpmDashboard/Overview';
import JpmIndicatorDetail from './components/economy/JpmDashboard/IndicatorDetail';

// Auth Pages
import LoginPage from './pages/LoginPage';
import UserManagementPage from './pages/admin/UserManagementPage';
import DataManagementPage from './pages/admin/DataManagementPage';
import DailyAnalysisPage from './pages/DailyAnalysisPage';
import VolumeRegimeReport from './pages/VolumeRegimeReport';
import { UserProfile } from './pages/UserProfile'; // New Profile Page
import { TermsModal } from './components/TermsModal'; // New Terms Modal
import VolatilityPage from './pages/VolatilityPage';
import WeeklyEconomicCalendar from './pages/WeeklyEconomicCalendar';
import SocialExportExample from './components/SocialExportExample';
import MarkdownViewer from './components/MarkdownViewer';

// Define API URLs and base settings
const API_BASE = "/api/v1";

// --- Utility: Get date range for display (Dummy function for now) ---
// This assumes the data object includes date metadata (not yet implemented in API, but useful for placeholders)
const getWindowDates = (windowYears) => {
  const today = new Date();
  const end = today.toISOString().slice(0, 10);

  // Check if the value is not a standard number (i.e., 'Max')
  if (windowYears === 'Max' || parseInt(windowYears) > 50) {
    // Fallback to max available date in the feature file (assuming 1993 for SPY)
    return { start: '1993-01-01', end };
  }

  // Standard window calculation
  const years = parseInt(windowYears);
  const startYear = today.getFullYear() - years;
  const start = `${startYear}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
  return { start, end };
};

// --- Data Fetching Logic (Custom Hook) ---

// FIX 6: Added priceData to state management and fetch
const useAnalyticalData = (settings) => {
  const [markovData, setMarkovData] = useState(null);
  const [markovMultiStepData, setMarkovMultiStepData] = useState(null);
  const [hmmData, setHmmData] = useState(null);
  const [hmmStats, setHmmStats] = useState(null);
  const [hmmDurations, setHmmDurations] = useState(null); // New state for durations
  const [hmmMetrics, setHmmMetrics] = useState(null); // New state for transition matrix
  const [priceData, setPriceData] = useState(null); // New state for price overlay

  const [latestMarkovState, setLatestMarkovState] = useState(null); // New state for latest context
  const [freshnessStatus, setFreshnessStatus] = useState(null); // New state for data freshness
  const [priceViewerData, setPriceViewerData] = useState(null); // New state for price viewer
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Derived URLs
  const markovStateMode = settings.nStates === 2 ? 'binary' : 'tri';
  const markovWindow = settings.windowYears === 'Max' ? 'MAX' : `${settings.windowYears}Y`;

  const HMM_URL = `${API_BASE}/hmm/probabilities/${settings.ticker}?n_states=${settings.nStates}&window_years=${settings.windowYears}`;
  const HMM_STATS_URL = `${API_BASE}/hmm/stats/${settings.ticker}?n_states=${settings.nStates}&window_years=${settings.windowYears}`;
  const HMM_METRICS_URL = `${API_BASE}/hmm/metrics/${settings.ticker}?n_states=${settings.nStates}&window_years=${settings.windowYears}`;
  const MARK_MATRIX_URL = `${API_BASE}/markov/matrix/${settings.ticker}?state_mode=${markovStateMode}&window_key=${markovWindow}&threshold_bps=${settings.thresholdBPS}&order=${settings.markovOrder}`;
  const MARK_MULTISTEP_URL = `${API_BASE}/markov/multistep/${settings.ticker}/${markovStateMode}?threshold_bps=${settings.thresholdBPS}`;
  const PRICE_URL = `${API_BASE}/features/price/${settings.ticker}`;
  const FRESHNESS_URL = `${API_BASE}/data/freshness/${settings.ticker}`;
  const PRICE_VIEWER_URL = `${API_BASE}/data/prices/${settings.ticker}?table_rows=${settings.rows}&state_mode=${settings.stateMode}&threshold_bps=${settings.thresholdBPS}`;


  useEffect(() => {
    async function fetchData() {
      setLoading(true);
      setError(null);

      // --- 1. Fetch HMM and Markov Core Data (MUST RUN) ---

      // HMM Probabilities (Critical for HMM Page)
      try {
        const response = await fetch(HMM_URL);
        const json = await response.json();
        if (response.ok) { setHmmData(json.data); } else { throw new Error(json.detail); }
      } catch (err) { console.warn("HMM Probabilities Failed:", err.message); setHmmData(null); }

      // HMM Statistics (Critical for HMM Page)
      try {
        const response = await fetch(HMM_STATS_URL);
        const json = await response.json();
        if (response.ok) {
          setHmmStats(json.data);
          if (json.expected_durations) {
            setHmmDurations(json.expected_durations);
          } else {
            setHmmDurations(null);
          }
        } else { throw new Error(json.detail); }
      } catch (err) { console.warn("HMM Stats Failed:", err.message); setHmmStats(null); setHmmDurations(null); }

      // HMM Metrics (Transition Matrix)
      try {
        const response = await fetch(HMM_METRICS_URL);
        const json = await response.json();
        if (response.ok) { setHmmMetrics(json.data); } else { throw new Error(json.detail); }
      } catch (err) { console.warn("HMM Metrics Failed:", err.message); setHmmMetrics(null); }

      // Markov Matrix (Critical for Markov Page)
      try {
        const response = await fetch(MARK_MATRIX_URL);
        const json = await response.json();
        if (response.ok) { setMarkovData(json.data); } else { throw new Error(json.detail); }
      } catch (err) { console.warn("Markov Matrix Failed:", err.message); setMarkovData(null); }

      // --- 2. Fetch Dependent/Utility Data (Can Fail Gracefully) ---

      // Markov Multi-Step (Can Fail Gracefully if data not generated)
      try {
        const response = await fetch(MARK_MULTISTEP_URL);
        const json = await response.json();
        if (response.ok) { setMarkovMultiStepData(json.data); } else { throw new Error(json.detail); }
      } catch (err) { console.warn("Markov Multi-Step Failed:", err.message); setMarkovMultiStepData(null); }

      // Price Data (Needed for Overlays/Viewer)
      try {
        const response = await fetch(PRICE_URL);
        const json = await response.json();
        if (response.ok) { setPriceData(json.data); } else { throw new Error(json.detail); }
      } catch (err) { console.warn("Price Features Failed:", err.message); setPriceData(null); }

      // Data Freshness Status
      try {
        const response = await fetch(FRESHNESS_URL);
        const json = await response.json();
        if (response.ok) { setFreshnessStatus(json); } else { throw new Error(json.detail); }
      } catch (err) { console.warn("Freshness Check Failed:", err.message); setFreshnessStatus(null); }

      // Price Viewer Data (Utility Page)
      try {
        const response = await fetch(PRICE_VIEWER_URL);
        const json = await response.json();
        if (response.ok) {
          // API now returns chart_data (full) and table_data (limited)
          setPriceViewerData({ chartData: json.chart_data, tableData: json.table_data });
        } else {
          throw new Error(json.detail);
        }
      } catch (err) { console.warn("Price Viewer Data Failed:", err.message); setPriceViewerData(null); }

      setLoading(false);

    }

    fetchData();
  }, [settings]); // Depend on settings change

  // FIX: Calculate Latest Markov State on frontend
  useEffect(() => {
    if (!priceData || priceData.length < 2) {
      setLatestMarkovState(null);
      return;
    }

    // Sort Descending
    const sorted = [...priceData].sort((a, b) => new Date(b.date) - new Date(a.date));
    const order = settings.markovOrder || 1;

    // Need order + 1 days to calculate 'order' returns
    if (sorted.length < order + 1) return;

    const states = [];
    // We walk backwards from the most recent day (index 0 is latest)
    // For Order 1: We need state of Day 0.
    for (let i = 0; i < order; i++) {
      const today = sorted[i];

      // Use pre-calc return or calc it
      let ret = 0;
      // FIX: Backend sends 'ret_1d' or 'return'
      if (today.ret_1d !== undefined && today.ret_1d !== null) {
        ret = today.ret_1d;
      } else if (today.return !== undefined && today.return !== null) {
        ret = today.return;
      } else {
        // Fallback calc
        const nextDay = sorted[i + 1]; // Older
        const pToday = today.adj_close || today.close;
        const pPrev = nextDay.adj_close || nextDay.close;
        if (pPrev) ret = (pToday - pPrev) / pPrev;
      }

      // Classify
      const valBps = parseFloat(settings.thresholdBPS) || 10;
      const thr = valBps / 10000;
      let s = 'N';
      if (settings.stateMode === 'binary') {
        s = ret > 0 ? 'U' : 'D';
      } else {
        if (ret > thr) s = 'U';
        else if (ret < -thr) s = 'D';
        else s = 'N';
      }
      states.unshift(s); // [Oldest ... Newest]
    }

    setLatestMarkovState(states.join('-'));

  }, [priceData, settings.markovOrder, settings.stateMode, settings.thresholdBPS]);

  // Updated return signature
  return { markovData, markovMultiStepData, hmmData, priceData, hmmStats, hmmMetrics, hmmDurations, latestMarkovState, freshnessStatus, priceViewerData, loading, error };
};


// --- Individual Page/Module Components ---

// SidebarLink removed (refactored to Sidebar component)

import DashboardHome from './components/DashboardHome';

// SidebarLink removed (refactored to Sidebar component)


const HMMRegimePage = ({ settings, setSettings, hmmData, priceData, hmmStats, hmmMetrics, hmmDurations, freshnessStatus, loading, error }) => {
  // FIX 4: Dynamic summary text based on settings
  const { start, end } = getWindowDates(settings.windowYears);
  const stateNames = settings.nStates === 2 ? 'Binary (Bull/Bear)' : 'Ternary (Bull/Neutral/Bear)';

  const summaryText = `States: ${stateNames} • Window: ${settings.windowYears}Y (${start} → ${end}) • ` +
    `Bull Signal Threshold: ${settings.bullThreshold}% • Bear Signal Threshold: ${settings.bearThreshold}%`;

  return (
    // FIX 7: Use fixed left panel and fluid right panel (flex-grow: 1)
    <div style={{ display: 'flex', gap: '20px', padding: '20px', width: '100%' }}>

      {/* Left Panel: Configuration (Fixed Width) */}
      <div style={{ width: '270px', flexShrink: 0 }}>
        <HMMChartSettings settings={settings} onSettingsChange={setSettings} />

        {/* Status/Debug */}
        <div style={{ padding: '15px', border: '1px solid #203049', borderRadius: '8px', marginTop: '20px', backgroundColor: '#0e1525', textAlign: 'left' }}>
          <h3 style={{ color: '#4caf50', marginTop: '0' }}>Data Status</h3>
          <p style={{ fontSize: '13px', marginBottom: '8px' }}>Proxy Status: Active</p>

          {/* NEW FRESHNESS DISPLAY */}
          {freshnessStatus && (
            <p style={{ fontSize: '14px', color: freshnessStatus.is_fresh ? '#4caf50' : '#f44336', fontWeight: 'bold' }}>
              Data: {freshnessStatus.ticker} last OHLC day {freshnessStatus.last_date}.
            </p>
          )}
          {freshnessStatus && (
            <p style={{ fontSize: '13px', color: freshnessStatus.is_fresh ? '#4caf50' : '#f44336' }}>
              {freshnessStatus.status_text}
            </p>
          )}
          {/* END NEW FRESHNESS DISPLAY */}

          <p style={{ fontSize: '13px', marginTop: '8px' }}>HMM Records: {hmmData ? hmmData.length : 'N/A'}</p>
          <p style={{ fontSize: '13px', color: error ? '#f44336' : 'inherit' }}>{error ? `Error: ${error}` : ''}</p>
        </div>
      </div>

      {/* Right Panel: Charts and Display (Fluid Width - FIX 7: flex-grow: 1) */}
      <div style={{ flexGrow: 1, padding: '0 10px', textAlign: 'left', minWidth: 0 }}>
        <h2 style={{ fontSize: '1.5rem', marginBottom: '0', textAlign: 'left' }}>HMM Regime Analysis: {settings.ticker}</h2>

        {/* FIX 4: Chart settings text display */}
        <p style={{ color: '#9e9e9e', fontSize: '0.8rem', borderBottom: '1px solid #203049', paddingBottom: '10px', marginBottom: '20px' }}>
          {summaryText}
        </p>

        {/* NEW: Current Regime Statistics Card */}
        {hmmData && hmmData.length > 0 && (
          <div style={{
            backgroundColor: '#1b2a40',
            border: '1px solid #4caf50',
            borderRadius: '8px',
            padding: '20px',
            marginBottom: '30px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            boxShadow: '0 4px 6px rgba(0,0,0,0.3)'
          }}>
            {(() => {
              // 1. Get Current State
              const currentRecord = hmmData[hmmData.length - 1];
              const currentState = currentRecord.hmm_state; // 0, 1, or 2

              // Map ID to Name/Color
              let stateName = "Unknown";
              let stateColor = "#9e9e9e";

              // 1. Try Authentic Name (from API/Parquet merge)
              if (currentRecord.hmm_state_name) {
                stateName = currentRecord.hmm_state_name;
                if (stateName.toLowerCase().includes('bull')) stateColor = '#4caf50';
                else if (stateName.toLowerCase().includes('bear')) stateColor = '#f44336';
                else if (stateName.toLowerCase().includes('neut')) stateColor = '#ffc107';
              }
              // 2. Fallback to Stats Lookup
              else {
                const stats = hmmStats ? hmmStats.find(s => s.state_id === currentState) : null;
                if (stats) {
                  stateName = stats.label || `State ${currentState}`;
                  if (stateName.toLowerCase().includes('bull')) stateColor = '#4caf50';
                  else if (stateName.toLowerCase().includes('bear')) stateColor = '#f44336';
                  else stateColor = '#ffc107';
                }
              }

              // 3. Calculate Duration
              let consecutiveDays = 0;
              let lastChangeDate = currentRecord.date;

              for (let i = hmmData.length - 1; i >= 0; i--) {
                if (hmmData[i].hmm_state === currentState) {
                  consecutiveDays++;
                  lastChangeDate = hmmData[i].date;
                } else {
                  break;
                }
              }

              // 4. Probability of Change (from Matrix)
              let probStay = 0;
              // FIX: hmmMetrics is an array of {metric, value}
              if (hmmMetrics && Array.isArray(hmmMetrics)) {
                const key = `trans_${currentState}_${currentState}`;
                const item = hmmMetrics.find(x => x.metric === key);
                if (item) probStay = item.value;
              }
              const probChange = 1.0 - probStay;

              return (
                <>
                  {/* Left: Ticker & State */}
                  <div>
                    <div style={{ fontSize: '14px', color: '#9e9e9e', textTransform: 'uppercase', letterSpacing: '1px' }}>
                      Current Regime ({settings.ticker}) <span style={{ fontSize: '0.8em', textTransform: 'none', color: '#666' }}>(Debug: ID={currentState}, Name={currentRecord.hmm_state_name || 'null'})</span>
                    </div>
                    <div style={{ fontSize: '32px', fontWeight: 'bold', color: stateColor, marginTop: '5px' }}>
                      {stateName}
                    </div>
                    <div style={{ fontSize: '13px', color: '#d7e3f3', marginTop: '5px' }}>
                      Probability of Change: <span style={{ color: probChange > 0.5 ? '#ff9800' : '#4caf50', fontWeight: 'bold' }}>{(probChange * 100).toFixed(1)}%</span>
                    </div>
                  </div>

                  {/* Right: Duration Stats */}
                  <div style={{ textAlign: 'right', borderLeft: '1px solid #203049', paddingLeft: '30px' }}>
                    <div style={{ marginBottom: '10px' }}>
                      <div style={{ fontSize: '12px', color: '#9e9e9e' }}>DAYS IN STATE</div>
                      <div style={{ fontSize: '24px', fontWeight: 'bold', color: 'white' }}>{consecutiveDays}</div>
                    </div>
                    <div>
                      <div style={{ fontSize: '12px', color: '#9e9e9e' }}>LAST MINOR CHANGE</div>
                      <div style={{ fontSize: '16px', color: 'white' }}>{lastChangeDate.slice(0, 10)}</div>
                    </div>
                  </div>
                </>
              );
            })()}
          </div>
        )}

        {/* Per-State Statistics Table */}
        <h3 style={{ marginTop: '0px', marginBottom: '15px', fontSize: '1.2rem', color: '#d7e3f3', fontWeight: 'bold' }}>
          Per-State Performance Statistics
        </h3>
        <HMMStatsTable
          statsData={hmmStats}
          hmmData={hmmData}
          priceData={priceData}
          bullThreshold={settings.bullThreshold}
          bearThreshold={settings.bearThreshold}
        />

        <div style={{ height: '40px' }}></div> {/* Spacer */}

        {/* Transition Matrix Table */}
        <HMMTransitionTable
          metricsData={hmmMetrics}
          nStates={settings.nStates}
          expectedDurations={hmmDurations} // FIX: Pass durations
        />

        <div style={{ height: '40px' }}></div> {/* Spacer */}

        {loading ? <p>Loading chart...</p> :
          <HMMRegimeChart
            data={hmmData}
            priceData={priceData} // FIX 6: Pass price data
            windowYears={settings.windowYears}
            nStates={settings.nStates}
            ticker={settings.ticker}
            bullThreshold={settings.bullThreshold}
            bearThreshold={settings.bearThreshold}
          />
        }
      </div>
    </div >
  );
};


const MarkovAnalysisPage = ({ settings, setSettings, markovData, markovMultiStepData, freshnessStatus, latestMarkovState, loading, error }) => {
  // Determine the state display for the title
  const stateDisplay = settings.nStates === 2 ? 'Binary (Bull/Bear)' : 'Ternary (Bull/Neutral/Red)';

  // Summary text for the page title area
  const summaryText = `Ticker: ${settings.ticker} • State Mode: ${stateDisplay} • Window: ${settings.windowYears}Y • Threshold: ${settings.thresholdBPS} bps (${(settings.thresholdBPS / 100).toFixed(3)}%) • Order: ${settings.markovOrder}`;

  return (
    <div style={{ display: 'flex', gap: '20px', padding: '20px', width: '100%' }}>

      {/* Left Panel: Configuration (STICKY WRAPPER) */}
      <div style={{
        width: '270px',
        flexShrink: 0,
        textAlign: 'left',
        position: 'sticky', // Apply sticky to the outermost left column
        top: '20px',        // Anchor 20px from the top
        alignSelf: 'flex-start', // Ensures the element doesn't stretch to parent height
        maxHeight: 'calc(100vh - 40px)', // Constrain height to viewport
        overflowY: 'auto',  // Allow the settings panel itself to scroll if it gets too long
      }}>

        <MarkovSettings settings={settings} onSettingsChange={setSettings} />

        {/* Data Status/Debug Box (Must be inside the sticky container) */}
        <div style={{ padding: '10px', border: '1px solid #203049', borderRadius: '8px', marginTop: '20px', backgroundColor: '#0e1525', textAlign: 'left' }}>
          <h3 style={{ color: '#4caf50', paddingTop: '0' }}>Data Status</h3>
          <p style={{ fontSize: '13px', marginBottom: '8px' }}>Proxy Status: Active</p>

          {/* NEW FRESHNESS DISPLAY */}
          {freshnessStatus && (
            <p style={{ fontSize: '14px', color: freshnessStatus.is_fresh ? '#4caf50' : '#f44336', fontWeight: 'bold' }}>
              Data: {freshnessStatus.ticker} last OHLC day {freshnessStatus.last_date}.
            </p>
          )}
          {freshnessStatus && (
            <p style={{ fontSize: '13px', color: freshnessStatus.is_fresh ? '#4caf50' : '#f44336' }}>
              {freshnessStatus.status_text}
            </p>
          )}
          {/* END NEW FRESHNESS DISPLAY */}

          <p style={{ fontSize: '13px', marginTop: '8px' }}>Markov Records: {markovData ? markovData.length : 'N/A'}</p>
          <p style={{ fontSize: '13px', color: error ? '#f44336' : 'inherit' }}>{error ? `Error: ${error}` : 'Data Loaded.'}</p>
        </div>
      </div>

      {/* Right Panel: Charts and Tables (Fluid Width) */}
      <div style={{ flexGrow: 1, padding: '0 10px', textAlign: 'left', minWidth: 0 }}>
        <h2 style={{ fontSize: '1.5rem', marginBottom: '0' }}>Markov Analysis: {settings.ticker}</h2>
        <p style={{ color: '#9e9e9e', fontSize: '0.85rem', borderBottom: '1px solid #203049', paddingBottom: '10px', marginBottom: '20px' }}>
          {summaryText}
        </p>

        {loading ? <p>Loading Markov data...</p> :
          <>
            {/* 1. Transition Matrix Section (Table and Heatmap) */}
            <h3 style={{ fontSize: '1.2rem', color: '#9ec4ff' }}>Transition Matrix: Order {settings.markovOrder}</h3>
            <MarkovTransitionMatrix
              data={markovData}
              settings={settings} // Pass all settings for filtering
            />
            <MarkovConclusion markovData={markovData} settings={settings} latestMarkovState={latestMarkovState} />

            {/* NEW ONE-STEP SECTION */}
            <MarkovOneStepMatrix markovData={markovData} settings={settings} />

            {/* 2. Multi-Step Forecast Section */}
            <div style={{ marginTop: '40px' }}>
              <h3 style={{ fontSize: '1.2rem', color: '#9ec4ff' }}>Multi-Step Forecast (1st-Order Approximation)</h3>
              <p style={{ color: '#9e9e9e', fontSize: '0.9rem', marginBottom: '15px' }}>
                Forecast Horizon: {settings.forecastHorizons.join(', ')} days
              </p>

              <MarkovMultiStepForecast settings={settings} />

              {/* NEW CONCLUSION COMPONENT */}
              <MarkovMultiStepConclusion forecastData={markovMultiStepData} settings={settings} />
            </div>
          </>
        }
      </div>
    </div>
  );
};


// --- Auth & Layout ---

const ProtectedLayout = ({ children }) => {
  const { user } = useAuth();
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  return children;
};

const AdminLayout = ({ children }) => {
  const { user } = useAuth();
  if (!user || !user.is_admin) {
    return <Navigate to="/" replace />;
    // Or show Not Authorized page
  }
  return children;
};

// --- Main Application Shell ---

function AppContent() {
  const { user, logout } = useAuth();
  const [settings, setSettings] = useState({
    ticker: 'SPY',
    nStates: 3, // Default to 3 States (Bull/Neutral/Bear)
    windowYears: 10, // Default to 10 Years
    thresholdBPS: 10, // Default to 10 bps
    bullThreshold: 50,
    bearThreshold: 50,
    markovOrder: 1, // Default Markov Order
    forecastHorizons: ['1', '2', '3', '4'], // Default Horizons for Multi-Step
    // NEW DEFAULTS FOR VIEWER
    rows: 50,
    stateMode: 'tri'
  });

  // FIX 6: Update hook usage to include priceData
  const { markovData, markovMultiStepData, hmmData, priceData, hmmStats, hmmMetrics, hmmDurations, latestMarkovState, freshnessStatus, priceViewerData, loading, error } = useAnalyticalData(settings);

  // --- Terms of Use Logic ---
  const [showTermsModal, setShowTermsModal] = useState(false);
  const { refreshUser } = useAuth(); // Destructure refreshUser

  useEffect(() => {
    // Check if user needs to accept terms
    if (user && (user.needsTermsUpdate || (user.termsAccepted === false))) {
      setShowTermsModal(true);
    } else {
      setShowTermsModal(false);
    }
  }, [user]);

  const handleTermsAccept = async (version) => {
    try {
      const response = await fetch('/api/users/accept-terms', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        },
        body: JSON.stringify({ terms_version: version }),
      });

      if (response.ok) {
        setShowTermsModal(false);
        // Refresh user to update local state logic
        if (refreshUser) refreshUser();
        // Reload page fallback if refreshUser fails to propogate fast enough
        // window.location.reload(); 
      } else {
        alert("Failed to accept terms. Server error.");
      }
    } catch (e) {
      console.error("Terms accept error", e);
      alert("Failed to accept terms. Connection error.");
    }
  };

  const handleTermsDecline = () => {
    logout();
    setShowTermsModal(false);
  };

  return (
    <div className="App">
      <TermsModal
        isOpen={showTermsModal}
        onAccept={handleTermsAccept}
        onDecline={handleTermsDecline}
      />
      <div style={{ display: 'flex', minHeight: '100vh', backgroundColor: '#0b1220', color: '#d7e3f3', width: '100%' }}>

        {/* Sidebar Navigation (Refactored) */}
        <Sidebar user={user} logout={logout} />

        {/* Main Content Area */}
        <main style={{ flexGrow: 1, overflowY: 'auto', padding: '0', width: '100%' }}>
          <Routes>
            <Route path="/" element={<ProtectedLayout><DashboardHome /></ProtectedLayout>} />
            <Route
              path="/analysis/hmm"
              element={<ProtectedLayout><HMMRegimePage
                settings={settings}
                setSettings={setSettings}
                hmmData={hmmData}
                priceData={priceData} // FIX 6: Pass price data
                hmmStats={hmmStats}
                hmmMetrics={hmmMetrics}
                hmmDurations={hmmDurations} // FIX: Pass durations
                freshnessStatus={freshnessStatus} // NEW PROP
                loading={loading}
                error={error}
              /></ProtectedLayout>}
            />
            {/* Future Nested Routes will go here */}
            <Route
              path="/analysis/daily"
              element={<ProtectedLayout><DailyAnalysisPage /></ProtectedLayout>}
            />
            <Route
              path="/analysis/markov"
              element={<ProtectedLayout><MarkovAnalysisPage
                settings={settings}
                setSettings={setSettings}
                markovData={markovData}
                markovMultiStepData={markovMultiStepData}
                latestMarkovState={latestMarkovState} // NEW PROP
                freshnessStatus={freshnessStatus} // NEW PROP
                loading={loading}
                error={error}
              /></ProtectedLayout>}
            />
            <Route path="/analysis/expected-moves" element={<ProtectedLayout><ExpectedMovesPage /></ProtectedLayout>} />
            <Route path="/analysis/expected-moves-massive" element={<ProtectedLayout><ExpectedMovesPageMassive /></ProtectedLayout>} />
            <Route path="/analysis/reliability" element={<ProtectedLayout><EMReliabilityPage /></ProtectedLayout>} />
            <Route
              path="/utility/price-viewer"
              element={<ProtectedLayout><PriceReturnsViewerPage
                settings={settings}
                onSettingsChange={setSettings}
                data={priceViewerData}
                loading={loading}
                error={error}
                freshnessStatus={freshnessStatus}
              /></ProtectedLayout>}
            />
            <Route
              path="/analysis/scanner/minervini"
              element={<ProtectedLayout><MinerviniScannerPage /></ProtectedLayout>}
            />
            <Route
              path="/theory/minervini"
              element={<ProtectedLayout><MinerviniPage settings={settings} setSettings={setSettings} /></ProtectedLayout>}
            />
            <Route
              path="/market/seasonality"
              element={<ProtectedLayout><SeasonalityPage
                settings={settings}
                onSettingsChange={setSettings}
              /></ProtectedLayout>}
            />
            <Route
              path="/analysis/dcs"
              element={<ProtectedLayout><DCSDashboardPage
                settings={settings}
                onSettingsChange={setSettings}
                loading={loading}
                error={error}
              /></ProtectedLayout>}
            />
            <Route
              path="/analysis/downtrend"
              element={<ProtectedLayout><DowntrendPage /></ProtectedLayout>}
            />
            <Route
              path="/analysis/gex"
              element={<ProtectedLayout><GammaExposurePage /></ProtectedLayout>}
            />
            <Route
              path="/analysis/volatility-term-structure"
              element={<ProtectedLayout><VolatilityTermStructurePage /></ProtectedLayout>}
            />
            <Route
              path="/analysis/skew"
              element={<ProtectedLayout><SkewAnalysisPage /></ProtectedLayout>}
            />
            <Route
              path="/analysis/volume"
              element={<ProtectedLayout><VolumeRegimeReport /></ProtectedLayout>}
            />
            <Route
              path="/analysis/volatility"
              element={<ProtectedLayout><VolatilityPage /></ProtectedLayout>}
            />
            <Route
              path="/analysis/neural/gaf"
              element={<ProtectedLayout><GAFAnalysisPage /></ProtectedLayout>}
            />
            <Route path="/hmm-backtest" element={<ProtectedLayout><HMMBacktestPage /></ProtectedLayout>} />
            <Route path="/hmm-signals" element={<ProtectedLayout><HmmSignalsPage /></ProtectedLayout>} />
            <Route path="/analysis/tsmom" element={<ProtectedLayout><TsmomDashboardPage /></ProtectedLayout>} />
            <Route path="/analysis/performance" element={<ProtectedLayout><PerformancePage /></ProtectedLayout>} />
            <Route path="/analysis/sector" element={<ProtectedLayout><SectorAnalysisPage /></ProtectedLayout>} />
            <Route path="/analysis/minsky" element={<ProtectedLayout><MinskyPage /></ProtectedLayout>} />
            <Route path="/analysis/abct" element={<ProtectedLayout><AbctPage /></ProtectedLayout>} />
            <Route path="/analysis/hp-filter" element={<ProtectedLayout><HPFilterPage /></ProtectedLayout>} />
            <Route path="/analysis/hamilton" element={<ProtectedLayout><HamiltonPage /></ProtectedLayout>} />
            <Route path="/analysis/liquidity" element={<ProtectedLayout><LiquidityImpulsePage /></ProtectedLayout>} />
            <Route path="/analysis/nfp-momentum" element={<ProtectedLayout><NfpRecessionPage /></ProtectedLayout>} />
            <Route path="/analysis/lei" element={<ProtectedLayout><LeiPage /></ProtectedLayout>} />
            <Route path="/analysis/prediction" element={<ProtectedLayout><PredictionAnalysisDashboard /></ProtectedLayout>} />
            <Route path="/analysis/coi" element={<ProtectedLayout><CoiPage /></ProtectedLayout>} />
            <Route path="/analysis/lag" element={<ProtectedLayout><LagPage /></ProtectedLayout>} />
            <Route path="/analysis/business-cycle" element={<ProtectedLayout><BusinessCyclePage /></ProtectedLayout>} />

            {/* JPM Dashboard Routes */}
            <Route path="/economy/jpm-dashboard" element={<ProtectedLayout><JpmDashboardOverview /></ProtectedLayout>} />
            <Route path="/economy/jpm-dashboard/:category" element={<ProtectedLayout><JpmIndicatorDetail /></ProtectedLayout>} />

            <Route path="/economy" element={<ProtectedLayout><EconomyDataViewer /></ProtectedLayout>} />
            <Route path="/economy/calendar" element={<ProtectedLayout><DataReleasesCalendar /></ProtectedLayout>} />
            <Route path="/economy/weekly" element={<ProtectedLayout><WeeklyEconomicCalendar /></ProtectedLayout>} />
            <Route path="/dev/social-export" element={<ProtectedLayout><SocialExportExample /></ProtectedLayout>} />
            <Route path="/system/pipelines" element={<ProtectedLayout><DataPipelines /></ProtectedLayout>} />
            <Route path="/analysis/ema-stack/:ticker" element={<ProtectedLayout><EmaStackReport /></ProtectedLayout>} />
            <Route path="/analysis/ema-stack" element={<ProtectedLayout><EmaStackReport /></ProtectedLayout>} />
            <Route path="/analysis/adx/:ticker" element={<ProtectedLayout><AdxReport /></ProtectedLayout>} />
            <Route path="/analysis/adx" element={<ProtectedLayout><AdxReport /></ProtectedLayout>} />
            <Route path="/analysis/psar/:ticker" element={<ProtectedLayout><PsarReport /></ProtectedLayout>} />
            <Route path="/analysis/psar" element={<ProtectedLayout><PsarReport /></ProtectedLayout>} />
            {/* Investing */}
            <Route path="/investing/trend-matrix" element={<ProtectedLayout><TrendMatrix /></ProtectedLayout>} />
            <Route path="/investing/ichimoku/:ticker" element={<ProtectedLayout><IchimokuReport /></ProtectedLayout>} />
            <Route path="/investing/ichimoku" element={<ProtectedLayout><IchimokuReport /></ProtectedLayout>} />
            <Route path="/system/pipelines" element={<ProtectedLayout><DataPipelines /></ProtectedLayout>} />

            {/* Tools */}
            <Route path="/tools/ema-respect" element={<ProtectedLayout><EmaRespectCalculator /></ProtectedLayout>} />
            <Route path="/profile" element={<ProtectedLayout><UserProfile /></ProtectedLayout>} />
            <Route path="/report-viewer" element={<ProtectedLayout><MarkdownViewer /></ProtectedLayout>} />

            {/* Auth Routes */}
            <Route path="/login" element={<LoginPage />} />

            {/* Admin Routes */}
            <Route path="/admin/users" element={<AdminLayout><UserManagementPage /></AdminLayout>} />
            <Route path="/admin/data" element={<AdminLayout><DataManagementPage /></AdminLayout>} />
            {/* Redirect old admin base to users */}
            <Route path="/admin" element={<Navigate to="/admin/users" replace />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}

function App() {
  // Use a placeholder ID if env var is missing, but best to set it.
  const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID || "GOOGLE_CLIENT_ID_MISSING";

  return (
    <GoogleOAuthProvider clientId={clientId}>
      <AuthProvider>
        <Router>
          <AppContent />
        </Router>
      </AuthProvider>
    </GoogleOAuthProvider>
  );
}

export default App;
