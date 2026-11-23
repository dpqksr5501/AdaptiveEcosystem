import contextlib
import io
import json
from pathlib import Path
import tempfile
import tomllib
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import configure_client as config
import readonly_server as server
import review_packages as packages


class ConfigurationTests(unittest.TestCase):
    def test_generated_entries_keep_port_and_other_settings(self):
        for client, (_, group, raw) in config.CLIENTS.items():
            with self.subTest(client=client):
                url = "http://127.0.0.1:8001/mcp"
                if client == "codex":
                    before = ('# keep this comment\r\nmodel = "example"\r\n'
                              '[mcp_servers.other]\r\ncommand = "custom"\r\n'
                              f'[mcp_servers.unreal-mcp]\r\nurl = "{url}"\r\n').encode()
                else:
                    url_key = "httpUrl" if client == "gemini" else "url"
                    before = json.dumps({"setting": True, group: {
                        "other": {"command": "custom"}, config.SERVER: {**raw, url_key: url},
                    }}).encode()
                port, entry, after = config.preview(client, before, None)
                parsed = (tomllib.loads if client == "codex" else json.loads)(after.decode())
                self.assertEqual(parsed[group]["other"], {"command": "custom"})
                self.assertEqual(parsed[group][config.SERVER], entry)
                self.assertEqual(port, 8001)
                self.assertEqual(config.preview(client, after, None)[2], after)
                self.assertEqual(config.preview(client, after, 8002)[0], 8002)
                if client == "codex":
                    self.assertIn(b'# keep this comment\r\nmodel = "example"\r\n', after)
                else:
                    self.assertTrue(parsed["setting"])

    def test_custom_invalid_and_direct_alias_settings_are_preserved(self):
        for before in (
            b'{"servers":',
            b'{"servers":{},"servers":{}}',
            b'{"servers":{"unreal-mcp":{"url":"http://127.0.0.1:8001/mcp","headers":{"custom":"x"}}}}',
            b'{"servers":{"direct":{"url":"http://127.0.0.1:8001/mcp"}}}',
        ):
            with self.subTest(before=before), self.assertRaises(ValueError):
                config.preview("vscode", before, None)
        with self.assertRaises(ValueError):
            config.preview("codex", b'[mcp_servers.unreal-mcp]\nurl="https://example.org"\n', None)

    def test_apply_refuses_file_changed_since_preview(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mcp.json"
            path.write_bytes(b"newer")
            with self.assertRaises(ValueError):
                config.install(path, b"before", b"after")
            self.assertEqual(path.read_bytes(), b"newer")


class ReadOnlyTests(unittest.TestCase):
    def test_only_known_calls_and_argument_shapes_reach_unreal(self):
        unreal = Mock()
        for call in (
            {"name": "call_tool", "arguments": {"tool_name": "load_level"}},
            {"name": "get_current_level", "arguments": {"tool_name": "load_level"}},
            {"name": "find_actors_by_label", "arguments": {"name": " "}},
            {"name": "find_actors_by_label", "arguments": {"name": "deer", "root": "/Game/X"}},
        ):
            self.assertIn("error", server.handle("tools/call", call, unreal))
        self.assertIn("error", server.handle("resources/read", {"uri": "file:///test"}, unreal))
        unreal.query.assert_not_called()
        server.handle("tools/call", {"name": "find_actors_by_label", "arguments": {"name": "deer"}}, unreal)
        unreal.query.assert_called_once_with(
            server.SCENE, "find_actors", {"name": "deer", "tag": "", "collision_channels": []},
        )

    def test_listener_requires_ipv4_loopback_and_rejects_wildcard(self):
        loopback = " TCP 127.0.0.1:8001 0.0.0.0:0 LISTENING 27\n"
        with patch.object(server.subprocess, "run") as run:
            run.return_value.stdout = loopback
            server.loopback_listener(8001)
            run.return_value.stdout += " TCP [::]:8001 [::]:0 LISTENING 27\n"
            with self.assertRaisesRegex(ValueError, "non-loopback"):
                server.loopback_listener(8001)
            run.return_value.stdout = ""
            with self.assertRaisesRegex(ValueError, "Start the Unreal MCP"):
                server.loopback_listener(8001)


class PackageTests(unittest.TestCase):
    def test_owned_map_review_detects_outside_packages_and_new_branch_overlap(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            content = root / packages.CONTENT
            owned = content / "JYU/Maps/Copy.umap"
            actor = content / "__ExternalActors__/JYU/Maps/Copy/1/AB/A.uasset"
            external = content / "__ExternalObjects__/JYU/Maps/Copy/2/CD/B.uasset"
            outside = content / "__ExternalActors__/JYU/Maps/Copy2/3/EF/C.uasset"
            for path in (owned, actor, external, outside):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"baseline")
            paths = [path.relative_to(root).as_posix() for path in (owned, actor, external, outside)]
            record = root / "review.json"
            args = SimpleNamespace(map="/Game/JYU/Maps/Copy", asset=[], against=["peer"])
            with patch.object(packages, "ROOT", root), contextlib.redirect_stdout(io.StringIO()) as output:
                packages.git("init", "-q")
                packages.git("add", "--", packages.CONTENT)
                packages.git("-c", "user.name=Test", "-c", "user.email=test@example.com",
                             "commit", "-qm", "Initial")
                head = packages.revision("HEAD")
                branch = packages.git("rev-parse", "--abbrev-ref", "HEAD").strip()
                packages.git("branch", "peer")
                owned.write_bytes(b"Pre-existing dirty map")
                self.assertEqual(packages.snapshot(args, record, head, branch), 0)
                actor.write_bytes(b"Owned actor update")
                external.unlink()
                self.assertEqual(packages.review(record, head, branch), 0)
                self.assertIn(paths[1], output.getvalue())
                self.assertIn(paths[2], output.getvalue())
                outside.write_bytes(b"Outside update")
                self.assertEqual(packages.review(record, head, branch), 1)
                self.assertIn(paths[3], output.getvalue())
                outside.write_bytes(b"baseline")
                packages.git("add", "--", paths[1])
                tree = packages.git("write-tree").strip()
                peer = packages.git("-c", "user.name=Test", "-c", "user.email=test@example.com",
                                    "commit-tree", tree, "-p", head, "-m", "Peer actor change").strip()
                packages.git("update-ref", "refs/heads/peer", peer)
                self.assertEqual(packages.review(record, head, branch), 1)
                self.assertIn("Overlapping packages on comparison branches (1)", output.getvalue())


if __name__ == "__main__":
    unittest.main()
