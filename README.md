# EDA: Optimising NYC Taxi Operations

Exploratory data analysis of 2023 NYC Yellow Taxi trip records (upGrad assignment EDA/02).

## Files

| File | Contents |
|---|---|
| `notebooks/EDA_Optimising_NYC_Taxis_Ishan_Ghosh.ipynb` | The upGrad starter notebook with every task (1.1.1 – 3.2.16) filled in. Headings and questions are unchanged; answers are added as cells below each question. |
| `tools/build_notebook.py` | Rebuilds the notebook from the starter: `python tools/build_notebook.py <starter.ipynb> <output.ipynb>` |

## Running

1. In the **Project settings** cell, set `project_dir` to your project folder.
2. Expected layout:
   ```
   <project_dir>/
   ├── data/
   │   └── yellow_tripdata_2023-01.parquet … yellow_tripdata_2023-12.parquet
   └── taxi_zones/
       └── taxi_zones/taxi_zones.shp (+ .shx, .dbf, .prj …)
   ```
3. Run all cells. The sample is saved to `<project_dir>/sampled_taxi_2023.parquet`.

## Assumptions

- **Sampling:** 0.75% of the trips in every date-hour (~290k trips). Each trip carries a `sample_weight` (trips in its date-hour ÷ trips sampled) used to scale counts and revenue to real totals.
- **Negative amounts:** rows with a negative fare or total are reversal records (refunds, disputes, voids) and are dropped; any other negative components are kept and flagged in `has_negative_component`.
- **Missing values:**
  - `passenger_count` and zero counts → mode (1)
  - `RatecodeID` (and invalid code 99) → mode (1)
  - `congestion_surcharge` → mode for the pickup zone
  - `airport_fee` → the airport fee for JFK/LaGuardia pickups, 0 elsewhere
- **Outliers dropped:**
  - passengers > 6
  - distance > 250 miles
  - distance ≈ 0 with fare > 300 USD
  - zero distance and fare between different zones
  - pickups outside 2023
  - duration ≤ 0 or > 24 h
  - speed > 100 mph
- **Recoded:** `payment_type` 0 → 5 (Unknown).
- **Analysis definitions:**
  - night = 11 PM – 5 AM
  - fare per mile uses trips of at least 0.5 miles
  - tip % = tip ÷ fare, credit-card trips only (cash tips are not recorded)
  - speed analysis leaves out same-zone trips and trips over 180 minutes
