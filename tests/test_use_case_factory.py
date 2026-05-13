"""
Unit tests for UseCaseFactory in backend/application/__init__.py.

Verifies that each factory method returns a correctly typed instance and that
each call produces a distinct (new) object — i.e. no singleton reuse.
"""
import pytest

from backend.application import (
    AddFuelUseCase,
    AddTripUseCase,
    GenerateReportUseCase,
    GetDashboardUseCase,
    EditFuelUseCase,
    UseCaseFactory,
)


class TestUseCaseFactoryTypes:
    def test_get_add_trip_use_case_returns_correct_type(self):
        uc = UseCaseFactory.get_add_trip_use_case()
        assert isinstance(uc, AddTripUseCase)

    def test_get_dashboard_use_case_returns_correct_type(self):
        uc = UseCaseFactory.get_dashboard_use_case()
        assert isinstance(uc, GetDashboardUseCase)

    def test_get_add_fuel_use_case_returns_correct_type(self):
        uc = UseCaseFactory.get_add_fuel_use_case()
        assert isinstance(uc, AddFuelUseCase)

    def test_get_edit_fuel_use_case_returns_correct_type(self):
        uc = UseCaseFactory.get_edit_fuel_use_case()
        assert isinstance(uc, EditFuelUseCase)

    def test_get_generate_report_use_case_returns_correct_type(self):
        uc = UseCaseFactory.get_generate_report_use_case()
        assert isinstance(uc, GenerateReportUseCase)


class TestUseCaseFactoryFreshInstances:
    def test_factory_creates_fresh_instances(self):
        uc1 = UseCaseFactory.get_add_trip_use_case()
        uc2 = UseCaseFactory.get_add_trip_use_case()
        assert uc1 is not uc2

    def test_dashboard_factory_creates_fresh_instances(self):
        uc1 = UseCaseFactory.get_dashboard_use_case()
        uc2 = UseCaseFactory.get_dashboard_use_case()
        assert uc1 is not uc2

    def test_fuel_factory_creates_fresh_instances(self):
        uc1 = UseCaseFactory.get_add_fuel_use_case()
        uc2 = UseCaseFactory.get_add_fuel_use_case()
        assert uc1 is not uc2
