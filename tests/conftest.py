from __future__ import annotations

from pathlib import Path

import pytest

SAMPLE_EN = """Jane Doe
jane.doe@example.com
+1 415 555 0101

Summary
Senior backend engineer with 8 years building distributed systems.

Experience
- Reduced API latency 38% by introducing a caching layer
- Led migration of 12 services to Kubernetes

Skills
Python, Go, Kubernetes, PostgreSQL

Education
B.S. Computer Science, MIT
"""

SAMPLE_FR = """Jean Dupont
jean.dupont@example.com
+33 6 12 34 56 78

Profil
Ingenieur backend senior, 8 ans en systemes distribues.

Experience
- Reduction de la latence API de 38% via une couche de cache
- Migration de 12 services vers Kubernetes

Competences
Python, Go, Kubernetes, PostgreSQL

Formation
Master Informatique, EPITA
"""


@pytest.fixture(scope="session")
def fixtures_dir(tmp_path_factory) -> Path:
    d = tmp_path_factory.mktemp("cv_fixtures")
    (d / "sample_en.txt").write_text(SAMPLE_EN, encoding="utf-8")
    (d / "sample_fr.txt").write_text(SAMPLE_FR, encoding="utf-8")

    # DOCX fixture
    from docx import Document

    doc = Document()
    for line in SAMPLE_EN.splitlines():
        doc.add_paragraph(line)
    doc.save(str(d / "sample.docx"))

    # PDF fixture with extractable text
    from reportlab.lib.pagesizes import LETTER
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(str(d / "sample.pdf"), pagesize=LETTER)
    y = 750
    for line in SAMPLE_EN.splitlines():
        c.drawString(50, y, line)
        y -= 14
    c.save()

    # "Scanned" PDF: no extractable text (only a drawn rectangle)
    c2 = canvas.Canvas(str(d / "scanned.pdf"), pagesize=LETTER)
    c2.rect(50, 600, 400, 100, fill=0)
    c2.save()

    return d
