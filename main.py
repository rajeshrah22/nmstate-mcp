import json
import yaml
import libnmstate
import subprocess
import time
import tempfile
import os
import shutil
from pathlib import Path
from libnmstate.schema import Interface
from mcp.server.fastmcp import FastMCP
from typing import Literal, Dict, List, Optional

# Create a named MCP server
mcp = FastMCP("Nmstate Network Manager")

# Global configuration for remote hosts
REMOTE_HOSTS_CONFIG = {
    "inventory_file": "inventory.yaml",  # User-provided inventory file
    "playbook_dir": "playbooks",
    "vars_dir": "vars"
}

def _run_connectivity_test(
        target: str, 
        interface: str | None = None,
        timeout: int = 10
) -> dict:

  """
  Run connectivity test to a target
  """

  try:
      cmd = ["ping", "-c", "5", "-W", str(timeout)]
      if interface:
          cmd.extend(["-I", interface])
      cmd.append(target)

      start_time = time.time()
      result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
      duration = time.time() - start_time

      success = result.returncode == 0

      return {
          "test": "connectivity",
          "target": target,
          "interface": interface,
          "success": success,
          "duration": round(duration, 2),
          "details": result.stdout if success else result.stderr
      }
  except Exception as e:
      return {
          "test": "connectivity",
          "target": target,
          "interface": interface,
          "success": False,
          "error": str(e)
      }

def _run_dns_test(
        domain: str, 
        timeout: int = 10
) -> dict:
    """Run DNS resolution test"""

    try:
        start_time = time.time()
        result = subprocess.run(
            ["nslookup", domain],
            capture_output=True,
            text=True, 
            timeout=timeout
        )
        duration = time.time() - start_time

        success = result.returncode == 0 and "server can't find" not in result.stdout.lower()

        return {
            "test": "dns_resolution",
            "domain": domain,
            "success": success,
            "duration": round(duration, 2),
            "details": result.stdout if success else result.stderr
        }
    except Exception as e:
        return {
            "test": "dns_resolution",
            "domain": domain,
            "success": False,
            "error": str(e)
        }

def _create_playbook(action: str) -> str:
    """Create Ansible playbook for nmstatectl operations"""
    
    playbooks = {
        "show": [
            {
                "name": "Show network state",
                "hosts": "all",
                "tasks": [
                    {
                        "name": "Run nmstatectl show",
                        "ansible.builtin.command": "nmstatectl show --json",
                        "register": "nmstate_output"
                    },
                    {
                        "name": "Display network state",
                        "ansible.builtin.debug": {
                            "var": "nmstate_output.stdout"
                        }
                    }
                ]
            }
        ],
        "apply": [
            {
                "name": "Apply network state using linux-system-roles.network",
                "hosts": "all",
                "become": "true",
                "vars": {
                    "network_state": "{{ nmstate_config }}"
                },
                "tasks": [
                    {
                        "name": "Apply network configuration using network role",
                        "ansible.builtin.include_role": {
                            "name": "linux-system-roles.network"
                        }
                    }
                ]
            }
        ]
    }
    
    playbook = playbooks.get(action)
    playbook_content = yaml.dump(playbook, default_flow_style=False)

    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as playbook_file:
        playbook_file.write(playbook_content)
        playbook_path = playbook_file.name
    
    return playbook_path

def _run_ansible_playbook(playbook_path: str, host: str | None = None, extra_vars: Dict = None) -> Dict:
    """Run Ansible playbook with given variables"""
    
    # _ensure_directories()
    
    vars_file = None
    if extra_vars:
        vars_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
        yaml.dump(extra_vars, vars_file)
        vars_file.close()
    
    try:
        # Build ansible-playbook command
        cmd = [
            "ansible-playbook",
            "-i", REMOTE_HOSTS_CONFIG['inventory_file'],
            playbook_path,
            "-v"  # verbose output
        ]
        
        if host:
            cmd.extend(["--limit", f"{host}"])
        if vars_file:
            cmd.extend(["--extra-vars", f"@{vars_file.name}"])

        print(cmd)
        
        # Run the playbook
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5 minutes timeout
        )

        print(result.stdout)
        
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
    finally:
        for temp_file in [playbook_path]:
            if os.path.exists(temp_file):
                os.unlink(temp_file)
        if vars_file and os.path.exists(vars_file.name):
            os.unlink(vars_file.name)

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
    commit: bool = True,
    rollback_timeout: int = 180
) -> str:
    """
    Here is the json schema for state_content
    ---
    $schema: http://json-schema.org/draft-04/schema#
    type: object
    properties:
      capabilities:
        type: array
        items:
          type: string
      interfaces:
        type: array
        items:
          type: object
          required:
            - name
          allOf:
            - $ref: "#/definitions/interface-base/rw"
            - $ref: "#/definitions/interface-base/ro"
            - $ref: "#/definitions/interface-ip/rw"
            - $ref: "#/definitions/interface-ethtool/rw"
            - $ref: "#/definitions/lldp/rw"
            - $ref: "#/definitions/lldp/ro"
            - $ref: "#/definitions/802.1x/rw"
            - oneOf:
                - "$ref": "#/definitions/interface-unknown/rw"
                - "$ref": "#/definitions/interface-ethernet/rw"
                - "$ref": "#/definitions/interface-bond/rw"
                - "$ref": "#/definitions/interface-linux-bridge/all"
                - "$ref": "#/definitions/interface-ovs-bridge/all"
                - "$ref": "#/definitions/interface-ovs-interface/rw"
                - "$ref": "#/definitions/interface-dummy/rw"
                - "$ref": "#/definitions/interface-vlan/rw"
                - "$ref": "#/definitions/interface-vxlan/rw"
                - "$ref": "#/definitions/interface-team/rw"
                - "$ref": "#/definitions/interface-vrf/rw"
                - "$ref": "#/definitions/interface-infiniband/rw"
                - "$ref": "#/definitions/interface-mac-vlan/rw"
                - "$ref": "#/definitions/interface-mac-vtap/rw"
                - "$ref": "#/definitions/interface-veth/rw"
                - "$ref": "#/definitions/interface-other/rw"
      routes:
        type: object
        properties:
          config:
            type: array
            items:
              $ref: "#/definitions/route"
          running:
            type: array
            items:
              $ref: "#/definitions/route"
      route-rules:
        type: object
        properties:
          config:
            type: array
            items:
              $ref: "#/definitions/route-rule"
      dns-resolver:
        type: object
        properties:
          config:
            items:
              $ref: "#/definitions/dns"
          running:
            items:
              $ref: "#/definitions/dns"
      ovs-db:
        type: object
        properties:
          external_ids:
            type: object
          other_config:
            type: object

    definitions:
      types:
        status:
          type: string
          enum:
            - up
            - down
        mac-address:
          type: string
          pattern: "^([a-fA-F0-9]{2}:){3,31}[a-fA-F0-9]{2}$"
        bridge-vlan-tag:
          type: integer
          minimum: 0
          maximum: 4095

      # Interface types
      interface-base:
        all:
          allOf:
            - $ref: "#/definitions/interface-base/rw"
            - $ref: "#/definitions/interface-base/ro"
        rw:
          properties:
            description:
              type: string
            name:
              type: string
            state:
              type: string
              enum:
                - absent
                - up
                - down
                - ignore
            mac-address:
              $ref: "#/definitions/types/mac-address"
            mtu:
              type: integer
              minimum: 0
            accept-all-mac-addresses:
              type: boolean
        ro:
          properties:
            if-index:
              type: integer
              minimum: 0
            admin-status:
              $ref: "#/definitions/types/status"
            link-status:
              $ref: "#/definitions/types/status"
            phys-address:
              $ref: "#/definitions/types/mac-address"
            higher-layer-if:
              type: string
            lower-layer-if:
              type: string
            statistics:
              properties:
                in-broadcast-pkts:
                  type: integer
                  minimum: 0
                in-discards:
                  type: integer
                  minimum: 0
                in-errors:
                  type: integer
                  minimum: 0
                in-multicast-pkts:
                  type: integer
                  minimum: 0
                in-octets:
                  type: integer
                  minimum: 0
                in-unicast-pkts:
                  type: integer
                  minimum: 0
                out-broadcast-pkts:
                  type: integer
                  minimum: 0
                out-discards:
                  type: integer
                  minimum: 0
                out-errors:
                  type: integer
                  minimum: 0
                out-multicast-pkts:
                  type: integer
                  minimum: 0
                out-octets:
                  type: integer
                  minimum: 0
                out-unicast-pkts:
                  type: integer
                  minimum: 0
      interface-unknown:
        rw:
          properties:
            type:
              type: string
              enum:
                - unknown
      interface-ethernet:
        rw:
          properties:
            type:
              type: string
              enum:
                - ethernet
            ethernet:
              type: object
              properties:
                auto-negotiation:
                  type: boolean
                duplex:
                  type: string
                  enum:
                    - full
                    - half
                speed:
                  type: integer
                  minimum: 0
                flow-control:
                  type: boolean
                sr-iov:
                  type: object
                  properties:
                    total-vfs:
                      type: integer
                      minimum: 0
                    vfs:
                      type: array
                      items:
                        type: object
                        properties:
                          id:
                            type: integer
                            minimum: 0
                          mac-address:
                            $ref: "#/definitions/types/mac-address"
                          spoof-check:
                            type: boolean
                          trust:
                            type: boolean
                          min-tx-rate:
                            type: integer
                            minimum: 0
                          max-tx-rate:
                            type: integer
                            minimum: 0
                        required:
                          - id
      interface-vlan:
        rw:
          properties:
            type:
              type: string
              enum:
                - vlan
            vlan:
              type: object
              properties:
                id:
                  type: integer
                  minimum: 0
                  maximum: 4095
                base-iface:
                  type: string
              required:
                - id
                - base-iface
      interface-vxlan:
        rw:
          properties:
            type:
              type: string
              enum:
                - vxlan
            vxlan:
              type: object
              properties:
                id:
                  type: integer
                  minimum: 0
                  maximum: 16777215
                remote:
                  type: string
                destination-port:
                  type: integer
                base-iface:
                  type: string

      interface-bond:
        rw:
          properties:
            type:
              type: string
              enum:
                - bond
            copy-mac-from:
              type: string
            link-aggregation:
              type: object
              properties:
                mode:
                  type: string
                port:
                  type: array
                  items:
                    type: string
                ports:
                  type: array
                  items:
                    type: string
                options:
                  type: object
                ports-config:
                  type: array
                  items:
                    type: string
      interface-linux-bridge:
        all:
          allOf:
            - $ref: "#/definitions/interface-linux-bridge/rw"
            - $ref: "#/definitions/interface-linux-bridge/ro"
        ro:
          properties:
            copy-mac-from:
              type: string
            bridge:
              type: object
              properties:
                options:
                  type: object
                  properties:
                    gc-timer:
                      type: integer
                    hello-timer:
                      type: integer
        rw:
          properties:
            type:
              type: string
              enum:
                - linux-bridge
            bridge:
              type: object
              properties:
                ports:
                  type: array
                  items:
                    type: object
                    properties:
                      name:
                        type: string
                      stp-priority:
                        type: integer
                      stp-path-cost:
                        type: integer
                      stp-hairpin-mode:
                        type: boolean
                      vlan:
                        type: object
                        properties:
                          mode:
                            type: string
                            enum:
                              - trunk
                              - access
                          trunk-tags:
                            type: array
                            items:
                              $ref: "#/definitions/bridge-port-vlan"
                          tag:
                            $ref: "#/definitions/types/bridge-vlan-tag"
                          enable-native:
                            type: boolean
                port:
                  type: array
                  items:
                    type: object
                    properties:
                      name:
                        type: string
                      stp-priority:
                        type: integer
                      stp-path-cost:
                        type: integer
                      stp-hairpin-mode:
                        type: boolean
                      vlan:
                        type: object
                        properties:
                          mode:
                            type: string
                            enum:
                              - trunk
                              - access
                          trunk-tags:
                            type: array
                            items:
                              $ref: "#/definitions/bridge-port-vlan"
                          tag:
                            $ref: "#/definitions/types/bridge-vlan-tag"
                          enable-native:
                            type: boolean
                options:
                  type: object
                  properties:
                    mac-ageing-time:
                      type: integer
                    group-forward-mask:
                      type: integer
                    group-addr:
                      $ref: "#/definitions/types/mac-address"
                    hash-max:
                      type: integer
                    multicast-snooping:
                      type: boolean
                    multicast-router:
                      type: integer
                    multicast-last-member-count:
                      type: integer
                    multicast-last-member-interval:
                      type: integer
                    multicast-membership-interval:
                      type: integer
                    multicast-querier:
                      type: boolean
                    multicast-querier-interval:
                      type: integer
                    multicast-query-use-ifaddr:
                      type: boolean
                    multicast-query-interval:
                      type: integer
                    multicast-query-response-interval:
                      type: integer
                    multicast-startup-query-count:
                      type: integer
                    multicast-startup-query-interval:
                      type: integer
                    stp:
                      type: object
                      properties:
                        enabled:
                          type: boolean
                        priority:
                          type: integer
                        forward-delay:
                          type: integer
                        hello-time:
                          type: integer
                        max-age:
                          type: integer
      interface-ovs-bridge:
        all:
          allOf:
            - $ref: "#/definitions/interface-ovs-bridge/rw"
            - $ref: "#/definitions/interface-ovs-bridge/ro"
        rw:
          properties:
            type:
              type: string
              enum:
                - ovs-bridge
            ovs-db:
              type: object
            bridge:
              type: object
              properties:
                ports:
                  type: array
                  items:
                    type: object
                    properties:
                      name:
                        type: string
                      vlan:
                        type: object
                        properties:
                          mode:
                            type: string
                            enum:
                              - trunk
                              - access
                          trunk-tags:
                            type: array
                            items:
                              $ref: "#/definitions/bridge-port-vlan"
                          tag:
                            $ref: "#/definitions/types/bridge-vlan-tag"
                          enable-native:
                            type: boolean
                      link-aggregation:
                        type: object
                        properties:
                          mode:
                            type: string
                          slaves:
                            type: array
                            items:
                              type: object
                              properties:
                                name:
                                  type: string
                          ports:
                            type: array
                            items:
                              type: object
                              properties:
                                name:
                                  type: string
                          port:
                            type: array
                            items:
                              type: object
                              properties:
                                name:
                                  type: string
                port:
                  type: array
                  items:
                    type: object
                    properties:
                      name:
                        type: string
                      vlan:
                        type: object
                        properties:
                          mode:
                            type: string
                            enum:
                              - trunk
                              - access
                          trunk-tags:
                            type: array
                            items:
                              $ref: "#/definitions/bridge-port-vlan"
                          tag:
                            $ref: "#/definitions/types/bridge-vlan-tag"
                          enable-native:
                            type: boolean
                      link-aggregation:
                        type: object
                        properties:
                          mode:
                            type: string
                          slaves:
                            type: array
                            items:
                              type: object
                              properties:
                                name:
                                  type: string
                          ports:
                            type: array
                            items:
                              type: object
                              properties:
                                name:
                                  type: string
                          port:
                            type: array
                            items:
                              type: object
                              properties:
                                name:
                                  type: string
                options:
                  type: object
                  properties:
                    stp:
                      type: boolean
                    rstp:
                      type: boolean
                    fail-mode:
                      type: string
                    mcast-snooping-enable:
                      type: boolean
        ro:
          properties:
            bridge:
              type: object
              properties:
                port:
                  type: array
                  items:
                    type: object
                    properties:
                      learned-mac-address:
                        type: array
                        items:
                          $ref: "#/definitions/types/mac-address"
      interface-ovs-interface:
        rw:
          properties:
            type:
              type: string
              enum:
                - ovs-interface
            ovs-db:
              type: object
            patch:
              type: object
              properties:
                peer:
                  type: string
      interface-dummy:
        rw:
          properties:
            type:
              type: string
              enum:
                - dummy
      interface-ip:
        all:
          allOf:
            - $ref: "#/definitions/interface-ip/rw"
            - $ref: "#/definitions/interface-ip/ro"
        rw:
          properties:
            ipv4:
              type: object
              properties:
                enabled:
                  type: boolean
                dhcp:
                  type: boolean
                auto-routes:
                  type: boolean
                auto-gateway:
                  type: boolean
                auto-dns:
                  type: boolean
                auto-route-table-id:
                  type: integer
                address:
                  type: array
                  items:
                    type: object
                    properties:
                      ip:
                        type: string
                      prefix-length:
                        type:
                          - integer
                          - string
                      netmask:
                        type: string
                neighbor:
                  type: array
                  items:
                    type: object
                    properties:
                      ip:
                        type: string
                      link-layer-address:
                        type: string
                forwarding:
                  type: boolean
            ipv6:
              type: object
              properties:
                enabled:
                  type: boolean
                autoconf:
                  type: boolean
                dhcp:
                  type: boolean
                auto-routes:
                  type: boolean
                auto-gateway:
                  type: boolean
                auto-dns:
                  type: boolean
                auto-route-table-id:
                  type: integer
                address:
                  type: array
                  items:
                    type: object
                    properties:
                      ip:
                        type: string
                      prefix-length:
                        type:
                          - integer
                          - string
                neighbor:
                  type: array
                  items:
                    type: object
                    properties:
                      ip:
                        type: string
                      link-layer-address:
                        type: string
                forwarding:
                  type: boolean
                dup-addr-detect-transmits:
                  type: integer
        ro:
          properties:
            ipv4:
              type: object
              properties:
                address:
                  type: array
                  items:
                    type: object
                    properties:
                      origin:
                        type: string
                neighbor:
                  type: array
                  items:
                    type: object
                    properties:
                      origin:
                        type: string
            ipv6:
              type: object
              properties:
                address:
                  type: array
                  items:
                    type: object
                    properties:
                      origin:
                        type: string
                      status:
                        type: string
                neighbor:
                  type: array
                  items:
                    type: object
                    properties:
                      origin:
                        type: string
                      is-router:
                        type: boolean
                      state:
                        type: string
      interface-ethtool:
        rw:
          properties:
            ethtool:
              type: object
              properties:
                pause:
                  type: object
                  properties:
                    autoneg:
                      type: boolean
                    rx:
                      type: boolean
                    tx:
                      type: boolean
                feature:
                  type: object
                  additionalProperties:
                    type: boolean
                ring:
                  type: object
                  properties:
                    tx:
                      type: integer
                      minimum: 0
                    rx:
                      type: integer
                      minimum: 0
                    rx-jumbo:
                      type: integer
                      minimum: 0
                    rx-mini:
                      type: integer
                      minimum: 0
                coalesce:
                  type: object
                  properties:
                    adaptive-rx:
                      type: boolean
                    adaptive-tx:
                      type: boolean
                    pkt-rate-high:
                      type: integer
                      minimum: 0
                    pkt-rate-low:
                      type: integer
                      minimum: 0
                    rx-frames:
                      type: integer
                      minimum: 0
                    rx-frames-high:
                      type: integer
                      minimum: 0
                    rx-frames-irq:
                      type: integer
                      minimum: 0
                    rx-frames-low:
                      type: integer
                      minimum: 0
                    rx-usecs:
                      type: integer
                      minimum: 0
                    rx-usecs-high:
                      type: integer
                      minimum: 0
                    rx-usecs-irq:
                      type: integer
                      minimum: 0
                    rx-usecs-low:
                      type: integer
                      minimum: 0
                    sample-interval:
                      type: integer
                      minimum: 0
                    stats-block-usecs:
                      type: integer
                      minimum: 0
                    tx-frames:
                      type: integer
                      minimum: 0
                    tx-frames-high:
                      type: integer
                      minimum: 0
                    tx-frames-irq:
                      type: integer
                      minimum: 0
                    tx-frames-low:
                      type: integer
                      minimum: 0
                    tx-usecs:
                      type: integer
                      minimum: 0
                    tx-usecs-high:
                      type: integer
                      minimum: 0
                    tx-usecs-irq:
                      type: integer
                      minimum: 0
                    tx-usecs-low:
                      type: integer
                      minimum: 0
      interface-team:
        rw:
          properties:
            type:
              type: string
              enum:
                - team
            team:
              type: object
              properties:
                ports:
                  type: array
                  items:
                    type: object
                    properties:
                      name:
                        type: string
                runner:
                  type: object
                  properties:
                    name:
                      type: string
      interface-vrf:
        rw:
          properties:
            type:
              type: string
              enum:
                - vrf
            vrf:
              type: object
              properties:
                port:
                  type: array
                  items:
                    type: string
                ports:
                  type: array
                  items:
                    type: string
                route-table-id:
                  type: integer
      interface-mac-vlan:
        rw:
          properties:
            type:
              type: string
              enum:
                - mac-vlan
            mac-vlan:
              type: object
              properties:
                base-iface:
                  type: string
                mode:
                  type: string
                  enum:
                    - private
                    - vepa
                    - bridge
                    - passthru
                    - source
                    - unknown
                promiscuous:
                  type: boolean
      interface-mac-vtap:
        rw:
          properties:
            type:
              type: string
              enum:
                - mac-vtap
            mac-vtap:
              type: object
              properties:
                base-iface:
                  type: string
                mode:
                  type: string
                  enum:
                    - private
                    - vepa
                    - bridge
                    - passthru
                    - source
                    - unknown
                promiscuous:
                  type: boolean
      interface-veth:
        rw:
          properties:
            type:
              type: string
              enum:
                - veth
            veth:
              type: object
              properties:
                peer:
                  type: string
              required:
                - peer
      interface-other:
        rw:
          properties:
            type:
              type: string
              enum:
                - other
      route:
        type: object
        properties:
          state:
            type: string
            enum:
              - absent
          table-id:
            type: integer
          metric:
            type: integer
          destination:
            type: string
          next-hop-interface:
            type: string
          next-hop-address:
            type: string
      dns:
        type: object
        properties:
          server:
            type: array
            items:
              type: string
          search:
            type: array
            items:
              type: string
          options:
            type: array
            items:
              type: string
      bridge-port-vlan:
        type: object
        properties:
          id:
            $ref: "#/definitions/types/bridge-vlan-tag"
          id-range:
            type: object
            properties:
              min:
                $ref: "#/definitions/types/bridge-vlan-tag"
              max:
                $ref: "#/definitions/types/bridge-vlan-tag"
      route-rule:
        type: object
        properties:
          from:
            type: string
          to:
            type: string
          priority:
            type: integer
          route-table:
            type: integer
          state:
            type: string
            enum:
              - absent
      lldp:
        ro:
          properties:
            neighbors:
              type: array
              items:
                type: object
        rw:
          properties:
            enabled:
              type: boolean
      802.1x:
        rw:
          properties:
            identity:
              type: string
            eap-methods:
              type: array
              items:
                type: string
            private-key:
              type: string
            private-key-password:
              type: string
            client-cert:
              type: string
            ca-cert:
              type: string
      interface-infiniband:
        rw:
          properties:
            type:
              type: string
              enum:
                - infiniband
            infiniband:
              type: object
              properties:
                base-iface:
                  type: string
                pkey:
                  type:
                    - string
                    - integer
                mode:
                  type: string
                  enum:
                    - datagram
                    - connected

    instruction: before using the tool, display the YAML desired state to the user.

    Args:
        state_content: The network state content (YAML string only).

    Returns:
        Returns success on success.
    """
    try:
        data = yaml.safe_load(state_content)
        libnmstate.apply(data, commit=commit, rollback_timeout=rollback_timeout)
        return "success"

    except Exception as e:
        return f"Error applying network state: {e}"

@mcp.tool()
def nmstatectl_apply_and_test_network(
    state_content: str,
    rollback_timeout: int = 60
) -> str:
    """
    Apply network state with automatic validation and commit/rollback based on test results.
    Only call this when user explicitly says to do automatic validation.

    instruction: before using the tool, display the YAML desired state to the user.

    Args:
        state_content: The network state content (YAML string only).
        rollback_timeout: Optional. The amount of time to wait after applying with no commit before automatically rolling back

    Returns:
        rollback with reason | commit | error
    """
    try:
        data = yaml.safe_load(state_content)
        libnmstate.apply(data, commit=False, rollback_timeout=rollback_timeout)

        # run tests
        result = _run_connectivity_test(target="1.1.1.1")
        if result["success"] == False:
            libnmstate.rollback()
            error_msg = result.get('details') or result.get('error', 'Unknown error')
            return f"rollback: test failed: {error_msg}"
        result = _run_dns_test(domain="google.com")
        if result["success"] == False:
            libnmstate.rollback()
            error_msg = result.get('details') or result.get('error', 'Unknown error')
            return f"rollback: test failed: {error_msg}"

        libnmstate.commit()
        return "commit"

    except Exception as e:
        return f"Error applying and validating network state: {e}"

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

@mcp.tool()
def nmstatectl_rollback() -> str:
    """
    Rollback network state to previous state (commit).
    User after applying a network state with commit=False.
    This is used when user is not satisfied with the network changes and/or some network tests fail.

    Returns:
        Returns success on success.
    """
    try:
        libnmstate.rollback()
        return "success"
    except Exception as e:
        return f"Error rolling back network state: {e}"

@mcp.tool()
def nmstatectl_commit() -> str:
    """
    Rollback network state to previous state (commit).
    User after applying a network state with commit=False.
    This is used when user is satisfied with the network changes and/or all network tests pass.

    Returns:
        Returns success on success.
    """
    try:
        libnmstate.commit()
        return "success"
    except Exception as e:
        return f"Error commiting back network state"

@mcp.tool()
def validate_inventory_file(
    inventory_file: str = "inventory.yaml"
) -> str:
    """
    Validate that the inventory file exists and is readable.
    
    Args:
        inventory_file: Path to the inventory file to validate
        
    Returns:
        Validation status
    """
    try:
        # Update the inventory file path
        REMOTE_HOSTS_CONFIG["inventory_file"] = inventory_file
        
        # Check if file exists
        if not os.path.exists(inventory_file):
            return f"Error: Inventory file not found at {inventory_file}. Please create it first."
        
        # Try to read and parse the inventory file
        with open(inventory_file, 'r') as f:
            inventory_content = f.read()
        
        # Validate YAML format
        try:
            inventory_data = yaml.safe_load(inventory_content)
        except yaml.YAMLError as e:
            return f"Error: Invalid YAML in inventory file: {e}"
        
        # Basic validation - check if it has expected structure
        if not isinstance(inventory_data, dict):
            return "Error: Inventory file should contain a dictionary structure"
        
        return f"✅ Inventory file validated successfully: {inventory_file}\n" \
               f"   Use this file for remote operations"
        
    except Exception as e:
        return f"Error validating inventory file: {e}"

@mcp.tool()
def remote_nmstatectl_show(
    target_host: str,
) -> str:
    """
    Show network state on remote hosts using Ansible.
    
    Args:
        target_host: ansible label for name of host
        
    Returns:
        Network state from remote hosts
    """
    try:
        if not os.path.exists(REMOTE_HOSTS_CONFIG["inventory_file"]):
            return "Error: No remote hosts configured. Use configure_remote_hosts first."
        
        # Read inventory to get configured hosts
        with open(REMOTE_HOSTS_CONFIG["inventory_file"], 'r') as f:
            inventory_content = f.read()
        
        playbook_path = _create_playbook("show")
        
        # Run playbook
        result = _run_ansible_playbook(playbook_path, target_host, None)
        
        if result["success"]:
            return f"Remote show completed successfully:\n{result['stdout']}"
        else:
            return f"Error running remote show: {result.get('stderr', result.get('error', 'Unknown error'))}"
            
    except Exception as e:
        return f"Error showing remote network state: {e}"

@mcp.tool()
def remote_nmstatectl_apply(
    state_content: str,
    target_host: str
) -> str:
    """
    Apply network state on remote hosts using linux-system-roles.network role.
    
    Args:
        state_content: The network state content (YAML string in nmstate format)
        target_hosts: host name to target
        
    Returns:
        Application result from remote hosts
    """
    try:
        if not os.path.exists(REMOTE_HOSTS_CONFIG["inventory_file"]):
            return "Error: No remote hosts configured. Use configure_remote_hosts first."
        
        # Parse the state content to ensure it's valid YAML
        try:
            state_data = yaml.safe_load(state_content)
        except yaml.YAMLError as e:
            return f"Error: Invalid YAML in state_content: {e}"
        
        # Create apply playbook with state content
        extra_vars = {
            "nmstate_config": state_data
        }
        
        playbook_content = _create_playbook("apply")
        
        # Run playbook
        result = _run_ansible_playbook(playbook_content, target_host, extra_vars)
        
        if result["success"]:
            return f"Remote apply completed successfully:\n{result['stdout']}"
        else:
            return f"Error running remote apply: {result.get('stderr', result.get('error', 'Unknown error'))}"
            
    except Exception as e:
        return f"Error applying remote network state: {e}"


@mcp.tool()
def show_remote_inventory(
    inventory_file: str | None = None
) -> str:
    """
    Show current remote host inventory configuration.
    
    Args:
        inventory_file: Path to inventory file (uses default if not provided)
    
    Returns:
        Current inventory configuration
    """
    try:
        # Use provided inventory file or default
        if inventory_file:
            inv_file = inventory_file
        else:
            inv_file = REMOTE_HOSTS_CONFIG["inventory_file"]
        
        if not os.path.exists(inv_file):
            return f"No inventory file found at {inv_file}. Please create it first.\n" \
                   f"See the documentation for inventory file guidelines."
        
        with open(inv_file, 'r') as f:
            inventory_content = f.read()
        
        # Parse and analyze inventory
        try:
            inventory_data = yaml.safe_load(inventory_content)
            
            return f"   Current inventory file: {inv_file}\n" \
                   f"   Content:\n" \
                   f"{'='*50}\n" \
                   f"{inventory_content}"
        except yaml.YAMLError as e:
            return f"Error parsing inventory file: {e}\n" \
                   f"Raw content:\n{inventory_content}"
        
    except Exception as e:
        return f"Error reading inventory: {e}"

# This block ensures the server runs when the script is executed
if __name__ == "__main__":
    print(f"Starting Nmstate Network Manager MCP server...")

    # Pass the host and port to the run method
    mcp.run()
