"""Portable locations. Works inside the CTTX repo (.claude/skills/<name>/), as an uploaded skill
(read-only skill folder), or from any working directory.

  CTTX_WORKDIR   where projects/ and data/ live   (default: repo root if installed in a repo, else CWD)
  CTTX_MAST_DIR  folder holding the mast KMZs / mast_index.json (optional)
"""
import glob
import os

SKILL_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_parent = os.path.dirname(SKILL_DIR)
_in_repo = os.path.basename(_parent) == "skills" and os.path.basename(os.path.dirname(_parent)) == ".claude"
WORK = os.path.abspath(os.environ.get("CTTX_WORKDIR")
                       or (os.path.dirname(os.path.dirname(_parent)) if _in_repo else os.getcwd()))
PROJECTS = os.path.join(WORK, "projects")
DATA = os.path.join(WORK, "data")
INTEL = os.path.join(DATA, "intelligence-graph.json")

_MAST_CANDIDATES = [d for d in (os.environ.get("CTTX_MAST_DIR"), os.path.join(SKILL_DIR, "data", "masts"),
                                os.path.join(DATA, "private", "masts")) if d]
MAST_WRITE_DIR = os.path.join(DATA, "private", "masts")


def mast_kmz_dir():
    """First folder that contains the carrier KMZ/KML files."""
    for d in _MAST_CANDIDATES:
        if glob.glob(os.path.join(d, "*.km[lz]")):
            return d
    return None


def mast_index():
    """Existing index if any, else the writable location a build will create."""
    for d in _MAST_CANDIDATES:
        p = os.path.join(d, "mast_index.json")
        if os.path.exists(p):
            return p
    return os.path.join(MAST_WRITE_DIR, "mast_index.json")
