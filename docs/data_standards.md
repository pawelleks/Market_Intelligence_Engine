# Data Standards & Formatting Guidelines

## Unit Abbreviations
To ensure consistency and improve readability across the application (especially on mobile devices), use the following standard abbreviations:

| Unit Type | Old Format | **Standard Format** | Example |
|-----------|------------|---------------------|---------|
| Thousands | "Thousands" | **"K"** | 157K |
| Billions | "Billions $" | **"$B"** | $14.2B |
| Millions | "Millions" | **"M"** | 2.5M |
| Percent | "Percent" | **"%"** | 4.2% |
| Index | "Index" | **"Index"** | 102.5 |
| Basis Points| "Basis Points"| **"bps"** | 25 bps |

## Frontend Implementation
Use the centralized `formatValueWithUnit` utility for all numeric formatting.

```javascript
import { formatValueWithUnit } from 'src/utils/formatters';

// Usage
formatValueWithUnit(150000, 'K'); // Returns "150K"
formatValueWithUnit(4.2, '%');    // Returns "4.2%"
```

## Backend Implementation
The backend API (`jpm_dashboard.py`) automatically standardizes units in `SERIES_UNITS_METADATA`.
When adding new series, ensure their units are mapped to the standard keys in `SERIES_UNITS_METADATA` if they deviate from the default.

## Housing Market Series
New standardized series for Housing Market:
- **Housing Starts**: K
- **Permits**: K
- **Home Sales**: K (New), M (Existing)
- **Mortgage Rates**: %
- **Supply**: months
