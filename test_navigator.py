"""Unit and end-to-end HTTP integration tests for Workspace Navigator."""

from http.server import ThreadingHTTPServer
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request

NAV_DIR = Path(__file__).resolve().parent
if str(NAV_DIR) not in sys.path:
    sys.path.insert(0, str(NAV_DIR))

import navigator_core as core
import server as srv


class TestNavigatorUniversal(unittest.TestCase):
    def test_token_safe_classification_avoids_false_positives(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "Workspace"
            dt = Path(tmp) / "Desktop"
            dt.mkdir()
            core.ensure_workspace_structure(ws)

            for name in ("mail_client", "html_parser", "internet_tools"):
                (dt / name).mkdir()
                dest = core.classify_desktop_item(dt / name, ws)
                self.assertEqual(dest.parent.name, "03_Development_Projects", f"{name} misclassified to {dest}")

            (dt / "Engineering Economics").mkdir()
            self.assertEqual(
                core.classify_desktop_item(dt / "Engineering Economics", ws).parent.name,
                "04_Academics_Study",
            )

            (dt / "ml-anomaly-detector").mkdir()
            self.assertEqual(
                core.classify_desktop_item(dt / "ml-anomaly-detector", ws).parent.name,
                "02_AI_MachineLearning",
            )

            (dt / "sih_2026_app").mkdir()
            self.assertEqual(
                core.classify_desktop_item(dt / "sih_2026_app", ws).parent.name,
                "01_Hackathons_SIH",
            )

            f_resume = dt / "John_Doe_Resume.pdf"
            f_resume.write_text("cv", encoding="utf-8")
            self.assertEqual(
                core.classify_desktop_item(f_resume, ws),
                ws / "06_Career_Personal" / "Resume" / "John_Doe_Resume.pdf",
            )

            # Content-aware: folder with PDF/PPTX and no code -> Academics & Study
            study_dir = dt / "Microeconomics_Deck"
            study_dir.mkdir()
            (study_dir / "slides.pptx").write_text("ppt", encoding="utf-8")
            self.assertEqual(
                core.classify_desktop_item(study_dir, ws).parent.name,
                "04_Academics_Study",
            )

            # Content-aware: folder with torch in requirements.txt -> AI & ML
            ml_dir = dt / "CoolTool"
            ml_dir.mkdir()
            (ml_dir / "requirements.txt").write_text("torch>=2.0\nfastapi\n", encoding="utf-8")
            self.assertEqual(
                core.classify_desktop_item(ml_dir, ws).parent.name,
                "02_AI_MachineLearning",
            )

    def test_duplicate_collision_handling_and_redundancy_scan(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "Workspace"
            core.ensure_workspace_structure(ws)
            notes_dir = ws / "04_Academics_Study" / "Course_PDFs"

            f1 = notes_dir / "lecture1.txt"
            f1.write_text("same-content-123", encoding="utf-8")

            # Identical file on Desktop should be flagged as redundant duplicate, not renamed
            dt_file = Path(tmp) / "lecture1.txt"
            dt_file.write_text("same-content-123", encoding="utf-8")
            action, _ = srv._handle_duplicate_collision(dt_file, f1, "recycle")
            self.assertEqual(action, "recycle_duplicate")

            # Modified file on Desktop should rename cleanly instead of overwriting
            dt_file.write_text("updated-content-456", encoding="utf-8")
            action2, target2 = srv._handle_duplicate_collision(dt_file, f1, "recycle")
            self.assertEqual(action2, "move")
            self.assertEqual(target2.name, "lecture1 (1).txt")

            # Create a duplicate inside Workspace & a vendor dir that should be ignored
            dup_in_ws = ws / "00_Archives_Storage" / "Project_Backups" / "lecture1 (1).txt"
            dup_in_ws.write_text("same-content-123", encoding="utf-8")
            nm = ws / "03_Development_Projects" / "demo" / "node_modules"
            nm.mkdir(parents=True)
            (nm / "pkg.txt").write_text("same-content-123", encoding="utf-8")
            custom_venv = ws / "03_Development_Projects" / "demo" / "my_custom_env"
            custom_venv.mkdir(parents=True)
            (custom_venv / "pyvenv.cfg").write_text("home = C:\\Python", encoding="utf-8")
            (custom_venv / "lib.txt").write_text("same-content-123", encoding="utf-8")

            # Create numbered collision folder subset
            base_folder = ws / "03_Development_Projects" / "DemoProj"
            copy_folder = ws / "03_Development_Projects" / "DemoProj (1)"
            base_folder.mkdir()
            copy_folder.mkdir()
            (base_folder / "a.py").write_text("print(1)", encoding="utf-8")
            (base_folder / "b.py").write_text("print(2)", encoding="utf-8")
            (copy_folder / "a.py").write_text("print(1)", encoding="utf-8")

            report = core.analyze_workspace_redundancy(ws)
            self.assertEqual(report["redundant_file_count"], 2)
            all_dup_paths = {d["path"] for g in report["duplicate_groups"] for d in g["duplicates"]}
            self.assertIn(str(dup_in_ws), all_dup_paths)
            self.assertNotIn(str(nm / "pkg.txt"), all_dup_paths)
            self.assertNotIn(str(custom_venv / "lib.txt"), all_dup_paths)
            self.assertEqual(len(report["folder_collisions"]), 1)
            self.assertEqual(report["folder_collisions"][0]["relation"], "src_subset_of_dest")
            self.assertTrue(report["folder_collisions"][0]["safe_to_recycle"])
            expected_bytes = len("same-content-123") + len("print(1)")
            self.assertEqual(report["reclaimable_bytes"], expected_bytes)

    def test_managed_root_containment(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "Workspace"
            dt = Path(tmp) / "Desktop"
            ws.mkdir()
            dt.mkdir()
            with srv.STATE_LOCK:
                old_ws = srv.RUNTIME_CFG["workspace_dir"]
                old_dt = srv.RUNTIME_CFG["desktop_dir"]
                srv.RUNTIME_CFG["workspace_dir"] = str(ws)
                srv.RUNTIME_CFG["desktop_dir"] = str(dt)
            try:
                self.assertFalse(srv.is_within_managed_roots(ws))
                self.assertFalse(srv.is_within_managed_roots(dt))
                self.assertFalse(srv.is_within_managed_roots(Path(tmp) / "Other"))
                self.assertTrue(srv.is_within_managed_roots(ws / "03_Development_Projects" / "app"))
            finally:
                with srv.STATE_LOCK:
                    srv.RUNTIME_CFG["workspace_dir"] = old_ws
                    srv.RUNTIME_CFG["desktop_dir"] = old_dt

    def test_ui_backend_http_contract_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            ws = tmp_path / "Workspace"
            dt = tmp_path / "Desktop"
            dt.mkdir()
            core.ensure_workspace_structure(ws)

            proj = ws / "03_Development_Projects" / "sample_app"
            proj.mkdir()
            (proj / "README.md").write_text("# Sample App\nHello world", encoding="utf-8")
            (proj / "app.py").write_text("print('ok')", encoding="utf-8")
            (dt / "study_notes.pdf").write_text("pdf-bytes", encoding="utf-8")

            with srv.STATE_LOCK:
                old_cfg = dict(srv.RUNTIME_CFG)
                old_fav = srv.FAVORITES_FILE
                old_cfg_file = srv.ORGANIZER_CONFIG_FILE
                srv.RUNTIME_CFG["workspace_dir"] = str(ws)
                srv.RUNTIME_CFG["desktop_dir"] = str(dt)
                srv.RUNTIME_CFG["enabled"] = False
                srv.FAVORITES_FILE = tmp_path / "favorites.json"
                srv.ORGANIZER_CONFIG_FILE = tmp_path / "organizer_config.json"
                srv.invalidate_caches()

            httpd = ThreadingHTTPServer(("127.0.0.1", 0), srv.NavigatorHandler)
            port = httpd.server_address[1]
            t = threading.Thread(target=httpd.serve_forever, daemon=True)
            t.start()

            def _req(path, method="GET", body=None):
                data = json.dumps(body).encode("utf-8") if body is not None else None
                headers = {"Content-Type": "application/json"} if data is not None else {}
                req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data, headers=headers, method=method)
                with urllib.request.urlopen(req, timeout=5) as resp:
                    return resp.status, resp.read().decode("utf-8")

            try:
                for static_path in ("/", "/styles.css", "/app.js", "/favicon.ico"):
                    st, _ = _req(static_path)
                    self.assertEqual(st, 200)

                st, raw = _req("/api/projects?refresh=1")
                self.assertEqual(st, 200)
                pdata = json.loads(raw)
                self.assertTrue(any(i["name"] == "sample_app" for i in pdata["items"]))

                st, raw = _req(f"/api/preview?path={urllib.parse.quote(str(proj))}")
                self.assertEqual(st, 200)
                prev = json.loads(raw)
                self.assertEqual(prev["kind"], "directory")
                self.assertIn("Sample App", prev["readme_text"])

                # Preview outside managed roots must be 403
                with self.assertRaises(urllib.error.HTTPError) as ctx:
                    _req(f"/api/preview?path={urllib.parse.quote(str(tmp_path))}")
                self.assertEqual(ctx.exception.code, 403)

                st, raw = _req("/api/toggle-favorite", "POST", {"path": str(proj), "name": "sample_app"})
                self.assertTrue(json.loads(raw)["is_favorite"])

                st, raw = _req("/api/organize-desktop", "POST", {"dry_run": True})
                dry = json.loads(raw)
                self.assertEqual(dry["moved_count"], 1)
                self.assertEqual(dry["moved_items"][0]["Item"], "study_notes.pdf")

                st, raw = _req("/api/duplicates?refresh=1")
                self.assertEqual(st, 200)
                self.assertIn("duplicate_groups", json.loads(raw))

                st, raw = _req("/api/config")
                self.assertEqual(json.loads(raw)["workspace_dir"], str(ws))

                # Quarantine -> List -> Restore -> Quarantine -> Purge workflow
                extra_dup = ws / "00_Archives_Storage" / "Project_Backups" / "dup_copy.txt"
                extra_dup.write_text("redundant", encoding="utf-8")
                st, raw = _req("/api/quarantine", "POST", {"paths": [str(extra_dup)], "reason": "Test dup"})
                q_res = json.loads(raw)
                self.assertEqual(q_res["moved_count"], 1)
                self.assertFalse(extra_dup.exists())
                q_path = q_res["moved"][0]["quarantine_path"]

                st, raw = _req("/api/quarantine")
                self.assertEqual(json.loads(raw)["count"], 1)

                st, raw = _req("/api/quarantine/restore", "POST", {"paths": [q_path]})
                self.assertEqual(json.loads(raw)["restored_count"], 1)
                self.assertTrue(extra_dup.exists())

                st, raw = _req("/api/quarantine", "POST", {"paths": [str(extra_dup)]})
                q_path2 = json.loads(raw)["moved"][0]["quarantine_path"]
                st, raw = _req("/api/quarantine/purge", "POST", {"paths": [q_path2]})
                self.assertEqual(json.loads(raw)["removed_count"], 1)
                st, raw = _req("/api/quarantine")
                self.assertEqual(json.loads(raw)["count"], 0)
            finally:
                httpd.shutdown()
                httpd.server_close()
                with srv.STATE_LOCK:
                    srv.RUNTIME_CFG.clear()
                    srv.RUNTIME_CFG.update(old_cfg)
                    srv.FAVORITES_FILE = old_fav
                    srv.ORGANIZER_CONFIG_FILE = old_cfg_file
                    srv.invalidate_caches()


if __name__ == "__main__":
    unittest.main()
