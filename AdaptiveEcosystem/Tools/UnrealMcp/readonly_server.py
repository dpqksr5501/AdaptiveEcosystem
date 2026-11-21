"""Expose selected Unreal Editor queries over MCP stdio."""

import argparse
import http.client
import ipaddress
import json
import subprocess
import sys


PROTOCOLS = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")
SCENE = "editor_toolset.toolsets.scene.SceneTools"
TOOLS = {
    "get_current_level": (SCENE, "get_current_level", "Read the current level package path.", {}),
    "is_pie_running": (
        "EditorToolset.EditorAppToolset", "IsPIERunning", "Check whether PIE or Simulate is active.", {},
    ),
    "find_actors_by_label": (
        SCENE, "find_actors", "Find actors in the current world by a label substring.",
        {"name": {"type": "string", "minLength": 1, "maxLength": 100}},
    ),
}
MAX_MESSAGE = 1024 * 1024


def port_number(value):
    port = int(value)
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("Port must be in 1..65535.")
    return port


def loopback_listener(port):
    """Inspect the actual Windows listener before contacting Unreal."""
    result = subprocess.run(
        ["netstat", "-ano", "-p", "tcp"], capture_output=True, text=True, errors="replace",
        check=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW,
    )
    ipv4_loopback = False
    for line in result.stdout.splitlines():
        fields = line.split()
        if len(fields) != 5 or fields[0] != "TCP" or fields[2] not in ("0.0.0.0:0", "[::]:0"):
            continue
        host, _, local_port = fields[1].rpartition(":")
        if local_port != str(port):
            continue
        address = ipaddress.ip_address(host.strip("[]"))
        if not address.is_loopback:
            raise ValueError("The Unreal MCP port has a non-loopback listener.")
        ipv4_loopback |= str(address) == "127.0.0.1"
    if not ipv4_loopback:
        raise ValueError("Start the Unreal MCP server on the configured local port.")


class UnrealConnection:
    def __init__(self, port):
        self.port = port
        self.version = None
        self.session = None
        self.request_id = 0

    def send(self, method, params, *, notification=False):
        self.request_id += 1
        request = {"jsonrpc": "2.0", "method": method, "params": params}
        if not notification:
            request["id"] = self.request_id
        headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        if self.session:
            headers.update({"Mcp-Session-Id": self.session, "MCP-Protocol-Version": self.version})
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=8)
        try:
            conn.request("POST", "/mcp", json.dumps(request), headers)
            response = conn.getresponse()
            if notification and response.status in (200, 202, 204):
                return None
            if response.status != 200:
                raise ValueError(f"Unreal MCP returned HTTP {response.status}.")
            session = response.getheader("Mcp-Session-Id")
            data = response.read(MAX_MESSAGE + 1)
            if len(data) > MAX_MESSAGE:
                raise ValueError("Unreal returned more than 1 MiB.")
            reply = json.loads(data)
            if not isinstance(reply, dict) or reply.get("id") != request["id"] or "result" not in reply:
                raise ValueError("Unreal rejected the request. Check the Editor Output Log.")
            return reply["result"], session
        finally:
            conn.close()

    def query(self, toolset, name, arguments):
        loopback_listener(self.port)
        try:
            if self.session is None:
                info, session = self.send("initialize", {
                    "protocolVersion": PROTOCOLS[0], "capabilities": {},
                    "clientInfo": {"name": "adaptive-unreal-readonly", "version": "1.0"},
                })
                self.version = info.get("protocolVersion")
                if self.version not in PROTOCOLS or not session:
                    raise ValueError("Unreal did not negotiate a supported MCP session.")
                self.session = session
                self.send("notifications/initialized", {}, notification=True)
            value, _ = self.send("tools/call", {"name": "call_tool", "arguments": {
                "toolset_name": toolset, "tool_name": name, "arguments": arguments,
            }})
            return value
        except (ValueError, OSError, http.client.HTTPException):
            self.session = None
            raise

    def close(self):
        if not self.session:
            return
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=2)
        try:
            conn.request("DELETE", "/mcp", headers={
                "Mcp-Session-Id": self.session, "MCP-Protocol-Version": self.version,
            })
            conn.getresponse().close()
        except (OSError, http.client.HTTPException):
            pass
        finally:
            conn.close()


def describe_tools():
    return [
        {"name": name, "description": description, "annotations": {"readOnlyHint": True},
         "inputSchema": {"type": "object", "properties": properties, "required": list(properties),
                         "additionalProperties": False}}
        for name, (_, _, description, properties) in TOOLS.items()
    ]


def error(code, message):
    return {"error": {"code": code, "message": message}}


def handle(method, params, unreal):
    if method == "initialize":
        version = params.get("protocolVersion")
        return {"result": {
            "protocolVersion": version if version in PROTOCOLS else PROTOCOLS[0],
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "adaptive-unreal-readonly", "version": "1.0"},
        }}
    if method == "ping":
        return {"result": {}}
    if method == "tools/list":
        return {"result": {"tools": describe_tools()}}
    if method != "tools/call":
        return error(-32601, "Method not available.")
    name = params.get("name")
    arguments = params.get("arguments", {})
    if not isinstance(name, str) or name not in TOOLS or not isinstance(arguments, dict):
        return error(-32602, "Only the listed read-only tools are available.")
    toolset, tool, _, properties = TOOLS[name]
    if arguments.keys() != properties.keys() or any(
        not isinstance(value, str) or not 1 <= len(value.strip()) <= len(value) <= 100
        for value in arguments.values()
    ):
        return error(-32602, "Arguments must match the read-only tool schema.")
    if name == "find_actors_by_label":
        # UE 5.8's generated schema requires these even though Python supplies defaults.
        arguments = {**arguments, "tag": "", "collision_channels": []}
    try:
        return {"result": unreal.query(toolset, tool, arguments)}
    except (OSError, ValueError, http.client.HTTPException, subprocess.SubprocessError) as exc:
        return {"result": {"isError": True, "content": [{"type": "text", "text": str(exc)}]}}


def serve(unreal):
    try:
        while line := sys.stdin.buffer.readline(MAX_MESSAGE + 1):
            if len(line) > MAX_MESSAGE:
                raise SystemExit("MCP request exceeds 1 MiB.")
            request_id = None
            try:
                request = json.loads(line)
            except ValueError:
                response = error(-32700, "Invalid JSON.")
            else:
                if not isinstance(request, dict) or request.get("jsonrpc") != "2.0":
                    response = error(-32600, "Invalid request.")
                elif "id" not in request:
                    continue
                else:
                    request_id = request["id"]
                    params = request.get("params", {})
                    response = (
                        handle(request.get("method"), params, unreal) if isinstance(params, dict)
                        else error(-32602, "Expected an object in params.")
                    )
            print(json.dumps({"jsonrpc": "2.0", "id": request_id, **response}), flush=True)
    finally:
        unreal.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=port_number, default=8000)
    serve(UnrealConnection(parser.parse_args().port))
