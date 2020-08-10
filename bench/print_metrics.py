import sys
from collections import defaultdict
from pathlib import Path

import tabulate


def tryInt(inp):
    try:
        return int(inp)
    except Exception:
        return None


ABOUT_METRICS = {
    "import": "Importing {n} commands from bash history",
    "log": "Logging {n} commands into recent. batch number {batchnum}",
    "query": "Querying {n} commands from recent",
}


def describe_metric(metric):
    split = metric.split(".")
    name = split[0]
    metric_params = {}
    for i in range(1, len(split)):
        if split[i].startswith("batch"):
            metric_params['batchnum'] = tryInt(split[i][5:])
        else:
            metric_params['n'] = metric_params.get('n') or tryInt(split[i])
    return ABOUT_METRICS[name].format(**metric_params)


def print_metrics(metrics, output_location):
    metrics = sorted(metrics.items())
    table_data = []
    for name, v in metrics:
        about = describe_metric(name)
        avg = "{:.2f}".format(sum(v) / len(v))
        range = "{}-{}".format(min(v), max(v))
        table_data.append([name, about, avg, range])

    out = tabulate.tabulate(table_data, headers=["Metric", "About", "Avg", "Range"])
    if output_location:
        Path(output_location).expanduser().absolute().write_text(out)
    else:
        print(out)


if __name__ == '__main__':
    metrics_file = sys.argv[1]
    output_location = sys.argv[2] if len(sys.argv) > 2 else None
    lines = Path(metrics_file).expanduser().absolute().read_text().strip().splitlines()
    metrics = defaultdict(list)
    metric_start_time = {}
    for line in lines:
        metric, event, event_time = line.split(" ")
        event_time = int(event_time)
        if event == "start":
            metric_start_time[metric] = event_time
        else:
            metrics[metric].append(event_time - metric_start_time[metric])
            del metric_start_time[metric]
    print_metrics(metrics, output_location)
