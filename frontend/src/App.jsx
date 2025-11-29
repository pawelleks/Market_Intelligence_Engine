import { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import './App.css';
import HMMRegimeChart from './components/HMMRegimeChart';
import HMMChartSettings from './components/HMMChartSettings';

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
  const [hmmData, setHmmData] = useState(null);
  const [priceData, setPriceData] = useState(null); // New state for price overlay
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // FIX 6: New API endpoint assumption for fetching features/price data
  const PRICE_URL = `${API_BASE}/features/price/${settings.ticker}`;
  const HMM_URL = `${API_BASE}/hmm/probabilities/${settings.ticker}?n_states=${settings.nStates}&window_years=${settings.windowYears}`;
  const MARK_URL = `${API_BASE}/markov/matrix/${settings.ticker}`;

  useEffect(() => {
    async function fetchData() {
      setLoading(true);
      setError(null);

      try {
        // --- Fetch Markov Data ---
        const markovResponse = await fetch(MARK_URL);
        const markovJson = await markovResponse.json();

        if (!markovResponse.ok) {
          throw new Error(`Markov API Error: ${markovJson.detail}`);
        }
        setMarkovData(markovJson.data);

        // --- Fetch HMM Data ---
        const hmmResponse = await fetch(HMM_URL);
        const hmmJson = await hmmResponse.json();

        if (!hmmResponse.ok) {
          throw new Error(`HMM API Error: ${hmmJson.detail}`);
        }
        setHmmData(hmmJson.data);

        // --- FIX 6: Fetch Price Data for Overlay ---
        // NOTE: We assume a dedicated price/feature endpoint exists or will be created
        const priceResponse = await fetch(PRICE_URL);
        const priceJson = await priceResponse.json();

        if (!priceResponse.ok) {
          throw new Error(`Price API Error: ${priceJson.detail}`);
        }
        setPriceData(priceJson.data);

      } catch (err) {
        console.error("Data Fetch Error:", err);
        setError(err.message || 'Check browser console for network details.');
      } finally {
        setLoading(false);
      }
    }

    fetchData();
  }, [settings]);

  // FIX 6: Return the new priceData state
  return { markovData, hmmData, priceData, loading, error };
};


// --- Individual Page/Module Components ---

const DashboardHome = () => (
  <div style={{ padding: '20px' }}>
    <h2 style={{ fontSize: '1.8rem' }}>Welcome to the Market Intelligence Engine</h2>
    <p>Use the navigation to access Markov, HMM, and Utility pages.</p>
  </div>
);

const HMMRegimePage = ({ settings, setSettings, hmmData, priceData, loading, error }) => {
  // FIX 4: Dynamic summary text based on settings
  const { start, end } = getWindowDates(settings.windowYears);
  const stateNames = settings.nStates === 2 ? 'Binary (Bull/Bear)' : 'Ternary (Bull/Neutral/Bear)';

  const summaryText = `States: ${stateNames} • Window: ${settings.windowYears}Y (${start} → ${end}) • ` +
    `Bull Signal Threshold: ${settings.bullThreshold}% • Bear Signal Threshold: ${settings.bearThreshold}%`;

  return (
    // FIX 7: Use fixed left panel and fluid right panel (flex-grow: 1)
    <div style={{ display: 'flex', gap: '20px', padding: '20px' }}>

      {/* Left Panel: Configuration (Fixed Width) */}
      <div style={{ width: '300px', flexShrink: 0 }}>
        <HMMChartSettings settings={settings} onSettingsChange={setSettings} />

        {/* Status/Debug */}
        <div style={{ padding: '15px', backgroundColor: '#0e1525', borderRadius: '8px', border: '1px solid #203049' }}>
          <h3 style={{ color: '#4caf50', marginTop: '0' }}>Data Status</h3>
          <p style={{ fontSize: '13px' }}>Proxy Status: Active</p>
          <p style={{ fontSize: '13px' }}>HMM Records: {hmmData ? hmmData.length : 'N/A'}</p>
          <p style={{ fontSize: '13px', color: error ? '#f44336' : 'inherit' }}>{error ? `Error: ${error}` : ''}</p>
        </div>
      </div>

      {/* Right Panel: Charts and Display (Fluid Width - FIX 7: flex-grow: 1) */}
      <div style={{ flexGrow: 1, padding: '0 10px', textAlign: 'left' }}>
        <h2 style={{ fontSize: '1.6rem', marginBottom: '5px', textAlign: 'left' }}>HMM Regime Analysis: {settings.ticker}</h2>

        {/* FIX 4: Chart settings text display */}
        <p style={{ color: '#9e9e9e', fontSize: '0.8rem', borderBottom: '1px solid #203049', paddingBottom: '10px', marginBottom: '20px' }}>
          {summaryText}
        </p>

        {loading ? <p>Loading chart...</p> :
          <HMMRegimeChart
            data={hmmData}
            priceData={priceData} // FIX 6: Pass price data
            windowYears={settings.windowYears}
            nStates={settings.nStates}
          />
        }
      </div>
    </div>
  );
};


// --- Main Application Shell ---

function App() {
  const [settings, setSettings] = useState({
    ticker: 'SPY',
    nStates: 3, // Set to 3 States default based on error message 'Ternary' in screenshot
    windowYears: 'Max', // FIX: Default to Max History
    thresholdBPS: 10,
    bullThreshold: 50, // FIX: Default to 50%
    bearThreshold: 50, // FIX: Default to 50%
  });

  // FIX 6: Update hook usage to include priceData
  const { markovData, hmmData, priceData, loading, error } = useAnalyticalData(settings);

  return (
    <Router>
      <div className="App">
        <div style={{ display: 'flex', minHeight: '100vh', backgroundColor: '#0b1220', color: '#d7e3f3' }}>

          {/* Sidebar Navigation */}
          <nav style={{ width: '200px', backgroundColor: '#0e1525', padding: '20px', borderRight: '1px solid #203049', flexShrink: 0 }}>
            <h3 style={{ color: '#9ec4ff' }}>MIE Sections</h3>
            <ul style={{ listStyle: 'none', padding: 0 }}>
              <li><Link to="/" style={{ color: '#d7e3f3', textDecoration: 'none' }}>Dashboard Home</Link></li>
              <li><Link to="/analysis/hmm" style={{ color: '#9ec4ff', textDecoration: 'none' }}>HMM Regimes</Link></li>
              {/* Placeholder for future sections */}
              <li><Link to="/analysis/markov" style={{ color: '#555', textDecoration: 'none' }}>Markov Analysis (WIP)</Link></li>
            </ul>
          </nav>

          {/* Main Content Area */}
          <main style={{ flexGrow: 1, overflowY: 'auto' }}>
            <Routes>
              <Route path="/" element={<DashboardHome />} />
              <Route
                path="/analysis/hmm"
                element={<HMMRegimePage
                  settings={settings}
                  setSettings={setSettings}
                  hmmData={hmmData}
                  priceData={priceData} // FIX 6: Pass price data
                  loading={loading}
                  error={error}
                />}
              />
              {/* Future Nested Routes will go here */}
              <Route path="/analysis/markov" element={<h2>Markov Section Placeholder</h2>} />
            </Routes>
          </main>

        </div>
      </div>
    </Router>
  );
}

export default App;
