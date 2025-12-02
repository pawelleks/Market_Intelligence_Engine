import { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
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
import MarkovOneStepMatrix from './components/MarkovOneStepMatrix';
import PriceReturnsViewerPage from './pages/PriceReturnsViewerPage';
import MinerviniPage from './pages/MinerviniPage';

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
  const PRICE_VIEWER_URL = `${API_BASE}/data/prices/${settings.ticker}?rows=${settings.rows}&state_mode=${settings.stateMode}&threshold_bps=${settings.thresholdBPS}`;


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
        if (response.ok) { setPriceViewerData(json.data); } else { throw new Error(json.detail); }
      } catch (err) { console.warn("Price Viewer Data Failed:", err.message); setPriceViewerData(null); }

      setLoading(false);

    }

    fetchData();
  }, [settings]); // Depend on settings change

  // Updated return signature
  return { markovData, markovMultiStepData, hmmData, priceData, hmmStats, hmmMetrics, hmmDurations, latestMarkovState, freshnessStatus, priceViewerData, loading, error };
};


// --- Individual Page/Module Components ---

const DashboardHome = () => (
  <div style={{ padding: '20px' }}>
    <h2 style={{ fontSize: '1.8rem' }}>Welcome to the Market Intelligence Engine</h2>
    <p>Use the navigation to access Markov, HMM, and Utility pages.</p>
  </div>
);

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
    </div>
  );
};


const MarkovAnalysisPage = ({ settings, setSettings, markovData, markovMultiStepData, freshnessStatus, loading, error }) => {
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
            <MarkovConclusion markovData={markovData} settings={settings} />

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




// --- Main Application Shell ---

function App() {
  const [settings, setSettings] = useState({
    ticker: 'SPY',
    nStates: 2, // Default to 2 States (Binary)
    windowYears: 20, // Default to 20 Years for a good range
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

  return (
    <Router>
      <div className="App">
        <div style={{ display: 'flex', minHeight: '100vh', backgroundColor: '#0b1220', color: '#d7e3f3', width: '100%' }}>

          {/* Sidebar Navigation */}
          <nav style={{ width: '200px', backgroundColor: '#0e1525', padding: '20px', borderRight: '1px solid #203049', flexShrink: 0, textAlign: 'left' }}>
            <h3 style={{ color: '#9ec4ff' }}>MIE Sections</h3>
            <ul style={{ listStyle: 'none', padding: 0 }}>
              <li><Link to="/" style={{ color: '#d7e3f3', textDecoration: 'none' }}>Dashboard Home</Link></li>
              <li><Link to="/analysis/hmm" style={{ color: '#9ec4ff', textDecoration: 'none' }}>HMM Regimes</Link></li>
              {/* Placeholder for future sections */}
              <li><Link to="/analysis/markov" style={{ color: '#9ec4ff', textDecoration: 'none' }}>Markov Analysis</Link></li>
              <li><Link to="/utility/price-viewer" style={{ color: '#9ec4ff', textDecoration: 'none' }}>Price & Returns Viewer</Link></li>
              <li><Link to="/theory/minervini" style={{ color: '#d7e3f3', textDecoration: 'none' }}>Minervini Template</Link></li>
            </ul>
          </nav>

          {/* Main Content Area */}
          <main style={{ flexGrow: 1, overflowY: 'auto', padding: '0', width: '100%' }}>
            <Routes>
              <Route path="/" element={<DashboardHome />} />
              <Route
                path="/analysis/hmm"
                element={<HMMRegimePage
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
                />}
              />
              {/* Future Nested Routes will go here */}
              <Route
                path="/analysis/markov"
                element={<MarkovAnalysisPage
                  settings={settings}
                  setSettings={setSettings}
                  markovData={markovData}
                  markovMultiStepData={markovMultiStepData}
                  latestMarkovState={latestMarkovState} // NEW PROP
                  freshnessStatus={freshnessStatus} // NEW PROP
                  loading={loading}
                  error={error}
                />}
              />
              <Route
                path="/utility/price-viewer"
                element={<PriceReturnsViewerPage
                  settings={settings}
                  onSettingsChange={setSettings}
                  data={priceViewerData}
                  loading={loading}
                  error={error}
                  freshnessStatus={freshnessStatus}
                />}
              />
              <Route
                path="/theory/minervini"
                element={<MinerviniPage
                  settings={settings}
                  onSettingsChange={setSettings}
                  priceData={priceData} // Pass the price data state
                  loading={loading}
                  error={error}
                />}
              />
            </Routes>
          </main>

        </div>
      </div>
    </Router>
  );
}

export default App;
