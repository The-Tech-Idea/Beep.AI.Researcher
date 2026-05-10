from pathlib import Path

import startup_dependency_bootstrap as bootstrap


def test_bootstrap_detects_missing_without_installing(monkeypatch):
    requirements = Path("unused-requirements.txt")

    def fake_check(requirement):
        return bootstrap.RequirementStatus(requirement=requirement, installed=False)

    monkeypatch.setattr(bootstrap, "_iter_requirements", lambda path: ("missing-package>=1.0",))
    monkeypatch.setattr(bootstrap, "_check_requirement", fake_check)

    report = bootstrap.bootstrap_requirements(
        requirements,
        install_enabled=False,
    )

    assert report.checked == 1
    assert report.missing == ("missing-package>=1.0",)
    assert report.installed == ()
    assert report.failed == ()
    assert report.ok is False


def test_bootstrap_installs_missing_with_active_python(monkeypatch):
    requirements = Path("unused-requirements.txt")
    calls = []

    monkeypatch.setattr(bootstrap, "_iter_requirements", lambda path: ("docling>=2.88.0",))
    monkeypatch.setattr(
        bootstrap,
        "_check_requirement",
        lambda requirement: bootstrap.RequirementStatus(requirement=requirement, installed=False),
    )
    monkeypatch.setattr(bootstrap, "_install_requirement", lambda requirement: calls.append(requirement))

    report = bootstrap.bootstrap_requirements(
        requirements,
        install_enabled=True,
    )

    assert calls == ["docling>=2.88.0"]
    assert report.installed == ("docling>=2.88.0",)
    assert report.failed == ()
    assert report.ok is True


def test_bootstrap_reports_install_failures(monkeypatch):
    requirements = Path("unused-requirements.txt")

    monkeypatch.setattr(bootstrap, "_iter_requirements", lambda path: ("unstructured[all-docs]>=0.16.0",))
    monkeypatch.setattr(
        bootstrap,
        "_check_requirement",
        lambda requirement: bootstrap.RequirementStatus(requirement=requirement, installed=False),
    )

    def fail_install(requirement):
        raise RuntimeError(f"cannot install {requirement}")

    monkeypatch.setattr(bootstrap, "_install_requirement", fail_install)

    report = bootstrap.bootstrap_requirements(
        requirements,
        install_enabled=True,
    )

    assert report.installed == ()
    assert len(report.failed) == 1
    assert report.failed[0].requirement == "unstructured[all-docs]>=0.16.0"
    assert report.ok is False


def test_auto_install_env_guard(monkeypatch):
    monkeypatch.setenv("AUTO_INSTALL_REQUIREMENTS_ON_STARTUP", "0")
    assert bootstrap._resolve_install_enabled(None) is False

    monkeypatch.setenv("AUTO_INSTALL_REQUIREMENTS_ON_STARTUP", "1")
    assert bootstrap._resolve_install_enabled(None) is True
