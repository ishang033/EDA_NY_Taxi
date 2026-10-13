####### Data Preprocessing and Cleaning ########

# =========================================================
# 1. Import libraries and set working directory
# =========================================================

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px
import numpy as np
import os

os.chdir(
    r"D:\Upgrad\Executive Diploma AIML\NY_Yellow_taxi_project"
)

print("Working directory:", os.getcwd())

sample_fraction = 0.05
random_seed = 42

# Screening assumptions for typical route-speed analysis
max_duration_minutes = 180
max_speed_mph = 100


# =========================================================
# 2. Check that all 12 monthly files exist
# =========================================================

file_paths = [
    f"data/yellow_tripdata_2023-{month:02d}.parquet"
    for month in range(1, 13)
]

missing_files = [
    path for path in file_paths if not os.path.isfile(path)
]

if missing_files:
    raise FileNotFoundError(
        "Missing monthly files:\n" + "\n".join(missing_files)
    )


# =========================================================
# 3. Load and sample one month at a time
# =========================================================

sampled_parts = []
sampling_records = []

for month, file_path in enumerate(file_paths, start=1):
    monthly_df = pd.read_parquet(file_path)

    monthly_sample = monthly_df.sample(
        frac=sample_fraction,
        random_state=random_seed
    ).copy()

    # Preserve which file each sampled record came from
    monthly_sample["source_month"] = month

    # Actual expansion weight accounts for sample-size rounding
    monthly_sample["sample_weight"] = (
        len(monthly_df) / len(monthly_sample)
    )

    sampled_parts.append(monthly_sample)

    sampling_records.append({
        "month": month,
        "original_rows": len(monthly_df),
        "sampled_rows": len(monthly_sample),
        "original_columns": monthly_df.shape[1]
    })

    print(
        f"Month {month:02d}: "
        f"{len(monthly_df):,} original rows "
        f"→ {len(monthly_sample):,} sampled rows"
    )

    del monthly_df, monthly_sample

taxi_df = pd.concat(sampled_parts, ignore_index=True)
sampling_summary = pd.DataFrame(sampling_records)

del sampled_parts

display(sampling_summary)
print("Combined dataset shape:", taxi_df.shape)
display(taxi_df.head())


# =========================================================
#  Inspect original sampled data
# =========================================================

taxi_df.info()

missing_summary = pd.DataFrame({
    "missing_count": taxi_df.isna().sum(),
    "missing_percent": taxi_df.isna().mean() * 100
})

display(
    missing_summary.sort_values(
        "missing_count", ascending=False
    )
)

# Exclude sampling metadata when checking exact trip duplicates
trip_columns = [
    column for column in taxi_df.columns
    if column not in ["source_month", "sample_weight"]
]

print(
    "Exact duplicate trip rows:",
    taxi_df.duplicated(subset=trip_columns).sum()
)

display(
    taxi_df.select_dtypes(include="number").describe().T
)

category_columns = [
    "VendorID",
    "RatecodeID",
    "payment_type",
    "store_and_fwd_flag",
    "passenger_count"
]

for column in category_columns:
    print(f"\n{column}")
    print(
        taxi_df[column]
        .value_counts(dropna=False)
        .sort_index()
    )


# =========================================================
# Create a working copy and fix column names
# =========================================================

taxi_clean = taxi_df.copy()
taxi_clean.columns = taxi_clean.columns.str.strip()

# Merge differently capitalized airport-fee columns.
# Do not silently overwrite conflicting values.
if (
    "airport_fee" in taxi_clean.columns
    and "Airport_fee" in taxi_clean.columns
):
    both_present = (
        taxi_clean["airport_fee"].notna()
        & taxi_clean["Airport_fee"].notna()
    )

    conflicts = (
        both_present
        & taxi_clean["airport_fee"].ne(
            taxi_clean["Airport_fee"]
        )
    )

    print("Rows with both airport-fee values:", both_present.sum())
    print("Conflicting airport-fee values:", conflicts.sum())

    if conflicts.any():
        display(
            taxi_clean.loc[
                conflicts, ["airport_fee", "Airport_fee"]
            ].head(10)
        )

        raise ValueError(
            "Review conflicting airport-fee values before continuing."
        )

    taxi_clean["airport_fee"] = (
        taxi_clean["airport_fee"].combine_first(
            taxi_clean["Airport_fee"]
        )
    )

    taxi_clean = taxi_clean.drop(columns="Airport_fee")

elif "Airport_fee" in taxi_clean.columns:
    taxi_clean = taxi_clean.rename(
        columns={"Airport_fee": "airport_fee"}
    )

if "airport_fee" in taxi_clean.columns:
    print(
        "Missing airport fees after standardization:",
        taxi_clean["airport_fee"].isna().sum()
    )


# =========================================================
# Convert timestamps and calculate duration
# =========================================================

datetime_columns = [
    "tpep_pickup_datetime",
    "tpep_dropoff_datetime"
]

for column in datetime_columns:
    missing_before = taxi_clean[column].isna().sum()

    taxi_clean[column] = pd.to_datetime(
        taxi_clean[column],
        errors="coerce"
    )

    missing_after = taxi_clean[column].isna().sum()

    print(
        f"{column}: "
        f"{missing_after - missing_before:,} additional "
        "missing values after conversion"
    )

taxi_clean["trip_duration_minutes"] = (
    taxi_clean["tpep_dropoff_datetime"]
    - taxi_clean["tpep_pickup_datetime"]
).dt.total_seconds() / 60


# =========================================================
# Audit potential quality issues
# =========================================================

pickup = taxi_clean["tpep_pickup_datetime"]

in_2023 = pickup.between(
    pd.Timestamp("2023-01-01"),
    pd.Timestamp("2024-01-01"),
    inclusive="left"
)

quality_flags = pd.DataFrame({
    "missing_pickup": pickup.isna(),

    "missing_dropoff":
        taxi_clean["tpep_dropoff_datetime"].isna(),

    "pickup_outside_2023":
        pickup.notna() & ~in_2023,

    "zero_or_negative_duration":
        taxi_clean["trip_duration_minutes"].le(0),

    "zero_or_negative_distance":
        taxi_clean["trip_distance"].le(0),

    "zero_or_negative_fare":
        taxi_clean["fare_amount"].le(0),

    "negative_tip":
        taxi_clean["tip_amount"].lt(0),

    "zero_tip":
        taxi_clean["tip_amount"].eq(0),

    "zero_or_negative_total":
        taxi_clean["total_amount"].le(0),

    "missing_passenger_count":
        taxi_clean["passenger_count"].isna(),

    "zero_or_negative_passenger_count":
        taxi_clean["passenger_count"].le(0)
})

quality_counts = quality_flags.sum().sort_values(
    ascending=False
)

display(quality_counts)

# Counts overlap; do not add them to count unique affected rows.


# =========================================================
# Retain pickups within 2023
# =========================================================

taxi_2023 = taxi_clean.loc[in_2023].copy()

print("Rows excluded by year filter:", (~in_2023).sum())
print("2023 rows retained:", len(taxi_2023))

# Preserve original passenger counts.
# Leave missing/nonpositive counts unknown for passenger analysis.
taxi_2023["passenger_count_valid"] = (
    taxi_2023["passenger_count"].where(
        taxi_2023["passenger_count"].gt(0)
    )
)

# Other missing values remain missing.
# Exclude them only where a calculation requires that field.


# =========================================================
# Add time features BEFORE creating analysis copies
# =========================================================

pickup = taxi_2023["tpep_pickup_datetime"]

taxi_2023["pickup_date"] = pickup.dt.normalize()
taxi_2023["pickup_hour"] = pickup.dt.hour
taxi_2023["pickup_day"] = pickup.dt.day_name()
taxi_2023["pickup_month"] = pickup.dt.month
taxi_2023["pickup_quarter"] = pickup.dt.quarter
taxi_2023["is_weekend"] = pickup.dt.dayofweek >= 5


# =========================================================
# Calculate speed and flag extreme values
# =========================================================

positive_distance_duration = (
    taxi_2023["trip_distance"].gt(0)
    & taxi_2023["trip_duration_minutes"].gt(0)
)

taxi_2023["average_speed_mph"] = np.nan

taxi_2023.loc[
    positive_distance_duration, "average_speed_mph"
] = (
    taxi_2023.loc[
        positive_distance_duration, "trip_distance"
    ]
    / (
        taxi_2023.loc[
            positive_distance_duration,
            "trip_duration_minutes"
        ] / 60
    )
)

taxi_2023["long_duration_flag"] = (
    taxi_2023["trip_duration_minutes"].gt(
        max_duration_minutes
    )
)

taxi_2023["high_speed_flag"] = (
    taxi_2023["average_speed_mph"].gt(max_speed_mph)
)

print(
    "Trips exceeding duration threshold:",
    taxi_2023["long_duration_flag"].sum()
)

print(
    "Trips exceeding speed threshold:",
    taxi_2023["high_speed_flag"].sum()
)


# =========================================================
# Inspect outliers without deleting source records
# =========================================================

inspection_columns = [
    "tpep_pickup_datetime",
    "tpep_dropoff_datetime",
    "trip_distance",
    "trip_duration_minutes",
    "average_speed_mph",
    "fare_amount",
    "total_amount",
    "PULocationID",
    "DOLocationID",
    "RatecodeID"
]

print("TEN LARGEST DISTANCES")
display(
    taxi_2023.nlargest(
        10, "trip_distance"
    )[inspection_columns]
)

print("TEN LONGEST DURATIONS")
display(
    taxi_2023.nlargest(
        10, "trip_duration_minutes"
    )[inspection_columns]
)

print("TEN HIGHEST CALCULATED SPEEDS")
display(
    taxi_2023.nlargest(
        10, "average_speed_mph"
    )[inspection_columns]
)


# =========================================================
# Create final datasets for specific analyses
# =========================================================

valid_speed = (
    positive_distance_duration
    & taxi_2023["trip_duration_minutes"].le(
        max_duration_minutes
    )
    & taxi_2023["average_speed_mph"].le(
        max_speed_mph
    )
)

speed_trips = taxi_2023.loc[valid_speed].copy()

# Distance-based fare analysis uses the same trip screening.
# This also excludes records whose speed cannot be assessed.
fare_trips = taxi_2023.loc[
    valid_speed
    & taxi_2023["fare_amount"].gt(0)
].copy()

fare_trips["fare_per_mile"] = (
    fare_trips["fare_amount"]
    / fare_trips["trip_distance"]
)

positive_tip_trips = fare_trips.loc[
    fare_trips["tip_amount"].gt(0)
].copy()

passenger_trips = fare_trips.loc[
    fare_trips["passenger_count_valid"].notna()
].copy()

passenger_trips["fare_per_mile_per_passenger"] = (
    passenger_trips["fare_per_mile"]
    / passenger_trips["passenger_count_valid"]
)

# Credit-card tip analysis includes zero tips.
# Cash tips are not recorded, so do not treat cash zeros
# as evidence that the passenger did not tip.
card_tip_trips = fare_trips.loc[
    fare_trips["payment_type"].eq(1)
    & fare_trips["tip_amount"].ge(0)
].copy()

# Explicit definition: tip as a percentage of base fare
card_tip_trips["tip_percent_of_fare"] = (
    card_tip_trips["tip_amount"]
    / card_tip_trips["fare_amount"]
) * 100

print("2023 pickup records:", len(taxi_2023))
print("Speed-analysis records:", len(speed_trips))
print("Fare-analysis records:", len(fare_trips))
print("Positive-tip records:", len(positive_tip_trips))
print("Passenger-analysis records:", len(passenger_trips))

print(
    "Excluded from speed analysis:",
    (~valid_speed).sum()
)

display(
    speed_trips["average_speed_mph"].describe(
        percentiles=[0.50, 0.95, 0.99]
    )
)


# =========================================================
# Updated missing-value and numeric summaries
# =========================================================

missing_summary_clean = pd.DataFrame({
    "missing_count": taxi_2023.isna().sum(),
    "missing_percent": taxi_2023.isna().mean() * 100
})

display(
    missing_summary_clean.sort_values(
        "missing_count", ascending=False
    )
)

display(
    taxi_2023[
        [
            "trip_distance",
            "trip_duration_minutes",
            "fare_amount",
            "tip_amount",
            "total_amount"
        ]
    ].describe(
        percentiles=[0.01, 0.50, 0.95, 0.99]
    ).T
)


# =========================================================
# First EDA: hourly pickup demand
# =========================================================

hourly_summary = (
    taxi_2023.groupby("pickup_hour")
    .agg(
        sampled_trips=("source_month", "size"),
        estimated_trips=("sample_weight", "sum")
    )
    .reindex(range(24), fill_value=0)
)

display(hourly_summary.round(0))

plt.figure(figsize=(12, 5))

plt.bar(
    hourly_summary.index,
    hourly_summary["sampled_trips"],
    color="steelblue"
)

plt.title("NYC Yellow Taxi Pickups by Hour — 2023 Sample")
plt.xlabel("Pickup Hour")
plt.ylabel("Number of Sampled Trips")
plt.xticks(range(24), rotation=0)
plt.tight_layout()
plt.show()

day_order = [
    "Monday", "Tuesday", "Wednesday", "Thursday",
    "Friday", "Saturday", "Sunday"
]

daily_pickups = (
    taxi_2023.groupby("pickup_day")
    .size()
    .reindex(day_order, fill_value=0)
)

daily_pickups.plot(
    kind="bar",
    figsize=(10, 5),
    color="steelblue"
)

plt.title("NYC Yellow Taxi Pickups by Weekday — 2023 Sample")
plt.xlabel("Day of Week")
plt.ylabel("Number of Sampled Trips")
plt.xticks(rotation=45)
plt.tight_layout()
plt.show()

display(daily_pickups.to_frame("sampled_trips"))

calendar_days = pd.Series(
    pd.date_range("2023-01-01", "2023-12-31", freq="D")
)

weekday_counts = (
    calendar_days.dt.day_name()
    .value_counts()
    .reindex(day_order)
)

weekday_summary = daily_pickups.to_frame("sampled_trips")
weekday_summary["calendar_days"] = weekday_counts

weekday_summary["avg_sampled_trips_per_day"] = (
    weekday_summary["sampled_trips"]
    / weekday_summary["calendar_days"]
)

display(weekday_summary.round(2))

weekday_summary["avg_sampled_trips_per_day"].plot(
    kind="bar",
    figsize=(10, 5),
    color="steelblue"
)

plt.title("Average Daily Pickups by Weekday — 2023 Sample")
plt.xlabel("Day of Week")
plt.ylabel("Average Sampled Trips per Calendar Day")
plt.xticks(rotation=45)
plt.tight_layout()
plt.show()


monthly_pickups = (
    taxi_2023.groupby("pickup_month")
    .size()
    .reindex(range(1, 13), fill_value=0)
)

display(monthly_pickups.to_frame("sampled_trips"))

monthly_pickups.plot(
    kind="bar",
    figsize=(10, 5),
    color="teal"
)

plt.title("NYC Yellow Taxi Pickups by Month — 2023 Sample")
plt.xlabel("Month")
plt.ylabel("Number of Sampled Trips")
plt.xticks(rotation=0)
plt.tight_layout()
plt.show()
