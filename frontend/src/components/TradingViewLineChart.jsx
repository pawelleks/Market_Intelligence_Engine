import React, { useEffect, useRef, useState } from 'react';
import { createChart, ColorType, LineSeries, HistogramSeries } from 'lightweight-charts';

const TradingViewLineChart = ({ data, recessions, overlayData = [], overlayLabel = '', height = 500, colors = {} }) => {
    const chartContainerRef = useRef();
    // State for chart instance (ensures effects re-run on creation)
    const [chartInstance, setChartInstance] = useState(null);
    const lineSeriesRef = useRef(null);
    const recessionSeriesRef = useRef(null);
    const overlaySeriesRef = useRef(null); // Second line series for overlay

    // Destructure colors for stable dependencies
    const {
        backgroundColor = '#0e1525',
        textColor = '#d7e3f3',
        lineColor = '#ffffff', // Changed from #2962FF to white
        overlayColor = '#ffeb3b', // Yellow for overlay series
        gridColor = '#203049',
        uSRecColor = 'rgba(128, 128, 128, 0.2)',
    } = colors;

    // 1. Initialization Effect (Run Once)
    useEffect(() => {
        if (!chartContainerRef.current) return;

        // Create Chart
        const chart = createChart(chartContainerRef.current, {
            layout: {
                background: { type: ColorType.Solid, color: backgroundColor },
                textColor: textColor,
            },
            width: chartContainerRef.current.clientWidth,
            height: height,
            grid: {
                vertLines: { color: gridColor },
                horzLines: { color: gridColor },
            },
            timeScale: {
                borderColor: gridColor,
                timeVisible: true,
                secondsVisible: false,
            },
            rightPriceScale: {
                borderColor: gridColor,
            },
        });

        // Initialize Series placeholders
        const recSeries = chart.addSeries(HistogramSeries, {
            priceScaleId: 'rec',
            priceFormat: { type: 'custom', minMove: 1, formatter: () => '' },
        });
        chart.priceScale('rec').applyOptions({
            scaleMargins: { top: 0, bottom: 0 },
            visible: false,
        });

        const lineSeries = chart.addSeries(LineSeries, {
            color: lineColor,
            lineWidth: 2,
        });

        // Create overlay series on RIGHT price scale
        const overlaySeries = chart.addSeries(LineSeries, {
            color: overlayColor,
            lineWidth: 2,
            priceScaleId: 'right', // Separate Y-axis on the right
        });

        recessionSeriesRef.current = recSeries;
        lineSeriesRef.current = lineSeries;
        overlaySeriesRef.current = overlaySeries;

        // Save instance to state to trigger other effects
        setChartInstance(chart);

        // Resize Observer
        const resizeObserver = new ResizeObserver(entries => {
            if (entries.length === 0 || !entries[0].contentRect) return;
            const newWidth = entries[0].contentRect.width;
            if (newWidth > 0) {
                chart.applyOptions({ width: newWidth });
            }
        });
        resizeObserver.observe(chartContainerRef.current);

        // Cleanup
        return () => {
            resizeObserver.disconnect();
            chart.remove();
            setChartInstance(null);
        };
    }, []); // Empty dependency array = Mount/Unmount only

    // 2. Data Update Effect
    useEffect(() => {
        if (!chartInstance || !data) return;

        // Prepare Main Series Data
        const lineData = [];
        const sortedData = [...data].filter(d => d.date).sort((a, b) => new Date(a.date) - new Date(b.date));

        sortedData.forEach(d => {
            let dateStr = d.date;
            if (typeof dateStr === 'string' && dateStr.includes('T')) {
                dateStr = dateStr.split('T')[0];
            }
            const val = parseFloat(d.value);
            if (!isNaN(val)) {
                lineData.push({ time: dateStr, value: val });
            }
        });

        // Update Line Series
        if (lineSeriesRef.current) {
            lineSeriesRef.current.setData(lineData);
        }

        // Prepare & Update Recession Data (Filter to match data date range)
        if (recessionSeriesRef.current && lineData.length > 0) {
            let recessionData = [];
            if (recessions && recessions.length > 0) {
                // Get min/max dates from actual data
                const minDataDate = new Date(lineData[0].time);
                const maxDataDate = new Date(lineData[lineData.length - 1].time);

                // Create a Set of recession dates for quick lookup
                const recessionDates = new Set();
                recessions.forEach(d => {
                    if (d.date && d.value === 1) {
                        let rDate = d.date;
                        if (typeof rDate === 'string' && rDate.includes('T')) {
                            rDate = rDate.split('T')[0];
                        }
                        const recDate = new Date(rDate);
                        if (recDate >= minDataDate && recDate <= maxDataDate) {
                            recessionDates.add(rDate);
                        }
                    }
                });

                // Create continuous recession bars by filling in ALL dates in the data range
                // For each date in lineData, if it's a recession date, add a high-value bar
                lineData.forEach(point => {
                    if (recessionDates.has(point.time)) {
                        recessionData.push({
                            time: point.time,
                            value: 1000000, // Very high value to span entire chart height
                            color: uSRecColor
                        });
                    }
                });
            }
            recessionSeriesRef.current.setData(recessionData);
        }

        // Zoom to fit ONLY the main data series (not recessions)
        if (lineData.length > 0) {
            chartInstance.timeScale().fitContent();
        }

    }, [chartInstance, data, recessions, uSRecColor]); // Depends on chartInstance

    // NEW: Overlay Data Update Effect
    useEffect(() => {
        if (!chartInstance || !overlaySeriesRef.current) return;

        if (!overlayData || overlayData.length === 0) {
            // Clear overlay series if no data
            overlaySeriesRef.current.setData([]);
            return;
        }

        // Prepare Overlay Series Data (same format as main series)
        const overlayLineData = [];
        const sortedOverlay = [...overlayData].filter(d => d.date).sort((a, b) => new Date(a.date) - new Date(b.date));

        sortedOverlay.forEach(d => {
            let dateStr = d.date;
            if (typeof dateStr === 'string' && dateStr.includes('T')) {
                dateStr = dateStr.split('T')[0];
            }
            const val = parseFloat(d.value);
            if (!isNaN(val)) {
                overlayLineData.push({ time: dateStr, value: val });
            }
        });

        // Update Overlay Series
        overlaySeriesRef.current.setData(overlayLineData);

        // Zoom to fit both series if overlay is present
        if (overlayLineData.length > 0) {
            chartInstance.timeScale().fitContent();
        }

    }, [chartInstance, overlayData]); // Depends on overlay data

    // 3. Options/Colors Update Effect
    useEffect(() => {
        if (!chartInstance) return;

        chartInstance.applyOptions({
            layout: {
                background: { type: ColorType.Solid, color: backgroundColor },
                textColor: textColor
            },
            grid: {
                vertLines: { color: gridColor },
                horzLines: { color: gridColor },
            }
        });

        if (lineSeriesRef.current) {
            lineSeriesRef.current.applyOptions({ color: lineColor });
        }
        if (overlaySeriesRef.current) {
            overlaySeriesRef.current.applyOptions({ color: overlayColor });
        }
    }, [chartInstance, backgroundColor, textColor, gridColor, lineColor, overlayColor]);

    return <div ref={chartContainerRef} style={{ width: '100%', height: height }} />;
};

export default TradingViewLineChart;
