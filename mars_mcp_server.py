from datetime import datetime, timedelta, timezone
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from typing import Any
import httpx
import json
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
    """Get MARS controller connection status

    Note:
        MARS is a hardware independent controller for building
        Software Defined Networking(SDN) and Network Function Virtualization(NFV) solutions.

    Returns:
        Returns a string containing the total count of controllers,
        the count of controllers online, and the count of controllers offline.
    """
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
    """Get MARS switch connection status

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

    switch_online_count = len(resp_json["devices"])

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
        return "Unable to obtain MARS switch cpu usage."

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

    cpu_usage_top5 = sorted(cpu_usage_data_list, key=lambda x: x[1], reverse=True)[:5]

    index = 0
    results = []
    for host, used_percent in cpu_usage_top5:
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
        return "Unable to obtain MARS switch cpu usage."

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

    cpu_usage_top5 = sorted(cpu_usage_data_list, key=lambda x: x[1], reverse=True)[:5]

    return (mermaid_chart_count_prompt() +
            generate_bar_chart(
                title =" 交換器CPU前5即時",
                x_axis_name = "",
                y_axis_name = "CPU usage (%)",
                keys = [item[0] for item in cpu_usage_top5],
                values = [item[1] for item in cpu_usage_top5],
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

        host += f"({used_percent}%)"
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

        host += f"({used_percent}%)"
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
        Returns string of the top five switch names and switch recent network throughput average.
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
        Returns Mermaid.js chart syntax of the top five switch names and switch recent network throughput.
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
            timepoint = datetime.fromisoformat(current["timepoint"].replace("Z", "")).strftime("%H:%M:%S")
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
        Returns string of the top five switch names and switch recent network packets per second(PPS) average.
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

    # In switch_pps_dict, including the packets per second(PPS) of each switch at each time point,
    # and the average PPS. Throughput list is sorted from oldest to newest.
    # e.g. {"<switch name>": {"pps_list": [<PPS>, ...], "pps_avg": <PPS average>}}
    switch_pps_dict = {}
    for stats in resp_json["portstats"]:
        host = stats.get("host")
        resources = stats.get("resources")[-10:]

        # Check if resources has data
        if not resources:
            continue

        pps_sum = 0
        pps_list = []
        for i in range(1, len(resources)):
            current = resources[i]
            previous = resources[i - 1]

            # Calculate the delta of each data point
            # and divide it by the interval time to get the PPS.
            packets_prev = previous["packetsReceived"] + previous["packetsSent"]
            packets_curr = current["packetsReceived"] + current["packetsSent"]

            delta_packets = packets_curr - packets_prev
            pps = delta_packets / resolution_second # packets/sec

            pps_sum += pps
            pps_list.append(pps)
        
        pps_avg = pps_sum / len(resources)
        switch_pps_dict[host] = {
            "pps_list": pps_list,
            "pps_avg": pps_avg
        }

    packet_count_top_5 = sorted(
        switch_pps_dict.items(),
        key=lambda item: item[1]["pps_avg"],
        reverse=True
    )[:5]

    index = 0
    results = []
    for host, data in packet_count_top_5:
        index += 1
        result_str = (
            f"#{index}\n"
            f"Switch name: {host}\n"
            f"Packet count average: {data['pps_avg']:.2f} packets/sec"
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
        Returns Mermaid.js chart syntax of the top five switch names and switch recent network packets per second(PPS).
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

    # In switch_pps_dict, including the packets per second(PPS) of each switch at each time point,
    # and the average PPS. Throughput list is sorted from oldest to newest.
    # e.g. {"<switch name>": {
    #           "timepoint_list": [<timepoint>, ...],
    #           "pps_list": [<PPS>, ...],
    #           "pps_avg": <PPS average>}
    #      }
    switch_pps_dict = {}
    for stats in resp_json["portstats"]:
        host = stats.get("host")
        resources = stats.get("resources")[-10:]

        # Check if resources has data
        if not resources:
            continue

        timepoint_list = []
        pps_sum = 0
        pps_list = []
        for i in range(1, len(resources)):
            current = resources[i]
            previous = resources[i - 1]

            # Calculate the delta of each data point
            # and divide it by the interval time to get the PPS.
            packets_prev = previous["packetsReceived"] + previous["packetsSent"]
            packets_curr = current["packetsReceived"] + current["packetsSent"]

            delta_packets = packets_curr - packets_prev
            pps = delta_packets / resolution_second # packets/sec

            # Adjust the time format to avoid the problem of too long strings
            timepoint = datetime.fromisoformat(current["timepoint"].replace("Z", "")).strftime("%H:%M:%S")
            timepoint_list.append(timepoint)

            pps_sum += pps
            pps_list.append(pps)
        
        pps_avg = pps_sum / len(resources)
        switch_pps_dict[host] = {
            "timepoint_list": timepoint_list,
            "pps_list": pps_list,
            "pps_avg": pps_avg
        }

    packet_count_top_5 = sorted(
        switch_pps_dict.items(),
        key=lambda item: item[1]["pps_avg"],
        reverse=True
    )[:5]

    index = 0
    results = [mermaid_chart_count_prompt(len(packet_count_top_5))]
    for item in packet_count_top_5:
        index += 1
        result_chart = generate_line_chart(
            title = "交換器最近封包數前5",
            x_axis_name = f"{item[0]} (#{index})",
            y_axis_name = "Packet count (packets/sec)",
            keys = item[1]["timepoint_list"],
            values = item[1]["pps_list"],
            range_min = min(item[1]["pps_list"]),
            range_max = max(item[1]["pps_list"])
        )
        results.append(result_chart)

    return "".join(results)

### Old MARS MCP tools test ###
@mcp.tool()
async def get_mars_api_calls_image_url(time_start: str, time_end: str) -> str:
    """Retrieve MARS API call statistics within a specific time range, generate a line chart based on the data,
    upload the chart image to a cloud server, and return the image URL.
    This tool returns a direct URL to a image that visualizes the number of API requests over time.
    Note: MARS is a hardware independent controller.

    IMPORTANT:
        When you receive the image URL, you MUST display it using Markdown syntax immediately.
        The correct Markdown format to embed the image: ![](image_url)
        Example: ![](http://your.server/path/image.png)
        Do NOT simply return the URL as plain text. Always wrap it in Markdown format so the image can be rendered.

    Args:
        time_start: Starting timestamp of analyze time range, in ISO 8601 format (e.g., "2025-08-01T00:00:00Z").
        time_end: Ending timestamp of analyze time range, in ISO 8601 format (e.g., "2025-08-01T00:00:00Z").

    Returns:
        On success: A URL (str) pointing to the generated chart image.
        On failure: A string containing an error message.
    """

    time_start_dt = datetime.fromisoformat(time_start.replace("Z", "+00:00"))
    time_end_dt = datetime.fromisoformat(time_end.replace("Z", "+00:00"))
    resolution_second = int((time_end_dt - time_start_dt).total_seconds() / 30)
    url = f"{MARS_SERVER_URL}/mars/analyzer/v1/nginx/{time_start}/{time_end}/{resolution_second}"
    print(url)
    response = await mars_get_request(url)
    resp_json = response.json()

    if not resp_json or "statistic" not in resp_json:
        return "Unable to fetch statistic or no statistic found."

    # Get statistic
    statistic_data = resp_json.get("statistic", [])
    if not statistic_data:
        return "No any statistics tada."

    x = [
        datetime.fromisoformat(item["timepoint"].replace("Z", "+00:00"))
        for item in statistic_data
    ]
    y = [item["count"] for item in statistic_data]

    # Draw chart
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(x, y, marker='o', linestyle='-', color='blue')
    ax.set_xlabel("Time")
    ax.set_ylabel("Count")
    ax.set_title("Request Counts Over Time")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    plt.xticks(rotation=45)

    # Save image
    image_name = "mars_api_calls_image.png"
    image_path = os.path.join(FILE_DIR, image_name)

    plt.tight_layout()
    plt.savefig(image_path, format='png')
    plt.close()

    return f"{MCP_SERVER_URL}/{FILE_DIR}/{image_name}"

@mcp.tool()
async def get_apps() -> str:
    """Get all installed applications in MARS.
    Note: MARS is a hardware independent controller.
    """
    url = f"{MARS_SERVER_URL}/mars/v1/applications"
    response = await mars_get_request(url)
    resp_json = response.json()

    if not resp_json or "applications" not in resp_json:
        return "Unable to fetch MARS APPs or no APPs found."

    if not resp_json["applications"]:
        return "No active APPs."

    apps = []
    for feature in resp_json["applications"]:
        app_str = (
            f"Name: {feature.get('name', 'Unknown')}\n"
            f"Category: {feature.get('category', 'Unknown')}"
        )
        apps.append(app_str.strip()) # Remove extra indentation spaces

    return "\n---\n".join(apps)

@mcp.tool()
async def get_app(name: str) -> str:
    """Get application details in MARS.
    Note: MARS is a hardware independent controller.

    Args:
        name: Application name
    """
    url = f"{MARS_SERVER_URL}/mars/v1/applications/{name}"
    response = await mars_get_request(url)
    resp_json = response.json()

    if not resp_json:
        return "Unable to fetch MARS APP or no APP found."

    return (
        f"Name: {resp_json.get('name', 'Unknown')}\n"
        f"Category: {resp_json.get('category', 'Unknown')}"
    )

@mcp.tool()
async def activate_app(name: str) -> str:
    """Activate MARS application.
    Note: MARS is a hardware independent controller.

    Args:
        name: Application name
    """
    url = f"{MARS_SERVER_URL}/mars/v1/applications/{name}/active"
    response = await mars_post_request(url, None)
    resp_json = response.json()

    if not resp_json:
        return "Failed to activate application."

    return f"{name} APP has been successfully active."

@mcp.tool()
async def deactivate_app(name: str) -> str:
    """Deactivate MARS application.
    Note: MARS is a hardware independent controller.

    Args:
        name: Application name
    """
    url = f"{MARS_SERVER_URL}/mars/v1/applications/{name}/active"
    resp = await mars_delete_request(url)

    if resp.status_code != 200:
        return "Failed to deactivate application."

    return f"{name} APP has been successfully deactive."

### Call MARS API related functions ###
async def get_mars_cookies():
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    url = f"{MARS_SERVER_URL}/mars/useraccount/v1/swagger-login"
    data = {"user_name": MARS_USER_NAME, "password": MARS_PASSWORD}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, headers=headers, json=data, timeout=30.0)
            response.raise_for_status()
            return {"marsGSessionId": response.headers["MARS_G_SESSION_ID"]}
        except Exception as e:
            return None

async def mars_post_request(url: str, data: dict[str, Any]):
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    async with httpx.AsyncClient() as client:
        try:
            cookies = await get_mars_cookies()
            response = await client.post(url, cookies=cookies, headers=headers, json=data, timeout=30.0)
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
def mermaid_chart_count_prompt(count: int = 1) -> str:
    # Added "Show Mermaid.js" prompt to enable Open WebUI to correctly render Mermaid.js charts
    if count < 2:
        return "Show Mermaid.js\n"
    else:
        return f"Show {count} Mermaid.js\n"

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
    test = asyncio.run(mars_get_switch_recent_network_packet_count_ranking_chart())
    print(test)
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5050)
