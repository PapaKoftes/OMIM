"""Tests for the domain registry (the map of every fabrication domain).

These pin the registry's integrity and its honesty guarantees: statuses are
truthful, the two real domains are PRODUCTION, dataset/tool refs are well-formed,
and the registry's query helpers work.
"""

from __future__ import annotations

import pytest

from omim.domains import DomainStatus, LicenseClass, build_registry


@pytest.fixture(scope="module")
def reg():
    return build_registry()


def test_registry_has_expected_size(reg):
    assert len(reg) == 13
    assert len(reg.keys()) == len(set(reg.keys()))  # unique keys


def test_only_real_domains_are_production(reg):
    """Honesty guard: nothing claims PRODUCTION except the two validated domains."""
    prod = {d.key for d in reg.by_status(DomainStatus.PRODUCTION)}
    assert prod == {"panel_furniture", "pid"}


def test_production_domains_have_implementing_module(reg):
    for d in reg.by_status(DomainStatus.PRODUCTION):
        assert d.module, f"{d.key} is PRODUCTION but has no module"


def test_non_production_domains_have_no_module_or_are_marked(reg):
    """STUB/PLANNED domains must not pretend to have a working implementation."""
    for d in reg.all():
        if d.status in (DomainStatus.STUB, DomainStatus.PLANNED):
            assert d.module is None, f"{d.key} is {d.status.value} but claims a module"


def test_every_domain_has_summary_and_fit(reg):
    for d in reg.all():
        assert d.summary.strip()
        assert d.fit.strip()


def test_stub_and_planned_have_blockers(reg):
    """A non-production domain must honestly state what's missing."""
    for d in reg.all():
        if d.status in (DomainStatus.STUB, DomainStatus.PLANNED):
            assert d.blockers, f"{d.key} has no stated blockers"


def test_dataset_refs_are_wellformed(reg):
    for d in reg.all():
        for ds in d.datasets:
            assert ds.name
            assert isinstance(ds.license, LicenseClass)


def test_has_real_data_reflects_license(reg):
    """has_real_data is True iff a permissive/share-alike dataset is attached."""
    # digital_fabrication has CC (share-alike) WikiHouse data -> real.
    assert reg.get("digital_fabrication").has_real_data is True
    # sheet_metal's only dataset is UNKNOWN-license BenDFM -> not usable yet.
    assert reg.get("sheet_metal").has_real_data is False
    # pid has PID2Graph (share-alike) -> real.
    assert reg.get("pid").has_real_data is True


def test_with_real_data_query(reg):
    keys = {d.key for d in reg.with_real_data()}
    assert {"panel_furniture", "pid"} <= keys


def test_digital_fabrication_is_the_priority_stub(reg):
    """The recommended next domain has joint vocabulary + real CC data."""
    d = reg.get("digital_fabrication")
    assert d.status == DomainStatus.STUB
    assert "TAB" in d.feature_vocabulary and "SLOT" in d.feature_vocabulary
    assert d.has_real_data
    assert "TAB_SLOT" in d.join_types


def test_unknown_key_returns_none(reg):
    assert reg.get("does_not_exist") is None
    assert "does_not_exist" not in reg


def test_cli_domains_lists_all():
    from omim.cli import main
    assert main(["domains"]) == 0


def test_cli_domains_detail_and_bad_key():
    from omim.cli import main
    assert main(["domains", "--key", "digital_fabrication"]) == 0
    assert main(["domains", "--key", "nope"]) == 1
    assert main(["domains", "--status", "production"]) == 0
