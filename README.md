# EDA: Optimising NYC Taxi Operations

Exploratory data analysis of 2023 NYC Yellow Taxi trip records (upGrad assignment EDA/02).

## Files

| File | Contents |
|---|---|
| `notebooks/01_data_preparation_and_cleaning.py` | Sections 1–2 and 3a(ii): sampling, combining, column fixes, missing values, outliers, time features, hourly/weekday/monthly pickups |
| `notebooks/02_eda_and_insights.py` | Sections 2b (missing-value approach), 3a(i), 3a(iv)–(xiv), 3b(i)–(xvi) and key numbers for section 4 |
| `notebooks/EDA_Optimising_NYC_Taxis.ipynb` | Both scripts combined into one notebook, one cell per section |

## Expected data layout

```
<project folder>/
└── data/
    ├── yellow_tripdata_2023-01.parquet … yellow_tripdata_2023-12.parquet
    └── taxi_zones/taxi_zones.shp (+ .shx, .dbf, .prj)
```

Set the `os.chdir(...)` path in the first cell to your project folder.

## Libraries

pandas, numpy, matplotlib, seaborn, plotly, and geopandas (only to read and plot the zone shapefile).

## Assumptions

- 5% random sample per month; `sample_weight` scales sampled counts and revenue to full-year estimates.
- Trips are kept for speed/fare analysis only if distance > 0, 0 < duration ≤ 180 min and speed ≤ 100 mph.
- Revenue = `total_amount` of trips with a positive total.
- Fare-per-mile analyses use trips of at least 0.5 miles (the fixed base fare distorts very short trips).
- Night = 11 PM to 5 AM.
- Tip percentage = tip / fare × 100, credit-card trips only (cash tips are not recorded).
- Route and zone averages require at least 20 / 100 sampled trips respectively.
