"""clients_daily_histogram_aggregates query generator."""
import argparse
import sys
from typing import Dict, List
from jinja2 import Environment, PackageLoader

from bigquery_etl.format_sql.formatter import reformat
from .utils import get_schema

ATTRIBUTES = ",".join(
    [
        "client_id",
        "ping_type",
        "submission_date",
        "os",
        "app_version",
        "app_build_id",
        "channel",
    ]
)


def render_main(**kwargs):
    """Create a SQL query for the clients_daily_histogram_aggregates dataset."""
    env = Environment(loader=PackageLoader("bigquery_etl", "glam/templates"))
    main_sql = env.get_template("clients_daily_histogram_aggregates_v1.sql")
    return reformat(main_sql.render(**kwargs))


def get_distribution_metrics(schema: Dict) -> Dict[str, List[str]]:
    """Find all distribution-like metrics in a Glean table.

    Metric types are defined in the Glean documentation found here:
    https://mozilla.github.io/glean/book/user/metrics/index.html
    """
    metric_type_set = {
        "timing_distribution",
        "memory_distribution",
        "custom_distribution",
    }
    metrics = {metric_type: [] for metric_type in metric_type_set}

    # Iterate over every element in the schema under the metrics section and
    # collect a list of metric names.
    for root_field in schema:
        if root_field["name"] != "metrics":
            continue
        for metric_field in root_field["fields"]:
            metric_type = metric_field["name"]
            if metric_type not in metric_type_set:
                continue
            for field in metric_field["fields"]:
                metrics[metric_type].append(field["name"])
    return metrics


def get_metrics_sql(metrics: Dict[str, List[str]]) -> str:
    """Return a tuple containing the relevant information about the distributions."""
    # accumulate relevant information about metrics
    items = []
    for metric_type, metric_names in metrics.items():
        for name in metric_names:
            path = f"metrics.{metric_type}.{name}"
            sum_path = f"{path}.sum"
            value_path = f"{path}.values"
            items.append((name, metric_type, sum_path, value_path))

    # create the query sub-string
    results = []
    for name, metric_type, sum_path, value_path in sorted(items):
        results.append(f"""("{name}", "{metric_type}", {sum_path}, {value_path})""")
    return ",".join(results)


def main():
    """Print a clients_daily_scalar_aggregates query to stdout."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--no-parameterize",
        action="store_true",
        help="Generate a query without parameters",
    )
    parser.add_argument(
        "--source-table",
        type=str,
        help="Name of Glean table",
        default="org_mozilla_fenix_stable.metrics_v1",
    )
    args = parser.parse_args()

    # If set to 1 day, then runs of copy_deduplicate may not be done yet
    submission_date = (
        "date_sub(current_date, interval 2 day)"
        if args.no_parameterize
        else "@submission_date"
    )
    header = (
        "-- Query generated by: "
        "python3 -m bigquery_etl.glam.clients_daily_histogram_aggregates "
        f"--source-table {args.source_table}"
        + (" --no-parameterize" if args.no_parameterize else "")
    )

    schema = get_schema(args.source_table)
    distributions = get_distribution_metrics(schema)
    metrics_sql = get_metrics_sql(distributions).strip()
    if not metrics_sql:
        print(header)
        print("-- Empty query: no probes found!")
        sys.exit(1)
    print(
        render_main(
            header=header,
            source_table=args.source_table,
            submission_date=submission_date,
            attributes=ATTRIBUTES,
            histograms=metrics_sql,
        )
    )


if __name__ == "__main__":
    main()
