from datetime import datetime, timedelta, timezone
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from itertools import chain
from typing import Any
import httpx
import json
import math
from mcp.server.fastmcp import FastMCP
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.routing import Route, Mount
import asyncio

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import os

# Initialize FastMCP server
mcp = FastMCP("MARS", log_level="ERROR")

# Constants
MCP_SERVER_URL = "http://192.168.42.140:5050"
FILE_DIR = "file"
MARS_SERVER_URL = "http://192.168.40.135:38181"
MARS_USER_NAME = "karaf"
MARS_PASSWORD = "AccP@88w0rdd"

### MARS MCP tools ###
@mcp.tool()
async def mars_get_controller_connection_status_string() -> str:
    """Get MARS controller connection status.

    Note:
        MARS is a hardware independent controller for building
        Software Defined Networking(SDN) and Network Function Virtualization(NFV) solutions.

    Returns:
        Returns a string containing the total count of controllers,
        the count of controllers online, and the count of controllers offline.
    """
    # Get MARS cluster
    url = f"{MARS_SERVER_URL}/mars/v1/cluster"
    response = await mars_get_request(url)
    resp_json = response.json()

    if not resp_json or "nodes" not in resp_json:
        return "Unable to obtain MARS controller connection status."

    if not resp_json["nodes"]:
        return "No MARS controller connected."

    controller_total_count = len(resp_json["nodes"])
    controller_online_count = 0
    for node in resp_json["nodes"]:
        if node.get("status") == "ACTIVE":
            controller_online_count += 1

    return (
        f"Total: {controller_total_count}\n"
        f"Online: {controller_online_count}\n"
        f"Offline: {controller_total_count - controller_online_count}"
    )

@mcp.tool()
async def mars_get_switch_connection_status_string() -> str:
    """Get MARS switch connection status.

    Note:
        MARS is a hardware independent controller for building
        Software Defined Networking(SDN) and Network Function Virtualization(NFV) solutions.

    Returns:
        Returns a string containing the total count of switches,
        the count of switches online, and the count of switches offline.
    """
    # Get MARS devices config
    url = f"{MARS_SERVER_URL}/mars/v1/devices/config"
    response = await mars_get_request(url)
    resp_json = response.json()

    if not resp_json or "configs" not in resp_json:
        return "Unable to obtain MARS switch configs."

    switch_total_count = len(resp_json["configs"])

    # Get MARS devices
    url = f"{MARS_SERVER_URL}/mars/v1/devices"
    response = await mars_get_request(url)
    resp_json = response.json()

    if not resp_json or "devices" not in resp_json:
        return "Unable to obtain MARS switch connection status."

    switch_online_count = 0
    for device in resp_json["devices"]:
        if device.get("available"):
            switch_online_count += 1

    return (
        f"Total: {switch_total_count}\n"
        f"Online: {switch_online_count}\n"
        f"Offline: {switch_total_count - switch_online_count}"
    )

@mcp.tool()
async def mars_get_alert_count_string() -> str:
    """Get MARS alert count of real-time and history.

    Note:
        MARS is a hardware independent controller for building
        Software Defined Networking(SDN) and Network Function Virtualization(NFV) solutions.

    Returns:
        Returns a string containing the total count of alert,
        the count of real-time alert, and the count of history alert.
    """
    # Get MARS real-time alert
    url = f"{MARS_SERVER_URL}/mars/alert/v1/realtime/list?start=0&number=0"
    response = await mars_get_request(url)
    resp_json = response.json()

    if not resp_json or "count" not in resp_json:
        return "Unable to obtain MARS real-time alert."

    realtime_alert_count = resp_json.get("count")

    # Get MARS history alert
    url = f"{MARS_SERVER_URL}/mars/alert/v1/history/list?start=0&number=0"
    response = await mars_get_request(url)
    resp_json = response.json()

    if not resp_json or "count" not in resp_json:
        return "Unable to obtain MARS history alert."

    history_alert_count = resp_json.get("count")

    return (
        f"Total: {realtime_alert_count + history_alert_count}\n"
        f"Real-time: {realtime_alert_count}\n"
        f"History: {history_alert_count}"
    )

@mcp.tool()
async def mars_get_switch_cpu_usage_ranking_string() -> str:
    """Get MARS switch cpu usage ranking.

    Note:
        MARS is a hardware independent controller for building
        Software Defined Networking(SDN) and Network Function Virtualization(NFV) solutions.

    Returns:
        Returns string of the top five switch names and switch CPU usage based on CPU usage.
    """
    # Get MARS switch cpu usage
    time_now = datetime.now(timezone.utc)
    time_30_sec_ago = (time_now - timedelta(seconds=30))

    time_start = time_30_sec_ago.isoformat(timespec='seconds').replace('+00:00', 'Z')
    time_end = time_now.isoformat(timespec='seconds').replace('+00:00', 'Z')
    resolution_second = 15
    url = f"{MARS_SERVER_URL}/mars/analyzer/v1/timerangebar_all/switch/cpu/{time_start}/{time_end}/{resolution_second}"
    response = await mars_get_request(url)
    resp_json = response.json()

    if not resp_json or "cpu" not in resp_json:
        return "Unable to obtain MARS switch CPU usage."

    if not resp_json["cpu"]:
        return "No switch CPU usage statistics."

    cpu_usage_data_list = []
    for cpu in resp_json["cpu"]:
        host = cpu.get("host")
        resources = cpu.get("resources")

        # Check if resources has data
        if not resources:
            continue

        # Obtain the first resource information
        resource = resources[0]

        # Check if used_percent exists
        used_percent = resource.get("used_percent")
        if used_percent is None:
            continue

        cpu_usage_data_list.append((host, used_percent))

    cpu_usage_top_5 = sorted(cpu_usage_data_list, key=lambda x: x[1], reverse=True)[:5]

    index = 0
    results = []
    for host, used_percent in cpu_usage_top_5:
        index += 1
        result_str = (
            f"#{index}\n"
            f"Switch name: {host}\n"
            f"CPU usage: {used_percent}%"
        )
        results.append(result_str.strip()) # Remove extra indentation spaces

    return "\n---\n".join(results)

@mcp.tool()
async def mars_get_switch_cpu_usage_ranking_chart() -> str:
    """Get MARS switch cpu usage ranking chart.
    If the UI supports Mermaid.js, the chart must be rendered directly.
    This is for MCP tools, automatic inference will cause errors.

    Note:
        MARS is a hardware independent controller for building
        Software Defined Networking(SDN) and Network Function Virtualization(NFV) solutions.

    Returns:
        Returns Mermaid.js chart syntax of the top five switch names and switch CPU usage based on CPU usage.
    """
    # Get MARS switch cpu usage
    time_now = datetime.now(timezone.utc)
    time_30_sec_ago = (time_now - timedelta(seconds=30))

    time_start = time_30_sec_ago.isoformat(timespec='seconds').replace('+00:00', 'Z')
    time_end = time_now.isoformat(timespec='seconds').replace('+00:00', 'Z')
    resolution_second = 15
    url = f"{MARS_SERVER_URL}/mars/analyzer/v1/timerangebar_all/switch/cpu/{time_start}/{time_end}/{resolution_second}"
    response = await mars_get_request(url)
    resp_json = response.json()

    if not resp_json or "cpu" not in resp_json:
        return "Unable to obtain MARS switch CPU usage."

    if not resp_json["cpu"]:
        return "No switch CPU usage statistics."

    cpu_usage_data_list = []
    for cpu in resp_json["cpu"]:
        host = cpu.get("host")
        resources = cpu.get("resources")

        # Check if resources has data
        if not resources:
            continue

        # Obtain the first resource information
        resource = resources[0]

        # Check if used_percent exists
        used_percent = resource.get("used_percent")
        if used_percent is None:
            continue

        cpu_usage_data_list.append((host, used_percent))

    cpu_usage_top_5 = sorted(cpu_usage_data_list, key=lambda x: x[1], reverse=True)[:5]

    return (mermaid_chart_count_prompt() +
            generate_bar_chart(
                title ="交換器CPU前5即時",
                x_axis_name = "",
                y_axis_name = "CPU usage (%)",
                keys = [item[0] for item in cpu_usage_top_5],
                values = [item[1] for item in cpu_usage_top_5],
                range_min = 0,
                range_max = 100
            ))

@mcp.tool()
async def mars_get_switch_memory_usage_proportion_string() -> str:
    """Get MARS switch memory usage proportion.

    Note:
        MARS is a hardware independent controller for building
        Software Defined Networking(SDN) and Network Function Virtualization(NFV) solutions.

    Returns:
        Returns string of the switch names and switch memory usage proportion.
    """
    # Get MARS switch memory usage
    time_now = datetime.now(timezone.utc)
    time_30_sec_ago = (time_now - timedelta(seconds=30))

    time_start = time_30_sec_ago.isoformat(timespec='seconds').replace('+00:00', 'Z')
    time_end = time_now.isoformat(timespec='seconds').replace('+00:00', 'Z')
    resolution_second = 15
    url = f"{MARS_SERVER_URL}/mars/analyzer/v1/timerangebar_all/switch/memory/{time_start}/{time_end}/{resolution_second}"
    response = await mars_get_request(url)
    resp_json = response.json()

    if not resp_json or "memory" not in resp_json:
        return "Unable to obtain MARS switch memory usage."

    if not resp_json["memory"]:
        return "No switch memory usage statistics."

    memory_usage_data_dict = {}
    for memory in resp_json["memory"]:
        host = memory.get("host")
        resources = memory.get("resources")

        # Check if resources has data
        if not resources:
            continue

        # Obtain the first resource information
        resource = resources[0]

        # Check if used_percent exists
        used_percent = resource.get("used_percent")
        if used_percent is None:
            continue

        memory_usage_data_dict[host] = used_percent

    results = []
    usage_data_sum = sum(memory_usage_data_dict.values())
    for key, value in memory_usage_data_dict.items():
        proportion = value / usage_data_sum * 100 if usage_data_sum > 0 else 0
        result_str = (
            f"Switch name: {key}\n"
            f"Memory usage: {value}%\n"
            f"Proportion: {proportion:.1f}%"
        )
        results.append(result_str.strip()) # Remove extra indentation spaces

    return "\n---\n".join(results)

@mcp.tool()
async def mars_get_switch_memory_usage_proportion_chart() -> str:
    """Get MARS switch memory usage proportion chart.
    If the UI supports Mermaid.js, the chart must be rendered directly.
    This is for MCP tools, automatic inference will cause errors.

    Note:
        MARS is a hardware independent controller for building
        Software Defined Networking(SDN) and Network Function Virtualization(NFV) solutions.

    Returns:
        Returns Mermaid.js chart syntax of the switch names and switch memory usage proportion.
    """
    # Get MARS switch memory usage
    time_now = datetime.now(timezone.utc)
    time_30_sec_ago = (time_now - timedelta(seconds=30))

    time_start = time_30_sec_ago.isoformat(timespec='seconds').replace('+00:00', 'Z')
    time_end = time_now.isoformat(timespec='seconds').replace('+00:00', 'Z')
    resolution_second = 15
    url = f"{MARS_SERVER_URL}/mars/analyzer/v1/timerangebar_all/switch/memory/{time_start}/{time_end}/{resolution_second}"
    response = await mars_get_request(url)
    resp_json = response.json()

    if not resp_json or "memory" not in resp_json:
        return "Unable to obtain MARS switch memory usage."

    if not resp_json["memory"]:
        return "No switch memory usage statistics."

    memory_usage_data_dict = {}
    for memory in resp_json["memory"]:
        host = memory.get("host")
        resources = memory.get("resources")

        # Check if resources has data
        if not resources:
            continue

        # Obtain the first resource information
        resource = resources[0]

        # Check if used_percent exists
        used_percent = resource.get("used_percent")
        if used_percent is None:
            continue

        host += f" ({used_percent}%)"
        memory_usage_data_dict[host] = used_percent

    return (mermaid_chart_count_prompt() +
            generate_pie_chart(title="交換器即時記憶體資源", data=memory_usage_data_dict))

@mcp.tool()
async def mars_get_switch_disk_usage_proportion_string() -> str:
    """Get MARS switch disk usage proportion.

    Note:
        MARS is a hardware independent controller for building
        Software Defined Networking(SDN) and Network Function Virtualization(NFV) solutions.

    Returns:
        Returns string of the switch names and switch disk usage proportion.
    """
    # Get MARS switch disk usage
    time_now = datetime.now(timezone.utc)
    time_30_sec_ago = (time_now - timedelta(seconds=30))

    time_start = time_30_sec_ago.isoformat(timespec='seconds').replace('+00:00', 'Z')
    time_end = time_now.isoformat(timespec='seconds').replace('+00:00', 'Z')
    resolution_second = 15
    url = f"{MARS_SERVER_URL}/mars/analyzer/v1/timerangebar_all/switch/disk/{time_start}/{time_end}/{resolution_second}"
    response = await mars_get_request(url)
    resp_json = response.json()

    if not resp_json or "disk" not in resp_json:
        return "Unable to obtain MARS switch disk usage."

    if not resp_json["disk"]:
        return "No switch disk usage statistics."

    disk_usage_data_dict = {}
    for disk in resp_json["disk"]:
        host = disk.get("host")
        resources = disk.get("resources")

        # Check if resources has data
        if not resources:
            continue

        # Obtain the first resource information
        resource = resources[0]

        # Check if used_percent exists
        used_percent = resource.get("used_percent")
        if used_percent is None:
            continue

        disk_usage_data_dict[host] = used_percent

    results = []
    usage_data_sum = sum(disk_usage_data_dict.values())
    for key, value in disk_usage_data_dict.items():
        proportion = value / usage_data_sum * 100 if usage_data_sum > 0 else 0
        result_str = (
            f"Switch name: {key}\n"
            f"Disk usage: {value}%\n"
            f"Proportion: {proportion:.1f}%"
        )
        results.append(result_str.strip()) # Remove extra indentation spaces

    return "\n---\n".join(results)

@mcp.tool()
async def mars_get_switch_disk_usage_proportion_chart() -> str:
    """Get MARS switch disk usage proportion chart.
    If the UI supports Mermaid.js, the chart must be rendered directly.
    This is for MCP tools, automatic inference will cause errors.

    Note:
        MARS is a hardware independent controller for building
        Software Defined Networking(SDN) and Network Function Virtualization(NFV) solutions.

    Returns:
        Returns Mermaid.js chart syntax of the switch names and switch disk usage proportion.
    """
    # Get MARS switch disk usage
    time_now = datetime.now(timezone.utc)
    time_30_sec_ago = (time_now - timedelta(seconds=30))

    time_start = time_30_sec_ago.isoformat(timespec='seconds').replace('+00:00', 'Z')
    time_end = time_now.isoformat(timespec='seconds').replace('+00:00', 'Z')
    resolution_second = 15
    url = f"{MARS_SERVER_URL}/mars/analyzer/v1/timerangebar_all/switch/disk/{time_start}/{time_end}/{resolution_second}"
    response = await mars_get_request(url)
    resp_json = response.json()

    if not resp_json or "disk" not in resp_json:
        return "Unable to obtain MARS switch disk usage."

    if not resp_json["disk"]:
        return "No switch disk usage statistics."

    disk_usage_data_dict = {}
    for disk in resp_json["disk"]:
        host = disk.get("host")
        resources = disk.get("resources")

        # Check if resources has data
        if not resources:
            continue

        # Obtain the first resource information
        resource = resources[0]

        # Check if used_percent exists
        used_percent = resource.get("used_percent")
        if used_percent is None:
            continue

        host += f" ({used_percent}%)"
        disk_usage_data_dict[host] = used_percent

    return (mermaid_chart_count_prompt() +
            generate_pie_chart(title="交換器即時硬碟資源", data=disk_usage_data_dict))

@mcp.tool()
async def mars_get_controller_resource_usage_proportion_string() -> str:
    """Get MARS controller resource usage proportion.

    Note:
        MARS is a hardware independent controller for building
        Software Defined Networking(SDN) and Network Function Virtualization(NFV) solutions.

    Returns:
        Returns string of the controller IP and resource usage proportion.
    """
    time_now = datetime.now(timezone.utc)
    time_30_sec_ago = (time_now - timedelta(seconds=30))

    time_start = time_30_sec_ago.isoformat(timespec='seconds').replace('+00:00', 'Z')
    time_end = time_now.isoformat(timespec='seconds').replace('+00:00', 'Z')
    resolution_second = 15

    # Get MARS controller resource usage
    # In resource_data_dict, includes CPU, memory, and disk usage for each controller.
    # e.g. {"<controller IP>": [<CPU>, <memory>, <disk>]}
    resource_data_dict = {}
    resource_type_tuple = ("cpu", "memory", "disk")
    for index, resource_type in enumerate(resource_type_tuple):
        url = f"{MARS_SERVER_URL}/mars/analyzer/v1/timerangebar_all/ctrl/{resource_type}/{time_start}/{time_end}/{resolution_second}"
        response = await mars_get_request(url)
        resp_json = response.json()

        if not resp_json or resource_type not in resp_json:
            return f"Unable to obtain MARS controller {resource_type} usage."

        if not resp_json[resource_type]:
            continue

        for data in resp_json[resource_type]:
            host = data.get("host")
            resources = data.get("resources")

            # Check if resources has data
            if not resources:
                continue

            # Obtain the first resource information
            resource = resources[0]

            # Check if usage exists
            if resource_type == "cpu":
                usage = resource.get("user_percent")
            else:
                usage = resource.get("used_percent")

            if usage is None:
                continue

            # If controller doesn't exist in resource_data_dict, initialize a resource list.
            # The elements in the resource list are CPU usage, memory usage, and disk usage in order.
            if host not in resource_data_dict:
                resource_data_dict[host] = [None, None, None]

            resource_data_dict[host][index] = usage

    results = []
    for key, value in resource_data_dict.items():
        cpu_usage = f"{value[0]:.1f}%" if value[0] is not None else "N/A"
        memory_usage = f"{value[1]:.1f}%" if value[1] is not None else "N/A"
        disk_usage = f"{value[2]:.1f}%" if value[2] is not None else "N/A"

        result_str = (
            f"Controller IP: {key}\n"
            f"CPU usage: {cpu_usage}\n"
            f"Memory usage: {memory_usage}\n"
            f"Disk usage: {disk_usage}"
        )
        results.append(result_str.strip()) # Remove extra indentation spaces

    return "\n---\n".join(results)

@mcp.tool()
async def mars_get_controller_resource_usage_proportion_chart() -> str:
    """Get MARS controller resource usage proportion chart.
    If the UI supports Mermaid.js, the chart must be rendered directly.
    This is for MCP tools, automatic inference will cause errors.

    Note:
        MARS is a hardware independent controller for building
        Software Defined Networking(SDN) and Network Function Virtualization(NFV) solutions.

    Returns:
        Returns Mermaid.js chart syntax of the controller IP and resource usage proportion.
    """
    time_now = datetime.now(timezone.utc)
    time_30_sec_ago = (time_now - timedelta(seconds=30))

    time_start = time_30_sec_ago.isoformat(timespec='seconds').replace('+00:00', 'Z')
    time_end = time_now.isoformat(timespec='seconds').replace('+00:00', 'Z')
    resolution_second = 15

    # Get MARS controller resource usage
    # In resource_data_dict, includes CPU, memory, and disk usage for each controller.
    # e.g. {"<controller IP>": [<CPU>, <memory>, <disk>]}
    resource_data_dict = {}
    resource_type_tuple = ("cpu", "memory", "disk")
    for index, resource_type in enumerate(resource_type_tuple):
        url = f"{MARS_SERVER_URL}/mars/analyzer/v1/timerangebar_all/ctrl/{resource_type}/{time_start}/{time_end}/{resolution_second}"
        response = await mars_get_request(url)
        resp_json = response.json()

        if not resp_json or resource_type not in resp_json:
            return f"Unable to obtain MARS controller {resource_type} usage."

        if not resp_json[resource_type]:
            continue

        for data in resp_json[resource_type]:
            host = data.get("host")
            resources = data.get("resources")

            # Check if resources has data
            if not resources:
                continue

            # Obtain the first resource information
            resource = resources[0]

            # Check if usage exists
            if resource_type == "cpu":
                usage = resource.get("user_percent")
            else:
                usage = resource.get("used_percent")

            if usage is None:
                continue

            # If controller doesn't exist in resource_data_dict, initialize a resource list.
            # The elements in the resource list are CPU usage, memory usage, and disk usage in order.
            if host not in resource_data_dict:
                resource_data_dict[host] = [None, None, None]

            resource_data_dict[host][index] = usage

    results = [mermaid_chart_count_prompt(len(resource_data_dict))]
    for key, value in resource_data_dict.items():
        cpu_usage = round(value[0], 1) if value[0] is not None else 0
        memory_usage = round(value[1], 1) if value[1] is not None else 0
        disk_usage = round(value[2], 1) if value[2] is not None else 0

        result_chart = generate_bar_chart(
            title = "控制器即時資源",
            x_axis_name = f"{key}",
            y_axis_name = "Resource usage (%)",
            keys = resource_type_tuple,
            values = [cpu_usage, memory_usage, disk_usage],
            range_min = 0,
            range_max = 100
        )
        results.append(result_chart)

    return "".join(results)

@mcp.tool()
async def mars_get_switch_simple_topology_diagram() -> str:
    """Get MARS switch simple topology diagram.
    If the UI supports Mermaid.js, the chart must be rendered directly.
    This is for MCP tools, automatic inference will cause errors.

    Note:
        MARS is a hardware independent controller for building
        Software Defined Networking(SDN) and Network Function Virtualization(NFV) solutions.

    Returns:
        Returns Mermaid.js chart syntax of the switch simple topology diagram.
        You just need to output it "as is", don't make any inferences or modifications,
        don't add any connections or nodes.
    """
    # Get MARS devices config
    url = f"{MARS_SERVER_URL}/mars/v1/devices/config"
    response = await mars_get_request(url)
    resp_json = response.json()

    if not resp_json or "configs" not in resp_json:
        return "Unable to obtain MARS switch configs."

    if not resp_json["configs"]:
        return "No switch configs."

    # In switch_dict, includes name and IP for each switch.
    # e.g. {"<switch ID>": {"name": <switch name>, "ip": <switch IP>}}
    switch_dict = {}
    for config in resp_json["configs"]:
        switch_id = config.get("id")
        switch_name = config.get("name")
        switch_ip = config.get("mgmtIpAddress")
        switch_dict[switch_id] = {"name": switch_name, "ip": switch_ip}

    # Get MARS switch link
    url = f"{MARS_SERVER_URL}/mars/v1/links"
    response = await mars_get_request(url)
    resp_json = response.json()

    if not resp_json or "links" not in resp_json:
        return "Unable to obtain MARS switch links."

    if not resp_json["links"]:
        return "No switch links."

    link_set = set()
    for link in resp_json["links"]:
        src_switch = link.get("src").get("device")
        dst_switch = link.get("dst").get("device")
        link_set.add((src_switch, dst_switch))

    link_pair_set = set()
    for src, dst in link_set:
        if (dst, src) in link_set:
            src_name = switch_dict[src]["name"]
            dst_name = switch_dict[dst]["name"]

            # Use sorting to unify pairs in both directions into one key
            pair = tuple(sorted((src_name, dst_name)))

            # Avoid duplicate records
            if pair not in link_pair_set:
                link_pair_set.add(pair)

    return (mermaid_chart_count_prompt() +
            generate_simple_topology(nodes=switch_dict, links=link_pair_set))

@mcp.tool()
async def mars_get_recent_event_string() -> str:
    """Get MARS recent event.

    Note:
        MARS is a hardware independent controller for building
        Software Defined Networking(SDN) and Network Function Virtualization(NFV) solutions.

    Returns:
        Returns a string containing the recent 10 events.
    """
    # Get MARS event
    url = f"{MARS_SERVER_URL}/mars/utility/event/v1/all"
    response = await mars_get_request(url)
    resp_json = response.json()

    if not resp_json or "events" not in resp_json:
        return "Unable to obtain MARS events."

    if not resp_json["events"]:
        return "No events."

    results = []
    for event in resp_json["events"][:10]:
        event_str = (
            f"Timestamp: {event.get('timestamp', 'Unknown')}\n"
            f"Date: {event.get('date', 'Unknown')}\n"
            f"Event type: {event.get('event', 'Unknown')}\n"
            f"Payload: {event.get('payload', 'Unknown')}"
        )
        results.append(event_str.strip()) # Remove extra indentation spaces

    return "\n---\n".join(results)

@mcp.tool()
async def mars_get_switch_recent_network_traffic_ranking_string() -> str:
    """Get MARS switch recent network traffic ranking.

    Note:
        MARS is a hardware independent controller for building
        Software Defined Networking(SDN) and Network Function Virtualization(NFV) solutions.

    Returns:
        Returns string of the top five switch names and switch recent network bytes throughput average.
    """
    # Get MARS switch port statistics
    time_now = datetime.now(timezone.utc)
    time_10_min_ago = (time_now - timedelta(minutes=10))

    time_start = time_10_min_ago.isoformat(timespec='seconds').replace('+00:00', 'Z')
    time_end = time_now.isoformat(timespec='seconds').replace('+00:00', 'Z')
    resolution_second = 40
    url = f"{MARS_SERVER_URL}/mars/analyzer/v1/timerangebar_all/switch_ports/{time_start}/{time_end}/{resolution_second}"
    response = await mars_get_request(url)
    resp_json = response.json()

    if not resp_json or "portstats" not in resp_json:
        return "Unable to obtain MARS switch port statistics."

    if not resp_json["portstats"]:
        return "No switch port statistics."

    # In switch_throughput_dict, including the throughput of each switch at each time point,
    # and the average throughput. Throughput list is sorted from oldest to newest.
    # e.g. {"<switch name>": {"throughput_list": [<throughput>, ...], "throughput_avg": <throughput average>}}
    switch_throughput_dict = {}
    for stats in resp_json["portstats"]:
        host = stats.get("host")
        resources = stats.get("resources")[-10:]

        # Check if resources has data
        if not resources:
            continue

        throughput_sum = 0
        throughput_list = []
        for i in range(1, len(resources)):
            current = resources[i]
            previous = resources[i - 1]

            # Calculate the delta of each data point
            # and divide it by the interval time to get the throughput.
            bytes_prev = previous["bytesReceived"] + previous["bytesSent"]
            bytes_curr = current["bytesReceived"] + current["bytesSent"]

            delta_bytes = bytes_curr - bytes_prev
            throughput_bps = delta_bytes / resolution_second # bytes/sec

            throughput_sum += throughput_bps
            throughput_list.append(throughput_bps)
        
        throughput_avg = throughput_sum / len(resources)
        switch_throughput_dict[host] = {
            "throughput_list": throughput_list,
            "throughput_avg": throughput_avg
        }

    traffic_top_5 = sorted(
        switch_throughput_dict.items(),
        key=lambda item: item[1]["throughput_avg"],
        reverse=True
    )[:5]

    index = 0
    results = []
    for host, data in traffic_top_5:
        index += 1
        result_str = (
            f"#{index}\n"
            f"Switch name: {host}\n"
            f"Throughput average: {data['throughput_avg']:.2f} bytes/sec"
        )
        results.append(result_str.strip()) # Remove extra indentation spaces

    return "\n---\n".join(results)

@mcp.tool()
async def mars_get_switch_recent_network_traffic_ranking_chart() -> str:
    """Get MARS switch recent network traffic ranking chart.
    If the UI supports Mermaid.js, the chart must be rendered directly.
    This is for MCP tools, automatic inference will cause errors.

    Note:
        MARS is a hardware independent controller for building
        Software Defined Networking(SDN) and Network Function Virtualization(NFV) solutions.

    Returns:
        Returns Mermaid.js chart syntax of the top five switch names and switch recent network bytes throughput.
        You just need to output it "as is".
        Modification of the content of the output is not permitted,
        nor is unauthorized inference of the output allowed.
    """
    # Get MARS switch port statistics
    time_now = datetime.now(timezone.utc)
    time_10_min_ago = (time_now - timedelta(minutes=10))

    time_start = time_10_min_ago.isoformat(timespec='seconds').replace('+00:00', 'Z')
    time_end = time_now.isoformat(timespec='seconds').replace('+00:00', 'Z')
    resolution_second = 40
    url = f"{MARS_SERVER_URL}/mars/analyzer/v1/timerangebar_all/switch_ports/{time_start}/{time_end}/{resolution_second}"
    response = await mars_get_request(url)
    resp_json = response.json()

    if not resp_json or "portstats" not in resp_json:
        return "Unable to obtain MARS switch port statistics."

    if not resp_json["portstats"]:
        return "No switch port statistics."

    # In switch_throughput_dict, including the throughput of each switch at each time point,
    # and the average throughput. Throughput list is sorted from oldest to newest.
    # e.g. {"<switch name>": {
    #           "timepoint_list": [<timepoint>, ...],
    #           "throughput_list": [<throughput>, ...],
    #           "throughput_avg": <throughput average>}
    #      }
    switch_throughput_dict = {}
    for stats in resp_json["portstats"]:
        host = stats.get("host")
        resources = stats.get("resources")[-10:]

        # Check if resources has data
        if not resources:
            continue

        timepoint_list = []
        throughput_sum = 0
        throughput_list = []
        for i in range(1, len(resources)):
            current = resources[i]
            previous = resources[i - 1]

            # Calculate the delta of each data point
            # and divide it by the interval time to get the throughput.
            bytes_prev = previous["bytesReceived"] + previous["bytesSent"]
            bytes_curr = current["bytesReceived"] + current["bytesSent"]

            delta_bytes = bytes_curr - bytes_prev
            throughput_bps = delta_bytes / resolution_second # bytes/sec

            # Adjust the time format to avoid the problem of too long strings
            utc_dt = datetime.fromisoformat(current["timepoint"].replace("Z", ""))
            local_dt = utc_dt + timedelta(hours=8) # UTC+8
            timepoint = local_dt.strftime("%H:%M:%S")
            timepoint_list.append(timepoint)

            throughput_sum += throughput_bps
            throughput_list.append(throughput_bps)
        
        throughput_avg = throughput_sum / len(resources)
        switch_throughput_dict[host] = {
            "timepoint_list": timepoint_list,
            "throughput_list": throughput_list,
            "throughput_avg": throughput_avg
        }

    traffic_top_5 = sorted(
        switch_throughput_dict.items(),
        key=lambda item: item[1]["throughput_avg"],
        reverse=True
    )[:5]

    index = 0
    results = [mermaid_chart_count_prompt(len(traffic_top_5))]
    for item in traffic_top_5:
        index += 1
        result_chart = generate_line_chart(
            title = "交換器最近流量前5",
            x_axis_name = f"{item[0]} (#{index})",
            y_axis_name = "Throughput (bytes/sec)",
            keys = item[1]["timepoint_list"],
            values = item[1]["throughput_list"],
            range_min = min(item[1]["throughput_list"]),
            range_max = max(item[1]["throughput_list"])
        )
        results.append(result_chart)

    return "".join(results)

@mcp.tool()
async def mars_get_switch_recent_network_packet_count_ranking_string() -> str:
    """Get MARS switch recent network packet count ranking.

    Note:
        MARS is a hardware independent controller for building
        Software Defined Networking(SDN) and Network Function Virtualization(NFV) solutions.

    Returns:
        Returns string of the top five switch names and switch recent network packets throughput average.
    """
    # Get MARS switch port statistics
    time_now = datetime.now(timezone.utc)
    time_10_min_ago = (time_now - timedelta(minutes=10))

    time_start = time_10_min_ago.isoformat(timespec='seconds').replace('+00:00', 'Z')
    time_end = time_now.isoformat(timespec='seconds').replace('+00:00', 'Z')
    resolution_second = 40
    url = f"{MARS_SERVER_URL}/mars/analyzer/v1/timerangebar_all/switch_ports/{time_start}/{time_end}/{resolution_second}"
    response = await mars_get_request(url)
    resp_json = response.json()

    if not resp_json or "portstats" not in resp_json:
        return "Unable to obtain MARS switch port statistics."

    if not resp_json["portstats"]:
        return "No switch port statistics."

    # In switch_throughput_dict, including the throughput of each switch at each time point,
    # and the average throughput. Throughput list is sorted from oldest to newest.
    # e.g. {"<switch name>": {"throughput_list": [<throughput>, ...], "throughput_avg": <throughput average>}}
    switch_throughput_dict = {}
    for stats in resp_json["portstats"]:
        host = stats.get("host")
        resources = stats.get("resources")[-10:]

        # Check if resources has data
        if not resources:
            continue

        throughput_sum = 0
        throughput_list = []
        for i in range(1, len(resources)):
            current = resources[i]
            previous = resources[i - 1]

            # Calculate the delta of each data point
            # and divide it by the interval time to get the throughput.
            packets_prev = previous["packetsReceived"] + previous["packetsSent"]
            packets_curr = current["packetsReceived"] + current["packetsSent"]

            delta_packets = packets_curr - packets_prev
            throughput_pps = delta_packets / resolution_second # packets/sec

            throughput_sum += throughput_pps
            throughput_list.append(throughput_pps)
        
        throughput_avg = throughput_sum / len(resources)
        switch_throughput_dict[host] = {
            "throughput_list": throughput_list,
            "throughput_avg": throughput_avg
        }

    traffic_top_5 = sorted(
        switch_throughput_dict.items(),
        key=lambda item: item[1]["throughput_avg"],
        reverse=True
    )[:5]

    index = 0
    results = []
    for host, data in traffic_top_5:
        index += 1
        result_str = (
            f"#{index}\n"
            f"Switch name: {host}\n"
            f"Throughput average: {data['throughput_avg']:.2f} packets/sec"
        )
        results.append(result_str.strip()) # Remove extra indentation spaces

    return "\n---\n".join(results)

@mcp.tool()
async def mars_get_switch_recent_network_packet_count_ranking_chart() -> str:
    """Get MARS switch recent network packet count ranking chart.
    If the UI supports Mermaid.js, the chart must be rendered directly.
    This is for MCP tools, automatic inference will cause errors.

    Note:
        MARS is a hardware independent controller for building
        Software Defined Networking(SDN) and Network Function Virtualization(NFV) solutions.

    Returns:
        Returns Mermaid.js chart syntax of the top five switch names and switch recent network packets throughput.
        You just need to output it "as is".
        Modification of the content of the output is not permitted,
        nor is unauthorized inference of the output allowed.
    """
    # Get MARS switch port statistics
    time_now = datetime.now(timezone.utc)
    time_10_min_ago = (time_now - timedelta(minutes=10))

    time_start = time_10_min_ago.isoformat(timespec='seconds').replace('+00:00', 'Z')
    time_end = time_now.isoformat(timespec='seconds').replace('+00:00', 'Z')
    resolution_second = 40
    url = f"{MARS_SERVER_URL}/mars/analyzer/v1/timerangebar_all/switch_ports/{time_start}/{time_end}/{resolution_second}"
    response = await mars_get_request(url)
    resp_json = response.json()

    if not resp_json or "portstats" not in resp_json:
        return "Unable to obtain MARS switch port statistics."

    if not resp_json["portstats"]:
        return "No switch port statistics."

    # In switch_throughput_dict, including the throughput of each switch at each time point,
    # and the average throughput. Throughput list is sorted from oldest to newest.
    # e.g. {"<switch name>": {
    #           "timepoint_list": [<timepoint>, ...],
    #           "throughput_list": [<throughput>, ...],
    #           "throughput_avg": <throughput average>}
    #      }
    switch_throughput_dict = {}
    for stats in resp_json["portstats"]:
        host = stats.get("host")
        resources = stats.get("resources")[-10:]

        # Check if resources has data
        if not resources:
            continue

        timepoint_list = []
        throughput_sum = 0
        throughput_list = []
        for i in range(1, len(resources)):
            current = resources[i]
            previous = resources[i - 1]

            # Calculate the delta of each data point
            # and divide it by the interval time to get the throughput.
            packets_prev = previous["packetsReceived"] + previous["packetsSent"]
            packets_curr = current["packetsReceived"] + current["packetsSent"]

            delta_packets = packets_curr - packets_prev
            throughput_pps = delta_packets / resolution_second # packets/sec

            # Adjust the time format to avoid the problem of too long strings
            utc_dt = datetime.fromisoformat(current["timepoint"].replace("Z", ""))
            local_dt = utc_dt + timedelta(hours=8) # UTC+8
            timepoint = local_dt.strftime("%H:%M:%S")
            timepoint_list.append(timepoint)

            throughput_sum += throughput_pps
            throughput_list.append(throughput_pps)
        
        throughput_avg = throughput_sum / len(resources)
        switch_throughput_dict[host] = {
            "timepoint_list": timepoint_list,
            "throughput_list": throughput_list,
            "throughput_avg": throughput_avg
        }

    traffic_top_5 = sorted(
        switch_throughput_dict.items(),
        key=lambda item: item[1]["throughput_avg"],
        reverse=True
    )[:5]

    index = 0
    results = [mermaid_chart_count_prompt(len(traffic_top_5))]
    for item in traffic_top_5:
        index += 1
        result_chart = generate_line_chart(
            title = "交換器最近封包數前5",
            x_axis_name = f"{item[0]} (#{index})",
            y_axis_name = "Throughput (packets/sec)",
            keys = item[1]["timepoint_list"],
            values = item[1]["throughput_list"],
            range_min = min(item[1]["throughput_list"]),
            range_max = max(item[1]["throughput_list"])
        )
        results.append(result_chart)

    return "".join(results)

@mcp.tool()
async def mars_get_switch_force_topology_diagram() -> str:
    """Get MARS switch force topology diagram.
    If the UI supports Mermaid.js, the chart must be rendered directly.
    This is for MCP tools, automatic inference will cause errors.

    Note:
        MARS is a hardware independent controller for building
        Software Defined Networking(SDN) and Network Function Virtualization(NFV) solutions.

    Returns:
        Returns Mermaid.js chart syntax of the switch force topology diagram.
        You just need to output it "as is", don't make any inferences or modifications,
        don't add any connections or nodes.
    """
    # Get MARS devices config
    url = f"{MARS_SERVER_URL}/mars/v1/devices/config"
    response = await mars_get_request(url)
    resp_json = response.json()

    if not resp_json or "configs" not in resp_json:
        return "Unable to obtain MARS switch configs."

    if not resp_json["configs"]:
        return "No switch configs."

    # In switch_dict, includes name and IP for each switch.
    # e.g. {"<switch ID>": {"name": <switch name>, "ip": <switch IP>}}
    switch_dict = {}
    for config in resp_json["configs"]:
        switch_id = config.get("id")
        switch_name = config.get("name")
        switch_ip = config.get("mgmtIpAddress")
        switch_dict[switch_id] = {"name": switch_name, "ip": switch_ip, "state": False}

    # Get MARS devices
    url = f"{MARS_SERVER_URL}/mars/v1/devices"
    response = await mars_get_request(url)
    resp_json = response.json()

    if not resp_json or "devices" not in resp_json:
        return "Unable to obtain MARS switch connection status."

    for device in resp_json["devices"]:
        switch_id = device.get("id")
        switch_state = device.get("available")
        if switch_state and switch_id in switch_dict:
            switch_dict[switch_id]["state"] = True

    # Get MARS switch link
    url = f"{MARS_SERVER_URL}/mars/v1/links"
    response = await mars_get_request(url)
    resp_json = response.json()

    if not resp_json or "links" not in resp_json:
        return "Unable to obtain MARS switch links."

    if not resp_json["links"]:
        return "No switch links."

    link_set = set()
    for link in resp_json["links"]:
        src_switch = link.get("src").get("device")
        dst_switch = link.get("dst").get("device")
        src_port = link.get("src").get("port")
        dst_port = link.get("dst").get("port")
        link_set.add((src_switch, dst_switch, src_port, dst_port))

    link_pair_set = set()
    for src, dst, src_port, dst_port in link_set:
        # Check if there is a reverse connection
        if (dst, src, dst_port, src_port) in link_set:
            src_name = switch_dict[src]["name"]
            dst_name = switch_dict[dst]["name"]

            # Sort to avoid duplicate direction records
            pair = tuple(sorted((src_name, dst_name)))

            # Avoid duplicate records
            if src_name < dst_name:
                pair = (
                    (src_name, src_port),
                    (dst_name, dst_port)
                )
            else:
                pair = (
                    (dst_name, dst_port),
                    (src_name, src_port)
                )

            if pair not in link_pair_set:
                link_pair_set.add(pair)

    return (mermaid_chart_count_prompt() +
            generate_force_topology(nodes=switch_dict, links=link_pair_set))

@mcp.tool()
async def mars_get_controller_information_string() -> str:
    """Get MARS controller information.

    Note:
        MARS is a hardware independent controller for building
        Software Defined Networking(SDN) and Network Function Virtualization(NFV) solutions.

    Returns:
        Returns a string containing controller IP, controller port,
        controller status, and controller last update time.
    """
    # Get MARS cluster
    url = f"{MARS_SERVER_URL}/mars/v1/cluster"
    response = await mars_get_request(url)
    resp_json = response.json()

    if not resp_json or "nodes" not in resp_json:
        return "Unable to obtain MARS controller information."

    if not resp_json["nodes"]:
        return "No MARS controller connected."

    results = []
    for node in resp_json["nodes"]:
        last_update = node.get('lastUpdate')
        if last_update:
            # Convert to seconds
            timestamp_sec = int(last_update) / 1000

            # Defines the time zone of UTC+8
            tz_utc_8 = timezone(timedelta(hours=8))

            # Convert to datetime format (UTC+8)
            dt = datetime.fromtimestamp(timestamp_sec, tz=tz_utc_8)
            last_update = dt.strftime("%Y-%m-%d %H:%M:%S")
        else:
            last_update = 'Unknown'
            
        result_str = (
            f"IP: {node.get('ip', 'Unknown')}\n"
            f"Port: {node.get('tcpPort', 'Unknown')}\n"
            f"Status: {node.get('status', 'Unknown')}\n"
            f"Last update: {last_update}"
        )
        results.append(result_str.strip()) # Remove extra indentation spaces

    return "\n---\n".join(results)

@mcp.tool()
async def mars_get_switch_information_string() -> str:
    """Get MARS switch information.

    Note:
        MARS is a hardware independent controller for building
        Software Defined Networking(SDN) and Network Function Virtualization(NFV) solutions.

    Returns:
        Returns a string containing switch's name, IP, MAC, type, role, rack, availability,
        default config, protocol, network OS, manufacturer, serial number, hardware, and software.
    """
    # Get MARS devices
    url = f"{MARS_SERVER_URL}/mars/v1/devices"
    response = await mars_get_request(url)
    resp_json = response.json()

    if not resp_json or "devices" not in resp_json:
        return "Unable to obtain MARS switch connection status."

    # In switch_available_dict, includes switch ID and available status for each switch.
    # e.g. {"<switch ID>": <available status bool>}
    switch_available_dict = {
        device.get("id"): bool(device.get("available"))
        for device in resp_json["devices"]
    }

    # Get MARS devices config
    url = f"{MARS_SERVER_URL}/mars/v1/devices/config"
    response = await mars_get_request(url)
    resp_json = response.json()

    if not resp_json or "configs" not in resp_json:
        return "Unable to obtain MARS switch configs."

    if not resp_json["configs"]:
        return "No switch configs."
    
    results = []
    for config in resp_json["configs"]:
        switch_id = config.get("id")
        switch_available = switch_available_dict.get(switch_id, False)

        result_str = (
            f"Name: {config.get('name', 'Unknown')}\n"
            f"IP: {config.get('mgmtIpAddress', 'Unknown')}\n"
            f"MAC: {config.get('mac', 'Unknown')}\n"
            f"Type: {config.get('type', 'Unknown')}\n"
            f"Role: {config.get('role', 'Unknown')}\n"
            f"Rack: {config.get('rack_id', 'Unknown')}\n"
            f"Availability: {switch_available}\n"
            f"Default config: {config.get('defaultCfg', 'Unknown')}\n"
            f"Protocol: {config.get('protocol', 'Unknown')}\n"
            f"Network OS: {config.get('nos', 'Unknown')}\n"
            f"Manufacturer: {config.get('mfr', 'Unknown')}\n"
            f"Serial number: {config.get('serial', 'Unknown')}\n"
            f"Hardware: {config.get('hw', 'Unknown')}\n"
            f"Software: {config.get('sw', 'Unknown')}"
        )
        results.append(result_str.strip()) # Remove extra indentation spaces

    return "\n---\n".join(results)

@mcp.tool()
async def mars_get_system_version_string() -> str:
    """Get MARS system version.

    Note:
        MARS is a hardware independent controller for building
        Software Defined Networking(SDN) and Network Function Virtualization(NFV) solutions.

    Returns:
        Returns a string containing controller IP, controller port,
        controller status, and controller last update time.
    """
    # Get MARS version
    url = f"{MARS_SERVER_URL}/mars/utility/v1/version"
    response = await mars_get_request(url)
    resp_json = response.json()

    if not resp_json:
        return "Unable to obtain MARS version information."

    return (
        f"Git commit: {resp_json.get('commit', 'Unknown')}\n"
        f"Version: {resp_json.get('version', 'Unknown')}\n"
        f"Build server: {resp_json.get('build_server', 'Unknown')}\n"
        f"build time: {resp_json.get('build_date', 'Unknown')}\n"
        f"Logstash version: {resp_json.get('logstash', 'Unknown')}\n"
        f"Elasticsearch version: {resp_json.get('elasticsearch', 'Unknown')}\n"
        f"Nginx version: {resp_json.get('nginx', 'Unknown')}"
    )

@mcp.tool()
async def mars_get_application_list_string() -> str:
    """Get MARS all installed applications.

    Note:
        MARS is a hardware independent controller for building
        Software Defined Networking(SDN) and Network Function Virtualization(NFV) solutions.

    Returns:
        Returns a string containing names and categories of all applications.
    """
    url = f"{MARS_SERVER_URL}/mars/v1/applications"
    response = await mars_get_request(url)
    resp_json = response.json()

    if not resp_json or "applications" not in resp_json:
        return "Unable to fetch MARS APPs or no APPs found."

    if not resp_json["applications"]:
        return "No active APPs."

    apps = []
    for app in resp_json["applications"]:
        app_str = (
            f"Name: {app.get('name', 'Unknown')}\n"
            f"Category: {app.get('category', 'Unknown')}"
        )
        apps.append(app_str.strip()) # Remove extra indentation spaces

    return "\n---\n".join(apps)

@mcp.tool()
async def mars_get_application_information_string(name: str) -> str:
    """Get MARS specified application information.

    Note:
        MARS is a hardware independent controller for building
        Software Defined Networking(SDN) and Network Function Virtualization(NFV) solutions.

    Args:
        name: Application name sting

    Returns:
        Returns a string containing specified application's name,
        state, version, category, origin and description.
    """
    url = f"{MARS_SERVER_URL}/mars/v1/applications/{name}"
    response = await mars_get_request(url)
    resp_json = response.json()

    if not resp_json:
        return "Unable to fetch MARS APP or no APP found."

    return (
        f"Name: {resp_json.get('name', 'Unknown')}\n"
        f"State: {resp_json.get('state', 'Unknown')}\n"
        f"Version: {resp_json.get('version', 'Unknown')}\n"
        f"Category: {resp_json.get('category', 'Unknown')}\n"
        f"Origin: {resp_json.get('origin', 'Unknown')}\n"
        f"Description: {resp_json.get('description', 'Unknown')}"
    )

@mcp.tool()
async def mars_activate_application(name: str) -> str:
    """Activate specified MARS application.

    Note:
        MARS is a hardware independent controller for building
        Software Defined Networking(SDN) and Network Function Virtualization(NFV) solutions.

    Args:
        name: Application name sting

    Returns:
        Returns the application activate status string.
    """
    url = f"{MARS_SERVER_URL}/mars/v1/applications/{name}/active"
    response = await mars_post_request(url)

    if response.status_code != 200:
        return "Failed to activate application."

    return f"{name} APP has been successfully active."

@mcp.tool()
async def mars_deactivate_application(name: str) -> str:
    """Deactivate specified MARS application.

    Note:
        MARS is a hardware independent controller for building
        Software Defined Networking(SDN) and Network Function Virtualization(NFV) solutions.

    Args:
        name: Application name sting

    Returns:
        Returns the application deactivate status string.
    """
    url = f"{MARS_SERVER_URL}/mars/v1/applications/{name}/active"
    response = await mars_delete_request(url)

    if response.status_code != 200:
        return "Failed to deactivate application."

    return f"{name} APP has been successfully deactive."

@mcp.tool()
async def mars_add_application(app_file: bytes) -> str:
    # This MCP tool still needs to be adjusted.
    # Currently, it is not possible to make Open WebUI recognize
    # that files need to be brought into this tool.
    """Add specified MARS application.
    This tool allows you to upload a packaged MARS application file (such as a .zip or .tar.gz) 
    and register it into the system via the MARS server.
    Please upload the application package when prompted.

    Note:
        MARS is a hardware independent controller for building
        Software Defined Networking(SDN) and Network Function Virtualization(NFV) solutions.

    Args:
        file: The application file to upload (binary file upload required). 
              Please select the application file from your local device.

    Returns:
        Returns the application add status string.
    """
    url = f"{MARS_SERVER_URL}/mars/v1/applications?activate=false"
    response = await mars_post_request(url=url, data=app_file, content_type="application/octet-stream")

    if response.status_code != 200:
        return "Failed to add application."

    return f"APP has been successfully add."

@mcp.tool()
async def mars_delete_application(name: str) -> str:
    """Delete specified MARS application.

    Note:
        MARS is a hardware independent controller for building
        Software Defined Networking(SDN) and Network Function Virtualization(NFV) solutions.

    Args:
        name: Application name sting

    Returns:
        Returns the application delete status string.
    """
    url = f"{MARS_SERVER_URL}/mars/v1/applications"
    response = await mars_get_request(url)
    resp_json = response.json()

    if not resp_json or "applications" not in resp_json:
        return "Unable to fetch MARS APPs or no APPs found."

    if not resp_json["applications"]:
        return "No active APPs."

    for app in resp_json["applications"]:
        if app["name"] == name:
            url = f"{MARS_SERVER_URL}/mars/v1/applications/{name}"
            response = await mars_delete_request(url)
            if response.status_code == 204:
                return f"{name} application has been successfully delete."
            else:
                return "Failed to delete application."
    
    return f"{name} application not found."

@mcp.tool()
async def mars_get_api_call_count_trend_chart() -> str:
    """Get MARS API call count trend chart.
    If the UI supports Mermaid.js, the chart must be rendered directly.
    This is for MCP tools, automatic inference will cause errors.

    Note:
        MARS is a hardware independent controller for building
        Software Defined Networking(SDN) and Network Function Virtualization(NFV) solutions.

    Returns:
        Returns Mermaid.js chart syntax of the count of recent MARS API call count.
        You just need to output it "as is".
        Modification of the content of the output is not permitted,
        nor is unauthorized inference of the output allowed.
    """
    # Get MARS API call statistics
    time_now = datetime.now(timezone.utc)
    time_10_min_ago = (time_now - timedelta(minutes=10))

    time_start = time_10_min_ago.isoformat(timespec='seconds').replace('+00:00', 'Z')
    time_end = time_now.isoformat(timespec='seconds').replace('+00:00', 'Z')
    resolution_second = 60
    url = f"{MARS_SERVER_URL}/mars/analyzer/v1/nginx/{time_start}/{time_end}/{resolution_second}"
    response = await mars_get_request(url)
    resp_json = response.json()

    if not resp_json or "statistic" not in resp_json:
        return "Unable to obtain MARS API call statistics."

    if not resp_json["statistic"]:
        return "No MARS API call statistics."

    timepoint_list = []
    count_list = []
    for stats in resp_json["statistic"][-10:]:
        # Adjust the time format to avoid the problem of too long strings
        utc_dt = datetime.fromisoformat(stats["timepoint"].replace("Z", ""))
        local_dt = utc_dt + timedelta(hours=8) # UTC+8
        timepoint = local_dt.strftime("%H:%M:%S")
        timepoint_list.append(timepoint)

        count = stats.get("count")
        count_list.append(count)

    return (mermaid_chart_count_prompt() +
            generate_bar_chart(
                title ="API呼叫趨勢",
                x_axis_name = "",
                y_axis_name = "API call count",
                keys = timepoint_list,
                values = count_list,
                range_min = min(count_list),
                range_max = max(count_list)
            ))

@mcp.tool()
async def mars_get_api_call_count_top_10_client_chart() -> str:
    """Get MARS API call count top 10 client chart.
    If the UI supports Mermaid.js, the chart must be rendered directly.
    This is for MCP tools, automatic inference will cause errors.

    Note:
        MARS is a hardware independent controller for building
        Software Defined Networking(SDN) and Network Function Virtualization(NFV) solutions.

    Returns:
        Returns Mermaid.js chart syntax of the client IP and MARS API call count.
    """
    # Get MARS API call statistics
    time_now = datetime.now(timezone.utc)
    time_10_min_ago = (time_now - timedelta(minutes=10))

    time_start = time_10_min_ago.isoformat(timespec='seconds').replace('+00:00', 'Z')
    time_end = time_now.isoformat(timespec='seconds').replace('+00:00', 'Z')
    url = f"{MARS_SERVER_URL}/mars/analyzer/v1/nginx/{time_start}/{time_end}/type/clientip"
    response = await mars_get_request(url)
    resp_json = response.json()

    if not resp_json or "statistic" not in resp_json:
        return "Unable to obtain MARS API call statistics."

    if not resp_json["statistic"]:
        return "No MARS API call statistics."

    # In client_ip_count_dict, includes client IP and MARS API call count for each client.
    # e.g. {"<client IP>": <MARS API call count>}
    client_ip_count_dict = {}
    for stats in resp_json["statistic"]:
        client_ip = stats.get("clientIp") or "Unknown"
        count = stats.get("count")

        client_ip += f" ({count})"
        client_ip_count_dict[client_ip] = count

    client_ip_top_10 = sorted(client_ip_count_dict.items(), key=lambda item: item[1], reverse=True)[:10]

    return (mermaid_chart_count_prompt() +
            generate_pie_chart(title="客戶端IP呼叫API次數前10名", data=dict(client_ip_top_10)))

@mcp.tool()
async def mars_get_api_call_count_top_10_url_chart() -> str:
    """Get MARS API call count top 10 URL chart.
    If the UI supports Mermaid.js, the chart must be rendered directly.
    This is for MCP tools, automatic inference will cause errors.

    Note:
        MARS is a hardware independent controller for building
        Software Defined Networking(SDN) and Network Function Virtualization(NFV) solutions.

    Returns:
        Returns Mermaid.js chart syntax of the MARS API URL and MARS API call count.
    """
    # Get MARS API call statistics
    time_now = datetime.now(timezone.utc)
    time_10_min_ago = (time_now - timedelta(minutes=10))

    time_start = time_10_min_ago.isoformat(timespec='seconds').replace('+00:00', 'Z')
    time_end = time_now.isoformat(timespec='seconds').replace('+00:00', 'Z')
    url = f"{MARS_SERVER_URL}/mars/analyzer/v1/nginx/{time_start}/{time_end}/type/url"
    response = await mars_get_request(url)
    resp_json = response.json()

    if not resp_json or "statistic" not in resp_json:
        return "Unable to obtain MARS API call statistics."

    if not resp_json["statistic"]:
        return "No MARS API call statistics."

    # In url_count_dict, includes MARS API URL and MARS API call count for each client.
    # e.g. {"<MARS API URL>": <MARS API call count>}
    url_count_dict = {}
    for stats in resp_json["statistic"]:
        url = stats.get("url") or "Unknown"
        count = stats.get("count")

        url += f" ({count})"
        url_count_dict[url] = count

    url_top_10 = sorted(url_count_dict.items(), key=lambda item: item[1], reverse=True)[:10]

    return (mermaid_chart_count_prompt() +
            generate_pie_chart(title="URL呼叫API次數前10名", data=dict(url_top_10)))

@mcp.tool()
async def mars_get_system_module_log_top_10_chart() -> str:
    """Get MARS system module log top 10 chart.
    If the UI supports Mermaid.js, the chart must be rendered directly.
    This is for MCP tools, automatic inference will cause errors.

    Note:
        MARS is a hardware independent controller for building
        Software Defined Networking(SDN) and Network Function Virtualization(NFV) solutions.

    Returns:
        Returns Mermaid.js chart syntax of the MARS system module name and module log count.
    """
    # Get MARS system module log statistics
    time_now = datetime.now(timezone.utc)
    time_10_min_ago = (time_now - timedelta(minutes=10))

    time_start = time_10_min_ago.isoformat(timespec='seconds').replace('+00:00', 'Z')
    time_end = time_now.isoformat(timespec='seconds').replace('+00:00', 'Z')
    resolution_second = 600
    url = f"{MARS_SERVER_URL}/mars/analyzer/v1/filebeat/handler/{time_start}/{time_end}/{resolution_second}"
    response = await mars_get_request(url)
    resp_json = response.json()

    if not resp_json or "filebeat" not in resp_json:
        return "Unable to obtain MARS system module log statistics."

    if not resp_json["filebeat"]:
        return "No MARS system module log statistics."

    # In system_module_count_dict includes MARS system module name and module log count for each module.
    # e.g. {"<MARS system module name>": <module log count>}
    system_module_count_dict = {}
    for log in resp_json["filebeat"]:
        handlers = log.get("handlers")

        # Check if handlers has data
        if not handlers:
            continue

        for handler in handlers:
            module_name = handler.get("key") or "Unknown"
            count = handler.get("count")

            if module_name in system_module_count_dict:
                system_module_count_dict[module_name] += count
            else:
                system_module_count_dict[module_name] = count

    # Add module log count to the module name
    system_module_count_dict = {f"{k} ({v})": v for k, v in system_module_count_dict.items()}

    system_module_top_10 = sorted(system_module_count_dict.items(), key=lambda item: item[1], reverse=True)[:10]

    return (mermaid_chart_count_prompt() +
            generate_pie_chart(title="系統模組日誌前10名", data=dict(system_module_top_10)))

@mcp.tool()
async def mars_get_system_thread_log_top_10_chart() -> str:
    """Get MARS system thread log top 10 chart.
    If the UI supports Mermaid.js, the chart must be rendered directly.
    This is for MCP tools, automatic inference will cause errors.

    Note:
        MARS is a hardware independent controller for building
        Software Defined Networking(SDN) and Network Function Virtualization(NFV) solutions.

    Returns:
        Returns Mermaid.js chart syntax of the MARS system thread name and thread log count.
    """
    # Get MARS system thread log statistics
    time_now = datetime.now(timezone.utc)
    time_10_min_ago = (time_now - timedelta(minutes=10))

    time_start = time_10_min_ago.isoformat(timespec='seconds').replace('+00:00', 'Z')
    time_end = time_now.isoformat(timespec='seconds').replace('+00:00', 'Z')
    resolution_second = 600
    url = f"{MARS_SERVER_URL}/mars/analyzer/v1/filebeat/thread/{time_start}/{time_end}/{resolution_second}"
    response = await mars_get_request(url)
    resp_json = response.json()

    if not resp_json or "filebeat" not in resp_json:
        return "Unable to obtain MARS system thread log statistics."

    if not resp_json["filebeat"]:
        return "No MARS system thread log statistics."

    # In system_thread_count_dict includes MARS system thread name and thread log count for each thread.
    # e.g. {"<MARS system thread name>": <thread log count>}
    system_thread_count_dict = {}
    for log in resp_json["filebeat"]:
        threads = log.get("threads")

        # Check if threads has data
        if not threads:
            continue

        for thread in threads:
            thread_name = thread.get("key") or "Unknown"
            count = thread.get("count")

            if thread_name in system_thread_count_dict:
                system_thread_count_dict[thread_name] += count
            else:
                system_thread_count_dict[thread_name] = count

    # Add thread log count to the thread name
    system_thread_count_dict = {f"{k} ({v})": v for k, v in system_thread_count_dict.items()}

    system_thread_top_10 = sorted(system_thread_count_dict.items(), key=lambda item: item[1], reverse=True)[:10]

    return (mermaid_chart_count_prompt() +
            generate_pie_chart(title="系統執行緒日誌前10名", data=dict(system_thread_top_10)))

@mcp.tool()
async def mars_get_switch_cpu_top_10_chart() -> str:
    """Get MARS switch cpu top 10 chart.
    If the UI supports Mermaid.js, the chart must be rendered directly.
    This is for MCP tools, automatic inference will cause errors.

    Note:
        MARS is a hardware independent controller for building
        Software Defined Networking(SDN) and Network Function Virtualization(NFV) solutions.

    Returns:
        Returns Mermaid.js chart syntax of the top ten switch names and switch CPU usage based on CPU usage.
    """
    # Get MARS switch cpu usage
    time_now = datetime.now(timezone.utc)
    time_10_min_ago = (time_now - timedelta(minutes=10))

    time_start = time_10_min_ago.isoformat(timespec='seconds').replace('+00:00', 'Z')
    time_end = time_now.isoformat(timespec='seconds').replace('+00:00', 'Z')
    resolution_second = 60
    url = f"{MARS_SERVER_URL}/mars/analyzer/v1/timerangebar_all/switch/cpu/{time_start}/{time_end}/{resolution_second}"
    response = await mars_get_request(url)
    resp_json = response.json()

    if not resp_json or "cpu" not in resp_json:
        return "Unable to obtain MARS switch CPU usage."

    if not resp_json["cpu"]:
        return "No switch CPU usage statistics."

    # In cpu_usage_data_dict, including the CPU usage of each switch at each time point,
    # and the average CPU usage. CPU usage list is sorted from oldest to newest.
    # e.g. {"<switch name>": {
    #           "timepoint_list": [<timepoint>, ...],
    #           "cpu_usage_list": [<CPU usage>, ...],
    #           "cpu_usage_avg": <CPU usage average>
    #      }
    cpu_usage_data_dict = {}
    for cpu in resp_json["cpu"]:
        host = cpu.get("host")
        resources = cpu.get("resources")[-10:]

        # Check if resources has data
        if not resources:
            continue

        timepoint_list = []
        cpu_usage_sum = 0
        cpu_usage_list = []
        for resource in resources:
            used_percent = resource.get("used_percent")
            cpu_usage_sum += used_percent
            cpu_usage_list.append(used_percent)

            # Adjust the time format to avoid the problem of too long strings
            utc_dt = datetime.fromisoformat(resource["timepoint"].replace("Z", ""))
            local_dt = utc_dt + timedelta(hours=8) # UTC+8
            timepoint = local_dt.strftime("%H:%M:%S")
            timepoint_list.append(timepoint)

        cpu_usage_avg = cpu_usage_sum / len(resources)
        cpu_usage_data_dict[host] = {
            "timepoint_list": timepoint_list,
            "cpu_usage_list": cpu_usage_list,
            "cpu_usage_avg": cpu_usage_avg
        }
    
    # item[0] is dict key
    # item[1] is dict value
    cpu_usage_top_10 = sorted(
        cpu_usage_data_dict.items(),
        key=lambda item: item[1]["cpu_usage_avg"],
        reverse=True
    )[:10]

    param = convert_mars_analyzer_chart_parameters(cpu_usage_top_10, "cpu_usage_list")

    return (mermaid_chart_count_prompt() +
            generate_multiple_line_chart(
                title ="交換器CPU前10名",
                x_axis_name = param["chart_label"],
                y_axis_name = "CPU usage (%)",
                keys = param["chart_timepoint_list"],
                values = param["chart_multiple_values_list"],
                range_min = 0,
                range_max = 100
            ))

@mcp.tool()
async def mars_get_switch_memory_top_10_chart() -> str:
    """Get MARS switch memory top 10 chart.
    If the UI supports Mermaid.js, the chart must be rendered directly.
    This is for MCP tools, automatic inference will cause errors.

    Note:
        MARS is a hardware independent controller for building
        Software Defined Networking(SDN) and Network Function Virtualization(NFV) solutions.

    Returns:
        Returns Mermaid.js chart syntax of the top ten switch names and switch memory usage based on memory usage.
    """
    # Get MARS switch memory usage
    time_now = datetime.now(timezone.utc)
    time_10_min_ago = (time_now - timedelta(minutes=10))

    time_start = time_10_min_ago.isoformat(timespec='seconds').replace('+00:00', 'Z')
    time_end = time_now.isoformat(timespec='seconds').replace('+00:00', 'Z')
    resolution_second = 60
    url = f"{MARS_SERVER_URL}/mars/analyzer/v1/timerangebar_all/switch/memory/{time_start}/{time_end}/{resolution_second}"
    response = await mars_get_request(url)
    resp_json = response.json()

    if not resp_json or "memory" not in resp_json:
        return "Unable to obtain MARS switch memory usage."

    if not resp_json["memory"]:
        return "No switch memory usage statistics."

    # In memory_usage_data_dict, including the memory usage of each switch at each time point,
    # and the average memory usage. memory usage list is sorted from oldest to newest.
    # e.g. {"<switch name>": {
    #           "timepoint_list": [<timepoint>, ...],
    #           "memory_usage_list": [<memory usage>, ...],
    #           "memory_usage_avg": <memory usage average>
    #      }
    memory_usage_data_dict = {}
    for memory in resp_json["memory"]:
        host = memory.get("host")
        resources = memory.get("resources")[-10:]

        # Check if resources has data
        if not resources:
            continue

        timepoint_list = []
        memory_usage_sum = 0
        memory_usage_list = []
        for resource in resources:
            used_percent = resource.get("used_percent")
            memory_usage_sum += used_percent
            memory_usage_list.append(used_percent)

            # Adjust the time format to avoid the problem of too long strings
            utc_dt = datetime.fromisoformat(resource["timepoint"].replace("Z", ""))
            local_dt = utc_dt + timedelta(hours=8) # UTC+8
            timepoint = local_dt.strftime("%H:%M:%S")
            timepoint_list.append(timepoint)

        memory_usage_avg = memory_usage_sum / len(resources)
        memory_usage_data_dict[host] = {
            "timepoint_list": timepoint_list,
            "memory_usage_list": memory_usage_list,
            "memory_usage_avg": memory_usage_avg
        }
    
    # item[0] is dict key
    # item[1] is dict value
    memory_usage_top_10 = sorted(
        memory_usage_data_dict.items(),
        key=lambda item: item[1]["memory_usage_avg"],
        reverse=True
    )[:10]

    param = convert_mars_analyzer_chart_parameters(memory_usage_top_10, "memory_usage_list")

    return (mermaid_chart_count_prompt() +
            generate_multiple_line_chart(
                title ="交換器記憶體前10名",
                x_axis_name = param["chart_label"],
                y_axis_name = "Memory usage (%)",
                keys = param["chart_timepoint_list"],
                values = param["chart_multiple_values_list"],
                range_min = 0,
                range_max = 100
            ))

@mcp.tool()
async def mars_get_switch_disk_top_10_chart() -> str:
    """Get MARS switch disk top 10 chart.
    If the UI supports Mermaid.js, the chart must be rendered directly.
    This is for MCP tools, automatic inference will cause errors.

    Note:
        MARS is a hardware independent controller for building
        Software Defined Networking(SDN) and Network Function Virtualization(NFV) solutions.

    Returns:
        Returns Mermaid.js chart syntax of the top ten switch names and switch disk usage based on disk usage.
    """
    # Get MARS switch disk usage
    time_now = datetime.now(timezone.utc)
    time_10_min_ago = (time_now - timedelta(minutes=10))

    time_start = time_10_min_ago.isoformat(timespec='seconds').replace('+00:00', 'Z')
    time_end = time_now.isoformat(timespec='seconds').replace('+00:00', 'Z')
    resolution_second = 60
    url = f"{MARS_SERVER_URL}/mars/analyzer/v1/timerangebar_all/switch/disk/{time_start}/{time_end}/{resolution_second}"
    response = await mars_get_request(url)
    resp_json = response.json()

    if not resp_json or "disk" not in resp_json:
        return "Unable to obtain MARS switch disk usage."

    if not resp_json["disk"]:
        return "No switch disk usage statistics."

    # In disk_usage_data_dict, including the disk usage of each switch at each time point,
    # and the average disk usage. disk usage list is sorted from oldest to newest.
    # e.g. {"<switch name>": {
    #           "timepoint_list": [<timepoint>, ...],
    #           "disk_usage_list": [<disk usage>, ...],
    #           "disk_usage_avg": <disk usage average>
    #      }
    disk_usage_data_dict = {}
    for disk in resp_json["disk"]:
        host = disk.get("host")
        resources = disk.get("resources")[-10:]

        # Check if resources has data
        if not resources:
            continue

        timepoint_list = []
        disk_usage_sum = 0
        disk_usage_list = []
        for resource in resources:
            used_percent = resource.get("used_percent")
            disk_usage_sum += used_percent
            disk_usage_list.append(used_percent)

            # Adjust the time format to avoid the problem of too long strings
            utc_dt = datetime.fromisoformat(resource["timepoint"].replace("Z", ""))
            local_dt = utc_dt + timedelta(hours=8) # UTC+8
            timepoint = local_dt.strftime("%H:%M:%S")
            timepoint_list.append(timepoint)

        disk_usage_avg = disk_usage_sum / len(resources)
        disk_usage_data_dict[host] = {
            "timepoint_list": timepoint_list,
            "disk_usage_list": disk_usage_list,
            "disk_usage_avg": disk_usage_avg
        }
    
    # item[0] is dict key
    # item[1] is dict value
    disk_usage_top_10 = sorted(
        disk_usage_data_dict.items(),
        key=lambda item: item[1]["disk_usage_avg"],
        reverse=True
    )[:10]

    param = convert_mars_analyzer_chart_parameters(disk_usage_top_10, "disk_usage_list")

    return (mermaid_chart_count_prompt() +
            generate_multiple_line_chart(
                title ="交換器硬碟前10名",
                x_axis_name = param["chart_label"],
                y_axis_name = "Disk usage (%)",
                keys = param["chart_timepoint_list"],
                values = param["chart_multiple_values_list"],
                range_min = 0,
                range_max = 100
            ))

@mcp.tool()
async def mars_get_switch_sent_bytes_traffic_top_10_chart() -> str:
    """Get MARS switch sent bytes traffic top 10 chart.
    If the UI supports Mermaid.js, the chart must be rendered directly.
    This is for MCP tools, automatic inference will cause errors.

    Note:
        MARS is a hardware independent controller for building
        Software Defined Networking(SDN) and Network Function Virtualization(NFV) solutions.

    Returns:
        Returns Mermaid.js chart syntax of the top ten switch names and switch sent bytes based on network throughput.
    """
   # Get MARS switch port statistics
    time_now = datetime.now(timezone.utc)
    time_10_min_ago = (time_now - timedelta(minutes=10))

    time_start = time_10_min_ago.isoformat(timespec='seconds').replace('+00:00', 'Z')
    time_end = time_now.isoformat(timespec='seconds').replace('+00:00', 'Z')
    resolution_second = 60
    url = f"{MARS_SERVER_URL}/mars/analyzer/v1/timerangebar_all/switch_ports/{time_start}/{time_end}/{resolution_second}"
    response = await mars_get_request(url)
    resp_json = response.json()

    if not resp_json or "portstats" not in resp_json:
        return "Unable to obtain MARS switch port statistics."

    if not resp_json["portstats"]:
        return "No switch port statistics."

    # In switch_sent_bytes_dict, including the sent throughput of each switch at each time point,
    # and the average sent throughput. Throughput list is sorted from oldest to newest.
    # e.g. {"<switch name>": {
    #           "timepoint_list": [<timepoint>, ...],
    #           "throughput_list": [<sent throughput>, ...],
    #           "throughput_avg": <sent throughput average>}
    #      }
    switch_sent_bytes_dict = {}
    for stats in resp_json["portstats"]:
        host = stats.get("host")
        resources = stats.get("resources")[-10:]

        # Check if resources has data
        if not resources:
            continue

        timepoint_list = []
        throughput_sum = 0
        throughput_list = []
        for i in range(1, len(resources)):
            current = resources[i]
            previous = resources[i - 1]

            # Calculate the delta of each data point
            # and divide it by the interval time to get the sent throughput.
            bytes_prev = previous["bytesSent"]
            bytes_curr = current["bytesSent"]

            delta_bytes = bytes_curr - bytes_prev
            throughput_bps = round(delta_bytes / resolution_second, 2) # bytes/sec

            # Adjust the time format to avoid the problem of too long strings
            utc_dt = datetime.fromisoformat(current["timepoint"].replace("Z", ""))
            local_dt = utc_dt + timedelta(hours=8) # UTC+8
            timepoint = local_dt.strftime("%H:%M:%S")
            timepoint_list.append(timepoint)

            throughput_sum += throughput_bps
            throughput_list.append(throughput_bps)

        throughput_avg = throughput_sum / len(resources)
        switch_sent_bytes_dict[host] = {
            "timepoint_list": timepoint_list,
            "throughput_list": throughput_list,
            "throughput_avg": throughput_avg
        }

    # item[0] is dict key
    # item[1] is dict value
    sent_bytes_top_10 = sorted(
        switch_sent_bytes_dict.items(),
        key=lambda item: item[1]["throughput_avg"],
        reverse=True
    )[:10]

    param = convert_mars_analyzer_chart_parameters(sent_bytes_top_10, "throughput_list")

    # Iterate over all values ​​and get the maximum and minimum values
    all_values_list = list(chain.from_iterable(param["chart_multiple_values_list"]))
    range_min = min(all_values_list)
    range_max = max(all_values_list)

    return (mermaid_chart_count_prompt() +
            generate_multiple_line_chart(
                title ="交換器發送位元組流量前10名",
                x_axis_name = param["chart_label"],
                y_axis_name = "Sent throughput (bytes/sec)",
                keys = param["chart_timepoint_list"],
                values = param["chart_multiple_values_list"],
                range_min = math.floor(range_min / 5) * 5, # Round down to the nearest multiple of 5
                range_max = math.ceil(range_max / 5) * 5 # Round up to the nearest multiple of 5
            ))

@mcp.tool()
async def mars_get_switch_received_bytes_traffic_top_10_chart() -> str:
    """Get MARS switch received bytes traffic top 10 chart.
    If the UI supports Mermaid.js, the chart must be rendered directly.
    This is for MCP tools, automatic inference will cause errors.

    Note:
        MARS is a hardware independent controller for building
        Software Defined Networking(SDN) and Network Function Virtualization(NFV) solutions.

    Returns:
        Returns Mermaid.js chart syntax of the top ten switch names and switch received bytes based on network throughput.
    """
   # Get MARS switch port statistics
    time_now = datetime.now(timezone.utc)
    time_10_min_ago = (time_now - timedelta(minutes=10))

    time_start = time_10_min_ago.isoformat(timespec='seconds').replace('+00:00', 'Z')
    time_end = time_now.isoformat(timespec='seconds').replace('+00:00', 'Z')
    resolution_second = 60
    url = f"{MARS_SERVER_URL}/mars/analyzer/v1/timerangebar_all/switch_ports/{time_start}/{time_end}/{resolution_second}"
    response = await mars_get_request(url)
    resp_json = response.json()

    if not resp_json or "portstats" not in resp_json:
        return "Unable to obtain MARS switch port statistics."

    if not resp_json["portstats"]:
        return "No switch port statistics."

    # In switch_received_bytes_dict, including the received throughput of each switch at each time point,
    # and the average received throughput. Throughput list is sorted from oldest to newest.
    # e.g. {"<switch name>": {
    #           "timepoint_list": [<timepoint>, ...],
    #           "throughput_list": [<received throughput>, ...],
    #           "throughput_avg": <received throughput average>}
    #      }
    switch_received_bytes_dict = {}
    for stats in resp_json["portstats"]:
        host = stats.get("host")
        resources = stats.get("resources")[-10:]

        # Check if resources has data
        if not resources:
            continue

        timepoint_list = []
        throughput_sum = 0
        throughput_list = []
        for i in range(1, len(resources)):
            current = resources[i]
            previous = resources[i - 1]

            # Calculate the delta of each data point
            # and divide it by the interval time to get the received throughput.
            bytes_prev = previous["bytesReceived"]
            bytes_curr = current["bytesReceived"]

            delta_bytes = bytes_curr - bytes_prev
            throughput_bps = round(delta_bytes / resolution_second, 2) # bytes/sec

            # Adjust the time format to avoid the problem of too long strings
            utc_dt = datetime.fromisoformat(current["timepoint"].replace("Z", ""))
            local_dt = utc_dt + timedelta(hours=8) # UTC+8
            timepoint = local_dt.strftime("%H:%M:%S")
            timepoint_list.append(timepoint)

            throughput_sum += throughput_bps
            throughput_list.append(throughput_bps)

        throughput_avg = throughput_sum / len(resources)
        switch_received_bytes_dict[host] = {
            "timepoint_list": timepoint_list,
            "throughput_list": throughput_list,
            "throughput_avg": throughput_avg
        }

    # item[0] is dict key
    # item[1] is dict value
    received_bytes_top_10 = sorted(
        switch_received_bytes_dict.items(),
        key=lambda item: item[1]["throughput_avg"],
        reverse=True
    )[:10]

    param = convert_mars_analyzer_chart_parameters(received_bytes_top_10, "throughput_list")

    # Iterate over all values ​​and get the maximum and minimum values
    all_values_list = list(chain.from_iterable(param["chart_multiple_values_list"]))
    range_min = min(all_values_list)
    range_max = max(all_values_list)

    return (mermaid_chart_count_prompt() +
            generate_multiple_line_chart(
                title ="交換器接收位元組流量前10名",
                x_axis_name = param["chart_label"],
                y_axis_name = "Received throughput (bytes/sec)",
                keys = param["chart_timepoint_list"],
                values = param["chart_multiple_values_list"],
                range_min = math.floor(range_min / 5) * 5, # Round down to the nearest multiple of 5
                range_max = math.ceil(range_max / 5) * 5 # Round up to the nearest multiple of 5
            ))

@mcp.tool()
async def mars_get_switch_sent_packets_traffic_top_10_chart() -> str:
    """Get MARS switch sent packets traffic top 10 chart.
    If the UI supports Mermaid.js, the chart must be rendered directly.
    This is for MCP tools, automatic inference will cause errors.

    Note:
        MARS is a hardware independent controller for building
        Software Defined Networking(SDN) and Network Function Virtualization(NFV) solutions.

    Returns:
        Returns Mermaid.js chart syntax of the top ten switch names and switch sent packets based on network throughput.
    """
   # Get MARS switch port statistics
    time_now = datetime.now(timezone.utc)
    time_10_min_ago = (time_now - timedelta(minutes=10))

    time_start = time_10_min_ago.isoformat(timespec='seconds').replace('+00:00', 'Z')
    time_end = time_now.isoformat(timespec='seconds').replace('+00:00', 'Z')
    resolution_second = 60
    url = f"{MARS_SERVER_URL}/mars/analyzer/v1/timerangebar_all/switch_ports/{time_start}/{time_end}/{resolution_second}"
    response = await mars_get_request(url)
    resp_json = response.json()

    if not resp_json or "portstats" not in resp_json:
        return "Unable to obtain MARS switch port statistics."

    if not resp_json["portstats"]:
        return "No switch port statistics."

    # In switch_sent_packets_dict, including the sent throughput of each switch at each time point,
    # and the average sent throughput. Throughput list is sorted from oldest to newest.
    # e.g. {"<switch name>": {
    #           "timepoint_list": [<timepoint>, ...],
    #           "throughput_list": [<sent throughput>, ...],
    #           "throughput_avg": <sent throughput average>}
    #      }
    switch_sent_packets_dict = {}
    for stats in resp_json["portstats"]:
        host = stats.get("host")
        resources = stats.get("resources")[-10:]

        # Check if resources has data
        if not resources:
            continue

        timepoint_list = []
        throughput_sum = 0
        throughput_list = []
        for i in range(1, len(resources)):
            current = resources[i]
            previous = resources[i - 1]

            # Calculate the delta of each data point
            # and divide it by the interval time to get the sent throughput.
            packets_prev = previous["packetsSent"]
            packets_curr = current["packetsSent"]

            delta_packets = packets_curr - packets_prev
            throughput_bps = round(delta_packets / resolution_second, 2) # packets/sec

            # Adjust the time format to avoid the problem of too long strings
            utc_dt = datetime.fromisoformat(current["timepoint"].replace("Z", ""))
            local_dt = utc_dt + timedelta(hours=8) # UTC+8
            timepoint = local_dt.strftime("%H:%M:%S")
            timepoint_list.append(timepoint)

            throughput_sum += throughput_bps
            throughput_list.append(throughput_bps)

        throughput_avg = throughput_sum / len(resources)
        switch_sent_packets_dict[host] = {
            "timepoint_list": timepoint_list,
            "throughput_list": throughput_list,
            "throughput_avg": throughput_avg
        }

    # item[0] is dict key
    # item[1] is dict value
    sent_packets_top_10 = sorted(
        switch_sent_packets_dict.items(),
        key=lambda item: item[1]["throughput_avg"],
        reverse=True
    )[:10]

    param = convert_mars_analyzer_chart_parameters(sent_packets_top_10, "throughput_list")

    # Iterate over all values ​​and get the maximum and minimum values
    all_values_list = list(chain.from_iterable(param["chart_multiple_values_list"]))
    range_min = min(all_values_list)
    range_max = max(all_values_list)

    return (mermaid_chart_count_prompt() +
            generate_multiple_line_chart(
                title ="交換器發送封包流量前10名",
                x_axis_name = param["chart_label"],
                y_axis_name = "Sent throughput (packets/sec)",
                keys = param["chart_timepoint_list"],
                values = param["chart_multiple_values_list"],
                range_min = math.floor(range_min / 5) * 5, # Round down to the nearest multiple of 5
                range_max = math.ceil(range_max / 5) * 5 # Round up to the nearest multiple of 5
            ))

@mcp.tool()
async def mars_get_switch_received_packets_traffic_top_10_chart() -> str:
    """Get MARS switch received packets traffic top 10 chart.
    If the UI supports Mermaid.js, the chart must be rendered directly.
    This is for MCP tools, automatic inference will cause errors.

    Note:
        MARS is a hardware independent controller for building
        Software Defined Networking(SDN) and Network Function Virtualization(NFV) solutions.

    Returns:
        Returns Mermaid.js chart syntax of the top ten switch names and switch received packets based on network throughput.
    """
   # Get MARS switch port statistics
    time_now = datetime.now(timezone.utc)
    time_10_min_ago = (time_now - timedelta(minutes=10))

    time_start = time_10_min_ago.isoformat(timespec='seconds').replace('+00:00', 'Z')
    time_end = time_now.isoformat(timespec='seconds').replace('+00:00', 'Z')
    resolution_second = 60
    url = f"{MARS_SERVER_URL}/mars/analyzer/v1/timerangebar_all/switch_ports/{time_start}/{time_end}/{resolution_second}"
    response = await mars_get_request(url)
    resp_json = response.json()

    if not resp_json or "portstats" not in resp_json:
        return "Unable to obtain MARS switch port statistics."

    if not resp_json["portstats"]:
        return "No switch port statistics."

    # In switch_received_packets_dict, including the received throughput of each switch at each time point,
    # and the average received throughput. Throughput list is sorted from oldest to newest.
    # e.g. {"<switch name>": {
    #           "timepoint_list": [<timepoint>, ...],
    #           "throughput_list": [<received throughput>, ...],
    #           "throughput_avg": <received throughput average>}
    #      }
    switch_received_packets_dict = {}
    for stats in resp_json["portstats"]:
        host = stats.get("host")
        resources = stats.get("resources")[-10:]

        # Check if resources has data
        if not resources:
            continue

        timepoint_list = []
        throughput_sum = 0
        throughput_list = []
        for i in range(1, len(resources)):
            current = resources[i]
            previous = resources[i - 1]

            # Calculate the delta of each data point
            # and divide it by the interval time to get the received throughput.
            packets_prev = previous["packetsReceived"]
            packets_curr = current["packetsReceived"]

            delta_packets = packets_curr - packets_prev
            throughput_bps = round(delta_packets / resolution_second, 2) # packets/sec

            # Adjust the time format to avoid the problem of too long strings
            utc_dt = datetime.fromisoformat(current["timepoint"].replace("Z", ""))
            local_dt = utc_dt + timedelta(hours=8) # UTC+8
            timepoint = local_dt.strftime("%H:%M:%S")
            timepoint_list.append(timepoint)

            throughput_sum += throughput_bps
            throughput_list.append(throughput_bps)

        throughput_avg = throughput_sum / len(resources)
        switch_received_packets_dict[host] = {
            "timepoint_list": timepoint_list,
            "throughput_list": throughput_list,
            "throughput_avg": throughput_avg
        }

    # item[0] is dict key
    # item[1] is dict value
    received_packets_top_10 = sorted(
        switch_received_packets_dict.items(),
        key=lambda item: item[1]["throughput_avg"],
        reverse=True
    )[:10]

    param = convert_mars_analyzer_chart_parameters(received_packets_top_10, "throughput_list")

    # Iterate over all values ​​and get the maximum and minimum values
    all_values_list = list(chain.from_iterable(param["chart_multiple_values_list"]))
    range_min = min(all_values_list)
    range_max = max(all_values_list)

    return (mermaid_chart_count_prompt() +
            generate_multiple_line_chart(
                title ="交換器接收封包流量前10名",
                x_axis_name = param["chart_label"],
                y_axis_name = "Received throughput (packets/sec)",
                keys = param["chart_timepoint_list"],
                values = param["chart_multiple_values_list"],
                range_min = math.floor(range_min / 5) * 5, # Round down to the nearest multiple of 5
                range_max = math.ceil(range_max / 5) * 5 # Round up to the nearest multiple of 5
            ))

### Call MARS API related functions ###
async def get_mars_cookies():
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    url = f"{MARS_SERVER_URL}/mars/useraccount/v1/swagger-login"
    json = {"user_name": MARS_USER_NAME, "password": MARS_PASSWORD}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, headers=headers, json=json, timeout=30.0)
            response.raise_for_status()
            return {"marsGSessionId": response.headers["MARS_G_SESSION_ID"]}
        except Exception as e:
            return None

async def mars_post_request(url: str, json: dict[str, Any] = None, data: bytes = None,
                            content_type: str = "application/json"):
    headers = {
        "Content-Type": content_type,
        "Accept": "application/json"
    }
    async with httpx.AsyncClient() as client:
        try:
            cookies = await get_mars_cookies()
            response = await client.post(url, cookies=cookies, headers=headers,
                                        json=json, data=data, timeout=30.0)
            response.raise_for_status()
            return response
        except Exception as e:
            return None

async def mars_get_request(url: str):
    headers = {
        "Accept": "application/json"
    }
    async with httpx.AsyncClient() as client:
        try:
            cookies = await get_mars_cookies()
            response = await client.get(url, cookies=cookies, headers=headers, timeout=30.0)
            response.raise_for_status()
            return response
        except Exception as e:
            print(e)
            return None

async def mars_delete_request(url: str):
    headers = {
        "Accept": "application/json"
    }
    async with httpx.AsyncClient() as client:
        try:
            cookies = await get_mars_cookies()
            response = await client.delete(url, cookies=cookies, headers=headers, timeout=30.0)
            response.raise_for_status()
            return response
        except Exception as e:
            return None

### Convert Mermaid.js syntax template functions ###
def mermaid_line_chart_color_text(index: int) -> str:
    color_text_list = ["藍", "綠", "紅", "黃", "灰", "白", "灰藍", "紫", "青綠", "橘"]
    return color_text_list[index]

def mermaid_chart_count_prompt(count: int = 1) -> str:
    # Added "Show Mermaid.js" prompt to enable Open WebUI to correctly render Mermaid.js charts
    if count < 2:
        return "Show Mermaid.js\n"
    else:
        return f"Show {count} Mermaid.js\n"

def convert_mars_analyzer_chart_parameters(data: list, resource_key: str) -> dict:
    # Need to get the most complete list of time points to use as the x-axis of the chart.
    chart_timepoint_list = []
    for item in data:
        resource = item[1]
        if len(chart_timepoint_list) < len(resource["timepoint_list"]):
            chart_timepoint_list = resource["timepoint_list"]
    
    chart_label = ""
    chart_multiple_values_list = []
    for index, item in enumerate(data):
        name = item[0]
        resource = item[1]

        # Establish the corresponding relationship label
        # between the chart line color and the name.
        # e.g. "Blue:name1 Green:name2"
        chart_label += f"{mermaid_line_chart_color_text(index)}:{name} "

        # When the data length is less than the number of time points on the x-axis of the chart,
        # need to add 0 in front of the data.
        data_list = resource[resource_key]
        data_length = len(data_list)
        chart_timepoint_length = len(chart_timepoint_list)
        if data_length < chart_timepoint_length:
            padding = [0] * (chart_timepoint_length - data_length)
            data_list = padding + data_list

        chart_multiple_values_list.append(data_list)

    return {
        "chart_label": chart_label,
        "chart_timepoint_list": chart_timepoint_list,
        "chart_multiple_values_list": chart_multiple_values_list
    }

def generate_bar_chart(title: str, x_axis_name: str, y_axis_name: str, keys: list | tuple,
                       values: list | tuple, range_min: int,  range_max: int) -> str:
    return (
        "xychart-beta\n"
        f"title \"{title}\"\n"
        f"x-axis \"{x_axis_name}\" {json.dumps(keys)}\n"
        f"y-axis \"{y_axis_name}\" {range_min} --> {range_max}\n"
        f"bar {values}\n"
    )

def generate_line_chart(title: str, x_axis_name: str, y_axis_name: str, keys: list | tuple,
                       values: list | tuple, range_min: int,  range_max: int) -> str:
    return (
        "xychart-beta\n"
        f"title \"{title}\"\n"
        f"x-axis \"{x_axis_name}\" {json.dumps(keys)}\n"
        f"y-axis \"{y_axis_name}\" {range_min} --> {range_max}\n"
        f"line {values}\n"
    )

def generate_multiple_line_chart(title: str, x_axis_name: str, y_axis_name: str, keys: list | tuple,
                                 values: list | tuple, range_min: int,  range_max: int) -> str:
    results = [
        "xychart-beta",
        f"title \"{title}\"",
        f"x-axis \"{x_axis_name}\" {json.dumps(keys)}",
        f"y-axis \"{y_axis_name}\" {range_min} --> {range_max}"
    ]

    # "values" is a two-dimensional list
    for value in values:
        results.append(f"line {value}")
    
    return "\n".join(results) + "\n"

def generate_pie_chart(title: str, data: dict) -> str:
    results = ["pie", f"title {title}"]
    for key, value in data.items():
        results.append(f"\"{key}\" : {value}")
    
    # Combine the elements of the results list with newline characters
    return "\n".join(results) + "\n"

def generate_simple_topology(nodes: dict, links: set) -> str:
    results = ["flowchart LR"]
    for node in nodes.values():
        results.append(f"{node["name"]}(\"{node["name"]}<br>{node["ip"]}\")")

    for a, b in links:
        results.append(f"{a}==={b}")
    
    # Combine the elements of the results list with newline characters
    return "\n".join(results) + "\n"

def generate_force_topology(nodes: dict, links: set) -> str:
    results = ["flowchart LR"]
    for node in nodes.values():
        results.append(f"{node["name"]}(\"{node["name"]}<br>{node["ip"]}\")")
        if not node["state"]:
            results.append(f"style {node["name"]} stroke:#f00")

    for a, b in links:
        results.append(f"{a[0]}===|port {a[1]}---port {b[1]}|{b[0]}")
    
    # Combine the elements of the results list with newline characters
    return "\n".join(results) + "\n"

### Handling Server-Sent Events(SSE) connections ###
transport = SseServerTransport("/messages/")

async def handle_sse(request):
    # Prepare bidirectional streams over SSE
    async with transport.connect_sse(
        request.scope,
        request.receive,
        request._send
    ) as (in_stream, out_stream):
        # Run the MCP server: read JSON-RPC from in_stream, write replies to out_stream
        await mcp._mcp_server.run(
            in_stream,
            out_stream,
            mcp._mcp_server.create_initialization_options()
        )


# Build a small Starlette app for the two MCP endpoints
os.makedirs(FILE_DIR, exist_ok=True)
sse_app = Starlette(
    routes=[
        Route("/sse", handle_sse, methods=["GET"]),
        # Note the trailing slash to avoid 307 redirects
        Mount("/messages/", app=transport.handle_post_message),
        Mount("/file", StaticFiles(directory=FILE_DIR), name=FILE_DIR)
    ]
)

app = FastAPI()
app.mount("/", sse_app)

@app.get("/health")
def read_root():
    return {"message": "MCP SSE Server is running"}

if __name__ == "__main__":
    test = asyncio.run(mars_get_switch_cpu_top_10_chart())
    print(test)
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5050)
