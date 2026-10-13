"""Add result-based answers and conclusions to the executed notebook.

Every number below comes from the saved outputs of the executed notebook
(sample of 284,168 cleaned trips, scaled with sample weights).

Usage:
    python tools/add_conclusions.py <executed.ipynb> <output.ipynb>
"""

import sys

import nbformat as nbf

RATECODE_ANSWER = """
**Answer:** The negative-fare trips do not stand out by `RatecodeID`: 2,488 of the 2,833 (88%) are standard-rate trips, much the same mix as the whole dataset. What they share is the **payment type**: Dispute (1,679), Cash (665) and No charge (444). In 97.2% of them *every* charge is zero or negative, and the amounts mirror normal fares (e.g. -17.70 fare, -0.50 MTA tax, -1.00 improvement surcharge). They are reversal records that cancel an earlier charge, not real trips with a negative price, so they are dropped rather than turned positive.
"""

GENERAL_FINDINGS = """
**Findings from the general analysis** (estimated full-year figures, scaled from the 0.75% sample):

* **Busiest hours:** demand climbs from 6 AM and peaks at **6 PM** (about 2.68 million trips a year, ~7,300 a day); the quietest hour is 4–5 AM (~0.21 million a year).
* **Busiest days:** **Thursday** (114,208 trips per day) and Wednesday (111,667); Sunday (90,336) and Monday (90,787) are the quietest.
* **Busiest months:** May and October (~3.48 million trips each); demand dips in July–September (August lowest, 2.79 million).
* **Revenue trend:** about **$1.10 billion** in 2023. October is highest ($103.9M), February lowest ($79.1M). Revenue per trip rose from $27.56 in January to $30.25 in September.
* **Quarterly revenue:** Q1 23.5%, Q2 26.7%, Q3 22.9%, Q4 27.0%: the two strongest quarters are spring and autumn, the weakest is summer.
* **Fare vs distance:** strong linear relationship (correlation **0.945**), with a flat line at the 70 USD JFK flat fare.
* **Fare vs duration:** weaker (0.275), because time stuck in traffic adds little to the meter compared with distance.
* **Fare vs passengers:** almost no relationship (0.042); median fares are 13.5–14.9 USD for every group size.
* **Tip vs distance:** moderate to strong (0.592 on all trips, **0.734 on card trips**, since cash tips are not recorded).
* **Payment:** credit card 78.7%, cash 16.7%, unknown 3.4%, dispute 0.7%, no charge 0.5%.
* **Busiest zones:** JFK Airport (1.97M pickups), Upper East Side South (1.77M), Midtown Center (1.76M), Upper East Side North (1.60M), Midtown East (1.34M). Manhattan has **89.3%** of all pickups and Queens (mainly the airports) 9.8%.
"""

WEEKDAY_WEEKEND_ANSWER = """
**Answer:** Weekdays have a commuter pattern: demand rises sharply from 6 AM (3,477 trips/day at 7 AM vs 1,244 at weekends) and peaks at **6 PM with ~7,800 trips/day**. Weekends start slowly but stay busy late: between midnight and 4 AM there are **2.5–5.8 times** more trips than on a weekday night (e.g. 3,122 vs 565 at 2 AM), and the afternoon peak is flatter (~6,100 trips/day from 4–6 PM). By day of week, Thursday is busiest and Tuesday–Thursday at 5–6 PM are the strongest slots; Friday and Saturday stay busy past midnight, while Sunday and Monday are the quietest days.

Knowing the busy and quiet hours for each day lets the operator schedule driver shifts to the demand curve, plan breaks and maintenance in quiet hours (4–5 AM, weekend mornings), and move cabs to nightlife areas before the weekend late-night peak instead of after it.
"""

RECOMMENDATIONS_ROUTING = """
**Recommendations to optimise routing and dispatching:**

1. **Shape the fleet to the daily demand curve.** On weekdays, bring cabs online from 6 AM and have the most cabs on the road from 3 PM to 7 PM (6 PM averages ~7,800 trips per weekday). Keep the smallest fleet at 4–5 AM, when demand is under a tenth of the peak.
2. **Run a separate weekend schedule.** Move driver hours from weekend mornings (7–8 AM is well under half the weekday level) to **11 PM–4 AM**, when weekend demand is 2.5–5.8 times that of a weekday night.
3. **Avoid Midtown cross-traffic in the daytime.** The slowest routes are short Midtown hops (Penn Station → Garment District, Midtown East → Times Square) at **3–4 mph from 8 AM to 7 PM**; under a mile can take 15–20 minutes. Dispatch should assign the nearest cab on the same side of Midtown, avoid sending empty cabs through Midtown to reach a pickup, and show realistic ETAs for these routes.
4. **Run the airports as dedicated queues.** JFK is the single busiest pickup zone (~225 pickups an hour) and both airports have far more pickups than dropoffs (JFK 4.3×, LaGuardia 2.5×), so they need a steady flow of cabs, fed from nearby Queens dropoffs.
5. **Plan for the seasons.** Demand per day is lowest in July–September (~90,000–94,000 trips per day) and highest in May and October (~112,000). Schedule leave and vehicle maintenance in summer and run a full fleet in spring and Q4.
"""

RECOMMENDATIONS_POSITIONING = """
**Suggestions for positioning cabs across zones:**

1. **Daytime core (weekdays 7 AM–8 PM):** Upper East Side South and North, Midtown Center and East, Penn Station/Madison Square West, Lincoln Square East, Times Square/Theatre District and Murray Hill. These zones have 125–200 pickups per hour on average.
2. **Airports all day:** keep JFK and LaGuardia stocked. Together they take about 8.5% of all pickups, and the nearby East Elmhurst zone has 8× more pickups than dropoffs.
3. **Nightlife at night (11 PM–5 AM), especially Friday and Saturday:** East Village (the busiest night pickup zone), West Village, Clinton East, Lower East Side, Greenwich Village South and Times Square. Night dropoffs are mostly in residential Manhattan (East Village, East Chelsea, Murray Hill, Gramercy, Lenox Hill, Yorkville), so cabs should head back to the nightlife zones after those drops.
4. **Rebalance from zones where cabs end up empty.** Outer-borough residential zones and Newark Airport receive many more dropoffs than they generate pickups (pickup/dropoff ratio below 0.1). After a drop there, guide drivers back to Manhattan, or to JFK/LaGuardia from Queens, instead of waiting for a fare.
5. **Larger vehicles where groups travel:** Battery Park, the Seaport, the Financial District, JFK and Times Square have the highest average group sizes (1.5–1.7 passengers, about 30% of trips with 2+ passengers). Group trips are also more common at night and at weekends.
"""

RECOMMENDATIONS_PRICING = """
**Data-driven pricing adjustments:**

1. **Group trips are under-priced per passenger.** Fare per mile is the same (~7.4–7.6 USD) whatever the group size, so the price per passenger falls from 7.52 USD/mile for one rider to 1.24 USD/mile for six. A small per-extra-passenger fee, or a group fare for larger vehicles, would add revenue without affecting the 77% of trips with a single rider.
2. **Keep rates in line with competitors.** The two main vendors charge almost the same in every distance tier (VeriFone vs Creative Mobile: 9.08 vs 9.03 USD/mile up to 2 miles, 6.54 vs 6.40 for 2–5 miles, 4.49 vs 4.43 above 5 miles). The market is effectively price-matched, so a new operator should price within this band and compete on availability and service. (Myle has only 50 sampled trips, too few to compare.)
3. **Long trips earn the least per mile.** Trips over 5 miles bring in ~4.5 USD/mile, half the short-trip rate, and also get lower tips (20.4% vs 27.7%). A slightly higher per-mile rate beyond 5 miles (outside the fixed airport fares) would lift revenue on the trips that tie up a cab longest.
4. **Use off-peak incentives instead of raising peak fares.** Fare per mile is highest at midday (8.2 USD at noon) and lowest at 4 AM (5.7 USD), and Q3 has the lowest revenue share (22.9%). Targeted discounts for summer and weekday early mornings can fill idle capacity, while peak pricing stays competitive.
5. **Make card tipping easy.** Card trips (78.7% of all trips) tip ~25% of the fare on average. Low tips (<10%) are most common on long trips, airport-rate trips and from 3 to 6 AM (about 17% of trips). Suggested tip percentages on the payment screen help keep tips up on these trips.
"""


def markdown(source):
    return nbf.v4.new_markdown_cell(source.strip("\n"))


def find(nb, prefix, cell_type="markdown"):
    matches = [i for i, c in enumerate(nb.cells)
               if c.cell_type == cell_type and c.source.startswith(prefix)]
    assert len(matches) == 1, (prefix, matches)
    return matches[0]


def main(source_path, output_path):
    nb = nbf.read(source_path, as_version=4)

    # Empty answer cells under 4.1.1-4.1.3 become markdown cells
    for prefix, text in [("**4.1.1**", RECOMMENDATIONS_ROUTING),
                         ("**4.1.2**", RECOMMENDATIONS_POSITIONING),
                         ("**4.1.3**", RECOMMENDATIONS_PRICING)]:
        index = find(nb, prefix) + 1
        assert nb.cells[index].cell_type == "code" and not nb.cells[index].source.strip()
        nb.cells[index] = markdown(text)

    # New answer cells, inserted from the bottom up so indices stay valid
    insertions = [
        (find(nb, "Did you notice something different in the `RatecodeID`"), RATECODE_ANSWER),
        (find(nb, "You can consider the following points:"), GENERAL_FINDINGS),
        (find(nb, "What can you infer from the above patterns?"), WEEKDAY_WEEKEND_ANSWER),
    ]
    for index, text in sorted(insertions, reverse=True):
        nb.cells.insert(index + 1, markdown(text))

    for number, cell in enumerate(nb.cells):
        cell.setdefault("id", f"cell-{number}")
    nbf.validate(nb)
    nbf.write(nb, output_path)
    print(f"Wrote {output_path} with {len(nb.cells)} cells")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
