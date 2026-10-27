"""Test scalar and composed pandas conversion operations."""

from datetime import time

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from engine.core.operation_registry import execute_operation
def execute(operation: str, frame: pd.DataFrame, **parameters) -> pd.DataFrame:
	return execute_operation(operation, [frame], **parameters)


@pytest.mark.parametrize(
	"operation, source, expected",
	[
		("date", ["2024-02-29 12:34:56"], [pd.Timestamp("2024-02-29")]),
		("datetime", ["2024-02-29 12:34:56"], [pd.Timestamp("2024-02-29 12:34:56")]),
		("float", ["1.5", "2"], [1.5, 2.0]),
		("int", ["1", "2"], [1, 2]),
		("str", [1, None], ["1.0", pd.NA]),
	],
)
def test_conversions_create_columns_and_preserve_sources(operation, source, expected) -> None:
	frame = pd.DataFrame({"value": source})
	before = frame.copy(deep=True)
	result = execute(
		operation, frame, column="value",
		create_new_column=True, new_column_name="converted",
	)

	assert result["converted"].tolist() == expected
	assert_frame_equal(result[["value"]], before)


@pytest.mark.parametrize(
	"day, month, year, expected",
	[
		(31, 4, 2024, pd.Timestamp("2024-04-30")),
		(29, 2, 2024, pd.Timestamp("2024-02-29")),
		(29, 2, 2023, pd.Timestamp("2023-02-28")),
	],
)
def test_make_date_clamps_day_to_last_valid_date(day, month, year, expected) -> None:
	frame = pd.DataFrame({"day": [day], "month": [month], "year": [year]})

	result = execute(
		"make_date", frame, column_day="day", column_month="month",
		column_year="year", new_column_name="combined_date",
	)

	assert result["combined_date"].iloc[0] == expected
	assert result[["day", "month", "year"]].iloc[0].tolist() == [day, month, year]


def test_make_date_rejects_invalid_components_and_can_replace_day_column() -> None:
	frame = pd.DataFrame({"day": [31, 4], "month": [4, 13], "year": [2024, 2024]})
	with pytest.raises(ValueError, match="month values"):
		execute("make_date", frame, column_day="day", column_month="month", column_year="year")

	result = execute(
		"make_date", frame.iloc[:1], column_day="day", column_month="month",
		column_year="year", create_new_column=False,
	)
	assert result["day"].iloc[0] == pd.Timestamp("2024-04-30")


def test_make_time_and_make_date_time_create_new_columns() -> None:
	frame = pd.DataFrame({
		"day": ["2024-04-30", "2024-05-01"],
		"hour": [8, 23],
		"minute": [5, 59],
		"second": [0, 59],
	})
	with_time = execute(
		"make_time", frame, column_hour="hour", column_minute="minute",
		column_second="second", new_column_name="time_value",
	)
	with_datetime = execute(
		"make_date_time", with_time, column_date="day", column_hour="time_value",
		new_column_name="timestamp",
	)

	assert with_time["time_value"].tolist() == [time(8, 5), time(23, 59, 59)]
	assert with_datetime["timestamp"].tolist() == [
		pd.Timestamp("2024-04-30 08:05:00"),
		pd.Timestamp("2024-05-01 23:59:59"),
	]
	assert with_datetime["day"].tolist() == ["2024-04-30", "2024-05-01"]
	assert with_datetime["time_value"].tolist() == with_time["time_value"].tolist()


def test_conversion_rejects_the_legacy_replace_parameter() -> None:
	with pytest.raises(TypeError, match="replace"):
		execute(
			"float", pd.DataFrame({"value": ["1.5"]}),
			column="value", replace=False, new_column_name="converted",
		)
