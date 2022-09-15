from dataclasses import dataclass, asdict
import enum
import time
from typing import Any, Dict, List
import docker
from pathlib import Path
import pandas as pd

class ContainerState(enum.Enum):
    restarting = "RESTARTING"
    dead = "DEAD"
    created = "CREATED"
    exited = "EXITED"
    paused = "PAUSED"
    running = "RUNNING"
    removing = "REMOVING"


class MetricType(enum.Enum):
    memory_usage = "MEMORY_USAGE"
    disk_usage = "DISK_USAGE"
    cpu_usage = "CPU_USAGE"
    network_in = "NETWORK_IN"
    network_out = "NETWORK_OUT"

@dataclass
class PercentMetric:
    metric_type: MetricType
    value: float
    total: float
    percent: float

@dataclass
class ContainerSummary:
    id: str
    timestamp: float
    name: str
    image: str
    state: str
    metrics: List[PercentMetric]


def get_container_name(container_name: str) -> str:
    if container_name.startswith("/"):
        return container_name[1:]
    return container_name

def get_metric_from_data(metric_name: str, data: Any) -> PercentMetric:
    if metric_name == "virtual_memory":
        return PercentMetric(
            MetricType.memory_usage, data.used, data.total, data.percent
        )
    elif metric_name == "disk_memory":
        return PercentMetric(MetricType.disk_usage, data.used, data.total, data.percent)
    elif metric_name == "host_cpu_usage":
        percentage = data
        return PercentMetric(MetricType.cpu_usage, percentage, 100, percentage)
    elif metric_name == "container_cpu_usage":
        # NOTE (@bplewnia) - Divide by number of nanoseconds in second -> 10e9
        percentage = (
            abs(
                data["cpu_stats"]["cpu_usage"]["total_usage"]
                - data["precpu_stats"]["cpu_usage"]["total_usage"]
            )
            * 100
            / 10 ** 9
        )
        return PercentMetric(MetricType.cpu_usage, percentage, 100, percentage)
    elif metric_name == "container_memory_usage":
        return (
            PercentMetric(MetricType.memory_usage, 0, 0, 0)
            if not data
            else PercentMetric(
                MetricType.memory_usage,
                data["usage"],
                data["limit"],
                (data["usage"] / data["limit"]) * 100,
            )
        )
    else:
        print(f"DID NOT FIND OPTION FOR {metric_name}")
        return PercentMetric(MetricType.cpu_usage, 0, 0, 0)

def save_metrics_to_file(filename: str, metrics: Dict) -> None:
    json_df = pd.json_normalize(metrics)
    if not Path(filename).exists():
        json_df.to_csv(filename, mode="w+", index=False)
    else:
        json_df.to_csv(filename, mode="a", index=False, header=False)

class DockerAgent:
    def __init__(self) -> None:
        self.docker_client = docker.from_env()
        self.fetch_freq = 60

    def get_containers_summary(self) -> List[ContainerSummary]:
        summaries = []
        timestamp = time.time()
        containers_data = self.docker_client.containers.list()
        for c in containers_data:
            attrs, stats = c.attrs, c.stats(stream=False)

            virtual_memory_metric = get_metric_from_data(
                metric_name="container_memory_usage", data=stats["memory_stats"]
            )
            cpu_metric = get_metric_from_data(
                metric_name="container_cpu_usage", data=stats
            )
            container_summary = ContainerSummary(
                id=attrs["Id"],
                timestamp=timestamp,
                name=get_container_name(attrs["Name"]),
                image=attrs["Config"]["Image"],
                state=ContainerState[attrs["State"]["Status"]].name,
                metrics=[asdict(virtual_memory_metric), asdict(cpu_metric)],
            )

            summaries.append(asdict(container_summary))
        return summaries
    
    def get_networks_info(self) -> List[Dict]:
        summaries = []
        timestamp = time.time()
        networks_data = self.docker_client.networks.list()
        for n in networks_data:
            d = n.attrs
            d['timestamp'] = timestamp
            summaries.append(d)
        return summaries

    def run(self):
        while True:
            containers_info = self.get_containers_summary()
            networks_info = self.get_networks_info()

            for c in containers_info:
                save_metrics_to_file("containers_info.csv", c)
            
            for n in networks_info:
                save_metrics_to_file("networks_info.csv", n)

            print("Containers and networks metrics saved!")
            time.sleep(self.fetch_freq)
    

if __name__ == "__main__":
    agent = DockerAgent()
    agent.run()