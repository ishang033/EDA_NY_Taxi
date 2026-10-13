"""Fill the upGrad starter notebook with the analysis code.

Starter cells keep their position, headings and questions. Code cells
are filled in place; answers to the notebook's questions are added as
new markdown cells directly below each question.

Usage:
    python tools/build_notebook.py <starter.ipynb> <output.ipynb>
"""

import sys

import nbformat as nbf

CODE = {}      # starter cell index -> code to place in that cell
INSERT = {}    # starter cell index -> list of (cell_type, source) added after it


def insert_after(index, cell_type, source):
    INSERT.setdefault(index, []).append((cell_type, source.strip("\n")))


# ---------------------------------------------------------------------
# 1. Data preparation
# ---------------------------------------------------------------------

CODE[13] = """
# Import warnings
import warnings
warnings.filterwarnings("ignore")
"""

CODE[14] = """
# Import the libraries you will be using for analysis
import os

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import geopandas as gpd  # only for reading and plotting the zone shapefile

pd.set_option("display.max_columns", 50)
sns.set_style("whitegrid")
"""

insert_after(15, "markdown", "### Project settings and helper functions")
insert_after(15, "code", r'''
# ---- Paths: change project_dir to the folder on your machine ----
project_dir = r"D:\Upgrad\Executive Diploma AIML\NY_Yellow_taxi_project"
trip_records_dir = os.path.join(project_dir, "data")
zones_path = os.path.join(project_dir, "data", "taxi_zones", "taxi_zones.shp")
sampled_file = os.path.join(project_dir, "sampled_taxi_2023.parquet")

# ---- Sampling ----
# 0.75% of every date-hour gives roughly 290,000 trips for the year,
# inside the 250,000-300,000 range suggested for this assignment.
sampling_fraction = 0.0075
random_seed = 42

# ---- Analysis assumptions (state these in the report) ----
night_hours = [23, 0, 1, 2, 3, 4]       # 11 PM to 5 AM
airport_fee_zone_ids = [132, 138]       # JFK, LaGuardia (fee is on pickups)
max_passengers = 6                      # yellow-cab legal maximum
max_speed_mph = 100                     # faster than this is a recording error
max_duration_minutes = 180              # longer trips are left out of speed analysis
min_distance_for_rate = 0.5             # very short trips distort fare per mile
min_route_trips = 10                    # sampled trips before a route average is used
min_zone_trips = 50                     # sampled trips before a zone average is used
distance_bins = [0, 2, 5, np.inf]
distance_labels = ["Up to 2 miles", "2 to 5 miles", "Over 5 miles"]

day_order = ["Monday", "Tuesday", "Wednesday", "Thursday",
             "Friday", "Saturday", "Sunday"]
calendar_2023 = pd.Series(pd.date_range("2023-01-01", "2023-12-31", freq="D"))
days_in_2023 = len(calendar_2023)
hours_in_2023 = days_in_2023 * 24

payment_labels = {1: "Credit card", 2: "Cash", 3: "No charge",
                  4: "Dispute", 5: "Unknown", 6: "Voided trip"}
vendor_labels = {1: "Creative Mobile Technologies", 2: "VeriFone",
                 6: "Myle Technologies", 7: "Helix"}


# ---- Helper functions for repeated tasks ----
def plot_bar(data, title, xlabel, ylabel, color="steelblue",
             rotation=0, figsize=(10, 5), labels_fmt=None):
    """Bar chart for a Series or DataFrame with consistent styling."""
    ax = data.plot(kind="bar", figsize=figsize, color=color)
    ax.set(title=title, xlabel=xlabel, ylabel=ylabel)
    plt.xticks(rotation=rotation)
    if labels_fmt:
        for container in ax.containers:
            ax.bar_label(container, fmt=labels_fmt, padding=2)
    plt.tight_layout()
    plt.show()


def plot_line(data, title, xlabel, ylabel, figsize=(12, 5), xticks=None):
    """Line chart with markers for a Series or DataFrame."""
    ax = data.plot(kind="line", marker="o", figsize=figsize)
    ax.set(title=title, xlabel=xlabel, ylabel=ylabel)
    if xticks is not None:
        ax.set_xticks(xticks)
    plt.tight_layout()
    plt.show()


def plot_top_zones(left, right, left_title, right_title, xlabel):
    """Two horizontal bar charts side by side (e.g. pickups vs dropoffs)."""
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    for ax, series, title, color in zip(
        axes, [left, right], [left_title, right_title], ["steelblue", "teal"]
    ):
        series.sort_values().plot(kind="barh", ax=ax, color=color)
        ax.set(title=title, xlabel=xlabel, ylabel="")
    plt.tight_layout()
    plt.show()


def add_zone_names(data, id_column, prefix):
    """Merge zone and borough names onto a frame keyed by a location ID."""
    lookup = zone_lookup.rename(columns={
        "LocationID": id_column,
        "zone": f"{prefix}_zone",
        "borough": f"{prefix}_borough"
    })
    named = data.merge(lookup, on=id_column, how="left")
    # IDs 264/265 are "Unknown" / "Outside of NYC" and have no shape
    named[f"{prefix}_zone"] = named[f"{prefix}_zone"].fillna("Unknown / Outside NYC")
    named[f"{prefix}_borough"] = named[f"{prefix}_borough"].fillna("Unknown")
    return named


def add_distance_tier(data):
    """Label each trip with its distance tier."""
    data["distance_tier"] = pd.cut(data["trip_distance"],
                                   bins=distance_bins, labels=distance_labels)
    return data


def estimated_trips(data, by):
    """Scale sampled trips up to estimated real trips using sample weights."""
    return data.groupby(by)["sample_weight"].sum()


def share_with_charge(data, by, charge_column, min_trips=0):
    """Percentage of trips in each group where a charge was applied."""
    summary = (
        data.assign(charged=data[charge_column].gt(0))
        .groupby(by)
        .agg(sampled_trips=("charged", "size"), share_percent=("charged", "mean"))
    )
    summary["share_percent"] *= 100
    return summary.loc[summary["sampled_trips"] >= min_trips]
''')

CODE[18] = """
# Try loading one file
file_list = sorted(f for f in os.listdir(trip_records_dir) if f.endswith(".parquet"))
print("Monthly files found:", len(file_list))

first_month = pd.read_parquet(os.path.join(trip_records_dir, file_list[0]))
first_month.info()
print(f"\\n{file_list[0]} alone has {len(first_month):,} rows")
del first_month
"""

insert_after(19, "markdown", """
**Answer:** One month has about 3 million rows, so the full year has about 38 million. Combining all twelve months would need several GB of memory and make every groupby and plot slow, so we work with a representative sample instead.
""")

insert_after(20, "markdown", """
**Why sample by date AND hour?** Demand changes by hour *and* by date (weekdays vs weekends, holidays, weather, events). Sampling the same fraction from every hour of every date keeps the sample's shape identical to the full data: no date or hour can end up over- or under-represented by chance. Each sampled trip also gets a `sample_weight` (trips in its date-hour ÷ trips sampled from it), so sampled counts and revenue can be scaled back up to real totals.
""")

CODE[26] = """
# Take a small percentage of entries from each hour of every date.
# Iterating through the monthly data:
#   read a month file -> day -> hour: append sampled data -> move to next hour -> move to next day after 24 hours -> move to next month file
# Create a single dataframe for the year combining all the monthly data

# groupby([date, hour]).sample() does the date and hour loops in one step:
# it samples the same fraction from every date-hour group.
sampled_parts = []
sampling_records = []

for file_name in file_list:
    try:
        # file path for the current file
        file_path = os.path.join(trip_records_dir, file_name)

        # Reading the current file
        monthly_df = pd.read_parquet(file_path)

        pickup = pd.to_datetime(monthly_df["tpep_pickup_datetime"])
        monthly_df["sample_date"] = pickup.dt.date
        monthly_df["sample_hour"] = pickup.dt.hour
        strata = ["sample_date", "sample_hour"]

        # Number of trips in each date-hour, used for the sample weight
        monthly_df["stratum_trips"] = (
            monthly_df.groupby(strata)["VendorID"].transform("size")
        )

        # Sample the same fraction from every hour of every date
        sampled_data = monthly_df.groupby(strata).sample(
            frac=sampling_fraction, random_state=random_seed
        )

        # Weight = trips in the date-hour / trips sampled from it
        sampled_data["sample_weight"] = (
            sampled_data["stratum_trips"]
            / sampled_data.groupby(strata)["VendorID"].transform("size")
        )
        sampled_data = sampled_data.drop(columns=strata + ["stratum_trips"])

        sampled_parts.append(sampled_data)
        sampling_records.append({
            "file": file_name,
            "original_rows": len(monthly_df),
            "sampled_rows": len(sampled_data),
        })
        print(f"{file_name}: {len(monthly_df):,} rows -> {len(sampled_data):,} sampled")
        del monthly_df, sampled_data

    except Exception as e:
        print(f"Error reading file {file_name}: {e}")

# Concatenate the sampled data of all the months into a single dataframe
df = pd.concat(sampled_parts, ignore_index=True)
del sampled_parts

sampling_summary = pd.DataFrame(sampling_records)
display(sampling_summary)
print(f"Total sampled trips: {len(df):,} "
      f"({len(df) / sampling_summary['original_rows'].sum():.2%} of all rows)")
print(f"Sum of sample weights: {df['sample_weight'].sum():,.0f} "
      f"vs original rows: {sampling_summary['original_rows'].sum():,}")
"""

CODE[28] = """
# Store the df in csv/parquet
df.to_parquet(sampled_file, index=False)
print("Saved:", sampled_file)
"""

# ---------------------------------------------------------------------
# 2. Data cleaning
# ---------------------------------------------------------------------

CODE[31] = """
# Load the new data file
df = pd.read_parquet(sampled_file)
print(df.shape)
"""
CODE[32] = "df.head()"
CODE[33] = "df.info()"

CODE[36] = """
# Fix the index and drop any columns that are not needed
df = df.reset_index(drop=True)

# store_and_fwd_flag only records whether the trip record was buffered
# in the vehicle before being sent; it says nothing about demand,
# revenue or service, so it is not needed for this analysis.
df = df.drop(columns=["store_and_fwd_flag"])
print(df.shape)
"""

CODE[38] = """
# Combine the two airport fee columns
# January uses 'airport_fee' and the other months 'Airport_fee',
# so each trip has a value in at most one of them.
if "Airport_fee" in df.columns:
    both_filled = df["airport_fee"].notna() & df["Airport_fee"].notna()
    print("Rows with a value in both columns:", both_filled.sum())

    df["airport_fee"] = df["airport_fee"].combine_first(df["Airport_fee"])
    df = df.drop(columns="Airport_fee")

print("Missing airport_fee after combining:", df["airport_fee"].isna().sum())
"""

CODE[40] = """
# check where values of fare amount are negative
money_columns = ["fare_amount", "extra", "mta_tax", "tip_amount", "tolls_amount",
                 "improvement_surcharge", "total_amount", "congestion_surcharge",
                 "airport_fee"]

negative_fares = df.loc[df["fare_amount"].lt(0)]
print("Trips with negative fare_amount:", len(negative_fares))
negative_fares.head(10)
"""

CODE[42] = """
# Analyse RatecodeID for the negative fare amounts
print("RatecodeID of negative-fare trips:")
display(negative_fares["RatecodeID"].value_counts(dropna=False))

print("Payment type of negative-fare trips:")
display(negative_fares["payment_type"].value_counts(dropna=False))

print("Share of negative-fare trips where every charge is zero or negative:",
      round(negative_fares[money_columns].le(0).all(axis=1).mean() * 100, 1), "%")
"""

CODE[43] = """
# Find which columns have negative values
negative_counts = df[money_columns].lt(0).sum()
negative_counts[negative_counts > 0].to_frame("rows_with_negative_values")
"""

CODE[44] = """
# fix these negative values
# A negative fare or total marks a reversal record (refund, dispute or
# void) that cancels an earlier charge. Turning it positive would count
# the money twice, so these rows are dropped.
reversal_rows = df["fare_amount"].lt(0) | df["total_amount"].lt(0)
print("Reversal rows dropped:", reversal_rows.sum())
df = df.loc[~reversal_rows].copy()

# Remaining negative components sit on otherwise valid trips, so the
# sign is treated as an entry error and the absolute value is kept.
df[money_columns] = df[money_columns].abs()
print("Negative values left:", int(df[money_columns].lt(0).sum().sum()))
"""

CODE[47] = """
# Find the proportion of missing values in each column
missing_percent = df.isna().mean().mul(100).sort_values(ascending=False)
display(missing_percent.round(3).to_frame("missing_percent"))

# Do the missing values fall on the same rows?
missing_columns = missing_percent[missing_percent > 0].index.tolist()
print("Missing-value patterns (True = missing):")
display(df[missing_columns].isna().value_counts().to_frame("rows"))

print("payment_type of rows with missing passenger_count:")
display(df.loc[df["passenger_count"].isna(), "payment_type"].value_counts())
"""

CODE[49] = """
# Display the rows with null values
display(df.loc[df["passenger_count"].isna()].head())

# Impute NaN values in 'passenger_count'
# Most trips carry one passenger, so the mode is the most likely value.
passenger_mode = df["passenger_count"].mode()[0]
print("Mode of passenger_count:", passenger_mode)
df["passenger_count"] = df["passenger_count"].fillna(passenger_mode)
print("Missing passenger_count left:", df["passenger_count"].isna().sum())
"""

insert_after(50, "code", """
# A completed, paid trip carried at least one passenger, so a count of
# 0 is a missed driver entry; replace it with the mode as well.
print("Trips with passenger_count = 0:", df["passenger_count"].eq(0).sum())
df.loc[df["passenger_count"].eq(0), "passenger_count"] = passenger_mode
print("Zero passenger counts left:", df["passenger_count"].eq(0).sum())
""")

CODE[52] = """
# Fix missing values in 'RatecodeID'
display(df["RatecodeID"].value_counts(dropna=False).sort_index())

# 99 is not a rate code in the data dictionary, so it is treated as
# missing. Missing codes are filled with the mode (1 = Standard rate).
df["RatecodeID"] = df["RatecodeID"].replace(99, np.nan)
ratecode_mode = df["RatecodeID"].mode()[0]
df["RatecodeID"] = df["RatecodeID"].fillna(ratecode_mode)
print("RatecodeID filled with:", ratecode_mode)
"""

CODE[54] = """
# handle null values in congestion_surcharge
# The surcharge applies to trips in Manhattan south of 96th Street, so it
# depends on location: fill with the most common value for the same
# pickup zone, and the overall mode for any zone with no known value.
zone_surcharge = df.groupby("PULocationID")["congestion_surcharge"].agg(
    lambda values: values.mode().iloc[0] if values.notna().any() else np.nan
)
df["congestion_surcharge"] = (
    df["congestion_surcharge"]
    .fillna(df["PULocationID"].map(zone_surcharge))
    .fillna(df["congestion_surcharge"].mode()[0])
)
print("Missing congestion_surcharge left:", df["congestion_surcharge"].isna().sum())
display(df["congestion_surcharge"].value_counts().head())
"""

CODE[56] = """
# Handle any remaining missing values
remaining = df.isna().sum()
display(remaining[remaining > 0].to_frame("missing_rows"))

# airport_fee is charged only on pickups at JFK and LaGuardia: fill with
# the usual airport fee for those pickups and 0 everywhere else.
is_airport_pickup = df["PULocationID"].isin(airport_fee_zone_ids)
observed_fee = df.loc[is_airport_pickup & df["airport_fee"].gt(0), "airport_fee"].mode()
airport_fee_value = observed_fee.iloc[0] if not observed_fee.empty else 0

df["airport_fee"] = df["airport_fee"].fillna(
    pd.Series(np.where(is_airport_pickup, airport_fee_value, 0), index=df.index)
)
print("Airport fee used for missing airport pickups:", airport_fee_value)
print("Missing values left in the data:", int(df.isna().sum().sum()))
"""

CODE[59] = """
# Describe the data and check if there are any potential outliers present
display(df.describe(percentiles=[0.01, 0.5, 0.99]).T)

# Check for potential out of place values in various columns
pickup = df["tpep_pickup_datetime"]
duration_minutes = (df["tpep_dropoff_datetime"] - pickup).dt.total_seconds() / 60

out_of_place = pd.Series({
    "pickup outside 2023": (~pickup.between(pd.Timestamp("2023-01-01"),
                                            pd.Timestamp("2024-01-01"),
                                            inclusive="left")).sum(),
    "zero/negative trip duration": duration_minutes.le(0).sum(),
    "trip duration over 24 hours": duration_minutes.gt(24 * 60).sum(),
    "passenger_count over 6": df["passenger_count"].gt(max_passengers).sum(),
    "distance ~0 but fare over 300": (df["trip_distance"].lt(0.1)
                                      & df["fare_amount"].gt(300)).sum(),
    "distance and fare 0, different zones": (df["trip_distance"].eq(0)
                                             & df["fare_amount"].eq(0)
                                             & df["PULocationID"].ne(df["DOLocationID"])).sum(),
    "distance over 250 miles": df["trip_distance"].gt(250).sum(),
    "payment_type 0 (not in dictionary)": df["payment_type"].eq(0).sum(),
    "VendorID not in dictionary": (~df["VendorID"].isin([1, 2])).sum(),
})
display(out_of_place.to_frame("rows"))

fig, axes = plt.subplots(1, 4, figsize=(18, 4))
for ax, column in zip(axes, ["trip_distance", "fare_amount", "tip_amount", "total_amount"]):
    sns.boxplot(x=df[column], ax=ax, color="steelblue")
    ax.set_title(f"{column} (before outlier handling)")
plt.tight_layout()
plt.show()
"""

insert_after(61, "markdown", """
**Approach:**

| Issue | Action | Reason |
|---|---|---|
| `passenger_count` > 6 | Drop | Above a yellow cab's legal capacity and very rare |
| Distance ≈ 0 but fare > 300 USD | Drop | No meter fare can reach this without distance |
| Distance and fare both 0, different zones | Drop | A trip between zones cannot be 0 miles and free |
| Distance > 250 miles | Drop | Impossible within NYC trips (meter/GPS error) |
| Pickup outside 2023 | Drop | Outside the analysis period |
| Duration ≤ 0 or > 24 hours | Drop | Clock errors / meter left running |
| Speed > 100 mph | Drop | Physically impossible in city traffic |
| `payment_type` = 0 | Replace with 5 (Unknown) | Real trips with fares, but the payment method was not recorded |
| `VendorID` 6 | Keep | A valid newer provider, just not in the older dictionary |
| Long trips (> 180 min) | Keep, but leave out of speed analysis | Can be genuine (e.g. long airport waits) |
""")

CODE[63] = """
# remove passenger_count > 6
rows_before = len(df)
df = df.loc[df["passenger_count"].le(max_passengers)].copy()
print("Rows removed:", rows_before - len(df))
"""

CODE[64] = """
# Continue with outlier handling
df["trip_duration"] = (
    df["tpep_dropoff_datetime"] - df["tpep_pickup_datetime"]
).dt.total_seconds() / 60   # minutes

speed_mph = df["trip_distance"] / (df["trip_duration"].where(df["trip_duration"].gt(0)) / 60)

outlier_rules = {
    "pickup outside 2023": ~df["tpep_pickup_datetime"].between(
        pd.Timestamp("2023-01-01"), pd.Timestamp("2024-01-01"), inclusive="left"),
    "distance ~0 but fare over 300": df["trip_distance"].lt(0.1) & df["fare_amount"].gt(300),
    "distance and fare 0, different zones": (df["trip_distance"].eq(0)
                                             & df["fare_amount"].eq(0)
                                             & df["PULocationID"].ne(df["DOLocationID"])),
    "distance over 250 miles": df["trip_distance"].gt(250),
    "zero/negative duration": df["trip_duration"].le(0),
    "duration over 24 hours": df["trip_duration"].gt(24 * 60),
    "speed over 100 mph": speed_mph.gt(max_speed_mph),
}
outlier_flags = pd.DataFrame(outlier_rules)
display(outlier_flags.sum().to_frame("rows_flagged"))

drop_rows = outlier_flags.any(axis=1)
print(f"Rows dropped (any rule): {drop_rows.sum():,} ({drop_rows.mean():.2%})")
df = df.loc[~drop_rows].copy()

# payment_type 0 is not defined in the dictionary; these trips are valid,
# only the payment method is unknown, so they are recoded to 5 = Unknown.
print("payment_type 0 recoded to 5:", df["payment_type"].eq(0).sum())
df["payment_type"] = df["payment_type"].replace(0, 5)
"""

CODE[65] = """
# Do any columns need standardising?
# Counts and codes are whole numbers once missing values are filled.
df["passenger_count"] = df["passenger_count"].astype(int)
df["RatecodeID"] = df["RatecodeID"].astype(int)

# Time features used throughout the EDA
pickup = df["tpep_pickup_datetime"]
df["pickup_date"] = pickup.dt.normalize()
df["pickup_hour"] = pickup.dt.hour
df["pickup_day"] = pickup.dt.day_name()
df["pickup_month"] = pickup.dt.month
df["pickup_quarter"] = pickup.dt.quarter
df["is_weekend"] = pickup.dt.dayofweek >= 5
df["is_night"] = df["pickup_hour"].isin(night_hours)

df["average_speed_mph"] = df["trip_distance"] / (df["trip_duration"] / 60)
df["estimated_revenue"] = df["total_amount"] * df["sample_weight"]

df = df.reset_index(drop=True)
print("Cleaned data:", df.shape)
"""

# ---------------------------------------------------------------------
# 3.1 General EDA
# ---------------------------------------------------------------------

insert_after(69, "markdown", """
**Answer:**
* `VendorID`: Categorical (nominal code for the technology provider)
* `tpep_pickup_datetime`: Datetime (used to derive categorical time features)
* `tpep_dropoff_datetime`: Datetime
* `passenger_count`: Numerical (discrete)
* `trip_distance`: Numerical (continuous)
* `RatecodeID`: Categorical (nominal)
* `PULocationID`: Categorical (nominal zone code; numbers are labels, not quantities)
* `DOLocationID`: Categorical (nominal)
* `payment_type`: Categorical (nominal)
* `pickup_hour`: Categorical (ordinal; 0–23 has an order but is used to group trips)
* `trip_duration`: Numerical (continuous, minutes)

The monetary parameters (`fare_amount`, `extra`, `mta_tax`, `tip_amount`, `tolls_amount`, `improvement_surcharge`, `total_amount`, `congestion_surcharge`, `airport_fee`) are all **numerical (continuous)**.
""")

CODE[72] = """
# Find and show the hourly trends in taxi pickups
hourly_pickups = estimated_trips(df, "pickup_hour").reindex(range(24))
display((hourly_pickups / 1e6).round(2).to_frame("estimated_trips_millions"))
plot_bar(hourly_pickups / 1e6, "Estimated Taxi Pickups by Hour of Day, 2023",
         "Pickup hour", "Estimated trips (millions)")
"""

CODE[73] = """
# Find and show the daily trends in taxi pickups (days of the week)
# 2023 has 53 Sundays and 52 of every other day, so compare the
# average per calendar day rather than the yearly total.
daily_summary = pd.DataFrame({
    "estimated_trips": estimated_trips(df, "pickup_day").reindex(day_order),
    "calendar_days": calendar_2023.dt.day_name().value_counts().reindex(day_order),
})
daily_summary["avg_trips_per_day"] = (
    daily_summary["estimated_trips"] / daily_summary["calendar_days"]
)
display(daily_summary.round(0))
plot_bar(daily_summary["avg_trips_per_day"] / 1e3,
         "Average Daily Taxi Pickups by Day of Week, 2023",
         "Day of week", "Estimated trips per day (thousands)", rotation=45)
"""

CODE[74] = """
# Show the monthly trends in pickups
monthly_pickups = pd.DataFrame({
    "estimated_trips": estimated_trips(df, "pickup_month").reindex(range(1, 13)),
    "days_in_month": calendar_2023.dt.month.value_counts().reindex(range(1, 13)),
})
monthly_pickups["avg_trips_per_day"] = (
    monthly_pickups["estimated_trips"] / monthly_pickups["days_in_month"]
)
display(monthly_pickups.round(0))
plot_bar(monthly_pickups["estimated_trips"] / 1e6,
         "Estimated Taxi Pickups by Month, 2023",
         "Month", "Estimated trips (millions)", color="teal")
"""

CODE[77] = """
# Analyse the above parameters
financial_columns = ["fare_amount", "tip_amount", "total_amount", "trip_distance"]
zero_summary = pd.DataFrame({
    "zero_rows": df[financial_columns].eq(0).sum(),
    "negative_rows": df[financial_columns].lt(0).sum(),
})
zero_summary["zero_percent"] = zero_summary["zero_rows"] / len(df) * 100
display(zero_summary.round(2))

same_zone_zero = df["trip_distance"].eq(0) & df["PULocationID"].eq(df["DOLocationID"])
print("Zero-distance trips that start and end in the same zone:", same_zone_zero.sum())
print("Zero tips by payment type:")
display(df.loc[df["tip_amount"].eq(0), "payment_type"].map(payment_labels).value_counts())
"""

insert_after(78, "markdown", """
**Answer:** Yes. Zero fares and zero distances would distort ratios such as fare per mile and speed (division by zero or meaningless values), so those analyses use a filtered copy. The full cleaned `df` is still kept for counting trips and demand, where every trip counts. Zero **tips** are not removed: most come from cash trips, where tips are not recorded, and the rest are real non-tippers, so dropping them would overstate tipping.
""")

insert_after(79, "markdown", """
**Answer:** Not for every analysis. A zero distance within the same zone is usually a very short trip or a cancelled trip that was still charged, so those trips stay in `df` for demand and revenue. They are only dropped in `df_nonzero`, which is used for distance-based measures (fare vs distance, fare per mile, speed), where a zero distance gives no information.
""")

CODE[80] = """
# Create a df with non zero entries for the selected parameters.
df_nonzero = df.loc[
    df["fare_amount"].gt(0)
    & df["total_amount"].gt(0)
    & df["trip_distance"].gt(0)
].copy()
# Tip zeros are kept (cash tips are not recorded); see the answer above.

df_nonzero["fare_per_mile"] = df_nonzero["fare_amount"] / df_nonzero["trip_distance"]
print(f"Rows in df: {len(df):,} | rows in df_nonzero: {len(df_nonzero):,}")
"""

CODE[82] = """
# Group data by month and analyse monthly revenue
monthly_revenue = df.groupby("pickup_month").agg(
    estimated_revenue=("estimated_revenue", "sum"),
    estimated_trips=("sample_weight", "sum"),
).reindex(range(1, 13))
monthly_revenue["revenue_millions"] = monthly_revenue["estimated_revenue"] / 1e6
monthly_revenue["avg_revenue_per_trip"] = (
    monthly_revenue["estimated_revenue"] / monthly_revenue["estimated_trips"]
)
display(monthly_revenue.round(2))

fig, ax1 = plt.subplots(figsize=(12, 5))
monthly_revenue["revenue_millions"].plot(kind="bar", ax=ax1, color="teal", alpha=0.8)
ax1.set(title="Estimated Monthly Revenue (total_amount), 2023",
        xlabel="Month", ylabel="Revenue (USD millions)")
ax1.tick_params(axis="x", rotation=0)
ax2 = ax1.twinx()
ax2.plot(range(12), monthly_revenue["avg_revenue_per_trip"], color="darkorange",
         marker="o", label="Average revenue per trip")
ax2.set_ylabel("Average revenue per trip (USD)")
ax2.grid(False)
ax2.legend(loc="upper left")
plt.tight_layout()
plt.show()
"""

CODE[84] = """
# Calculate proportion of each quarter
quarterly_revenue = df.groupby("pickup_quarter")["estimated_revenue"].sum()
quarterly_share = quarterly_revenue / quarterly_revenue.sum() * 100
display(pd.DataFrame({"revenue_millions": quarterly_revenue / 1e6,
                      "share_percent": quarterly_share}).round(2))

plot_bar(quarterly_share.rename(index=lambda q: f"Q{q}"),
         "Share of 2023 Revenue by Quarter", "Quarter",
         "Share of yearly revenue (%)", color="teal", figsize=(8, 5),
         labels_fmt="%.1f%%")
"""

CODE[86] = """
# Show how trip fare is affected by distance
distance_fare_corr = df_nonzero["trip_distance"].corr(df_nonzero["fare_amount"])
print(f"Correlation between trip_distance and fare_amount: {distance_fare_corr:.3f}")

plot_sample = df_nonzero.sample(n=min(30_000, len(df_nonzero)), random_state=random_seed)
plot_sample["rate"] = np.where(plot_sample["RatecodeID"].eq(2), "JFK flat fare", "Other rates")

plt.figure(figsize=(10, 6))
sns.scatterplot(data=plot_sample, x="trip_distance", y="fare_amount",
                hue="rate", alpha=0.25, s=8)
plt.title("Trip Distance vs Fare Amount (random sample of 30,000 trips)")
plt.xlabel("Trip distance (miles)")
plt.ylabel("Fare amount (USD)")
plt.xlim(0, df_nonzero["trip_distance"].quantile(0.995))
plt.ylim(0, df_nonzero["fare_amount"].quantile(0.995))
plt.tight_layout()
plt.show()
"""

CODE[88] = """
# Show relationship between fare and trip duration
duration_fare_corr = df_nonzero["trip_duration"].corr(df_nonzero["fare_amount"])
print(f"Correlation between trip duration and fare_amount: {duration_fare_corr:.3f}")

plt.figure(figsize=(10, 6))
plt.scatter(plot_sample["trip_duration"], plot_sample["fare_amount"], alpha=0.2, s=8)
plt.title("Trip Duration vs Fare Amount (random sample)")
plt.xlabel("Trip duration (minutes)")
plt.ylabel("Fare amount (USD)")
plt.xlim(0, df_nonzero["trip_duration"].quantile(0.995))
plt.ylim(0, df_nonzero["fare_amount"].quantile(0.995))
plt.tight_layout()
plt.show()
"""

CODE[89] = """
# Show relationship between fare and number of passengers
passenger_fare_corr = df_nonzero["passenger_count"].corr(df_nonzero["fare_amount"])
print(f"Correlation between passenger_count and fare_amount: {passenger_fare_corr:.3f}")
display(df_nonzero.groupby("passenger_count")["fare_amount"]
        .agg(["size", "mean", "median"]).round(2))

plt.figure(figsize=(10, 5))
sns.boxplot(data=df_nonzero, x="passenger_count", y="fare_amount",
            showfliers=False, color="steelblue")
plt.title("Fare Amount by Passenger Count (outliers hidden)")
plt.xlabel("Passenger count")
plt.ylabel("Fare amount (USD)")
plt.tight_layout()
plt.show()
"""

CODE[90] = """
# Show relationship between tip and trip distance
# Cash tips are not recorded, so credit-card trips give the true picture.
card_nonzero = df_nonzero.loc[df_nonzero["payment_type"].eq(1)]
print(f"Correlation, all trips: {df_nonzero['trip_distance'].corr(df_nonzero['tip_amount']):.3f}")
print(f"Correlation, card trips only: {card_nonzero['trip_distance'].corr(card_nonzero['tip_amount']):.3f}")

card_sample = card_nonzero.sample(n=min(30_000, len(card_nonzero)), random_state=random_seed)
plt.figure(figsize=(10, 6))
plt.scatter(card_sample["trip_distance"], card_sample["tip_amount"],
            alpha=0.2, s=8, color="darkorange")
plt.title("Trip Distance vs Tip Amount (credit-card trips, random sample)")
plt.xlabel("Trip distance (miles)")
plt.ylabel("Tip amount (USD)")
plt.xlim(0, card_nonzero["trip_distance"].quantile(0.995))
plt.ylim(0, card_nonzero["tip_amount"].quantile(0.995))
plt.tight_layout()
plt.show()
"""

CODE[92] = """
# Analyse the distribution of different payment types (payment_type).
payment_summary = (
    df.assign(payment_method=df["payment_type"].map(payment_labels))
    .groupby("payment_method")
    .agg(estimated_trips=("sample_weight", "sum"),
         avg_tip=("tip_amount", "mean"),
         avg_total=("total_amount", "mean"))
    .sort_values("estimated_trips", ascending=False)
)
payment_summary["share_percent"] = (
    payment_summary["estimated_trips"] / payment_summary["estimated_trips"].sum() * 100
)
display(payment_summary.round(2))

plot_bar(payment_summary["share_percent"], "Share of Trips by Payment Type, 2023",
         "Payment type", "Share of trips (%)", rotation=30, labels_fmt="%.2f%%")
"""

CODE[99] = """
# import geopandas as gpd


# Read the shapefile using geopandas
zones = gpd.read_file(zones_path)
zones.head()
"""

CODE[101] = """
zones.info()

fig, ax = plt.subplots(figsize=(10, 10))
zones.plot(column="borough", ax=ax, legend=True, cmap="Set2",
           edgecolor="white", linewidth=0.3)
ax.set_title("NYC Taxi Zones by Borough")
ax.set_axis_off()
plt.show()
"""

CODE[104] = """
# Merge zones and trip records using locationID and PULocationID
# The shapefile repeats a few LocationIDs (zones drawn as several shapes),
# so keep one row per ID; otherwise the merge would duplicate trips.
print("Duplicate LocationIDs in the shapefile:",
      zones["LocationID"].duplicated().sum())
zone_lookup = zones[["LocationID", "zone", "borough"]].drop_duplicates("LocationID")

rows_before = len(df)
df = add_zone_names(df, "PULocationID", "pickup")
df = add_zone_names(df, "DOLocationID", "dropoff")
print("Rows before/after merge:", rows_before, len(df))
print("Trips picked up in zones with no shape (IDs 264/265):",
      (~df["PULocationID"].isin(zone_lookup["LocationID"])).sum())
df[["PULocationID", "pickup_zone", "pickup_borough",
    "DOLocationID", "dropoff_zone", "dropoff_borough"]].head()
"""

CODE[106] = """
# Group data by location and calculate the number of trips
trips_per_zone = (
    df.groupby("PULocationID")
    .agg(sampled_trips=("sample_weight", "size"),
         estimated_trips=("sample_weight", "sum"))
    .rename_axis("LocationID")
    .reset_index()
)
trips_per_zone.sort_values("sampled_trips", ascending=False).head(10)
"""

CODE[108] = """
# Merge trip counts back to the zones GeoDataFrame
zones_with_trips = zones.merge(trips_per_zone, on="LocationID", how="left")
zones_with_trips[["sampled_trips", "estimated_trips"]] = (
    zones_with_trips[["sampled_trips", "estimated_trips"]].fillna(0)
)
zones_with_trips[["LocationID", "zone", "borough", "sampled_trips", "estimated_trips"]].head()
"""

CODE[112] = """
# Define figure and axis
fig, ax = plt.subplots(1, 1, figsize=(12, 10))

# Plot the map and display it
zones_with_trips.plot(
    column="estimated_trips", ax=ax, cmap="OrRd", legend=True,
    edgecolor="grey", linewidth=0.2,
    legend_kwds={"label": "Estimated pickups in 2023", "orientation": "vertical"}
)
ax.set_title("Yellow Taxi Pickups by Zone, 2023")
ax.set_axis_off()
plt.show()
"""

CODE[113] = """
# can you try displaying the zones DF sorted by the number of trips?
# One row per LocationID, so a zone drawn as several shapes (in some
# versions of the shapefile) is not listed or counted twice.
unique_zone_trips = zones_with_trips.drop_duplicates("LocationID")
display(
    unique_zone_trips.sort_values("estimated_trips", ascending=False)
    [["LocationID", "zone", "borough", "estimated_trips"]]
    .head(15).round(0)
)

borough_share = unique_zone_trips.groupby("borough")["estimated_trips"].sum()
display((borough_share / borough_share.sum() * 100).sort_values(ascending=False)
        .round(2).to_frame("share_of_pickups_percent"))
"""

# ---------------------------------------------------------------------
# 3.2 Detailed EDA
# ---------------------------------------------------------------------

CODE[122] = """
# Find routes which have the slowest speeds at different times of the day
# Speed on route X in hour Y = average distance / average duration.
# Same-zone trips are left out (very short, dominated by waiting time),
# as are trips over the duration limit set in the settings cell.
route_trips = df_nonzero.loc[
    df_nonzero["PULocationID"].ne(df_nonzero["DOLocationID"])
    & df_nonzero["trip_duration"].le(max_duration_minutes)
]
route_hour_speed = (
    route_trips.groupby(["PULocationID", "DOLocationID", "pickup_hour"])
    .agg(trips=("trip_distance", "size"),
         avg_distance=("trip_distance", "mean"),
         avg_duration_min=("trip_duration", "mean"))
    .reset_index()
)
route_hour_speed["avg_speed_mph"] = (
    route_hour_speed["avg_distance"] / (route_hour_speed["avg_duration_min"] / 60)
)
reliable_routes = route_hour_speed.loc[route_hour_speed["trips"] >= min_route_trips]
print(f"Route-hour combinations with at least {min_route_trips} trips: {len(reliable_routes):,}")

def name_routes(routes):
    named = add_zone_names(add_zone_names(routes, "PULocationID", "pickup"),
                           "DOLocationID", "dropoff")
    return named[["pickup_zone", "dropoff_zone", "pickup_hour", "trips",
                  "avg_distance", "avg_duration_min", "avg_speed_mph"]].round(2)

print("Ten slowest route-hours overall:")
display(name_routes(reliable_routes.nsmallest(10, "avg_speed_mph")))

print("Slowest route in each hour of the day:")
slowest_each_hour = reliable_routes.loc[
    reliable_routes.groupby("pickup_hour")["avg_speed_mph"].idxmin()
]
display(name_routes(slowest_each_hour))

# Typical speed across the week
speed_heatmap = (
    route_trips.pivot_table(index="pickup_day", columns="pickup_hour",
                            values="average_speed_mph", aggfunc="median")
    .reindex(day_order)
)
plt.figure(figsize=(16, 5))
sns.heatmap(speed_heatmap, cmap="RdYlGn", cbar_kws={"label": "Median speed (mph)"})
plt.title("Median Trip Speed by Day and Hour (red = slow)")
plt.xlabel("Pickup hour")
plt.ylabel("")
plt.tight_layout()
plt.show()
"""

insert_after(123, "markdown", """
**Answer:** High-demand routes are where most revenue is earned, and slow routes are where cab time is lost. Knowing both lets dispatch (1) keep more cabs near busy origins at the hours they are busy, (2) avoid sending cabs through routes and hours with very low speeds when an alternative exists, (3) give passengers realistic arrival-time estimates, and (4) price trips on congested routes so time spent in traffic is still paid for.
""")

CODE[125] = """
# Visualise the number of trips per hour and find the busiest hour
hourly_sampled = df.groupby("pickup_hour").size().reindex(range(24), fill_value=0)
busiest_hour = hourly_sampled.idxmax()
print(f"Busiest hour: {busiest_hour}:00 with {hourly_sampled.max():,} sampled trips")

plot_bar(hourly_sampled, "Sampled Trips by Pickup Hour", "Pickup hour",
         "Number of sampled trips")
"""

CODE[128] = """
# Scale up the number of trips

# Fill in the value of your sampling fraction and use that to scale up the numbers
sample_fraction = sampling_fraction   # 0.0075, the fraction used in 1.1.1

busiest_five = hourly_sampled.nlargest(5).to_frame("sampled_trips")
busiest_five["actual_trips_by_fraction"] = busiest_five["sampled_trips"] / sample_fraction
# Cross-check with the exact date-hour weights from sampling
busiest_five["actual_trips_by_weights"] = estimated_trips(df, "pickup_hour").loc[busiest_five.index]
busiest_five["actual_trips_per_day"] = busiest_five["actual_trips_by_weights"] / days_in_2023
busiest_five.round(0)
"""

CODE[130] = """
# Compare traffic trends for the week days and weekends
weekend_days = int((calendar_2023.dt.dayofweek >= 5).sum())
weekday_days = days_in_2023 - weekend_days

hourly_day_type = (
    estimated_trips(df, ["pickup_hour", "is_weekend"])
    .unstack("is_weekend")
    .rename(columns={False: "Weekday", True: "Weekend"})
)
# Average per day, so one weekday is compared with one weekend day
hourly_day_type["Weekday"] /= weekday_days
hourly_day_type["Weekend"] /= weekend_days
display(hourly_day_type.round(0))

plot_line(hourly_day_type, "Average Hourly Pickups: Weekday vs Weekend Day",
          "Pickup hour", "Estimated trips per day", xticks=range(24))

# Busy and quiet hours for each day
day_hour_trips = (
    estimated_trips(df, ["pickup_day", "pickup_hour"]).unstack()
    .reindex(day_order)
    .div(calendar_2023.dt.day_name().value_counts().reindex(day_order), axis=0)
)
plt.figure(figsize=(16, 5))
sns.heatmap(day_hour_trips, cmap="YlOrRd", cbar_kws={"label": "Estimated trips per day"})
plt.title("Average Pickups by Day of Week and Hour")
plt.xlabel("Pickup hour")
plt.ylabel("")
plt.tight_layout()
plt.show()
"""

CODE[133] = """
# Find top 10 pickup and dropoff zones
# Average hourly trips = estimated yearly trips / hours in 2023
hourly_pickups_by_zone = estimated_trips(df, "pickup_zone") / hours_in_2023
hourly_dropoffs_by_zone = estimated_trips(df, "dropoff_zone") / hours_in_2023

top_pickup_zones = hourly_pickups_by_zone.nlargest(10)
top_dropoff_zones = hourly_dropoffs_by_zone.nlargest(10)
display(pd.DataFrame({"zone": top_pickup_zones.index,
                      "avg_pickups_per_hour": top_pickup_zones.values.round(1)}))
display(pd.DataFrame({"zone": top_dropoff_zones.index,
                      "avg_dropoffs_per_hour": top_dropoff_zones.values.round(1)}))

plot_top_zones(top_pickup_zones, top_dropoff_zones,
               "Top 10 Pickup Zones", "Top 10 Dropoff Zones",
               "Average trips per hour")

# Hourly pickup and dropoff trends in these zones
for zone_column, top_zones, label, cmap in [
    ("pickup_zone", top_pickup_zones, "Pickups", "Blues"),
    ("dropoff_zone", top_dropoff_zones, "Dropoffs", "Greens"),
]:
    trend = (
        estimated_trips(df.loc[df[zone_column].isin(top_zones.index)],
                        [zone_column, "pickup_hour"])
        .unstack(fill_value=0)
        .reindex(top_zones.index)
        / days_in_2023
    )
    plt.figure(figsize=(16, 5))
    sns.heatmap(trend, cmap=cmap, cbar_kws={"label": "Average trips per day"})
    plt.title(f"Hourly {label} in the Top 10 {label[:-1]} Zones")
    plt.xlabel("Hour of day")
    plt.ylabel("")
    plt.tight_layout()
    plt.show()
"""

CODE[135] = """
# Find the top 10 and bottom 10 pickup/dropoff ratios
zone_flow = pd.concat(
    [df["pickup_zone"].value_counts().rename("pickups"),
     df["dropoff_zone"].value_counts().rename("dropoffs")],
    axis=1
).fillna(0)
# Ignore zones with very few trips, where one trip changes the ratio a lot
zone_flow = zone_flow.loc[zone_flow.sum(axis=1) >= min_zone_trips].copy()
zone_flow["pickup_dropoff_ratio"] = (
    zone_flow["pickups"] / zone_flow["dropoffs"].replace(0, np.nan)
)

print("Highest ratios (more pickups than dropoffs):")
display(zone_flow.nlargest(10, "pickup_dropoff_ratio").round(2))
print("Lowest ratios (more dropoffs than pickups):")
display(zone_flow.nsmallest(10, "pickup_dropoff_ratio").round(2))
"""

CODE[137] = """
# During night hours (11pm to 5am) find the top 10 pickup and dropoff zones
# Note that the top zones should be of night hours and not the overall top zones
night_trips = df.loc[df["is_night"]]
top_night_pickups = estimated_trips(night_trips, "pickup_zone").nlargest(10)
top_night_dropoffs = estimated_trips(night_trips, "dropoff_zone").nlargest(10)
display(top_night_pickups.round(0).to_frame("estimated_night_pickups"))
display(top_night_dropoffs.round(0).to_frame("estimated_night_dropoffs"))

plot_top_zones(top_night_pickups, top_night_dropoffs,
               "Top 10 Night Pickup Zones (11 PM - 5 AM)",
               "Top 10 Night Dropoff Zones (11 PM - 5 AM)",
               "Estimated trips in 2023")
"""

CODE[139] = """
# Filter for night hours (11 PM to 5 AM)
day_night = (
    df.assign(period=np.where(df["is_night"], "Night (11 PM - 5 AM)", "Day (5 AM - 11 PM)"))
    .groupby("period")
    .agg(estimated_revenue=("estimated_revenue", "sum"),
         estimated_trips=("sample_weight", "sum"),
         avg_total_per_trip=("total_amount", "mean"),
         avg_distance=("trip_distance", "mean"))
)
day_night["revenue_share_percent"] = (
    day_night["estimated_revenue"] / day_night["estimated_revenue"].sum() * 100
)
day_night["trip_share_percent"] = (
    day_night["estimated_trips"] / day_night["estimated_trips"].sum() * 100
)
display(day_night.round(2))

plot_bar(day_night[["trip_share_percent", "revenue_share_percent"]],
         "Share of Trips and Revenue: Day vs Night", "", "Share (%)",
         color=["steelblue", "darkorange"], figsize=(8, 5), labels_fmt="%.1f%%")
"""

CODE[142] = """
# Analyse the fare per mile per passenger for different passenger counts
# Trips under the minimum distance are left out: the fixed starting
# fare makes their per-mile value very large and unrepresentative.
rate_trips = add_distance_tier(
    df_nonzero.loc[df_nonzero["trip_distance"].ge(min_distance_for_rate)].copy()
)
rate_trips["vendor"] = rate_trips["VendorID"].map(vendor_labels)

fare_per_passenger = rate_trips.groupby("passenger_count").agg(
    trips=("fare_per_mile", "size"),
    avg_fare_per_mile=("fare_per_mile", "mean"),
)
fare_per_passenger["avg_fare_per_mile_per_passenger"] = (
    fare_per_passenger["avg_fare_per_mile"] / fare_per_passenger.index
)
display(fare_per_passenger.round(2))

plot_bar(fare_per_passenger["avg_fare_per_mile_per_passenger"],
         "Average Fare per Mile per Passenger", "Passenger count",
         "USD per mile per passenger", color="teal", labels_fmt="%.2f")
"""

CODE[144] = """
# Compare the average fare per mile for different days and for different times of the day
fare_per_mile_hour = rate_trips.groupby("pickup_hour")["fare_per_mile"].mean()
fare_per_mile_day = rate_trips.groupby("pickup_day")["fare_per_mile"].mean().reindex(day_order)

fig, axes = plt.subplots(1, 2, figsize=(16, 5))
fare_per_mile_hour.plot(kind="line", marker="o", ax=axes[0], color="steelblue")
axes[0].set(title="Average Fare per Mile by Hour", xlabel="Pickup hour",
            ylabel="USD per mile", xticks=range(24))
fare_per_mile_day.plot(kind="bar", ax=axes[1], color="teal")
axes[1].set(title="Average Fare per Mile by Day of Week", xlabel="",
            ylabel="USD per mile")
axes[1].tick_params(axis="x", rotation=45)
plt.tight_layout()
plt.show()

display(fare_per_mile_hour.round(2).to_frame("avg_fare_per_mile").T)
display(fare_per_mile_day.round(2).to_frame("avg_fare_per_mile"))
"""

CODE[146] = """
# Compare fare per mile for different vendors
vendor_counts = rate_trips["vendor"].value_counts()
main_vendors = vendor_counts[vendor_counts >= min_zone_trips].index
vendor_trips = rate_trips.loc[rate_trips["vendor"].isin(main_vendors)]

display(vendor_trips.groupby("vendor")["fare_per_mile"]
        .agg(["size", "mean", "median"]).round(2))

vendor_hourly = (
    vendor_trips.groupby(["pickup_hour", "vendor"])["fare_per_mile"]
    .mean().unstack("vendor")
)
plot_line(vendor_hourly, "Average Fare per Mile by Vendor and Hour",
          "Pickup hour", "USD per mile", xticks=range(24))
"""

CODE[148] = """
# Defining distance tiers
vendor_tiers = (
    vendor_trips.groupby(["distance_tier", "vendor"], observed=True)["fare_per_mile"]
    .mean().unstack("vendor")
)
display(vendor_tiers.round(2))

plot_bar(vendor_tiers, "Average Fare per Mile by Distance Tier and Vendor",
         "Distance tier", "USD per mile", color=None, labels_fmt="%.2f")
"""

CODE[151] = """
#  Analyze tip percentages based on distances, passenger counts and pickup times
# Credit-card trips only: cash tips are not recorded in the data.
card_trips = add_distance_tier(df_nonzero.loc[df_nonzero["payment_type"].eq(1)].copy())
card_trips["tip_percent"] = card_trips["tip_amount"] / card_trips["fare_amount"] * 100
card_trips["low_tip"] = card_trips["tip_percent"].lt(10)

print(f"Average tip: {card_trips['tip_percent'].mean():.1f}% of fare "
      f"(median {card_trips['tip_percent'].median():.1f}%)")

tip_factors = {
    "distance_tier": "Distance tier",
    "passenger_count": "Passenger count",
    "pickup_hour": "Pickup hour",
}
fig, axes = plt.subplots(1, 3, figsize=(18, 5))
for ax, (column, label) in zip(axes, tip_factors.items()):
    summary = card_trips.groupby(column, observed=True).agg(
        avg_tip_percent=("tip_percent", "mean"),
        low_tip_share=("low_tip", "mean"),
    )
    summary["low_tip_share"] *= 100
    display(summary.round(2))
    summary["avg_tip_percent"].plot(kind="bar", ax=ax, color="darkorange")
    ax.set(title=f"Average Tip % by {label}", xlabel=label, ylabel="Tip (% of fare)")
    ax.tick_params(axis="x", rotation=0)
plt.tight_layout()
plt.show()
"""

CODE[153] = """
# Compare trips with tip percentage < 10% to trips with tip percentage > 25%
tip_group = np.select(
    [card_trips["tip_percent"].lt(10), card_trips["tip_percent"].gt(25)],
    ["Low tip (< 10%)", "High tip (> 25%)"], default="Middle"
)
tip_comparison = (
    card_trips.assign(tip_group=tip_group)
    .loc[lambda data: data["tip_group"].ne("Middle")]
    .groupby("tip_group")
    .agg(trips=("tip_percent", "size"),
         avg_distance=("trip_distance", "mean"),
         avg_duration=("trip_duration", "mean"),
         avg_fare=("fare_amount", "mean"),
         avg_speed=("average_speed_mph", "mean"),
         avg_passengers=("passenger_count", "mean"),
         night_share=("is_night", "mean"),
         airport_rate_share=("RatecodeID", lambda codes: codes.isin([2, 3]).mean()))
)
tip_comparison.round(2).T
"""

CODE[155] = """
# See how passenger count varies across hours and days
passenger_day_hour = df.pivot_table(index="pickup_day", columns="pickup_hour",
                                    values="passenger_count", aggfunc="mean").reindex(day_order)

fig, axes = plt.subplots(1, 2, figsize=(16, 5))
df.groupby("pickup_hour")["passenger_count"].mean().plot(
    kind="line", marker="o", ax=axes[0], color="purple")
axes[0].set(title="Average Passengers per Trip by Hour", xlabel="Pickup hour",
            ylabel="Average passengers", xticks=range(24))
df.groupby("pickup_day")["passenger_count"].mean().reindex(day_order).plot(
    kind="bar", ax=axes[1], color="purple")
axes[1].set(title="Average Passengers per Trip by Day", xlabel="", ylabel="Average passengers")
axes[1].tick_params(axis="x", rotation=45)
plt.tight_layout()
plt.show()

plt.figure(figsize=(16, 5))
sns.heatmap(passenger_day_hour, cmap="Purples", cbar_kws={"label": "Average passengers"})
plt.title("Average Passengers per Trip by Day and Hour")
plt.xlabel("Pickup hour")
plt.ylabel("")
plt.tight_layout()
plt.show()

display((df["passenger_count"].value_counts(normalize=True).sort_index() * 100)
        .round(2).to_frame("share_of_trips_percent"))
"""

CODE[157] = """
# How does passenger count vary across zones
zone_passengers = (
    df.groupby("PULocationID")
    .agg(sampled_trips=("passenger_count", "size"),
         avg_passenger_count=("passenger_count", "mean"),
         group_trip_share=("passenger_count", lambda counts: counts.ge(2).mean() * 100))
    .rename_axis("LocationID")
    .reset_index()
)
zone_passengers = zone_passengers.loc[zone_passengers["sampled_trips"] >= min_zone_trips]
zone_passengers = zone_passengers.merge(zone_lookup, on="LocationID", how="inner")

print("Zones with the highest average passengers per trip:")
display(zone_passengers.nlargest(10, "avg_passenger_count").round(2))
print("Zones with the lowest average passengers per trip:")
display(zone_passengers.nsmallest(10, "avg_passenger_count").round(2))
"""

CODE[158] = """
# For a more detailed analysis, we can use the zones_with_trips GeoDataFrame
# Create a new column for the average passenger count in each zone.
zones_with_trips = zones_with_trips.drop(columns="avg_passenger_count", errors="ignore").merge(
    zone_passengers[["LocationID", "avg_passenger_count"]], on="LocationID", how="left"
)

fig, ax = plt.subplots(1, 1, figsize=(12, 10))
zones_with_trips.plot(
    column="avg_passenger_count", ax=ax, cmap="Purples", legend=True,
    edgecolor="grey", linewidth=0.2,
    missing_kwds={"color": "lightgrey", "label": "Too few trips"},
    legend_kwds={"label": "Average passengers per trip", "orientation": "vertical"}
)
ax.set_title(f"Average Passengers per Pickup by Zone (zones with at least {min_zone_trips} sampled trips)")
ax.set_axis_off()
plt.show()
"""

CODE[161] = """
# How often is each surcharge applied?
surcharge_columns = ["extra", "mta_tax", "improvement_surcharge",
                     "congestion_surcharge", "airport_fee", "tolls_amount"]
surcharge_frequency = (df[surcharge_columns].gt(0).mean() * 100).sort_values(ascending=False)
display(surcharge_frequency.round(2).to_frame("percent_of_trips_charged"))
plot_bar(surcharge_frequency, "How Often Each Charge Is Applied", "Charge",
         "Trips charged (%)", rotation=20, labels_fmt="%.1f%%")

# When: share of trips charged by hour and by day
variable_charges = ["extra", "congestion_surcharge", "airport_fee", "tolls_amount"]
charge_by_hour = pd.DataFrame({
    charge: share_with_charge(df, "pickup_hour", charge)["share_percent"]
    for charge in variable_charges
})
plot_line(charge_by_hour, "Share of Trips Charged, by Pickup Hour",
          "Pickup hour", "Trips charged (%)", xticks=range(24))

charge_by_day = pd.DataFrame({
    charge: share_with_charge(df, "pickup_day", charge)["share_percent"]
    for charge in variable_charges
}).reindex(day_order)
display(charge_by_day.round(1))

# Where: zones with the highest share of trips charged
for charge in ["extra", "congestion_surcharge", "airport_fee", "tolls_amount"]:
    for zone_column in ["pickup_zone", "dropoff_zone"]:
        top = share_with_charge(df, zone_column, charge, min_zone_trips).nlargest(5, "share_percent")
        print(f"Top {zone_column.replace('_', ' ')}s for {charge}:")
        display(top.round(1))
"""


# ---------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------

def build(starter_path, output_path):
    nb = nbf.read(starter_path, as_version=4)
    for index, source in CODE.items():
        assert nb.cells[index].cell_type == "code", f"cell {index} is not code"
        nb.cells[index].source = source.strip("\n")

    new_cells = []
    for index, cell in enumerate(nb.cells):
        new_cells.append(cell)
        for cell_type, source in INSERT.get(index, []):
            maker = nbf.v4.new_code_cell if cell_type == "code" else nbf.v4.new_markdown_cell
            new_cells.append(maker(source))
    nb.cells = new_cells
    # The starter uses format 4.0; 4.5 adds the cell ids new cells carry
    nb.nbformat_minor = max(nb.nbformat_minor, 5)
    for number, cell in enumerate(nb.cells):
        cell.setdefault("id", f"cell-{number}")
    nbf.validate(nb)
    nbf.write(nb, output_path)
    print(f"Wrote {output_path} with {len(nb.cells)} cells")


if __name__ == "__main__":
    build(sys.argv[1], sys.argv[2])
