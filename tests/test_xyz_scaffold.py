"""Tests for cv.xyz_scaffold — pure deterministic XYZ bullet scaffolding.

TDD order:
  RED  (this file first, before implementation)
  GREEN (implement xyz_scaffold.py to pass)
  IMPROVE (refactor)
"""
from __future__ import annotations

from decroche.cv.xyz_scaffold import scaffold_bullet, scaffold_resume
from decroche.models import JSONResume, Work, XyzScaffold


# ── scaffold_bullet ───────────────────────────────────────────────────────────────


class TestScaffoldBulletMetricPresent:
    def test_pct_metric_detected(self):
        s = scaffold_bullet("Reduced latency 38% by adding caching")
        assert s.y_present is True

    def test_x_extracted(self):
        s = scaffold_bullet("Reduced latency 38% by adding caching")
        assert "latency" in s.x.lower()

    def test_verb_detected_strong(self):
        s = scaffold_bullet("Reduced latency 38% by adding caching")
        assert s.verb is not None
        assert s.verb.lower() == "reduced"
        assert s.weak_verb is False

    def test_z_extracted_after_by(self):
        s = scaffold_bullet("Reduced latency 38% by adding caching")
        assert s.z is not None
        assert "caching" in s.z.lower()

    def test_template_filled_known_parts(self):
        s = scaffold_bullet("Reduced latency 38% by adding caching")
        assert "latency" in s.template.lower()
        assert "38%" in s.template or "38" in s.template

    def test_no_missing_metric_prompt_when_metric_present(self):
        s = scaffold_bullet("Reduced latency 38% by adding caching")
        assert s.missing_metric_prompt is None


class TestScaffoldBulletNoMetric:
    def test_y_not_present(self):
        s = scaffold_bullet("Responsible for the database")
        assert s.y_present is False

    def test_weak_verb_flagged(self):
        s = scaffold_bullet("Responsible for the database")
        assert s.weak_verb is True

    def test_missing_metric_prompt_set(self):
        s = scaffold_bullet("Responsible for the database")
        assert s.missing_metric_prompt is not None
        assert "Do NOT invent" in s.missing_metric_prompt or "real number" in s.missing_metric_prompt.lower()

    def test_template_has_placeholder_for_y(self):
        s = scaffold_bullet("Responsible for the database")
        assert "[Y" in s.template


class TestScaffoldBulletWorkedOn:
    def test_worked_on_is_weak(self):
        s = scaffold_bullet("Worked on backend infrastructure improvements")
        assert s.weak_verb is True

    def test_helped_is_weak(self):
        s = scaffold_bullet("Helped the team with deployments")
        assert s.weak_verb is True

    def test_managed_without_metric_is_weak(self):
        s = scaffold_bullet("Managed the database systems")
        assert s.weak_verb is True


class TestScaffoldBulletEuroMetric:
    def test_euro_currency_detected(self):
        s = scaffold_bullet("Generated €2M revenue by launching new product line")
        assert s.y_present is True

    def test_dollar_detected(self):
        s = scaffold_bullet("Saved $500k by renegotiating vendor contracts")
        assert s.y_present is True

    def test_multiplier_x_detected(self):
        s = scaffold_bullet("Doubled throughput 2x by refactoring pipeline")
        assert s.y_present is True


class TestScaffoldBulletZClause:
    def test_z_after_via(self):
        s = scaffold_bullet("Improved performance 40% via query optimization")
        assert s.z is not None
        assert "optimization" in s.z.lower()

    def test_z_after_using(self):
        s = scaffold_bullet("Increased conversion 15% using A/B testing")
        assert s.z is not None
        assert "testing" in s.z.lower()

    def test_z_none_when_no_method_clause(self):
        s = scaffold_bullet("Built a new authentication system achieving 99.9% uptime")
        assert s.z is None

    def test_template_z_placeholder_when_z_missing(self):
        s = scaffold_bullet("Built a new authentication system achieving 99.9% uptime")
        assert "[Z]" in s.template or "[doing" in s.template.lower() or "how" in s.template.lower()


class TestScaffoldBulletFrench:
    def test_french_verb_detected_strong(self):
        s = scaffold_bullet("Réduit la latence de 38% en ajoutant un cache")
        assert s.verb is not None
        assert s.weak_verb is False

    def test_french_metric_detected(self):
        s = scaffold_bullet("Réduit la latence de 38% en ajoutant un cache")
        assert s.y_present is True

    def test_compound_verb_mis_en_place(self):
        s = scaffold_bullet("Mis en place un processus réduisant les erreurs de 20%")
        assert s.verb is not None
        assert "mis en place" in s.verb.lower()

    def test_no_verb_match_returns_scaffold(self):
        s = scaffold_bullet("38% reduction in latency via caching")
        assert isinstance(s, XyzScaffold)


class TestScaffoldBulletReturnType:
    def test_returns_xyzscaffold(self):
        s = scaffold_bullet("Reduced latency 38% by adding caching")
        assert isinstance(s, XyzScaffold)

    def test_original_preserved(self):
        bullet = "Reduced latency 38% by adding caching"
        s = scaffold_bullet(bullet)
        assert s.original == bullet


# ── scaffold_resume ─────────────────────────────────────────────────────────────────────


class TestScaffoldResume:
    def _make_resume(self) -> JSONResume:
        return JSONResume(
            work=[
                Work(
                    name="Acme Corp",
                    highlights=[
                        "Reduced latency 38% by adding caching",
                        "Responsible for the database",
                        "Led migration of 12 services to Kubernetes",
                    ],
                )
            ]
        )

    def test_returns_list(self):
        result = scaffold_resume(self._make_resume())
        assert isinstance(result, list)

    def test_one_entry_per_highlight(self):
        jr = self._make_resume()
        result = scaffold_resume(jr)
        total_highlights = sum(len(w.highlights) for w in jr.work)
        assert len(result) == total_highlights

    def test_all_entries_are_xyzscaffold(self):
        result = scaffold_resume(self._make_resume())
        assert all(isinstance(s, XyzScaffold) for s in result)

    def test_metric_bullets_detected(self):
        result = scaffold_resume(self._make_resume())
        metric_bullets = [s for s in result if s.y_present]
        assert len(metric_bullets) >= 1

    def test_weak_bullets_detected(self):
        result = scaffold_resume(self._make_resume())
        weak_bullets = [s for s in result if s.weak_verb]
        assert len(weak_bullets) >= 1

    def test_empty_resume_returns_empty_list(self):
        jr = JSONResume(work=[Work(name="Co", highlights=[])])
        result = scaffold_resume(jr)
        assert result == []

    def test_multiple_work_entries(self):
        jr = JSONResume(
            work=[
                Work(name="Co1", highlights=["Built pipeline saving 20% cost"]),
                Work(name="Co2", highlights=["Responsible for reporting"]),
            ]
        )
        result = scaffold_resume(jr)
        assert len(result) == 2
