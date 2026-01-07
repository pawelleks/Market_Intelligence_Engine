const results = {
    chart_data: [
        { date: '2023-01-01', open: 100, high: 105, low: 95, close: 102, ema_10: 101, bounce_10: 'bullish' },
        { date: '2023-01-02', open: 102, high: 108, low: 101, close: 107, ema_10: 103, bounce_10: null },
        { date: '2023-01-01', open: 100, high: 105, low: 95, close: 102 }, // Duplicate
        { date: '2023-01-03', open: null, close: null } // Invalid
    ]
};

const uniqueDataMap = new Map();
results.chart_data.forEach(item => {
    if (item.date && !uniqueDataMap.has(item.date)) {
        uniqueDataMap.set(item.date, item);
    }
});

const processData = Array.from(uniqueDataMap.values()).sort((a, b) => new Date(a.date) - new Date(b.date));

console.log("Processed Data Length:", processData.length);
console.log("Processed Data:", JSON.stringify(processData, null, 2));

const candleData = processData
    .filter(d => d.open != null && d.close != null)
    .map(d => ({
        time: d.date,
        open: d.open, high: d.high, low: d.low, close: d.close
    }));

console.log("Candle Data Length:", candleData.length);
console.log("Candle Data:", JSON.stringify(candleData, null, 2));
