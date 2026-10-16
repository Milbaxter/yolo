import contextlib
import io
import tempfile
import unittest
from argparse import Namespace
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from yolo import cli
from yolo.model import Message, Thread


def at(day, hour=0):
    return datetime(2026, 10, day, hour, tzinfo=timezone.utc)


class RefreshTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.vault = Path(self.tmp.name)
        self.args = Namespace(vault=self.vault, since="last", source=None, queue_since=None)

    def ingest(self, adapters, day):
        with patch.dict(cli.sources.ALL, adapters, clear=True), patch.object(cli, "now", return_value=at(day)), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return cli.cmd_ingest(self.args)

    def test_failed_source_retries_old_boundary_while_healthy_progresses(self):
        cli.save_state(self.vault, {"last_ingest": at(10).isoformat()})
        boundaries = []

        def broken(since, **_):
            boundaries.append(since)
            raise ValueError("bad export")

        def healthy(since, **_):
            yield Thread("good", "12345678", "Example", at(11), at(11), messages=[Message("user", "A durable preference")])

        self.ingest({"bad": SimpleNamespace(threads=broken), "good": SimpleNamespace(threads=healthy)}, 12)
        state = cli.load_state(self.vault)
        self.assertEqual(state["last_ingest_by_source"]["bad"], at(10).isoformat())
        self.assertEqual(state["last_ingest_by_source"]["good"], at(11).isoformat())
        self.assertEqual(len(state["pending"]), 1)
        self.assertIn("bad", state["ingest_errors"])
        self.ingest({"bad": SimpleNamespace(threads=broken)}, 16)
        self.assertEqual(boundaries, [at(9, 23), at(9, 23)])

    def test_quiet_inbox_does_not_skip_delayed_snapshot(self):
        cli.save_state(self.vault, {"last_ingest": at(10).isoformat()})
        self.ingest({"grok": SimpleNamespace(threads=lambda *a, **k: iter(()))}, 15)
        boundaries = []

        def late_export(since, **_):
            boundaries.append(since)
            if at(12) >= since:
                yield Thread("grok", "12345678", "Late snapshot", at(12), at(12), messages=[Message("user", "Example")])

        files = self.ingest({"grok": SimpleNamespace(threads=late_export)}, 16)
        self.assertEqual(boundaries, [at(9, 23)])
        self.assertEqual(len(files), 1)
        self.assertEqual(len(cli.load_state(self.vault)["pending"]), 1)
        self.assertEqual(self.ingest({"grok": SimpleNamespace(threads=late_export)}, 16), [])

    def test_selected_ingest_preserves_unselected_migration_baseline(self):
        cli.save_state(self.vault, {"last_ingest": at(10).isoformat()})
        self.args.source = ["first"]
        empty = SimpleNamespace(threads=lambda *a, **k: iter(()))
        self.ingest({"first": empty, "other": empty}, 16)
        self.assertEqual(cli.load_state(self.vault)["last_ingest_by_source"]["other"], at(10).isoformat())

    def test_recovery_clears_only_the_recovered_source_error(self):
        cli.save_state(self.vault, {"last_ingest": at(10).isoformat(),
                                   "ingest_errors": {"grok": "bad archive", "other": "still broken"}})
        self.ingest({"grok": SimpleNamespace(threads=lambda *a, **k: iter(()))}, 16)
        self.assertEqual(cli.load_state(self.vault)["ingest_errors"], {"other": "still broken"})

    def test_cli_rejects_zero_batch_to_avoid_nonprogressing_refresh(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            cli.main(["--vault", str(self.vault), "refresh", "--batch", "0"])
        self.assertEqual(error.exception.code, 2)

    def test_refresh_drains_all_batches_and_reports_source_failure(self):
        cli.save_state(self.vault, {"pending": ["one", "two"], "ingest_errors": {"grok": "bad export"}})

        def update(_):
            state = cli.load_state(self.vault)
            state["pending"].pop(0)
            cli.save_state(self.vault, state)
            return True

        with patch.object(cli, "cmd_ingest"), patch.object(cli, "cmd_update", side_effect=update) as updates, patch.object(cli, "git"), patch.object(cli, "notify"):
            self.assertFalse(cli.cmd_refresh(Namespace(vault=self.vault, dry_run=False)))
            self.assertEqual(updates.call_count, 2)

    def test_dry_refresh_does_not_ingest_or_commit(self):
        with patch.object(cli, "cmd_ingest") as ingest, patch.object(cli, "cmd_update", return_value=True), patch.object(cli, "git") as git, contextlib.redirect_stdout(io.StringIO()):
            self.assertTrue(cli.cmd_refresh(Namespace(vault=self.vault, dry_run=True)))
            ingest.assert_not_called()
            git.assert_not_called()


if __name__ == "__main__":
    unittest.main()
