import json
import yaml
import libnmstate
from libnmstate.schema import Interface
from mcp.server.fastmcp import FastMCP
from typing import Literal

# Create a named MCP server
mcp = FastMCP("Nmstate Network Manager")

@mcp.tool()
def nmstatectl_show(
    ifname: str | None = None,
    kernel_only: bool = False,
    running_config: bool = False,
) -> str:
    """
    Show network state using nmstatectl show.

    Args:
        ifname: Show specific interface only.
        kernel_only: Show kernel network state only.
        running_config: Show running configuration only.

    Returns:
        The network state as a string (JSON if json_format is True).
    """
    try:
        # libnmstate.show() returns a dictionary
        # We need to construct the arguments based on the nmstatectl options
        show_args = {}
        if kernel_only:
            show_args["kernel_only"] = True
        if running_config:
            show_args["running_config_only"] = True

        net_state = libnmstate.show(**show_args)

        if ifname:
            # Filter for a specific interface
            interfaces = net_state.get(Interface.KEY, [])
            filtered_interfaces = [
                iface for iface in interfaces if iface.get(Interface.NAME) == ifname
            ]
            if not filtered_interfaces:
                return f"Error: Interface '{ifname}' not found."
            net_state[Interface.KEY] = filtered_interfaces
            
            # If the only thing left is an empty interfaces list, return an error
            if not net_state.get(Interface.KEY):
                return f"Error: Could not retrieve state for interface '{ifname}'."

        return json.dumps(net_state, indent=2)

    except Exception as e:
        return f"Error showing network state: {e}"

@mcp.tool()
def nmstatectl_apply(
    state_content: str,
) -> None:
    """
    Apply specified network state content.

    Args:
        state_content: The network state content (YAML string only).

    Returns:
        Returns success on success.
    """
    try:
        data = yaml.safe_load(state_content)
        libnmstate.apply(data)
        return "success"

    except Exception as e:
        return f"Error applying network state: {e}"

@mcp.tool()
def nmstatectl_format(
    state_content: str,
) -> str:
    """
    format state_content into correct yaml and return it.
    Or return error if not possible.
    """
    try:
        data = yaml.safe_load(state_content)
        formatted_state = libnmstate.PrettyState(data)
        return formatted_state.yaml
    except Exception as e:
        return f"Error formatting network state: {e}"

# This block ensures the server runs when the script is executed
if __name__ == "__main__":
    print(f"Starting Nmstate Network Manager MCP server...")

    # Pass the host and port to the run method
    mcp.run()
