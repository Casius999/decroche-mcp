from __future__ import annotations

from fastmcp import FastMCP

from decroche.cv.parse import parse_cv
from decroche.models import CVParse

cv_server = FastMCP("cv")


@cv_server.tool
def parse(path: str) -> CVParse:
    """Parse a CV file (PDF/DOCX/MD/TXT) into a validated JSON Resume,
    detected sections, a parse-confidence score, and warnings."""
    return parse_cv(path)
