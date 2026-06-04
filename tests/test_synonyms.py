"""Tests for match.synonyms — normalize and expand."""
from __future__ import annotations


from decroche.match.synonyms import expand, normalize


class TestNormalize:
    def test_canonical_term_returns_itself(self):
        assert normalize("kubernetes") == "kubernetes"

    def test_alias_maps_to_canonical(self):
        assert normalize("k8s") == "kubernetes"

    def test_alias_case_insensitive(self):
        assert normalize("K8S") == "kubernetes"

    def test_alias_strips_whitespace(self):
        assert normalize("  k8s  ") == "kubernetes"

    def test_alias_js_to_javascript(self):
        assert normalize("js") == "javascript"

    def test_alias_ts_to_typescript(self):
        assert normalize("ts") == "typescript"

    def test_alias_py_to_python(self):
        assert normalize("py") == "python"

    def test_alias_ml_to_machine_learning(self):
        assert normalize("ml") == "machine learning"

    def test_alias_postgres_to_postgresql(self):
        assert normalize("postgres") == "postgresql"

    def test_alias_psql_to_postgresql(self):
        assert normalize("psql") == "postgresql"

    def test_alias_cicd_to_ci_cd(self):
        assert normalize("cicd") == "ci/cd"

    def test_unknown_term_returns_lowercased(self):
        assert normalize("SomethingUnknown") == "somethingunknown"

    def test_alias_bilingual_fr_project_management(self):
        assert normalize("project management") == "gestion de projet"

    def test_alias_node_to_nodejs(self):
        assert normalize("node") == "nodejs"

    def test_alias_mongo_to_mongodb(self):
        assert normalize("mongo") == "mongodb"

    def test_alias_aws_from_amazon(self):
        assert normalize("amazon web services") == "aws"

    def test_alias_spring_to_springboot(self):
        assert normalize("spring boot") == "springboot"


class TestExpand:
    def test_expand_kubernetes_includes_k8s(self):
        result = expand("kubernetes")
        assert "k8s" in result
        assert "kubernetes" in result

    def test_expand_alias_also_expands(self):
        # "k8s" resolves to "kubernetes", then expands to full set
        result = expand("k8s")
        assert "kubernetes" in result
        assert "k8s" in result

    def test_expand_unknown_returns_singleton(self):
        result = expand("unknownxyz")
        assert result == {"unknownxyz"}

    def test_expand_machine_learning_bilingual(self):
        result = expand("machine learning")
        assert "ml" in result
        assert "apprentissage automatique" in result

    def test_expand_javascript_includes_js(self):
        result = expand("javascript")
        assert "js" in result

    def test_expand_returns_set(self):
        assert isinstance(expand("python"), set)

    def test_expand_python_includes_py(self):
        result = expand("python")
        assert "py" in result
        assert "python3" in result
