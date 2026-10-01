"""Запис у Google Sheets без мережі: вибір рядка для нових записів."""
import pytest

from sheets_client import next_free_row, write_rows


class FakeWorksheet:
    def __init__(self, col_a, row_count=1000):
        self._col_a = col_a
        self.row_count = row_count
        self.updates = []
        self.added = 0

    def col_values(self, col):
        assert col == 1
        return self._col_a

    def add_rows(self, n):
        self.added += n
        self.row_count += n

    def update(self, range_name, values, value_input_option):
        assert value_input_option == "RAW"
        self.updates.append((range_name, values))


@pytest.mark.parametrize("col_a,first,expected", [
    (["Дата додавання"], 2, 2),                        # лише заголовок
    (["Дата додавання"], 3, 3),                        # заголовок + порожній рядок фільтрів
    (["Дата додавання", ""], 3, 3),
    (["Дата додавання", "фільтр"], 3, 3),              # фільтр має значення в A
    (["Дата додавання", "", "2026-10-01"], 3, 4),      # вже є дані з 3-го рядка
    (["Дата додавання", "2026-10-01", "2026-10-02"], 2, 4),
    ([], 2, 2),                                        # порожній аркуш
    ([], None, 2),
])
def test_next_free_row(col_a, first, expected):
    assert next_free_row(col_a, first) == expected


def test_write_rows_starts_at_first_data_row_and_never_above():
    ws = FakeWorksheet(["Дата додавання"])
    rows = [["2026-10-01", "Senior React Developer", "Acme", "Djinni", "https://x"]]
    assert write_rows(ws, rows, first_data_row=3) == 3
    assert ws.updates == [("A3", rows)]
    assert ws.added == 0


def test_write_rows_grows_grid_when_needed():
    ws = FakeWorksheet(["h"] + ["x"] * 998, row_count=999)   # заповнено до рядка 999
    rows = [["a"] * 5, ["b"] * 5, ["c"] * 5]
    assert write_rows(ws, rows, first_data_row=2) == 1000
    assert ws.added == 3
    assert ws.updates[0][0] == "A1000"
