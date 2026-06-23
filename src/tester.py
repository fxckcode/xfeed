"""Project detection, testing, and review for xfeed.

Detects GitHub/npm/PyPI projects in tweet links, clones/installs them,
runs basic smoke tests (install deps + ``--help``), and writes a review
note (``REVIEW.md``) to the Obsidian vault under ``X/Bookmarks/``.
"""

from __future__ import annotations

import datetime
import logging
import re
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

logger = logging.getLogger("xfeed.tester")

# ---------------------------------------------------------------------------
# URL classification
# ---------------------------------------------------------------------------

GITHUB_RE = re.compile(r"github\.com/([^/]+)/([^/#?]+)")
NPM_RE = re.compile(r"npmjs\.com/package/([^/#?]+)")
PYPI_RE = re.compile(r"pypi\.org/project/([^/#?]+)")
SHORT_DOMAINS = {"t.co", "x.co"}


def _is_short_url(url: str) -> bool:
    """Return ``True`` when *url* is hosted on a known link-shortener domain."""
    try:
        netloc = urlparse(url).netloc
    except ValueError:
        return False
    # Strip port if present
    return netloc.split(":")[0] in SHORT_DOMAINS


def _resolve_short_url(url: str) -> str | None:
    """Follow redirects for a shortened URL, returning the final destination.

    Tries HEAD first, falls back to GET (some servers reject HEAD).
    Returns ``None`` when resolution fails.
    """
    for method in (httpx.head, httpx.get):
        try:
            resp = method(url, follow_redirects=True, timeout=10)
            return str(resp.url)
        except httpx.HTTPError:
            continue
    return None


def _classify_link(url: str) -> dict[str, Any] | None:
    """Classify a single URL as GitHub, npm, PyPI, or ``None`` (unidentifiable).

    Resolves ``t.co`` / ``x.co`` short links automatically.
    """
    resolved = url

    if _is_short_url(url):
        resolved_url = _resolve_short_url(url)
        if resolved_url is None:
            return None
        resolved = resolved_url

    # GitHub
    m = GITHUB_RE.search(resolved)
    if m:
        owner = m.group(1)
        repo = m.group(2).removesuffix(".git")
        return {
            "type": "github",
            "url": resolved,
            "owner": owner,
            "repo": repo,
            "full_name": f"{owner}/{repo}",
            "project_name": repo,
        }

    # npm
    m = NPM_RE.search(resolved)
    if m:
        pkg = m.group(1)
        return {
            "type": "npm",
            "url": resolved,
            "package_name": pkg,
            "project_name": pkg,
        }

    # PyPI
    m = PYPI_RE.search(resolved)
    if m:
        pkg = m.group(1)
        return {
            "type": "pypi",
            "url": resolved,
            "package_name": pkg,
            "project_name": pkg,
        }

    return None


def _dedup_key(project: dict[str, Any]) -> str:
    """Return the deduplication key for a project dict."""
    return project.get("full_name") or project.get("package_name", "")


# ---------------------------------------------------------------------------
# 1. Project detection
# ---------------------------------------------------------------------------


def detect_projects(tweets: list[dict]) -> list[dict]:
    """Scan each tweet's ``links`` field and return deduplicated project dicts.

    For every link in each tweet:
    - Classifies it as ``github``, ``npm``, ``pypi``, or skips it (``other``).
    - Resolves ``t.co`` / ``x.co`` short URLs via HTTP redirect.
    - Extracts structured metadata (owner, repo, package name, etc.).
    - Deduplicates by ``full_name`` (GitHub) or ``package_name`` (npm/PyPI).

    Returns:
        List of project dicts. GitHub dicts include ``type``, ``url``,
        ``owner``, ``repo``, ``full_name``, ``project_name``. npm/PyPI dicts
        include ``type``, ``url``, ``package_name``, ``project_name``.
    """
    seen: set[str] = set()
    projects: list[dict[str, Any]] = []

    for tweet in tweets:
        links: list[str] = tweet.get("links", []) or []
        for link in links:
            project = _classify_link(link)
            if project is None:
                continue

            key = _dedup_key(project)
            if key in seen:
                continue
            seen.add(key)
            projects.append(project)

    return projects


# ---------------------------------------------------------------------------
# 2. Clone a GitHub repo
# ---------------------------------------------------------------------------


def clone_project(project: dict, dest_base: str, vault_path: str) -> Path:
    """Clone a GitHub repository into the vault's bookmarks directory.

    *dest_base* is unused (kept for interface compatibility). The actual
    destination is ``{vault_path}/X/Bookmarks/{project_name}/``.

    Returns:
        Path to the cloned (or already-existing) repo directory.
    """
    dest = Path(vault_path) / "X" / "Bookmarks" / project["project_name"]
    if dest.exists():
        logger.info("Already cloned: %s", dest)
        return dest

    logger.info("Cloning %s -> %s", project["url"], dest)
    dest.parent.mkdir(parents=True, exist_ok=True)

    try:
        subprocess.run(
            ["git", "clone", project["url"], str(dest)],
            capture_output=True,
            text=True,
            timeout=120,
            check=True,
        )
    except subprocess.TimeoutExpired:
        logger.warning("Clone timed out for %s", project["url"])
        raise
    except subprocess.CalledProcessError as e:
        logger.warning("Clone failed for %s: %s", project["url"], e.stderr.strip())
        raise

    return dest


# ---------------------------------------------------------------------------
# 3. Test a GitHub repo
# ---------------------------------------------------------------------------


def _detect_project_type(repo_path: Path) -> str:
    """Detect the project language by scanning for manifest files.

    Returns ``'node'``, ``'python'``, ``'rust'``, ``'go'``, or ``'unknown'``.
    """
    if (repo_path / "package.json").exists():
        return "node"
    if (repo_path / "pyproject.toml").exists() or (repo_path / "requirements.txt").exists():
        return "python"
    if (repo_path / "Cargo.toml").exists():
        return "rust"
    if (repo_path / "go.mod").exists():
        return "go"
    return "unknown"


def _install_deps(repo_path: Path, ptype: str) -> bool:
    """Install dependencies for a detected project type.

    Returns ``True`` when installation succeeded, ``False`` otherwise.
    """
    try:
        if ptype == "node":
            subprocess.run(
                ["npm", "install"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=60,
                check=True,
            )
            return True

        if ptype == "python":
            if (repo_path / "pyproject.toml").exists():
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-e", "."],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=60,
                    check=False,
                )
            if (repo_path / "requirements.txt").exists():
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=60,
                    check=False,
                )
            return True

        if ptype == "rust":
            subprocess.run(
                ["cargo", "build"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=120,
                check=True,
            )
            return True

        if ptype == "go":
            subprocess.run(
                ["go", "build"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=120,
                check=True,
            )
            return True

    except subprocess.TimeoutExpired:
        logger.warning("Install timed out for %s", repo_path)
    except subprocess.CalledProcessError as e:
        logger.warning("Install failed for %s: %s", repo_path, e.stderr.strip())

    return False


def _run_help(repo_path: Path, ptype: str, project_name: str) -> str:
    """Try to capture ``--help`` / ``--version`` output from a built project.

    Returns the captured text, or ``""`` if nothing responded.
    """
    candidates: list[list[str]] = []

    if ptype == "node":
        candidates.append(["npx", project_name, "--help"])
        candidates.append(["npx", project_name, "--version"])
    elif ptype == "python":
        candidates.append([sys.executable, "-m", project_name, "--help"])
        candidates.append([project_name, "--help"])
        candidates.append([project_name, "--version"])
    elif ptype == "rust":
        candidates.append(["cargo", "run", "--", "--help"])
    elif ptype == "go":
        candidates.append(["go", "run", ".", "--help"])
    else:
        candidates.append([project_name, "--help"])
        candidates.append([project_name, "--version"])

    for cmd in candidates:
        try:
            result = subprocess.run(
                cmd,
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                output = (result.stdout or result.stderr).strip()
                if output:
                    return output
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue

    return ""


def test_github_repo(project: dict, repo_path: Path) -> dict:
    """Install dependencies and smoke-test a cloned GitHub repo.

    Detects the project language, runs the appropriate install command,
    then tries ``--help`` / ``--version`` on the resulting binary.

    Returns:
        Dict with keys: ``status`` ('ok'|'partial'|'failed'), ``install_ok``,
        ``help_output``, ``errors`` (list), ``project_type``.
    """
    errors: list[str] = []
    ptype = _detect_project_type(repo_path)

    install_ok = _install_deps(repo_path, ptype)
    if not install_ok:
        errors.append(f"Failed to install dependencies ({ptype})")

    help_output = ""
    if install_ok:
        help_output = _run_help(repo_path, ptype, project.get("project_name", ""))
        if not help_output:
            errors.append("No help output available")

    if install_ok and help_output:
        status = "ok"
    elif install_ok or help_output:
        status = "partial"
    else:
        status = "failed"

    return {
        "status": status,
        "install_ok": install_ok,
        "help_output": help_output,
        "errors": errors,
        "project_type": ptype,
    }


# ---------------------------------------------------------------------------
# 4. Test an npm package directly
# ---------------------------------------------------------------------------


def test_npm_package(project: dict, vault_path: str) -> dict:
    """Inspect, globally install, and smoke-test an npm package.

    Runs ``npm view``, ``npm install -g``, then tries ``{name} --help``.

    Returns:
        Dict with keys: ``status``, ``install_ok``, ``help_output``,
        ``errors``, ``project_type`` (always ``'node'``).
    """
    name = project["package_name"]
    errors: list[str] = []

    # npm view (informational — non-fatal)
    try:
        subprocess.run(
            ["npm", "view", name],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
        logger.warning("npm view failed for %s: %s", name, e)
        errors.append(f"npm view failed: {e}")

    # Global install
    install_ok = False
    try:
        subprocess.run(
            ["npm", "install", "-g", name],
            capture_output=True,
            text=True,
            timeout=60,
            check=True,
        )
        install_ok = True
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
        logger.warning("npm install -g failed for %s: %s", name, e)
        errors.append(f"Global install failed: {e}")

    # Smoke test
    help_output = ""
    if install_ok:
        for cmd in [[name, "--help"], ["npx", name, "--help"], [name, "--version"]]:
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                if result.returncode == 0:
                    output = (result.stdout or result.stderr).strip()
                    if output:
                        help_output = output
                        break
            except (subprocess.TimeoutExpired, FileNotFoundError):
                continue

        if not help_output:
            errors.append("No help output available")

    if install_ok and help_output:
        status = "ok"
    elif install_ok:
        status = "partial"
    else:
        status = "failed"

    return {
        "status": status,
        "install_ok": install_ok,
        "help_output": help_output,
        "errors": errors,
        "project_type": "node",
    }


# ---------------------------------------------------------------------------
# 5. Test a PyPI package directly
# ---------------------------------------------------------------------------


def test_pypi_package(project: dict, vault_path: str) -> dict:
    """Install and smoke-test a PyPI package.

    Runs ``pip install {name}``, then tries ``{name} --help``.

    Returns:
        Dict with keys: ``status``, ``install_ok``, ``help_output``,
        ``errors``, ``project_type`` (always ``'python'``).
    """
    name = project["package_name"]
    errors: list[str] = []

    install_ok = False
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", name],
            capture_output=True,
            text=True,
            timeout=60,
            check=True,
        )
        install_ok = True
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
        logger.warning("pip install failed for %s: %s", name, e)
        errors.append(f"pip install failed: {e}")

    help_output = ""
    if install_ok:
        for cmd in [
            [name, "--help"],
            [sys.executable, "-m", name, "--help"],
            [name, "--version"],
        ]:
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                if result.returncode == 0:
                    output = (result.stdout or result.stderr).strip()
                    if output:
                        help_output = output
                        break
            except (subprocess.TimeoutExpired, FileNotFoundError):
                continue

        if not help_output:
            errors.append("No help output available")

    if install_ok and help_output:
        status = "ok"
    elif install_ok:
        status = "partial"
    else:
        status = "failed"

    return {
        "status": status,
        "install_ok": install_ok,
        "help_output": help_output,
        "errors": errors,
        "project_type": "python",
    }


# ---------------------------------------------------------------------------
# 6. Write review
# ---------------------------------------------------------------------------


def _verdict_callout(status: str) -> str:
    """Map a test status to an Obsidian callout type."""
    if status == "ok":
        return "note"
    if status == "partial":
        return "warning"
    return "danger"


def _verdict_summary(status: str, errors: list[str]) -> str:
    """Return a human-readable verdict line based on test status."""
    if status == "ok":
        return "Works correctly. Install succeeded and help output was captured."
    if status == "partial":
        return "Partially working — install succeeded but help output could not be captured."
    if errors:
        return "Failed — " + errors[0]
    return "Failed — could not install or run the project."


def write_review(project: dict, test_result: dict, vault_path: str) -> str:
    """Write a ``REVIEW.md`` for a tested project into the Obsidian vault.

    File path: ``{vault_path}/X/Bookmarks/{project_name}/REVIEW.md``

    Returns:
        Absolute path to the written file.
    """
    project_name = project["project_name"]
    url = project["url"]
    ptype_label = project.get("type", "unknown")
    ptype = test_result.get("project_type", "unknown")

    install_ok = test_result.get("install_ok", False)
    status = test_result.get("status", "failed")
    help_output = test_result.get("help_output", "")
    errors: list[str] = test_result.get("errors", [])
    today = datetime.date.today().isoformat()

    dest = Path(vault_path) / "X" / "Bookmarks" / project_name
    dest.mkdir(parents=True, exist_ok=True)
    file_path = dest / "REVIEW.md"

    sections: list[str] = [
        "---",
        f"title: 'Review: {project_name}'",
        f"date: {today}",
        f"tags: [xfeed, review, {ptype}]",
        "---",
        "",
        f"# Review: {project_name}",
        "",
        "> [!info] Source",
        f"> URL: {url}",
        f"> Type: {ptype_label}",
        "",
        "## Project Info",
        f"- **Name**: {project_name}",
        f"- **Source**: {url}",
        "",
        "## Test Results",
        f"- **Install**: {'✅' if install_ok else '❌'}",
        f"- **Type**: {ptype}",
        "",
        "## Help Output",
        "",
    ]

    if help_output:
        sections.append(f"```\n{help_output}\n```")
        sections.append("")

    callout = _verdict_callout(status)
    verdict = _verdict_summary(status, errors)
    sections.append("## Verdict")
    sections.append(f"> [!{callout}]")
    sections.append(f"> {verdict}")
    sections.append("")

    if errors:
        sections.append("## Errors")
        for err in errors:
            sections.append(f"- {err}")
        sections.append("")

    sections.append("## Notes")
    sections.append("_Auto-generated by xfeed tester._")
    sections.append("")

    content = "\n".join(sections)
    file_path.write_text(content, encoding="utf-8")
    logger.info("Wrote review: %s", file_path)
    return str(file_path)


# ---------------------------------------------------------------------------
# 7. Orchestrator
# ---------------------------------------------------------------------------


def _test_project(project: dict, vault_path: str) -> dict:
    """Route a project dict to the correct test function."""
    ptype = project["type"]

    if ptype == "github":
        repo_path = clone_project(project, "", vault_path)
        return test_github_repo(project, repo_path)

    if ptype == "npm":
        return test_npm_package(project, vault_path)

    if ptype == "pypi":
        return test_pypi_package(project, vault_path)

    return {
        "status": "failed",
        "install_ok": False,
        "help_output": "",
        "errors": [f"Unknown project type: {ptype}"],
        "project_type": "unknown",
    }


def process_tweet_projects(
    tweets: list[dict],
    vault_path: str,
    tested_projects: set[str] | None = None,
) -> list[dict]:
    """Detect projects in tweets, test them, write reviews, return results.

    Orchestration flow:
    1. Detect projects from tweet links (``detect_projects``)
    2. Skip any that are already in *tested_projects* (if provided)
    3. Clone / install each project
    4. Run smoke tests
    5. Write ``REVIEW.md`` for each
    6. Handle partial failures — one bad project never blocks others

    Returns:
        List of result dicts with keys: ``project_name`` (str),
        ``project_type`` (str), ``status`` (str), ``review_path`` (str).
    """
    if tested_projects is None:
        tested_projects = set()

    detected = detect_projects(tweets)
    results: list[dict[str, Any]] = []

    for project in detected:
        dedup_key = _dedup_key(project)
        if dedup_key in tested_projects:
            logger.info("Skipping already-tested project: %s", dedup_key)
            continue

        try:
            test_result = _test_project(project, vault_path)
            review_path = write_review(project, test_result, vault_path)
        except Exception:
            logger.exception("Failed to process project: %s", project.get("project_name"))
            results.append(
                {
                    "project_name": project.get("project_name", "unknown"),
                    "project_type": project.get("type", "unknown"),
                    "status": "failed",
                    "review_path": "",
                }
            )
            continue

        results.append(
            {
                "project_name": project.get("project_name", "unknown"),
                "project_type": test_result.get("project_type", "unknown"),
                "status": test_result.get("status", "failed"),
                "review_path": review_path,
            }
        )

    return results
