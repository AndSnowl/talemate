;; Reproducible dev shell for Talemate's local app testing (Playwright
;; browser tests, AI-opt-in tests, and the app itself).
;;
;; - uv, python@3.11: the app's package manager and interpreter (pinned to
;;   the lower bound of pyproject.toml's requires-python).
;; - node: Playwright's driver shells out to a Node binary; the one its pip
;;   package bundles can't run on this non-FHS system, so tests/e2e/conftest.py
;;   symlinks the driver at this Guix node instead.
;; - ruff: lint/format, run via `guix shell uv python@3.11 ruff -- ruff ...`
;;   since the venv's ruff shim doesn't run on Guix.
;; - ungoogled-chromium: the browser Playwright drives for e2e tests.
;; - nss-certs, font-dejavu: TLS certs and fonts so headless Chromium
;;   renders and networks correctly.
(specifications->manifest
 (list "uv"
       "python@3.11"
       "node"
       "ruff"
       "ungoogled-chromium"
       "nss-certs"
       "font-dejavu"))
