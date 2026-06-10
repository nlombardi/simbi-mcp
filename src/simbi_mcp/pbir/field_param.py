"""Field-parameter calculated-table TMDL builder.

A field parameter is a calc table of (label, field, order) rows where the field
is a NAMEOF([measure]) reference. The ParameterMetadata extended property on the
`<Name> Fields` column flags the table as a parameter so Power BI renders a
measure switcher. Structure verified against two Power BI-generated samples:
resources/PowerBI_Files/Starter Report/.../tables/Parameter.tmdl and
.../Revenue Widget/.../tables/prm_measures.tmdl.
"""
from __future__ import annotations

import uuid

from simbi_mcp.types import FieldParameter


def build_field_param_tmdl(
    fp: FieldParameter, measure_tables: dict[str, str] | None = None
) -> str:
    n = fp.name

    def _nameof(m: str) -> str:
        tbl = (measure_tables or {}).get(m)
        return f"NAMEOF('{tbl}'[{m}])" if tbl else f"NAMEOF([{m}])"

    rows = ",\n".join(
        f'\t\t\t\t("{m}", {_nameof(m)}, {i})' for i, m in enumerate(fp.measures)
    )

    def tag() -> str:
        return str(uuid.uuid4())

    return f"""table {n}
\tlineageTag: {tag()}

\tcolumn {n}
\t\tlineageTag: {tag()}
\t\tsummarizeBy: none
\t\tsourceColumn: [Value1]
\t\tsortByColumn: '{n} Order'

\t\trelatedColumnDetails
\t\t\tgroupByColumn: '{n} Fields'

\t\tannotation SummarizationSetBy = Automatic

\tcolumn '{n} Fields'
\t\tisHidden
\t\tlineageTag: {tag()}
\t\tsummarizeBy: none
\t\tsourceColumn: [Value2]
\t\tsortByColumn: '{n} Order'

\t\textendedProperty ParameterMetadata =
\t\t\t\t{{
\t\t\t\t  "version": 3,
\t\t\t\t  "kind": 2
\t\t\t\t}}

\t\tannotation SummarizationSetBy = Automatic

\tcolumn '{n} Order'
\t\tisHidden
\t\tformatString: 0
\t\tlineageTag: {tag()}
\t\tsummarizeBy: sum
\t\tsourceColumn: [Value3]

\t\tannotation SummarizationSetBy = Automatic

\tpartition {n} = calculated
\t\tmode: import
\t\tsource =
\t\t\t\t{{
{rows}
\t\t\t\t}}

\tannotation PBI_Id = {uuid.uuid4().hex}
"""
