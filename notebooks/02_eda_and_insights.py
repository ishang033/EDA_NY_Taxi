####### EDA: Patterns, Insights and Strategies ########
#
# Continues from 01_data_preparation_and_cleaning.py.
# Run that file (or those notebook cells) first: this part reuses
# taxi_2023, speed_trips, fare_trips, passenger_trips,
# card_tip_trips, hourly_summary, calendar_days and day_order.


# =========================================================
# Settings for this part
# =========================================================

import geopandas as gpd  # only used to read/plot the zone shapefile

zones_path = "data/taxi_zones/taxi_zones.shp"

# Night = 11 PM to 4:59 AM (assumption; state it in the report)
night_hours = [23, 0, 1, 2, 3, 4]

# Very short trips inflate fare-per-mile because of the fixed
# base fare, so per-mile rates use trips of at least 0.5 miles.
min_distance_for_rate = 0.5

# Minimum sampled trips before a route/zone average is trusted
min_route_trips = 20
min_zone_trips = 100

# Distance tiers used in the vendor and tip analyses
distance_bins = [0, 2, 5, np.inf]
distance_labels = ["Up to 2 miles", "2 to 5 miles", "Over 5 miles"]

days_in_2023 = len(calendar_days)
hours_in_2023 = days_in_2023 * 24

payment_labels = {
    0: "Flex fare / unknown",
    1: "Credit card",
    2: "Cash",
    3: "No charge",
    4: "Dispute",
    5: "Unknown",
    6: "Voided trip"
}

vendor_labels = {
    1: "Creative Mobile Technologies",
    2: "VeriFone (Curb)",
    6: "Myle Technologies",
    7: "Helix"
}


# =========================================================
# Helper functions for repeated tasks
# =========================================================

def plot_bar(data, title, xlabel, ylabel, color="steelblue",
             rotation=0, figsize=(10, 5), horizontal=False):
    """Bar chart for a Series or DataFrame with consistent styling."""
    kind = "barh" if horizontal else "bar"
    ax = data.plot(kind=kind, figsize=figsize, color=color)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    if not horizontal:
        plt.xticks(rotation=rotation)
    plt.tight_layout()
    plt.show()


def plot_line(data, title, xlabel, ylabel, figsize=(12, 5), xticks=None):
    """Line chart with markers for a Series or DataFrame."""
    ax = data.plot(kind="line", marker="o", figsize=figsize)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    if xticks is not None:
        ax.set_xticks(xticks)
    ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.show()


def add_zone_names(df, id_column, prefix):
    """Attach zone and borough names to a frame keyed by a location ID."""
    lookup = zone_lookup.rename(columns={
        "LocationID": id_column,
        "zone": f"{prefix}_zone",
        "borough": f"{prefix}_borough"
    })
    named = df.merge(lookup, on=id_column, how="left")
    # IDs 264/265 (Unknown / Outside NYC) have no shape in the file
    named[f"{prefix}_zone"] = named[f"{prefix}_zone"].fillna("Unknown / Outside NYC")
    named[f"{prefix}_borough"] = named[f"{prefix}_borough"].fillna("Unknown")
    return named


def add_distance_tier(df):
    """Label each trip with its distance tier."""
    df["distance_tier"] = pd.cut(
        df["trip_distance"],
        bins=distance_bins,
        labels=distance_labels
    )
    return df


def flag_share_by(df, group_column, flag, min_trips=0):
    """Percentage of trips in each group where a boolean flag is True."""
    summary = (
        df.assign(flag=flag)
        .groupby(group_column)
        .agg(sampled_trips=("flag", "size"),
             share_percent=("flag", "mean"))
    )
    summary["share_percent"] *= 100
    return summary.loc[summary["sampled_trips"] >= min_trips]


# =========================================================
# 2b. Handling missing values: pattern and approach
# =========================================================

missing_columns = [
    "passenger_count",
    "RatecodeID",
    "store_and_fwd_flag",
    "congestion_surcharge",
    "airport_fee"
]

# Each row of this table is one missing/not-missing pattern.
# If almost all missing values fall in a single pattern, the
# same records lack every optional field together.
missing_patterns = (
    taxi_2023[missing_columns]
    .isna()
    .value_counts()
    .to_frame("rows")
)
missing_patterns["percent"] = (
    missing_patterns["rows"] / len(taxi_2023) * 100
)
display(missing_patterns.round(2))

print("Payment type of records with missing passenger_count:")
display(
    taxi_2023.loc[
        taxi_2023["passenger_count"].isna(), "payment_type"
    ].value_counts(dropna=False)
)

# Approach: EDA does not require filling these values, so the
# analysis keeps them missing and excludes them only where a
# calculation needs the field. If they had to be filled:
airport_zone_ids = [1, 132, 138]  # Newark, JFK, LaGuardia
is_airport_pickup = taxi_2023["PULocationID"].isin(airport_zone_ids)

observed_airport_fee = taxi_2023.loc[
    is_airport_pickup & taxi_2023["airport_fee"].gt(0), "airport_fee"
]
airport_fee_fill = (
    observed_airport_fee.mode().iloc[0]
    if not observed_airport_fee.empty else 0
)

imputation_plan = pd.DataFrame({
    "column": missing_columns,
    "fill_strategy": [
        "Mode (most trips carry one passenger)",
        "1 = Standard rate (mode)",
        "'N' (mode: trip was not stored and forwarded)",
        "Mode of observed surcharge",
        "Airport-pickup fee for airport zones, otherwise 0"
    ],
    "fill_value": [
        taxi_2023["passenger_count"].mode().iloc[0],
        1,
        taxi_2023["store_and_fwd_flag"].mode().iloc[0],
        taxi_2023["congestion_surcharge"].mode().iloc[0],
        f"{airport_fee_fill} / 0"
    ]
})
display(imputation_plan)

# Demonstrate the plan on a small copy; the analysis itself
# keeps the original missing values.
imputed_preview = taxi_2023[missing_columns].copy()
for column, value in zip(missing_columns[:4],
                         imputation_plan["fill_value"][:4]):
    imputed_preview[column] = imputed_preview[column].fillna(value)

imputed_preview["airport_fee"] = imputed_preview["airport_fee"].fillna(
    pd.Series(
        np.where(is_airport_pickup, airport_fee_fill, 0),
        index=imputed_preview.index
    )
)

print("Missing values after demonstrating the imputation plan:")
display(imputed_preview.isna().sum())
del imputed_preview


# =========================================================
# 3a(i). Classify variables into categorical and numerical
# =========================================================

variable_types = pd.DataFrame(
    [
        ("VendorID", "Categorical (nominal)", "Technology provider code"),
        ("tpep_pickup_datetime", "Datetime", "Meter engaged"),
        ("tpep_dropoff_datetime", "Datetime", "Meter disengaged"),
        ("passenger_count", "Numerical (discrete)", "Driver-entered passengers"),
        ("trip_distance", "Numerical (continuous)", "Miles reported by the meter"),
        ("RatecodeID", "Categorical (nominal)", "Final rate code"),
        ("store_and_fwd_flag", "Categorical (binary)", "Record held in vehicle memory"),
        ("PULocationID", "Categorical (nominal)", "Pickup taxi zone"),
        ("DOLocationID", "Categorical (nominal)", "Drop-off taxi zone"),
        ("payment_type", "Categorical (nominal)", "How the passenger paid"),
        ("fare_amount", "Numerical (continuous)", "Time-and-distance fare"),
        ("extra", "Numerical (continuous)", "Rush-hour/overnight extras"),
        ("mta_tax", "Numerical (continuous)", "MTA tax"),
        ("tip_amount", "Numerical (continuous)", "Card tips only"),
        ("tolls_amount", "Numerical (continuous)", "Tolls paid"),
        ("improvement_surcharge", "Numerical (continuous)", "Improvement surcharge"),
        ("total_amount", "Numerical (continuous)", "Total charged (excl. cash tips)"),
        ("congestion_surcharge", "Numerical (continuous)", "NYS congestion surcharge"),
        ("airport_fee", "Numerical (continuous)", "LGA/JFK pickup fee"),
        ("trip_duration_minutes", "Numerical (derived)", "Drop-off minus pickup"),
        ("average_speed_mph", "Numerical (derived)", "Distance / duration"),
        ("pickup_hour", "Categorical (ordinal, derived)", "Hour of pickup"),
        ("pickup_day", "Categorical (ordinal, derived)", "Weekday of pickup"),
        ("pickup_month", "Categorical (ordinal, derived)", "Month of pickup"),
        ("pickup_quarter", "Categorical (ordinal, derived)", "Quarter of pickup"),
        ("is_weekend", "Categorical (binary, derived)", "Saturday or Sunday")
    ],
    columns=["variable", "type", "meaning"]
)
display(variable_types)

# Location, vendor, rate and payment IDs are stored as numbers
# but are codes: averaging them has no meaning.


# =========================================================
# 3a(iv). Monthly revenue trends
# =========================================================

# Revenue = total_amount of trips with a positive total, scaled
# up by sample_weight to estimate the full-population revenue.
taxi_2023["estimated_revenue"] = (
    taxi_2023["total_amount"].where(taxi_2023["total_amount"].gt(0))
    * taxi_2023["sample_weight"]
)

monthly_revenue = (
    taxi_2023.groupby("pickup_month")
    .agg(
        estimated_revenue=("estimated_revenue", "sum"),
        estimated_trips=("sample_weight", "sum"),
        avg_total_per_trip=("total_amount", "mean")
    )
    .reindex(range(1, 13))
)
monthly_revenue["revenue_millions"] = (
    monthly_revenue["estimated_revenue"] / 1e6
)
display(monthly_revenue.round(2))

plot_line(
    monthly_revenue["revenue_millions"],
    "Estimated Monthly Revenue — NYC Yellow Taxis 2023",
    "Month", "Revenue (USD millions)", xticks=range(1, 13)
)


# =========================================================
# 3a(v). Proportion of each quarter's revenue
# =========================================================

quarterly_revenue = taxi_2023.groupby("pickup_quarter")[
    "estimated_revenue"
].sum()
quarterly_share = quarterly_revenue / quarterly_revenue.sum() * 100

display(pd.DataFrame({
    "revenue_millions": quarterly_revenue / 1e6,
    "share_percent": quarterly_share
}).round(2))

ax = quarterly_share.plot(kind="bar", figsize=(8, 5), color="teal")
ax.bar_label(ax.containers[0], fmt="%.1f%%")
ax.set_title("Share of 2023 Revenue by Quarter")
ax.set_xlabel("Quarter")
ax.set_ylabel("Share of Yearly Revenue (%)")
plt.xticks(rotation=0)
plt.tight_layout()
plt.show()


# =========================================================
# 3a(vi). Relationship between distance and fare amount
# =========================================================

# fare_trips already excludes zero/negative fares and distances
# and implausible speeds/durations (task 3a(iii)).
scatter_sample = fare_trips.sample(
    n=min(50_000, len(fare_trips)), random_state=random_seed
)
scatter_sample["rate_type"] = np.where(
    scatter_sample["RatecodeID"].eq(2), "JFK flat fare", "Other rates"
)

plt.figure(figsize=(10, 6))
sns.scatterplot(
    data=scatter_sample, x="trip_distance", y="fare_amount",
    hue="rate_type", alpha=0.2, s=8
)
plt.title("Trip Distance vs Fare Amount (random sample of trips)")
plt.xlabel("Trip Distance (miles)")
plt.ylabel("Fare Amount (USD)")
plt.xlim(0, fare_trips["trip_distance"].quantile(0.995))
plt.ylim(0, fare_trips["fare_amount"].quantile(0.995))
plt.tight_layout()
plt.show()

correlation_columns = [
    "trip_distance", "trip_duration_minutes",
    "fare_amount", "tip_amount", "total_amount"
]
print("Pearson correlation:")
display(fare_trips[correlation_columns].corr().round(2))

print("Spearman (rank) correlation, robust to outliers:")
display(fare_trips[correlation_columns].corr(method="spearman").round(2))

distance_fare = (
    fare_trips.assign(distance_band=pd.cut(
        fare_trips["trip_distance"],
        bins=[0, 1, 2, 3, 5, 10, 20, np.inf]
    ))
    .groupby("distance_band", observed=True)["fare_amount"]
    .agg(["size", "mean", "median"])
)
display(distance_fare.round(2))


# =========================================================
# 3a(vii). Fare/tips vs trips/passengers
# =========================================================

passenger_fare_summary = (
    passenger_trips.groupby("passenger_count_valid")
    .agg(
        sampled_trips=("fare_amount", "size"),
        estimated_trips=("sample_weight", "sum"),
        avg_fare=("fare_amount", "mean"),
        avg_tip=("tip_amount", "mean"),
        avg_distance=("trip_distance", "mean")
    )
)
passenger_fare_summary["share_of_trips_percent"] = (
    passenger_fare_summary["estimated_trips"]
    / passenger_fare_summary["estimated_trips"].sum() * 100
)
display(passenger_fare_summary.round(2))

fig, axes = plt.subplots(1, 3, figsize=(16, 4.5))
passenger_fare_summary["share_of_trips_percent"].plot(
    kind="bar", ax=axes[0], color="steelblue",
    title="Share of Trips (%)"
)
passenger_fare_summary["avg_fare"].plot(
    kind="bar", ax=axes[1], color="teal", title="Average Fare (USD)"
)
passenger_fare_summary["avg_tip"].plot(
    kind="bar", ax=axes[2], color="darkorange", title="Average Tip (USD)"
)
for ax in axes:
    ax.set_xlabel("Passenger Count")
    ax.tick_params(axis="x", rotation=0)
plt.suptitle("Trips, Fares and Tips by Passenger Count")
plt.tight_layout()
plt.show()

# Fare vs tip on card trips (cash tips are not recorded)
card_sample = card_tip_trips.sample(
    n=min(50_000, len(card_tip_trips)), random_state=random_seed
)
plt.figure(figsize=(10, 6))
plt.scatter(card_sample["fare_amount"], card_sample["tip_amount"],
            alpha=0.15, s=6, color="darkorange")
plt.title("Fare vs Tip — Credit Card Trips")
plt.xlabel("Fare Amount (USD)")
plt.ylabel("Tip Amount (USD)")
plt.xlim(0, card_tip_trips["fare_amount"].quantile(0.995))
plt.ylim(0, card_tip_trips["tip_amount"].quantile(0.995))
plt.tight_layout()
plt.show()

print(
    "Fare–tip correlation (card trips):",
    round(card_tip_trips["fare_amount"].corr(card_tip_trips["tip_amount"]), 2)
)


# =========================================================
# 3a(viii). Distribution of payment types
# =========================================================

payment_summary = (
    taxi_2023.assign(
        payment_method=taxi_2023["payment_type"].map(payment_labels)
    )
    .groupby("payment_method")
    .agg(
        estimated_trips=("sample_weight", "sum"),
        avg_tip=("tip_amount", "mean"),
        avg_total=("total_amount", "mean")
    )
    .sort_values("estimated_trips", ascending=False)
)
payment_summary["share_percent"] = (
    payment_summary["estimated_trips"]
    / payment_summary["estimated_trips"].sum() * 100
)
display(payment_summary.round(2))

plot_bar(
    payment_summary["share_percent"],
    "Share of Trips by Payment Type — 2023",
    "Payment Type", "Share of Trips (%)", rotation=30
)


# =========================================================
# 3a(ix). Load the taxi zones shapefile and display it
# =========================================================

zones = gpd.read_file(zones_path)
print("Zones shape:", zones.shape)
display(zones.head())

# The TLC shapefile repeats a few LocationIDs (multi-part zones),
# so the name lookup keeps one row per ID.
zone_lookup = (
    zones[["LocationID", "zone", "borough"]]
    .drop_duplicates("LocationID")
)

ax = zones.plot(
    column="borough", legend=True, figsize=(10, 10),
    edgecolor="white", linewidth=0.3, cmap="Set2"
)
ax.set_title("NYC Taxi Zones by Borough")
ax.set_axis_off()
plt.show()


# =========================================================
# 3a(x). Merge the zone data with trips data
# =========================================================

taxi_2023 = add_zone_names(taxi_2023, "PULocationID", "pickup")
taxi_2023 = add_zone_names(taxi_2023, "DOLocationID", "dropoff")

print(
    "Trips whose pickup zone has no shape (IDs 264/265):",
    (~taxi_2023["PULocationID"].isin(zone_lookup["LocationID"])).sum()
)
display(taxi_2023[[
    "PULocationID", "pickup_zone", "pickup_borough",
    "DOLocationID", "dropoff_zone", "dropoff_borough"
]].head())


# =========================================================
# 3a(xi). Number of trips for each zone/location ID
# =========================================================

trips_per_zone = (
    taxi_2023.groupby("PULocationID")
    .agg(
        sampled_pickups=("sample_weight", "size"),
        estimated_pickups=("sample_weight", "sum")
    )
    .rename_axis("LocationID")
    .reset_index()
)
display(
    trips_per_zone.merge(zone_lookup, on="LocationID", how="left")
    .sort_values("estimated_pickups", ascending=False)
    .head(10)
    .round(0)
)


# =========================================================
# 3a(xii). Add the number of trips to the zones dataframe
# =========================================================

zones = zones.merge(trips_per_zone, on="LocationID", how="left")
zones[["sampled_pickups", "estimated_pickups"]] = (
    zones[["sampled_pickups", "estimated_pickups"]].fillna(0)
)
display(zones[["LocationID", "zone", "borough", "estimated_pickups"]].head())


# =========================================================
# 3a(xiii). Map of zones showing number of trips
# =========================================================

ax = zones.plot(
    column="estimated_pickups", cmap="OrRd", legend=True,
    figsize=(12, 10), edgecolor="grey", linewidth=0.2,
    legend_kwds={"label": "Estimated Pickups in 2023"}
)
ax.set_title("Yellow Taxi Pickups by Zone — 2023")
ax.set_axis_off()
plt.show()

borough_pickups = (
    zones.groupby("borough")["estimated_pickups"].sum()
    .sort_values(ascending=False)
)
display((borough_pickups / borough_pickups.sum() * 100).round(2)
        .to_frame("share_of_pickups_percent"))


# =========================================================
# 3a(xiv). Conclusions from general EDA (key numbers)
# =========================================================

busiest_month = monthly_revenue["estimated_revenue"].idxmax()
quietest_month = monthly_revenue["estimated_revenue"].idxmin()
top_zone = zones.loc[zones["estimated_pickups"].idxmax(), "zone"]

print(f"Busiest pickup hour: {hourly_summary['sampled_trips'].idxmax()}:00")
print(f"Highest-revenue month: {busiest_month}; lowest: {quietest_month}")
print(f"Largest quarter share: Q{quarterly_share.idxmax()} "
      f"({quarterly_share.max():.1f}%)")
print(f"Credit card share of trips: "
      f"{payment_summary.loc['Credit card', 'share_percent']:.1f}%")
print(f"Busiest pickup zone: {top_zone}")
print(f"Manhattan share of pickups: "
      f"{borough_pickups.get('Manhattan', 0) / borough_pickups.sum() * 100:.1f}%")


# =========================================================
# 3b(i). Slow routes: average speed by route and hour
# =========================================================

# Same-zone trips are excluded: they are short and dominated by
# waiting time, so they would swamp the slow-route list.
route_speed = (
    speed_trips.loc[
        speed_trips["PULocationID"].ne(speed_trips["DOLocationID"])
    ]
    .groupby(["PULocationID", "DOLocationID", "pickup_hour"])
    .agg(
        trips=("average_speed_mph", "size"),
        median_speed_mph=("average_speed_mph", "median"),
        avg_distance=("trip_distance", "mean"),
        avg_duration_min=("trip_duration_minutes", "mean")
    )
    .reset_index()
)
reliable_routes = route_speed.loc[route_speed["trips"] >= min_route_trips]

slowest_routes = add_zone_names(
    add_zone_names(
        reliable_routes.nsmallest(10, "median_speed_mph"),
        "PULocationID", "pickup"
    ),
    "DOLocationID", "dropoff"
)
print(f"Ten slowest routes (≥ {min_route_trips} sampled trips):")
display(slowest_routes[[
    "pickup_zone", "dropoff_zone", "pickup_hour", "trips",
    "median_speed_mph", "avg_distance", "avg_duration_min"
]].round(2))

# Route level across all hours (more trips per route, so more
# routes pass the reliability threshold)
route_overall = (
    speed_trips.loc[
        speed_trips["PULocationID"].ne(speed_trips["DOLocationID"])
    ]
    .groupby(["PULocationID", "DOLocationID"])
    .agg(
        trips=("average_speed_mph", "size"),
        median_speed_mph=("average_speed_mph", "median")
    )
    .reset_index()
)
slowest_routes_overall = add_zone_names(
    add_zone_names(
        route_overall.loc[route_overall["trips"] >= min_route_trips]
        .nsmallest(10, "median_speed_mph"),
        "PULocationID", "pickup"
    ),
    "DOLocationID", "dropoff"
)
print("Ten slowest routes across all hours:")
display(slowest_routes_overall[[
    "pickup_zone", "dropoff_zone", "trips", "median_speed_mph"
]].round(2))

speed_by_hour = speed_trips.groupby("pickup_hour")["average_speed_mph"].median()
plot_line(
    speed_by_hour, "Median Trip Speed by Pickup Hour",
    "Pickup Hour", "Median Speed (mph)", xticks=range(24)
)

speed_by_hour_day = (
    speed_trips.pivot_table(
        index="pickup_day", columns="pickup_hour",
        values="average_speed_mph", aggfunc="median"
    )
    .reindex(day_order)
)
plt.figure(figsize=(16, 5))
sns.heatmap(speed_by_hour_day, cmap="RdYlGn", annot=False,
            cbar_kws={"label": "Median Speed (mph)"})
plt.title("Median Trip Speed by Weekday and Hour")
plt.xlabel("Pickup Hour")
plt.ylabel("Day of Week")
plt.tight_layout()
plt.show()


# =========================================================
# 3b(ii). Hourly number of trips and busy hours
# =========================================================

busiest_hours = hourly_summary.nlargest(5, "sampled_trips")
print("Five busiest pickup hours:")
display(busiest_hours.round(0))


# =========================================================
# 3b(iii). Scale up the number of trips
# =========================================================

# estimated_trips = sum of sample_weight (≈ 1 / sample_fraction),
# so each sampled trip stands for ~20 real trips.
hourly_summary["avg_trips_per_day"] = (
    hourly_summary["estimated_trips"] / days_in_2023
)
display(hourly_summary.round(0))

print(f"Estimated 2023 trips: {hourly_summary['estimated_trips'].sum():,.0f}")
print(f"Actual rows in the 12 files: {sampling_summary['original_rows'].sum():,}")

plot_bar(
    hourly_summary["avg_trips_per_day"],
    "Estimated Average Pickups per Day, by Hour — 2023",
    "Pickup Hour", "Estimated Trips per Day"
)


# =========================================================
# 3b(iv). Hourly traffic: weekdays vs weekends
# =========================================================

weekend_days = int((calendar_days.dt.dayofweek >= 5).sum())
weekday_days = days_in_2023 - weekend_days

hourly_day_type = (
    taxi_2023.groupby(["pickup_hour", "is_weekend"])["sample_weight"]
    .sum()
    .unstack("is_weekend")
    .rename(columns={False: "Weekday", True: "Weekend"})
)
# Divide by the number of such days so the two lines compare a
# typical weekday with a typical weekend day.
hourly_day_type["Weekday"] /= weekday_days
hourly_day_type["Weekend"] /= weekend_days
display(hourly_day_type.round(0))

plot_line(
    hourly_day_type,
    "Average Hourly Pickups: Weekday vs Weekend Day",
    "Pickup Hour", "Estimated Trips per Day", xticks=range(24)
)


# =========================================================
# 3b(v). Top 10 zones with high hourly pickups and drops
# =========================================================

def average_hourly_trips(id_column, prefix):
    """Estimated average trips per hour for each zone."""
    hourly = (
        taxi_2023.groupby(id_column)["sample_weight"].sum()
        / hours_in_2023
    ).rename("avg_trips_per_hour").reset_index()
    return add_zone_names(hourly, id_column, prefix)


hourly_pickups = average_hourly_trips("PULocationID", "pickup")
hourly_dropoffs = average_hourly_trips("DOLocationID", "dropoff")

top_pickup_zones = hourly_pickups.nlargest(10, "avg_trips_per_hour")
top_dropoff_zones = hourly_dropoffs.nlargest(10, "avg_trips_per_hour")
display(top_pickup_zones.round(1))
display(top_dropoff_zones.round(1))

fig, axes = plt.subplots(1, 2, figsize=(16, 6))
top_pickup_zones.set_index("pickup_zone")["avg_trips_per_hour"] \
    .sort_values().plot(kind="barh", ax=axes[0], color="steelblue")
axes[0].set_title("Top 10 Pickup Zones")
top_dropoff_zones.set_index("dropoff_zone")["avg_trips_per_hour"] \
    .sort_values().plot(kind="barh", ax=axes[1], color="teal")
axes[1].set_title("Top 10 Drop-off Zones")
for ax in axes:
    ax.set_xlabel("Estimated Average Trips per Hour")
    ax.set_ylabel("")
plt.tight_layout()
plt.show()


# =========================================================
# 3b(vi). Ratio of pickups to dropoffs in each zone
# =========================================================

zone_flow = pd.concat(
    [
        taxi_2023["PULocationID"].value_counts().rename("pickups"),
        taxi_2023["DOLocationID"].value_counts().rename("dropoffs")
    ],
    axis=1
).fillna(0).rename_axis("LocationID").reset_index()

zone_flow = zone_flow.loc[
    (zone_flow["pickups"] + zone_flow["dropoffs"]) >= min_zone_trips
].copy()
# Ratio > 1: more trips start than end here (cabs drain away);
# ratio < 1: cabs accumulate here and leave empty.
zone_flow["pickup_dropoff_ratio"] = (
    zone_flow["pickups"] / zone_flow["dropoffs"].replace(0, np.nan)
)
zone_flow = add_zone_names(zone_flow, "LocationID", "location")

print("Zones with the highest pickup/dropoff ratio:")
display(zone_flow.nlargest(10, "pickup_dropoff_ratio").round(2))
print("Zones with the lowest pickup/dropoff ratio:")
display(zone_flow.nsmallest(10, "pickup_dropoff_ratio").round(2))


# =========================================================
# 3b(vii). Top zones with high traffic during night hours
# =========================================================

taxi_2023["is_night"] = taxi_2023["pickup_hour"].isin(night_hours)
night_trips = taxi_2023.loc[taxi_2023["is_night"]]

def top_zones(df, zone_column, n=10):
    """Estimated trips for the n busiest zones in a subset."""
    return (
        df.groupby(zone_column)["sample_weight"].sum()
        .nlargest(n).rename("estimated_trips")
    )

top_night_pickups = top_zones(night_trips, "pickup_zone")
top_night_dropoffs = top_zones(night_trips, "dropoff_zone")
display(top_night_pickups.round(0).to_frame())
display(top_night_dropoffs.round(0).to_frame())

fig, axes = plt.subplots(1, 2, figsize=(16, 6))
top_night_pickups.sort_values().plot(kind="barh", ax=axes[0], color="midnightblue")
axes[0].set_title("Top 10 Night Pickup Zones (11 PM – 5 AM)")
top_night_dropoffs.sort_values().plot(kind="barh", ax=axes[1], color="slateblue")
axes[1].set_title("Top 10 Night Drop-off Zones (11 PM – 5 AM)")
for ax in axes:
    ax.set_xlabel("Estimated Trips in 2023")
    ax.set_ylabel("")
plt.tight_layout()
plt.show()


# =========================================================
# 3b(viii). Revenue share for nighttime and daytime hours
# =========================================================

day_night_summary = (
    taxi_2023.assign(period=np.where(taxi_2023["is_night"], "Night", "Day"))
    .groupby("period")
    .agg(
        estimated_revenue=("estimated_revenue", "sum"),
        estimated_trips=("sample_weight", "sum"),
        avg_total_per_trip=("total_amount", "mean"),
        avg_distance=("trip_distance", "mean")
    )
)
day_night_summary["revenue_share_percent"] = (
    day_night_summary["estimated_revenue"]
    / day_night_summary["estimated_revenue"].sum() * 100
)
day_night_summary["trip_share_percent"] = (
    day_night_summary["estimated_trips"]
    / day_night_summary["estimated_trips"].sum() * 100
)
display(day_night_summary.round(2))

plot_bar(
    day_night_summary[["trip_share_percent", "revenue_share_percent"]],
    "Share of Trips and Revenue: Day vs Night",
    "Period", "Share (%)", color=["steelblue", "darkorange"], figsize=(8, 5)
)


# =========================================================
# 3b(ix). Average fare per mile per passenger
# =========================================================

rate_trips = add_distance_tier(fare_trips.loc[
    fare_trips["trip_distance"].ge(min_distance_for_rate)
].copy())
passenger_rate_trips = passenger_trips.loc[
    passenger_trips["trip_distance"].ge(min_distance_for_rate)
]

fare_per_passenger = (
    passenger_rate_trips.groupby("passenger_count_valid")
    .agg(
        sampled_trips=("fare_per_mile", "size"),
        avg_fare_per_mile=("fare_per_mile", "mean"),
        avg_fare_per_mile_per_passenger=("fare_per_mile_per_passenger", "mean")
    )
)
display(fare_per_passenger.round(2))

plot_bar(
    fare_per_passenger["avg_fare_per_mile_per_passenger"],
    "Average Fare per Mile per Passenger",
    "Passenger Count", "USD per Mile per Passenger", color="teal"
)


# =========================================================
# 3b(x). Average fare per mile by hour and by weekday
# =========================================================

fare_per_mile_hour = rate_trips.groupby("pickup_hour")["fare_per_mile"].mean()
fare_per_mile_day = (
    rate_trips.groupby("pickup_day")["fare_per_mile"].mean().reindex(day_order)
)

fig, axes = plt.subplots(1, 2, figsize=(16, 5))
fare_per_mile_hour.plot(kind="line", marker="o", ax=axes[0], color="steelblue")
axes[0].set_title("Average Fare per Mile by Hour")
axes[0].set_xlabel("Pickup Hour")
axes[0].set_xticks(range(24))
fare_per_mile_day.plot(kind="bar", ax=axes[1], color="teal")
axes[1].set_title("Average Fare per Mile by Weekday")
axes[1].set_xlabel("Day of Week")
axes[1].tick_params(axis="x", rotation=45)
for ax in axes:
    ax.set_ylabel("USD per Mile")
plt.tight_layout()
plt.show()


# =========================================================
# 3b(xi). Average fare per mile for the different vendors
# =========================================================

rate_trips["vendor"] = (
    rate_trips["VendorID"].map(vendor_labels)
    .fillna(rate_trips["VendorID"].astype(str))
)

vendor_fares = (
    rate_trips.groupby("vendor")
    .agg(
        sampled_trips=("fare_per_mile", "size"),
        avg_fare_per_mile=("fare_per_mile", "mean"),
        median_fare_per_mile=("fare_per_mile", "median"),
        avg_distance=("trip_distance", "mean")
    )
    .sort_values("sampled_trips", ascending=False)
)
display(vendor_fares.round(2))

main_vendors = vendor_fares.index[vendor_fares["sampled_trips"] >= min_zone_trips]
plot_bar(
    vendor_fares.loc[main_vendors, ["avg_fare_per_mile", "median_fare_per_mile"]],
    "Fare per Mile by Vendor", "Vendor", "USD per Mile",
    color=["steelblue", "darkorange"], figsize=(9, 5)
)


# =========================================================
# 3b(xii). Vendor fare rates in a distance-tiered fashion
# =========================================================

vendor_tier_fares = (
    rate_trips.loc[rate_trips["vendor"].isin(main_vendors)]
    .groupby(["distance_tier", "vendor"], observed=True)["fare_per_mile"]
    .mean()
    .unstack("vendor")
)
display(vendor_tier_fares.round(2))

plot_bar(
    vendor_tier_fares,
    "Average Fare per Mile by Distance Tier and Vendor",
    "Distance Tier", "USD per Mile", color=None
)


# =========================================================
# 3b(xiii). Tip percentages
# =========================================================

# Credit-card trips only: cash tips are not recorded.
add_distance_tier(card_tip_trips)

print("Tip as % of fare (credit-card trips):")
display(card_tip_trips["tip_percent_of_fare"].describe(
    percentiles=[0.25, 0.5, 0.75, 0.95]
).round(2))

tip_bands = pd.cut(
    card_tip_trips["tip_percent_of_fare"],
    bins=[-0.01, 0, 10, 20, 25, 30, np.inf],
    labels=["No tip", "0–10%", "10–20%", "20–25%", "25–30%", "Over 30%"]
)
tip_band_share = tip_bands.value_counts(normalize=True, sort=False) * 100
display(tip_band_share.round(2).to_frame("share_of_card_trips_percent"))

plot_bar(
    tip_band_share, "Distribution of Tip Percentage — Card Trips",
    "Tip as % of Fare", "Share of Card Trips (%)", color="darkorange"
)

tip_by_tier = card_tip_trips.groupby(
    "distance_tier", observed=True
)["tip_percent_of_fare"].median()
tip_by_hour = card_tip_trips.groupby("pickup_hour")["tip_percent_of_fare"].median()
tip_by_passengers = card_tip_trips.groupby(
    "passenger_count_valid"
)["tip_percent_of_fare"].median()

fig, axes = plt.subplots(1, 3, figsize=(18, 4.5))
tip_by_tier.plot(kind="bar", ax=axes[0], color="darkorange",
                 title="By Distance Tier")
tip_by_hour.plot(kind="line", marker="o", ax=axes[1], color="darkorange",
                 title="By Pickup Hour")
tip_by_passengers.plot(kind="bar", ax=axes[2], color="darkorange",
                       title="By Passenger Count")
axes[0].tick_params(axis="x", rotation=0)
axes[2].tick_params(axis="x", rotation=0)
for ax in axes:
    ax.set_ylabel("Median Tip (% of Fare)")
plt.suptitle("Median Tip Percentage — Credit Card Trips")
plt.tight_layout()
plt.show()

# Low vs high tippers: what differs?
tip_group = np.select(
    [card_tip_trips["tip_percent_of_fare"].lt(10),
     card_tip_trips["tip_percent_of_fare"].gt(25)],
    ["Under 10%", "Over 25%"], default="10–25%"
)
display(
    card_tip_trips.assign(tip_group=tip_group)
    .groupby("tip_group")[[
        "trip_distance", "trip_duration_minutes",
        "fare_amount", "average_speed_mph", "pickup_hour"
    ]].mean().round(2)
)


# =========================================================
# 3b(xiv). Trends in passenger count
# =========================================================

passenger_share = (
    taxi_2023.groupby("passenger_count_valid")["sample_weight"].sum()
)
passenger_share = passenger_share / passenger_share.sum() * 100
display(passenger_share.round(2).to_frame("share_of_trips_percent"))

passenger_trends = {
    "Month": taxi_2023.groupby("pickup_month")["passenger_count_valid"].mean(),
    "Hour": taxi_2023.groupby("pickup_hour")["passenger_count_valid"].mean(),
    "Weekday": taxi_2023.groupby("pickup_day")["passenger_count_valid"]
                        .mean().reindex(day_order)
}

fig, axes = plt.subplots(1, 3, figsize=(18, 4.5))
for ax, (label, series) in zip(axes, passenger_trends.items()):
    series.plot(kind="line", marker="o", ax=ax, color="purple")
    ax.set_title(f"Average Passengers by {label}")
    ax.set_xlabel(label)
    ax.set_ylabel("Average Passenger Count")
    ax.grid(alpha=0.3)
axes[2].tick_params(axis="x", rotation=45)
plt.tight_layout()
plt.show()


# =========================================================
# 3b(xv). Variation of passenger counts across zones
# =========================================================

zone_passengers = (
    taxi_2023.dropna(subset=["passenger_count_valid"])
    .groupby("PULocationID")
    .agg(
        sampled_trips=("passenger_count_valid", "size"),
        avg_passengers=("passenger_count_valid", "mean"),
        group_trip_share=("passenger_count_valid", lambda s: (s >= 2).mean() * 100)
    )
    .rename_axis("LocationID")
    .reset_index()
)
zone_passengers = zone_passengers.loc[
    zone_passengers["sampled_trips"] >= min_zone_trips
].merge(zone_lookup, on="LocationID", how="inner")

print("Zones with the highest average passengers per trip:")
display(zone_passengers.nlargest(10, "avg_passengers").round(2))

zones = zones.merge(
    zone_passengers[["LocationID", "avg_passengers"]],
    on="LocationID", how="left"
)
ax = zones.plot(
    column="avg_passengers", cmap="Purples", legend=True,
    figsize=(12, 10), edgecolor="grey", linewidth=0.2,
    missing_kwds={"color": "lightgrey", "label": "Too few trips"},
    legend_kwds={"label": "Average Passengers per Trip"}
)
ax.set_title(f"Average Passengers per Pickup by Zone (zones with ≥ {min_zone_trips} sampled trips)")
ax.set_axis_off()
plt.show()


# =========================================================
# 3b(xvi). Where and when extra charges are applied
# =========================================================

charge_flags = {
    "extra": taxi_2023["extra"].gt(0),
    "congestion_surcharge": taxi_2023["congestion_surcharge"].gt(0),
    "airport_fee": taxi_2023["airport_fee"].gt(0)
}

charge_by_hour = pd.DataFrame({
    name: flag_share_by(taxi_2023, "pickup_hour", flag)["share_percent"]
    for name, flag in charge_flags.items()
})
display(charge_by_hour.round(1))

plot_line(
    charge_by_hour,
    "Share of Trips with Each Extra Charge, by Pickup Hour",
    "Pickup Hour", "Trips with Charge (%)", xticks=range(24)
)

charge_by_day = (
    flag_share_by(taxi_2023, "pickup_day", charge_flags["extra"])
    .reindex(day_order)
)
display(charge_by_day.round(1))

for name, flag in charge_flags.items():
    for zone_column in ["pickup_zone", "dropoff_zone"]:
        top = (
            flag_share_by(taxi_2023, zone_column, flag, min_zone_trips)
            .nlargest(10, "share_percent")
        )
        print(f"Top {zone_column.replace('_', ' ')}s for '{name}':")
        display(top.round(1))


# =========================================================
# 4. Key numbers for conclusions and recommendations
# =========================================================

peak_weekday_hour = hourly_day_type["Weekday"].idxmax()
peak_weekend_hour = hourly_day_type["Weekend"].idxmax()
slowest_hour = speed_by_hour.idxmin()
night_revenue_share = day_night_summary.loc["Night", "revenue_share_percent"]
night_trip_share = day_night_summary.loc["Night", "trip_share_percent"]
highest_rate_hour = fare_per_mile_hour.idxmax()
median_card_tip = card_tip_trips["tip_percent_of_fare"].median()
no_tip_share = tip_band_share.get("No tip", 0)

print("=== Demand (routing & dispatch) ===")
print(f"Weekday peak hour: {peak_weekday_hour}:00 | Weekend peak hour: {peak_weekend_hour}:00")
print(f"Slowest median speeds at {slowest_hour}:00")
print(f"Busiest pickup zones: {', '.join(top_pickup_zones['pickup_zone'].head(5).astype(str))}")

print("\n=== Positioning ===")
print(f"Net-supply zones (pickups > dropoffs): "
      f"{', '.join(zone_flow.nlargest(5, 'pickup_dropoff_ratio')['location_zone'].astype(str))}")
print(f"Net-sink zones (dropoffs > pickups): "
      f"{', '.join(zone_flow.nsmallest(5, 'pickup_dropoff_ratio')['location_zone'].astype(str))}")
print(f"Night: {night_trip_share:.1f}% of trips, {night_revenue_share:.1f}% of revenue")
print(f"Top night pickup zones: {', '.join(top_night_pickups.index[:5].astype(str))}")

print("\n=== Pricing ===")
print(f"Highest average fare per mile at {highest_rate_hour}:00")
display(vendor_tier_fares.round(2))
print(f"Median card tip: {median_card_tip:.1f}% of fare; "
      f"{no_tip_share:.1f}% of card trips leave no tip")
