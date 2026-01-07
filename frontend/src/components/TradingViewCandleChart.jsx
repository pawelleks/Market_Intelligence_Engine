import React, { useEffect, useRef } from 'react';
import { createChart, ColorType, CandlestickSeries, HistogramSeries } from 'lightweight-charts';

const TradingViewCandleChart = ({ data, height = 500, colors = {} }) => {
    const chartContainerRef = useRef();
    const chartRef = useRef(null); // Use Ref instead of State
    const candleSeriesRef = useRef(null);
    const volumeSeriesRef = useRef(null);

    // Default Colors
    const {
        backgroundColor = '#0e1525',
        textColor = '#d7e3f3',
        upColor = '#d7e3f3',
        downColor = '#0b1220',
        wickUpColor = '#d7e3f3',
        wickDownColor = '#9e9e9e',
        gridColor = '#203049',
    } = colors;

    // 1. Initialization Effect
    useEffect(() => {
        if (!chartContainerRef.current) return;

        // CLEANUP: Explicitly clear container to prevent duplicates
        chartContainerRef.current.innerHTML = '';

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

        chartRef.current = chart;

        // Add Series
        const candlestickSeries = chart.addSeries(CandlestickSeries, {
            upColor: upColor,
            downColor: downColor,
            borderUpColor: upColor,
            borderDownColor: wickDownColor,
            wickUpColor: wickUpColor,
            wickDownColor: wickDownColor,
        });
        candleSeriesRef.current = candlestickSeries;

        const volumeSeries = chart.addSeries(HistogramSeries, {
            priceFormat: { type: 'volume' },
            priceScaleId: '', // Overlay
        });
        volumeSeries.priceScale().applyOptions({
            scaleMargins: { top: 0.8, bottom: 0 },
        });
        volumeSeriesRef.current = volumeSeries;

        // Resize Handler (Window Resize is safer than Observer for now)
        const handleResize = () => {
            if (chartContainerRef.current && chartRef.current) {
                chartRef.current.applyOptions({ width: chartContainerRef.current.clientWidth });
            }
        };
        window.addEventListener('resize', handleResize);

        // Force initial resize to catch layout shifts
        setTimeout(handleResize, 100);

        return () => {
            window.removeEventListener('resize', handleResize);
            chart.remove();
            chartRef.current = null;
        };
    }, []); // Run Once

    // 2. Data Update Effect
    useEffect(() => {
        if (!chartRef.current || !data || data.length === 0) return;

        // Sort Data
        const sortedData = [...data]
            .filter(d => d.Date)
            .sort((a, b) => new Date(a.Date) - new Date(b.Date));

        const candleData = [];
        const volumeData = [];

        sortedData.forEach(d => {
            let dateStr = d.Date;
            if (typeof dateStr === 'string' && dateStr.includes('T')) {
                dateStr = dateStr.split('T')[0];
            }

            const o = parseFloat(d.Open);
            const h = parseFloat(d.High);
            const l = parseFloat(d.Low);
            const c = parseFloat(d.Close);
            const v = parseFloat(d.Volume);

            if (!isNaN(o) && !isNaN(h) && !isNaN(l) && !isNaN(c)) {
                candleData.push({ time: dateStr, open: o, high: h, low: l, close: c });
                if (!isNaN(v)) {
                    const isUp = c >= o;
                    volumeData.push({
                        time: dateStr,
                        value: v,
                        color: isUp ? 'rgba(215, 227, 243, 0.5)' : 'rgba(158, 158, 158, 0.5)',
                    });
                }
            }
        });

        if (candleSeriesRef.current) candleSeriesRef.current.setData(candleData);
        if (volumeSeriesRef.current) volumeSeriesRef.current.setData(volumeData);

        // Default Zoom: Show last 365 days
        if (candleData.length > 0) {
            const totalBars = candleData.length;
            const lastDate = new Date(candleData[totalBars - 1].time);
            const oneYearAgo = new Date(lastDate);
            oneYearAgo.setFullYear(oneYearAgo.getFullYear() - 1);

            // Find the index closest to 365 days ago
            let startIndex = candleData.findIndex(d => new Date(d.time) >= oneYearAgo);
            if (startIndex === -1) startIndex = 0;

            chartRef.current.timeScale().setVisibleLogicalRange({
                from: startIndex,
                to: totalBars + 10, // Add right margin
            });
        }

    }, [data]); // Depend on data

    // 3. Options Update Effect
    useEffect(() => {
        if (!chartRef.current) return;
        chartRef.current.applyOptions({
            layout: { background: { type: ColorType.Solid, color: backgroundColor }, textColor },
            grid: { vertLines: { color: gridColor }, horzLines: { color: gridColor } }
        });
        if (candleSeriesRef.current) {
            candleSeriesRef.current.applyOptions({
                upColor, downColor, borderUpColor: upColor, borderDownColor: wickDownColor, wickUpColor, wickDownColor
            });
        }
    }, [backgroundColor, textColor, gridColor, upColor, downColor, wickUpColor, wickDownColor]);

    return <div ref={chartContainerRef} style={{ width: '100%', height: height }} />;
};

export default TradingViewCandleChart;
