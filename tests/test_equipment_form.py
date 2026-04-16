"""Extended tests for parse_trip_equipment_form edge cases."""

import pytest
from backend.helpers import parse_trip_equipment_form


class DummyForm:
    """Lightweight form-like object for testing."""
    def __init__(self, data: dict):
        self._data = data

    def getlist(self, key):
        return self._data.get(key, [])


class TestParseTripEquipmentEdgeCases:
    """Edge cases for parse_trip_equipment_form."""

    def test_empty_form(self):
        """No equipment fields submitted returns empty list."""
        form = DummyForm({})
        assert parse_trip_equipment_form(form) == []

    def test_all_empty_rows_skipped(self):
        """Rows with all empty strings are skipped."""
        form = DummyForm({
            'eq_id[]': ['', ''],
            'eq_qty[]': ['', ''],
            'eq_min[]': ['', ''],
        })
        assert parse_trip_equipment_form(form) == []

    def test_partial_empty_row_with_id_only_requires_minutes(self):
        """Row with eq_id but no minutes raises ValueError."""
        form = DummyForm({
            'eq_id[]': ['1'],
            'eq_qty[]': [''],
            'eq_min[]': [''],
        })
        with pytest.raises(ValueError, match='czas'):
            parse_trip_equipment_form(form)

    def test_invalid_equipment_id(self):
        """Non-numeric eq_id raises ValueError."""
        form = DummyForm({
            'eq_id[]': ['abc'],
            'eq_qty[]': ['1'],
            'eq_min[]': ['10'],
        })
        with pytest.raises(ValueError, match='sprzęt'):
            parse_trip_equipment_form(form)

    def test_negative_equipment_id(self):
        """Negative eq_id raises ValueError."""
        form = DummyForm({
            'eq_id[]': ['-1'],
            'eq_qty[]': ['1'],
            'eq_min[]': ['10'],
        })
        with pytest.raises(ValueError, match='sprzęt'):
            parse_trip_equipment_form(form)

    def test_zero_equipment_id(self):
        """Zero eq_id raises ValueError."""
        form = DummyForm({
            'eq_id[]': ['0'],
            'eq_qty[]': ['1'],
            'eq_min[]': ['10'],
        })
        with pytest.raises(ValueError, match='sprzęt'):
            parse_trip_equipment_form(form)

    def test_negative_minutes(self):
        """Negative minutes raises ValueError."""
        form = DummyForm({
            'eq_id[]': ['1'],
            'eq_qty[]': ['1'],
            'eq_min[]': ['-5'],
        })
        with pytest.raises(ValueError, match='większy od 0'):
            parse_trip_equipment_form(form)

    def test_zero_minutes(self):
        """Zero minutes raises ValueError."""
        form = DummyForm({
            'eq_id[]': ['1'],
            'eq_qty[]': ['1'],
            'eq_min[]': ['0'],
        })
        with pytest.raises(ValueError, match='większy od 0'):
            parse_trip_equipment_form(form)

    def test_non_integer_minutes(self):
        """Float-like minutes raises ValueError."""
        form = DummyForm({
            'eq_id[]': ['1'],
            'eq_qty[]': ['1'],
            'eq_min[]': ['10.5'],
        })
        with pytest.raises(ValueError, match='liczbą całkowitą'):
            parse_trip_equipment_form(form)

    def test_negative_quantity(self):
        """Negative quantity raises ValueError."""
        form = DummyForm({
            'eq_id[]': ['1'],
            'eq_qty[]': ['-1'],
            'eq_min[]': ['10'],
        })
        with pytest.raises(ValueError, match='większa od 0'):
            parse_trip_equipment_form(form)

    def test_zero_quantity(self):
        """Zero quantity raises ValueError."""
        form = DummyForm({
            'eq_id[]': ['1'],
            'eq_qty[]': ['0'],
            'eq_min[]': ['10'],
        })
        with pytest.raises(ValueError, match='większa od 0'):
            parse_trip_equipment_form(form)

    def test_non_integer_quantity(self):
        """Non-integer quantity raises ValueError."""
        form = DummyForm({
            'eq_id[]': ['1'],
            'eq_qty[]': ['abc'],
            'eq_min[]': ['10'],
        })
        with pytest.raises(ValueError, match='liczbą całkowitą'):
            parse_trip_equipment_form(form)

    def test_default_quantity_is_one(self):
        """Empty quantity defaults to 1."""
        form = DummyForm({
            'eq_id[]': ['1'],
            'eq_qty[]': [''],
            'eq_min[]': ['10'],
        })
        result = parse_trip_equipment_form(form)
        assert len(result) == 1
        assert result[0]['quantity_used'] == 1

    def test_multiple_valid_rows(self):
        """Multiple valid equipment rows are parsed correctly."""
        form = DummyForm({
            'eq_id[]': ['1', '2', '3'],
            'eq_qty[]': ['2', '1', '5'],
            'eq_min[]': ['30', '15', '60'],
        })
        result = parse_trip_equipment_form(form)
        assert len(result) == 3
        assert result[0] == {'equipment_id': 1, 'quantity_used': 2, 'minutes_used': 30}
        assert result[1] == {'equipment_id': 2, 'quantity_used': 1, 'minutes_used': 15}
        assert result[2] == {'equipment_id': 3, 'quantity_used': 5, 'minutes_used': 60}

    def test_mismatched_array_lengths(self):
        """Arrays of different lengths — shorter arrays get empty string defaults."""
        form = DummyForm({
            'eq_id[]': ['1', '2'],
            'eq_qty[]': ['1'],
            'eq_min[]': ['10', '20'],
        })
        result = parse_trip_equipment_form(form)
        assert len(result) == 2
        # Second row has empty qty, defaults to 1
        assert result[1]['quantity_used'] == 1
