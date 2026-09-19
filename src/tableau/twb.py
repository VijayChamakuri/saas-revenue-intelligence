"""Generate Tableau workbook (.twb/.twbx) XML from a declarative spec.

The workbook reads aggregated CSV extracts through Tableau's text connector. Everything a viewer sees
is defined here in code, so the workbook can be rebuilt and diffed like any other generated artifact.
"""

from __future__ import annotations

import hashlib
import uuid
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

import pandas as pd

TYPE_SUFFIX = {"nominal": "nk", "ordinal": "ok", "quantitative": "qk"}
DERIVATION_PREFIX = {"None": "none", "Sum": "sum", "Avg": "avg", "Min": "min", "Max": "max",
                     "Month-Trunc": "tmn", "Year": "yr", "User": "usr", "Attribute": "attr",
                     "CountD": "ctd", "Count": "cnt"}


def _id(*parts: str) -> str:
    return hashlib.sha1("|".join(parts).encode()).hexdigest()[:28]


def _uuid(*parts: str) -> str:
    return "{" + str(uuid.UUID(hashlib.md5("|".join(parts).encode()).hexdigest())).upper() + "}"


def a(value: object) -> str:
    return quoteattr(str(value))


@dataclass
class Column:
    name: str
    datatype: str  # string, integer, real, date, boolean
    role: str = ""
    type: str = ""
    caption: str | None = None
    fmt: str | None = None
    formula: str | None = None  # calculated field
    hidden: bool = False

    def __post_init__(self) -> None:
        numeric = self.datatype in ("integer", "real")
        if not self.role:
            self.role = "measure" if numeric else "dimension"
        if not self.type:
            self.type = "quantitative" if self.role == "measure" else ("ordinal" if self.datatype == "date" else "nominal")

    def xml(self) -> str:
        attrs = []
        if self.caption:
            attrs.append(f"caption={a(self.caption)}")
        attrs.append(f"datatype={a(self.datatype)}")
        if self.fmt:
            attrs.append(f"default-format={a(self.fmt)}")
        if self.hidden:
            attrs.append("hidden='true'")
        attrs += [f"name={a('[' + self.name + ']')}", f"role={a(self.role)}", f"type={a(self.type)}"]
        head = "<column " + " ".join(attrs)
        if self.formula is None:
            return head + " />"
        return head + f"><calculation class='tableau' formula={a(self.formula)} /></column>"


@dataclass
class Parameter:
    name: str
    caption: str
    datatype: str
    value: object
    min: object | None = None
    max: object | None = None
    step: object | None = None
    members: list[object] | None = None
    fmt: str | None = None

    def literal(self, v: object) -> str:
        return f'"{v}"' if self.datatype == "string" else str(v)

    def xml(self) -> str:
        domain = "list" if self.members else "range"
        fmt = f" default-format={a(self.fmt)}" if self.fmt else ""
        head = (f"<column caption={a(self.caption)} datatype={a(self.datatype)}{fmt} name={a('[' + self.name + ']')} "
                f"param-domain-type={a(domain)} role='measure' type={a('nominal' if self.datatype == 'string' else 'quantitative')} "
                f"value={a(self.literal(self.value))}>")
        body = f"<calculation class='tableau' formula={a(self.literal(self.value))} />"
        if self.members:
            body += "<members>" + "".join(f"<member value={a(self.literal(m))} />" for m in self.members) + "</members>"
        else:
            body += f"<range granularity={a(self.step)} max={a(self.max)} min={a(self.min)} />"
        return head + body + "</column>"


@dataclass
class Datasource:
    key: str
    caption: str
    directory: str
    filename: str
    columns: list[Column]
    calcs: list[Column] = field(default_factory=list)
    color_maps: dict[str, dict[str, str]] = field(default_factory=dict)  # field -> value -> hex

    @property
    def name(self) -> str:
        return "federated." + _id("ds", self.key)

    @property
    def conn(self) -> str:
        return "hyper." + _id("conn", self.key)

    @property
    def hyper_path(self) -> str:
        return f"{self.directory}/{self.filename}"

    def col(self, name: str) -> Column:
        for c in self.columns + self.calcs:
            if c.name == name:
                return c
        raise KeyError(f"{self.key}: no column {name}")

    def xml(self) -> str:
        meta = "".join(
            f"<metadata-record class='column'><remote-name>{escape(c.name)}</remote-name>"
            f"<remote-type>{ {'string': 129, 'integer': 20, 'real': 5, 'date': 133, 'boolean': 11}[c.datatype] }</remote-type>"
            f"<local-name>[{escape(c.name)}]</local-name><parent-name>[Extract]</parent-name><remote-alias>{escape(c.name)}</remote-alias>"
            f"<ordinal>{i}</ordinal><local-type>{c.datatype}</local-type>"
            f"<aggregation>{'Sum' if c.role == 'measure' else ('Year' if c.datatype == 'date' else 'Count')}</aggregation>"
            f"<contains-null>true</contains-null></metadata-record>" for i, c in enumerate(self.columns))
        default = {c.name: Column(c.name, c.datatype) for c in self.columns}
        cols = "".join(c.xml() for c in self.columns
                       if c.caption or c.fmt or c.hidden or c.role != default[c.name].role or c.type != default[c.name].type)
        cols += "".join(c.xml() for c in self.calcs)
        return (f"<datasource caption={a(self.caption)} inline='true' name={a(self.name)} version='18.1'>"
                f"<connection class='federated'><named-connections><named-connection caption={a(self.caption)} name={a(self.conn)}>"
                f"<connection authentication='auth-none' author-locale='en_US' class='hyper' dbname={a(self.hyper_path)} "
                f"default-settings='yes' port='' sslmode='' username='tableau_internal_user' />"
                f"</named-connection></named-connections>"
                f"<relation connection={a(self.conn)} name='Extract' table='[Extract].[Extract]' type='table' />"
                f"<metadata-records>{meta}</metadata-records></connection>"
                f"<aliases enabled='yes' />{cols}{self._palette()}</datasource>")

    def _palette(self) -> str:
        if not self.color_maps:
            return ""
        rules = []
        for fieldname, mapping in sorted(self.color_maps.items()):
            c = self.col(fieldname)
            kind = "nk" if c.type == "nominal" else "ok"
            maps = "".join(
                f"<map to={a(color)}><bucket>{escape(value if c.datatype == 'boolean' else chr(34) + value + chr(34))}</bucket></map>"
                for value, color in mapping.items())
            rules.append(f"<encoding attr='color' field={a(f'[none:{fieldname}:{kind}]')} type='palette'>{maps}</encoding>")
        return "<style><style-rule element='mark'>" + "".join(rules) + "</style-rule></style>"

    def write_hyper(self, csv: Path, out: Path) -> None:
        """Build the .hyper extract from the governed CSV with the Tableau Hyper API."""
        from tableauhyperapi import (
            Connection,
            CreateMode,
            HyperProcess,
            Inserter,
            SqlType,
            TableDefinition,
            TableName,
            Telemetry,
        )
        types = {"string": SqlType.text(), "integer": SqlType.big_int(), "real": SqlType.double(),
                 "date": SqlType.date(), "boolean": SqlType.bool()}
        frame = pd.read_csv(csv)
        table = TableDefinition(TableName("Extract", "Extract"),
                                [TableDefinition.Column(c.name, types[c.datatype]) for c in self.columns])
        out.parent.mkdir(parents=True, exist_ok=True)
        rows = []
        for rec in frame[[c.name for c in self.columns]].itertuples(index=False):
            row: list[object] = []
            for c, v in zip(self.columns, rec, strict=True):
                if v is None or (not isinstance(v, str) and pd.isna(v)):
                    row.append(None)
                elif c.datatype == "string":
                    row.append(str(v))
                elif c.datatype == "integer":
                    row.append(int(v))
                elif c.datatype == "real":
                    row.append(float(v))
                elif c.datatype == "boolean":
                    row.append(bool(v) if not isinstance(v, str) else v.strip().lower() == "true")
                else:
                    row.append(pd.Timestamp(v).date())
            rows.append(row)
        with HyperProcess(Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU, parameters={"log_config": ""}) as hp:
            with Connection(hp.endpoint, str(out), CreateMode.CREATE_AND_REPLACE) as con:
                con.catalog.create_schema("Extract")
                con.catalog.create_table(table)
                with Inserter(con, table) as ins:
                    ins.add_rows(rows)
                    ins.execute()


@dataclass
class Pill:
    """A field on a shelf: column name plus derivation (None, Sum, Avg, Month-Trunc, User, Attribute...)."""
    field: str
    derivation: str = "None"
    type: str | None = None  # override nominal/ordinal/quantitative for the instance


@dataclass
class Filter:
    field: str
    members: list[str] | None = None  # categorical include-list; None means "all" (a shown quick filter)
    derivation: str = "None"
    group: int | None = None  # shared filter group across worksheets
    range: tuple[object, object] | None = None


@dataclass
class Sheet:
    name: str
    ds: Datasource
    mark: str  # Bar, Line, Text, Square, Circle, Area, Automatic
    rows: list[Pill] = field(default_factory=list)
    cols: list[Pill] = field(default_factory=list)
    color: Pill | None = None
    size: Pill | None = None
    text: list[Pill] = field(default_factory=list)
    label: list[Pill] = field(default_factory=list)
    tooltip: list[Pill] = field(default_factory=list)
    detail: list[Pill] = field(default_factory=list)
    filters: list[Filter] = field(default_factory=list)
    sort: tuple[Pill, Pill, str] | None = None  # (dimension, by measure, ASC/DESC)
    title: str | None = None
    tooltip_text: str | None = None
    label_text: str | None = None
    fit: str = "entire-view"
    palette: str | None = None
    color_map: dict[str, str] | None = None
    mark_color: str | None = None
    font_size: int | None = None


def _inst(ds: Datasource, p: Pill) -> tuple[str, Column, str, str]:
    c = ds.col(p.field)
    deriv = p.derivation
    if c.formula is not None and deriv == "None" and c.role == "measure":
        deriv = "User"
    itype = p.type or ("quantitative" if deriv in ("Sum", "Avg", "Min", "Max", "User", "Count", "CountD", "Month-Trunc") else c.type)
    if deriv == "Attribute":
        itype = p.type or "nominal"
    name = f"[{DERIVATION_PREFIX[deriv]}:{c.name}:{TYPE_SUFFIX[itype]}]"
    return name, c, deriv, itype


class Workbook:
    def __init__(self, title: str, params: list[Parameter] | None = None) -> None:
        self.title = title
        self.datasources: list[Datasource] = []
        self.params = params or []
        self.sheets: list[Sheet] = []
        self.dashboards: list[Dashboard] = []
        self.actions: list[FilterAction] = []

    def ref(self, ds: Datasource, p: Pill) -> str:
        return f"[{ds.name}].{_inst(ds, p)[0]}"

    def _deps(self, ds: Datasource, pills: list[Pill], filters: list[Filter]) -> str:
        used: dict[str, Column] = {}
        insts: dict[str, str] = {}
        extra_params = False
        for p in pills + [Pill(f.field, f.derivation) for f in filters]:
            name, c, deriv, itype = _inst(ds, p)
            used[c.name] = c
            if c.formula:
                for other in ds.columns + ds.calcs:
                    if f"[{other.name}]" in c.formula:
                        used.setdefault(other.name, other)
                        if other.formula:
                            for o2 in ds.columns + ds.calcs:
                                if f"[{o2.name}]" in other.formula:
                                    used.setdefault(o2.name, o2)
                extra_params = extra_params or "[Parameters]" in c.formula
            insts[name] = f"<column-instance column={a('[' + c.name + ']')} derivation={a(deriv)} name={a(name)} pivot='key' type={a(itype)} />"
        body = "".join(c.xml() for c in sorted(used.values(), key=lambda c: c.name)) + "".join(insts[k] for k in sorted(insts))
        out = f"<datasource-dependencies datasource={a(ds.name)}>{body}</datasource-dependencies>"
        if extra_params and self.params:
            out = ("<datasource-dependencies datasource='Parameters'>" + "".join(p.xml() for p in self.params)
                   + "</datasource-dependencies>") + out
        return out

    def _filter_xml(self, ds: Datasource, f: Filter) -> str:
        ref = self.ref(ds, Pill(f.field, f.derivation))
        group = f" filter-group='{f.group}'" if f.group is not None else ""
        if f.range is not None:
            return (f"<filter class='quantitative' column={a(ref)}{group} included-values='in-range'>"
                    f"<min>{escape(str(f.range[0]))}</min><max>{escape(str(f.range[1]))}</max></filter>")
        level = _inst(ds, Pill(f.field, f.derivation))[0]
        if not f.members:
            inner = f"<groupfilter function='level-members' level={a(level)} user:ui-enumeration='all' user:ui-marker='enumerate' />"
        elif len(f.members) == 1:
            inner = (f"<groupfilter function='member' level={a(level)} member={a(self._lit(ds, f.field, f.members[0]))} "
                     f"user:ui-domain='database' user:ui-enumeration='inclusive' user:ui-marker='enumerate' />")
        else:
            inner = ("<groupfilter function='union' user:ui-domain='database' user:ui-enumeration='inclusive' user:ui-marker='enumerate'>"
                     + "".join(f"<groupfilter function='member' level={a(level)} member={a(self._lit(ds, f.field, m))} />" for m in f.members)
                     + "</groupfilter>")
        return f"<filter class='categorical' column={a(ref)}{group}>{inner}</filter>"

    @staticmethod
    def _lit(ds: Datasource, fieldname: str, value: object) -> str:
        c = ds.col(fieldname)
        if c.datatype == "string":
            return f'"{value}"'
        if c.datatype == "date":
            return f"#{value}#"
        if c.datatype == "boolean":
            return "true" if str(value).lower() == "true" else "false"
        return str(value)

    def _shelf(self, ds: Datasource, pills: list[Pill]) -> str:
        return " / ".join(self.ref(ds, p) for p in pills)

    def sheet_xml(self, s: Sheet) -> str:
        ds = s.ds
        pills = s.rows + s.cols + s.text + s.label + s.tooltip + s.detail + [p for p in (s.color, s.size) if p]
        if s.sort:
            pills += [s.sort[0], s.sort[1]]
        title = s.title if s.title is not None else s.name
        layout = (f"<layout-options><title><formatted-text><run bold='true' fontsize='11'>{escape(title)}</run></formatted-text></title></layout-options>"
                  if title else "")
        filters = "".join(self._filter_xml(ds, f) for f in s.filters)
        sort = ""
        if s.sort:
            sort = f"<computed-sort column={a(self.ref(ds, s.sort[0]))} direction={a(s.sort[2])} using={a(self.ref(ds, s.sort[1]))} />"
        slices = ""
        cat = [f for f in s.filters]
        if cat:
            slices = "<slices>" + "".join(f"<column>{escape(self.ref(ds, Pill(f.field, f.derivation)))}</column>" for f in cat) + "</slices>"
        enc = []
        if s.color:
            enc.append(f"<color column={a(self.ref(ds, s.color))} />")
        if s.size:
            enc.append(f"<size column={a(self.ref(ds, s.size))} />")
        for p in s.text:
            enc.append(f"<text column={a(self.ref(ds, p))} />")
        for p in s.label:
            enc.append(f"<text column={a(self.ref(ds, p))} />")
        for p in s.detail:
            enc.append(f"<lod column={a(self.ref(ds, p))} />")
        for p in s.tooltip:
            enc.append(f"<tooltip column={a(self.ref(ds, p))} />")
        encodings = "<encodings>" + "".join(enc) + "</encodings>" if enc else ""
        style_rules = []
        mark_fmt = []
        if s.label or s.label_text:
            mark_fmt.append("<format attr='mark-labels-show' value='true' />")
        if s.mark_color and s.mark != "Text":
            mark_fmt.append(f"<format attr='mark-color' value={a(s.mark_color)} />")
        if s.mark == "Text":
            style_rules.append("<style-rule element='worksheet'><format attr='display-field-labels' scope='cols' value='false' /></style-rule>")
        pane_style = ("<style><style-rule element='mark'>" + "".join(mark_fmt) + "</style-rule></style>") if mark_fmt else ""
        custom_tt = ""
        if s.tooltip_text:
            custom_tt = f"<customized-tooltip><formatted-text><run>{escape(s.tooltip_text)}</run></formatted-text></customized-tooltip>"
        custom_label = ""
        if s.label_text:
            first = (s.text or s.label)[0]
            value = f"<{self.ref(ds, first)}>"
            text = s.label_text.replace("{v}", value)
            custom_label = (f"<customized-label><formatted-text><run bold='true' fontcolor={a(s.mark_color or '#1f3a5f')} "
                            f"fontsize='{s.font_size or 10}'>{escape(text)}</run></formatted-text></customized-label>")
        encoding_style = ""
        if s.color and s.color_map:
            ds.color_maps[s.color.field] = dict(s.color_map)
        style = "<style>" + "".join(style_rules) + encoding_style + "</style>"
        pane = (f"<panes><pane selection-relaxation-option='selection-relaxation-allow'><view><breakdown value='auto' /></view>"
                f"<mark class={a(s.mark)} />{encodings}{custom_tt}{custom_label}{pane_style}</pane></panes>")
        rows = f"<rows>{escape(self._shelf(ds, s.rows))}</rows>" if s.rows else "<rows />"
        cols = f"<cols>{escape(self._shelf(ds, s.cols))}</cols>" if s.cols else "<cols />"
        return (f"<worksheet name={a(s.name)}>{layout}<table><view><datasources><datasource caption={a(ds.caption)} name={a(ds.name)} />"
                f"{'<datasource name=' + a('Parameters') + ' />' if self.params else ''}</datasources>"
                f"{self._deps(ds, pills, s.filters)}{filters}{sort}{slices}<aggregation value='true' /></view>{style}{pane}{rows}{cols}</table>"
                f"<simple-id uuid={a(_uuid('ws', s.name))} /></worksheet>")

    def xml(self) -> str:
        params = ""
        if self.params:
            params = "<datasource hasconnection='false' inline='true' name='Parameters' version='18.1'><aliases enabled='yes' />" + "".join(p.xml() for p in self.params) + "</datasource>"
        worksheets = "<worksheets>" + "".join(self.sheet_xml(s) for s in self.sheets) + "</worksheets>"
        datasources = "<datasources>" + params + "".join(d.xml() for d in self.datasources) + "</datasources>"
        dashboards = "<dashboards>" + "".join(d.xml(self) for d in self.dashboards) + "</dashboards>" if self.dashboards else ""
        actions = "<actions>" + "".join(x.xml(self) for x in self.actions) + "</actions>" if self.actions else ""
        windows = ["<windows source-height='30'>"]
        for d in self.dashboards:
            windows.append(f"<window class='dashboard' name={a(d.name)}{' maximized=' + a('true') if d is self.dashboards[0] else ''}><viewpoints>"
                           + "".join(f"<viewpoint name={a(n)}><zoom type={a(self._sheet(n).fit)} /></viewpoint>" for n in d.sheet_names())
                           + f"</viewpoints><active id='-1' /><simple-id uuid={a(_uuid('win', d.name))} /></window>")
        in_dash = {n for d in self.dashboards for n in d.sheet_names()}
        for s in self.sheets:
            hidden = " hidden='true'" if s.name in in_dash else ""
            windows.append(f"<window class='worksheet'{hidden} name={a(s.name)}><cards><edge name='left'><strip size='160'><card type='pages' /><card type='filters' /><card type='marks' /></strip></edge>"
                           f"<edge name='top'><strip size='2147483647'><card type='columns' /></strip><strip size='2147483647'><card type='rows' /></strip><strip size='31'><card type='title' /></strip></edge></cards>"
                           f"<viewpoint><zoom type={a(s.fit)} /></viewpoint><simple-id uuid={a(_uuid('wsw', s.name))} /></window>")
        windows.append("</windows>")
        return ("<?xml version='1.0' encoding='utf-8' ?>\n"
                "<workbook source-build='2026.2.2 (20262.26.0819.2015)' source-platform='mac' version='18.1' "
                "xmlns:user='http://www.tableausoftware.com/xml/user'>"
                "<document-format-change-manifest><SheetIdentifierTracking /><SortTagCleanup /><WindowsPersistSimpleIdentifiers />"
                "<WorksheetBackgroundTransparency /><ZoneFriendlyName /></document-format-change-manifest>"
                "<preferences><preference name='ui.encoding.shelf.height' value='24' /><preference name='ui.shelf.height' value='26' /></preferences>"
                f"{datasources}{actions}{worksheets}{dashboards}{''.join(windows)}</workbook>\n")

    def _sheet(self, name: str) -> Sheet:
        for s in self.sheets:
            if s.name == name:
                return s
        raise KeyError(name)

    def save(self, twb: Path) -> Path:
        twb.write_text(self.xml(), encoding="utf-8")
        return twb

    def package(self, twbx: Path, csvs: dict[str, Path], workdir: Path) -> Path:
        """Write a .twbx: the workbook plus a Hyper extract for every datasource, built from its CSV."""
        with zipfile.ZipFile(twbx, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr(twbx.with_suffix(".twb").name, self.xml())
            for ds in self.datasources:
                hyper = workdir / ds.hyper_path
                ds.write_hyper(csvs[ds.key], hyper)
                z.write(hyper, ds.hyper_path)
        return twbx


# ---- dashboards -------------------------------------------------------------------------------------

@dataclass
class Text:
    text: str
    size: int = 10
    bold: bool = False
    color: str = "#333333"
    runs: list[tuple[str, dict[str, object]]] | None = None


@dataclass
class View:
    sheet: str


@dataclass
class QuickFilter:
    sheet: str
    field: str
    derivation: str = "None"
    mode: str = "dropdown"  # dropdown, checkdropdown, radiolist, slider


@dataclass
class Legend:
    sheet: str
    field: str


@dataclass
class ParamControl:
    param: str
    mode: str = "slider"  # slider, compact (dropdown), list, type_in
    caption: str | None = None


@dataclass
class Box:
    """A tiled container. direction 'horz' or 'vert'; weights split the space among children."""
    direction: str
    children: list[object]
    weights: list[float] | None = None
    background: str | None = None


@dataclass
class Dashboard:
    name: str
    width: int
    height: int
    root: Box
    title: str | None = None

    def sheet_names(self) -> list[str]:
        out: list[str] = []

        def walk(n: object) -> None:
            if isinstance(n, View):
                out.append(n.sheet)
            elif isinstance(n, Box):
                for c in n.children:
                    walk(c)
        walk(self.root)
        return out

    def xml(self, wb: Workbook) -> str:
        counter = [2]
        deps: dict[str, set[str]] = {}

        def nid() -> int:
            counter[0] += 1
            return counter[0]

        def zone(n: object, x: int, y: int, w: int, h: int) -> str:
            geo = f"h='{h}' id='{nid()}' w='{w}' x='{x}' y='{y}'"
            if isinstance(n, Box):
                weights = n.weights or [1.0] * len(n.children)
                total = sum(weights)
                parts = []
                pos = x if n.direction == "horz" else y
                span = w if n.direction == "horz" else h
                for i, (c, wt) in enumerate(zip(n.children, weights, strict=True)):
                    size = span - (pos - (x if n.direction == "horz" else y)) if i == len(n.children) - 1 else int(round(span * wt / total))
                    if n.direction == "horz":
                        parts.append(zone(c, pos, y, size, h))
                    else:
                        parts.append(zone(c, x, pos, w, size))
                    pos += size
                bg = (f"<zone-style><format attr='background-color' value={a(n.background)} /></zone-style>" if n.background else "")
                return f"<zone {geo} param={a(n.direction)} type-v2='layout-flow'>{''.join(parts)}{bg}</zone>"
            style = "<zone-style><format attr='border-style' value='none' /><format attr='margin' value='4' /></zone-style>"
            if isinstance(n, View):
                return f"<zone {geo} name={a(n.sheet)}>{style}</zone>"
            if isinstance(n, Text):
                runs = n.runs or [(n.text, {"size": n.size, "bold": n.bold, "color": n.color})]
                body = "".join(
                    f"<run{' bold=' + a('true') if o.get('bold') else ''} fontcolor={a(o.get('color', '#333333'))} fontsize={a(o.get('size', 10))}>{escape(t)}</run>"
                    for t, o in runs)
                return f"<zone {geo} type-v2='text'><formatted-text>{body}</formatted-text>{style}</zone>"
            if isinstance(n, QuickFilter):
                s = wb._sheet(n.sheet)
                ref = wb.ref(s.ds, Pill(n.field, n.derivation))
                deps.setdefault(s.ds.name, set()).add(n.field)
                return f"<zone {geo} mode={a(n.mode)} name={a(n.sheet)} param={a(ref)} type-v2='filter'>{style}</zone>"
            if isinstance(n, Legend):
                sh = wb._sheet(n.sheet)
                ref = wb.ref(sh.ds, Pill(n.field))
                return (f"<zone {geo} name={a(n.sheet)} pane-specification-id='0' param={a(ref)} "
                        f"show-title='false' type-v2='color'>{style}</zone>")
            if isinstance(n, ParamControl):
                title = (f"<formatted-text><run fontcolor='#555555' fontsize='10'>{escape(n.caption)}</run></formatted-text>"
                         if n.caption else "")
                custom = " custom-title='true'" if n.caption else ""
                return (f"<zone{custom} {geo} mode={a(n.mode)} param={a('[Parameters].[' + n.param + ']')} "
                        f"type-v2='paramctrl'>{title}{style}</zone>")
            raise TypeError(n)

        inner = zone(self.root, 0, 0, 100000, 100000)
        size = f"<size maxheight='{self.height}' maxwidth='{self.width}' minheight='{self.height}' minwidth='{self.width}' />"
        title = self.title or self.name
        return (f"<dashboard name={a(self.name)}><layout-options><title><formatted-text><run>{escape(title)}</run></formatted-text></title></layout-options>"
                f"<style />{size}<zones><zone h='100000' id='2' type-v2='layout-basic' w='100000' x='0' y='0'>{inner}</zone></zones>"
                f"<simple-id uuid={a(_uuid('dash', self.name))} /></dashboard>")


@dataclass
class FilterAction:
    """Selecting marks on `source` filters `targets` on the same dashboard by `field` (a drill-through)."""
    name: str
    dashboard: str
    source: str
    targets: list[str]
    field: str

    def xml(self, wb: Workbook) -> str:
        from urllib.parse import quote

        src = wb._sheet(self.source)
        dash = next(d for d in wb.dashboards if d.name == self.dashboard)
        exclude = [n for n in dash.sheet_names() if n not in self.targets]
        column = quote(f"[{src.ds.name}].[{self.field}]", safe="")
        expression = f"tsl:{quote(self.dashboard, safe='')}?{column}~s0=<[{self.field}]~na>"
        ident = "[Action_" + _id("act", self.name)[:32].upper() + "]"
        return (f"<action caption={a(self.name)} name={a(ident)}><activation auto-clear='true' type='on-select' />"
                f"<source dashboard={a(self.dashboard)} type='sheet' worksheet={a(self.source)} />"
                f"<link caption={a(self.name)} delimiter=',' escape='\\' expression={a(expression)} include-null='true' "
                f"multi-select='true' url-escape='true' />"
                f"<command command='tsc:tsl-filter'><param name='exclude' value={a(','.join(exclude))} />"
                f"<param name='target' value={a(self.dashboard)} /></command></action>")


def columns_from_csv(path: Path, overrides: dict[str, dict[str, object]] | None = None) -> list[Column]:
    """Infer Tableau column types from a CSV written by the pipeline."""
    frame = pd.read_csv(path, nrows=5000)
    out = []
    for name, dtype in frame.dtypes.items():
        o = (overrides or {}).get(str(name), {})
        if "datatype" in o:
            dt = str(o["datatype"])
        elif pd.api.types.is_bool_dtype(dtype):
            dt = "boolean"
        elif pd.api.types.is_integer_dtype(dtype):
            dt = "integer"
        elif pd.api.types.is_float_dtype(dtype):
            dt = "real"
        else:
            dt = "string"
        kwargs = {k: v for k, v in o.items() if k != "datatype"}
        out.append(Column(str(name), dt, **kwargs))  # type: ignore[arg-type]
    return out
