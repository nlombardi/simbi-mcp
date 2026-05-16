"""Tests for the TMDL schema reader."""
import pytest

from simbi_mcp.semantic.schema_reader import parse_tmdl_schema

# Representative TMDL string matching what ExportTMDL returns.
# Tabs for indentation, single-quoted measure names with spaces.
SAMPLE_TMDL = """\
/// Sales transactions
table Sales
\tlineageTag: 16af4f8a-dca7-41ce-a164-3ee7ed82e224

\t/// Sum of revenue
\tmeasure 'Total Revenue' = SUM(Sales[Revenue])
\t\tformatString: \\$#,0.00;(\\$#,0.00)
\t\tlineageTag: 774dd9c9-35a7-472f-a45c-0cf11b7dacdc

\tmeasure 'Number of Orders' = COUNTROWS(Sales)
\t\tformatString: #,0

\tcolumn OrderID
\t\tdataType: int64
\t\tsummarizeBy: none
\t\tsourceColumn: OrderID

\tcolumn OrderDate
\t\tdataType: dateTime
\t\tsummarizeBy: none
\t\tsourceColumn: OrderDate

\tcolumn Revenue
\t\tdataType: double
\t\tsummarizeBy: sum
\t\tsourceColumn: Revenue

\tpartition Sales = m
\t\tmode: import
\t\tsource =
\t\t\t\tlet Source = 1
\t\t\t\tin Source
"""


def test_parse_table_names() -> None:
    schema = parse_tmdl_schema(SAMPLE_TMDL)
    assert len(schema.tables) == 1
    assert schema.tables[0].name == "Sales"


def test_parse_column_names() -> None:
    schema = parse_tmdl_schema(SAMPLE_TMDL)
    cols = schema.tables[0].columns
    assert "OrderID" in cols
    assert "OrderDate" in cols
    assert "Revenue" in cols


def test_parse_measures() -> None:
    schema = parse_tmdl_schema(SAMPLE_TMDL)
    assert schema.has_measure("Total Revenue")
    assert schema.has_measure("Number of Orders")


def test_measure_fields() -> None:
    schema = parse_tmdl_schema(SAMPLE_TMDL)
    m = schema.find_measure("Total Revenue")
    assert m.table == "Sales"
    assert m.expression == "SUM(Sales[Revenue])"
    assert m.return_type == "currency"


def test_integer_return_type_inferred() -> None:
    schema = parse_tmdl_schema(SAMPLE_TMDL)
    m = schema.find_measure("Number of Orders")
    assert m.return_type == "integer"


def test_empty_relationships() -> None:
    schema = parse_tmdl_schema(SAMPLE_TMDL)
    assert schema.relationships == []


def test_multi_table_tmdl() -> None:
    tmdl = """\
table Customers
\tcolumn CustomerID
\t\tdataType: int64

table Orders
\tmeasure 'Order Count' = COUNTROWS(Orders)
\t\tformatString: #,0
\tcolumn OrderID
\t\tdataType: int64
"""
    schema = parse_tmdl_schema(tmdl)
    assert len(schema.tables) == 2
    assert any(t.name == "Customers" for t in schema.tables)
    orders_table = next(t for t in schema.tables if t.name == "Orders")
    assert "OrderID" in orders_table.columns
    assert schema.has_measure("Order Count")
    assert schema.find_measure("Order Count").table == "Orders"


def test_raises_on_empty_input() -> None:
    with pytest.raises(ValueError, match="empty"):
        parse_tmdl_schema("")


def test_model_level_ref_tables_ignored() -> None:
    """model.tmdl uses 'ref table Sales' — these should not create phantom tables."""
    tmdl = """\
model Model
\tculture: en-US

ref table Sales

table Sales
\tcolumn Revenue
\t\tdataType: double
"""
    schema = parse_tmdl_schema(tmdl)
    assert len(schema.tables) == 1
    assert schema.tables[0].name == "Sales"
