"""Preview or install the local read-only Unreal MCP entry for one client."""

import argparse
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import tomllib

from readonly_server import port_number


PROJECT = Path(__file__).resolve().parents[2]
SERVER = "unreal-mcp"
CLIENTS = {
    "codex": (".codex/config.toml", "mcp_servers", {"url": ""}),
    "claude": (".mcp.json", "mcpServers", {"type": "http", "url": ""}),
    "cursor": (".cursor/mcp.json", "mcpServers", {"url": ""}),
    "gemini": (".gemini/settings.json", "mcpServers", {"httpUrl": ""}),
    "vscode": (".vscode/mcp.json", "servers", {"type": "http", "url": ""}),
}
LOCAL_URL = re.compile(r"http://127\.0\.0\.1:([0-9]{1,5})/mcp")
SERVER_TOML = re.compile(
    r'^\[mcp_servers\.unreal-mcp\][ \t]*\r?\n(?:^(?:url|command|args) = [^\r\n]*(?:\r?\n|$))+',
    re.MULTILINE,
)


def unique_keys(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("Duplicate JSON key. Resolve it before applying the configuration.")
        obj[key] = value
    return obj


def invalid_constant(_):
    raise ValueError("Invalid JSON constant.")


def parse_json(text):
    return json.loads(text, object_pairs_hook=unique_keys, parse_constant=invalid_constant)


def make_entry(client, port):
    entry = {"command": sys.executable, "args": [
        str(PROJECT / "Tools" / "UnrealMcp" / "readonly_server.py"), "--port", str(port),
    ]}
    if client in ("vscode", "claude"):
        entry["type"] = "stdio"
    return entry


def existing_port(client, entry, raw_template):
    if isinstance(entry, dict):
        url_key = "httpUrl" if "httpUrl" in raw_template else "url"
        url = entry.get(url_key)
        match = LOCAL_URL.fullmatch(url) if isinstance(url, str) else None
        if match and entry == {**raw_template, url_key: url}:
            return port_number(match[1])
        args = entry.get("args")
        if isinstance(args, list) and len(args) == 3 and isinstance(args[2], str) and args[2].isdigit():
            port = port_number(args[2])
            if entry == make_entry(client, port):
                return port
    raise ValueError("The existing unreal-mcp entry has personal settings. Merge it manually.")


def preview(client, before, requested_port):
    _, group, raw_template = CLIENTS[client]
    is_toml = client == "codex"
    original = before.decode("utf-8-sig") if before is not None else ""
    try:
        data = (tomllib.loads(original) if is_toml else parse_json(original)) if before is not None else {}
    except ValueError as exc:
        raise ValueError("The existing configuration is invalid or uses unsupported JSON syntax. "
                         "It was preserved. Merge a preview from an empty file manually.") from exc
    if not isinstance(data, dict) or not isinstance(data.get(group, {}), dict):
        raise ValueError("The MCP server table must be an object.")
    servers = data.setdefault(group, {})
    present = SERVER in servers
    old_entry = servers.get(SERVER)
    prior_port = existing_port(client, old_entry, raw_template) if present else 8000
    port = requested_port or prior_port
    entry = make_entry(client, port)
    for name, server in servers.items():
        if name != SERVER and isinstance(server, dict) and any(
            isinstance(server.get(key), str) and LOCAL_URL.fullmatch(server[key])
            for key in ("url", "httpUrl")
        ):
            raise ValueError("Another server entry points directly to Unreal MCP. Review that entry first.")
    if old_entry == entry:
        return port, entry, before
    servers[SERVER] = entry
    eol = "\r\n" if "\r\n" in original else "\n"
    if is_toml:
        if present:
            original, count = SERVER_TOML.subn("", original, count=1)
            if count != 1:
                raise ValueError("The existing TOML entry needs a manual merge.")
        section = [
            f"[{group}.{SERVER}]", f"command = {json.dumps(entry['command'], ensure_ascii=False)}",
            f"args = {json.dumps(entry['args'], ensure_ascii=False)}",
        ]
        rendered = original + (eol if original.endswith(("\n", "\r")) else eol * 2 if original else "")
        rendered += eol.join(section) + eol
        try:
            parsed = tomllib.loads(rendered)
        except ValueError as exc:
            raise ValueError("This TOML layout needs a manual merge.") from exc
        if parsed != data:
            raise ValueError("This TOML layout needs a manual merge.")
    else:
        rendered = json.dumps(data, ensure_ascii=False, indent=2).replace("\n", eol) + eol
    encoding = "utf-8-sig" if before and before.startswith(b"\xef\xbb\xbf") else "utf-8"
    return port, entry, rendered.encode(encoding)


def install(path, before, after):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        pending = Path(stream.name)
        stream.write(after)
    try:
        current = path.read_bytes() if path.exists() else None
        if current != before:
            raise ValueError("Configuration changed after it was read. Preview again.")
        if before is None:
            # A concurrent creator keeps their file on Windows.
            pending.rename(path)
        else:
            os.replace(pending, path)
    finally:
        pending.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("client", choices=CLIENTS)
    parser.add_argument("--workspace", choices=("project", "repo"), default="project")
    parser.add_argument("--port", type=port_number, help="Unreal's local port. Defaults to the generated entry's port or 8000.")
    parser.add_argument("--apply", action="store_true", help="Write the previewed server entry.")
    args = parser.parse_args()
    workspace = PROJECT if args.workspace == "project" else PROJECT.parent
    path = workspace / CLIENTS[args.client][0]
    try:
        before = path.read_bytes() if path.exists() else None
        port, entry, after = preview(args.client, before, args.port)
        print(f"{path}\n{SERVER}: local Unreal port {port}\n{json.dumps(entry, ensure_ascii=False, indent=2)}")
        if before == after:
            print("Already configured.")
        elif args.apply:
            install(path, before, after)
            print("Applied. Reload the client configuration.")
        else:
            print("Preview only. Use --apply to write this entry.")
    except (OSError, ValueError, argparse.ArgumentTypeError) as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
