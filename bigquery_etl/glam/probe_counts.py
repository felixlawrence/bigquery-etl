r"""Metric counting.

```bash
python3 -m bigquery_etl.glam.probe_counts

diff \
    <(cat sql/telemetry_derived/clients_histogram_probe_counts_v1/query.sql) \
    <(python3 -m bigquery_etl.glam.probe_counts)
```
"""
from argparse import ArgumentParser
from itertools import combinations
from typing import List

from jinja2 import Environment, PackageLoader

from bigquery_etl.format_sql.formatter import reformat


def render_query(attributes: List[str], **kwargs) -> str:
    """Render the main query."""
    env = Environment(loader=PackageLoader("bigquery_etl", "glam/templates"))
    sql = env.get_template("probe_counts_v1.sql")

    # If the set of attributes grows, the max_combinations can be set only
    # compute a shallow set for less query complexity
    max_combinations = len(attributes)
    attribute_combinations = []
    for subset_size in reversed(range(max_combinations + 1)):
        for grouping in combinations(attributes, subset_size):
            # channel and app_version are required in the GLAM frontend
            if "channel" not in grouping or "app_version" not in grouping:
                continue
            select_expr = []
            for attribute in attributes:
                select_expr.append((attribute, attribute in grouping))
            attribute_combinations.append(select_expr)

    return reformat(sql.render(attribute_combinations=attribute_combinations, **kwargs))


def telemetry_variables():
    """Variables for probe_counts."""
    return dict(
        # source_table="clients_scalar_bucket_counts_v1",
        attributes=["os", "app_version", "app_build_id", "channel"],
        aggregate_attributes="""
            metric,
            metric_type,
            key,
            process
        """,
        # TODO: some of these are histogram specific
        aggregate_grouping="""
            client_agg_type,
            first_bucket,
            last_bucket,
            num_buckets
        """,
        scalar_metric_types="""
            "scalars",
            "keyed-scalars"
        """,
        boolean_metric_types="""
            "boolean",
            "keyed-scalar-boolean"
        """,
    )


def glean_variables():
    """Variables for probe_counts."""
    return dict(
        attributes=["ping_type", "os", "app_version", "app_build_id", "channel"],
        aggregate_attributes="""
            metric,
            metric_type,
            key
        """,
        aggregate_grouping="""
            client_agg_type,
            agg_type
        """,
        # not boolean
        scalar_metric_types="""
            "counter",
            "quantity",
            "labeled_counter"
        """,
        boolean_metric_types="""
            "boolean"
        """,
    )


def main():
    """Generate query for counting."""
    parser = ArgumentParser(description=main.__doc__)
    parser.add_argument(
        "--ping-type",
        default="glean",
        choices=["glean", "telemetry"],
        help="determine attributes and user data types to aggregate",
    )
    parser.add_argument(
        "--source-table", default="glam_etl.fenix_clients_scalar_bucket_counts_v1"
    )
    parser.add_argument(
        "--histogram",
        action="store_true",
        help="generate probe counts for histograms instead of scalars",
    )
    args = parser.parse_args()
    module_name = "bigquery_etl.glam.probe_counts"
    header = f"-- generated by: python3 -m {module_name}"
    header += " " + " ".join(
        [f"--{k} {v}" for k, v in vars(args).items() if k != "histogram"]
    )
    header += "--histogram" if args.histogram else ""

    variables = (
        telemetry_variables() if args.ping_type == "telemetry" else glean_variables()
    )
    if args.ping_type == "telemetry" and args.histogram:
        raise ValueError("histograms not supported for telemetry")

    print(
        render_query(
            header=header,
            is_scalar=not args.histogram,
            source_table=args.source_table,
            **variables,
        )
    )


if __name__ == "__main__":
    main()
