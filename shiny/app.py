"""Sovereign Prospectus Database -- Shiny for Python.

Shiny port of the Streamlit explorer. Reuses the query layer from
explorer/ and deploys to Posit Connect Cloud.
"""

from __future__ import annotations

import html as html_mod
import os
import re
import sys
from pathlib import Path

# Ensure the repo root is on sys.path so `from explorer.queries import ...`
# works on Posit Connect Cloud.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from explorer.display import (
    GITHUB_URL,
    PROTOTYPE_URL,
    QCRAFT_URL,
    ext_link,
    source_display,
)
from explorer.highlight import highlight_text
from explorer.queries import (
    browse_documents,
    count_documents,
    get_corpus_stats,
    get_document_detail,
    get_filter_options,
    get_markdown,
    get_markdown_size,
    get_max_page,
    get_page_text,
    search_pages_in_document,
)
from shiny import App, Inputs, Outputs, Session, reactive, render, ui

# ── Constants ────────────────────────────────────────────────────────

LOCAL_DB_PATH = Path("data/db/corpus.duckdb")
MARKDOWN_SIZE_LIMIT = 200_000


# ── Database connection ──────────────────────────────────────────────


def _get_connection():
    """Connect to MotherDuck or local DuckDB."""
    import duckdb

    token = os.environ.get("MOTHERDUCK_TOKEN")
    if token:
        return duckdb.connect(
            "md:sovereign_corpus",
            read_only=True,
            config={"motherduck_token": token},
        )
    if LOCAL_DB_PATH.exists():
        return duckdb.connect(str(LOCAL_DB_PATH), read_only=True)
    msg = "No database available. Set MOTHERDUCK_TOKEN or ensure data/db/corpus.duckdb exists."
    raise RuntimeError(msg)


# ── Cached data (loaded once at startup) ─────────────────────────────

_con = _get_connection()
_stats = get_corpus_stats(_con)
_filter_opts = get_filter_options(_con)

_source_choices = {s: source_display(s) for s in _filter_opts["sources"]}
_region_choices = {r: r for r in _filter_opts["regions"]}
_income_choices = {i: i for i in _filter_opts["income_groups"]}
_country_choices = dict(
    sorted(
        {code: name for code, name in _filter_opts["countries"]}.items(),
        key=lambda x: x[1],
    )
)


# ── About content ────────────────────────────────────────────────────


def _about_content():
    """Build the About section content."""
    return ui.div(
        ui.HTML(
            "<p>An open-source corpus of sovereign bond prospectuses collected "
            "from the FCA National Storage Mechanism, SEC EDGAR, "
            "the Sovereign Debt Forum's #PublicDebtIsPublic Dataset, and the "
            "Luxembourg Stock Exchange. Built by "
            + ext_link("https://tealemery.com", "Teal Insights")
            + " with support from "
            + ext_link("https://naturefinance.net", "NatureFinance")
            + ". "
            + ext_link(GITHUB_URL, "GitHub")
            + " | "
            + ext_link(GITHUB_URL + "/blob/main/LICENSE", "MIT License")
            + ".</p>"
        ),
        ui.HTML(
            "<p>This is an early-stage beta with plenty of rough edges. "
            "It grew out of community feedback on a "
            + ext_link(PROTOTYPE_URL, "prototype proposal")
            + " for scaling clause identification in sovereign bond contracts. "
            "That feedback pointed to an immediate pain point: just finding and "
            "navigating prospectuses across multiple sources is hard. "
            "This explorer is a first down payment on what could become something "
            "much more powerful, with your input.</p>"
        ),
        ui.h5("What's next?"),
        ui.tags.ul(
            ui.tags.li("Automated updates as new prospectuses are filed"),
            ui.tags.li("New data sources"),
            ui.tags.li(
                "Filtering by document type (base prospectus, supplement, final terms, etc.)"
            ),
            ui.tags.li(
                ui.HTML(
                    "Automated clause identification with expert validation ("
                    + ext_link(PROTOTYPE_URL, "learn more")
                    + ")"
                )
            ),
            ui.tags.li(
                ui.HTML(
                    "Part of a growing open-source SovTech ecosystem alongside "
                    "tools like the "
                    + ext_link(QCRAFT_URL, "Q-CRAFT Explorer")
                    + " -- open-source tools that elevate the sovereign debt "
                    "conversation by eliminating analytical toil"
                )
            ),
        ),
        ui.h5("Help shape this tool"),
        ui.p(
            "We're building this with the people who use sovereign debt data. "
            "If you have 2 minutes, we'd love to hear from you:"
        ),
        ui.tags.ol(
            ui.tags.li(
                "What are your biggest pain points in working with sovereign bond prospectuses?"
            ),
            ui.tags.li(
                "Are you a sovereign debt lawyer who might be interested in "
                '"lawyer-in-the-loop" validation to help automatically identify '
                "key clauses?"
            ),
            ui.tags.li(
                "Would you be willing to have a short conversation about how "
                "this tool could be more useful for your work?"
            ),
        ),
        ui.HTML(
            "<p>"
            + ext_link("mailto:lte@tealinsights.com", "Get in touch")
            + " or open an issue on "
            + ext_link(GITHUB_URL + "/issues", "GitHub")
            + ".</p>"
        ),
    )


# ── UI ───────────────────────────────────────────────────────────────

_TEAL = "#2c7a7b"
_TEAL_LIGHT = "#e6fffa"
_TEAL_DARK = "#234e52"

app_ui = ui.page_navbar(
    ui.nav_panel(
        "Explorer",
        ui.div(
            ui.output_ui("main_view"),
            class_="container-fluid pt-3",
        ),
    ),
    title=ui.div(
        ui.img(src="teal-insights-logo.png", height="36px", class_="me-2"),
        ui.span("Sovereign Prospectus Database"),
        class_="d-flex align-items-center",
    ),
    bg="white",
    inverse=False,
    header=ui.tags.style(f"""
        :root {{ --teal: {_TEAL}; --teal-light: {_TEAL_LIGHT}; --teal-dark: {_TEAL_DARK}; }}
        .navbar {{ border-bottom: 3px solid {_TEAL}; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }}
        .navbar-brand {{ font-size: 1.2rem; font-weight: 600; color: #1a202c !important; }}
        .nav-link {{ color: #1a202c !important; }}
        .back-btn {{ display: inline-flex; align-items: center; gap: 0.4rem;
                     padding: 0.5rem 1rem; font-size: 0.95rem;
                     color: {_TEAL_DARK}; background: {_TEAL_LIGHT};
                     border: 1px solid {_TEAL}; border-radius: 6px;
                     cursor: pointer; margin-bottom: 1rem; }}
        .back-btn:hover {{ background: {_TEAL}; color: white; }}

        .main-header {{ display: flex; align-items: center; gap: 1rem;
                        margin-bottom: 1.5rem; padding: 0.5rem 0;
                        border-bottom: 1px solid #e2e8f0; }}
        .main-header img {{ max-height: 50px; }}
        .main-header .title-block {{ flex: 1; }}
        .main-header h2 {{ margin: 0; font-size: 1.4rem; color: {_TEAL_DARK}; }}
        .main-header .subtitle {{ color: #666; font-style: italic;
                                   margin: 0.25rem 0 0 0; font-size: 0.95rem; }}
        .supported-by {{ display: flex; flex-direction: column; align-items: center;
                         gap: 0.25rem; }}
        .supported-label {{ font-size: 0.75rem; color: #888; text-transform: uppercase;
                            letter-spacing: 0.05em; }}

        .bslib-value-box {{ border: 1px solid #e2e8f0; border-radius: 8px; }}
        .bslib-value-box .value-box-title {{ color: {_TEAL_DARK}; font-weight: 600; }}
        .bslib-value-box .value-box-value {{ font-size: 2rem; font-weight: 700;
                                             color: {_TEAL}; }}

        .accordion {{ border: 1px solid {_TEAL}; border-radius: 8px;
                      overflow: hidden; margin-bottom: 1rem; }}
        .accordion-item {{ border: none; }}
        .accordion-button {{ font-weight: 600; color: {_TEAL_DARK};
                             background-color: {_TEAL_LIGHT};
                             padding: 0.75rem 1.25rem; }}
        .accordion-button:not(.collapsed) {{ background-color: {_TEAL_LIGHT};
                                              color: {_TEAL_DARK};
                                              box-shadow: none; }}
        .accordion-button::after {{ /* disclosure triangle */
            transition: transform 0.2s ease; }}
        .accordion-body {{ background: white; padding: 1.25rem; }}

        .btn-primary, .btn-default {{ background-color: {_TEAL}; border-color: {_TEAL}; }}
        .btn-primary:hover {{ background-color: {_TEAL_DARK}; border-color: {_TEAL_DARK}; }}

        pre {{ white-space: pre-wrap; word-wrap: break-word;
               background: #f7fafc; padding: 1rem; border-radius: 6px;
               border: 1px solid #e2e8f0;
               font-size: 0.9rem; line-height: 1.6; }}
        .detail-meta {{ color: #4a5568; }}
        mark {{ background-color: #fefcbf; padding: 1px 2px; border-radius: 2px; }}
    """),
)


# ── Server ───────────────────────────────────────────────────────────


def server(input: Inputs, output: Outputs, session: Session):
    # ── Navigation state ─────────────────────────────────────────
    current_view: reactive.Value[str] = reactive.value("browse")
    selected_doc_id: reactive.Value[int | None] = reactive.value(None)
    browse_page: reactive.Value[int] = reactive.value(0)

    # ── Main view router ─────────────────────────────────────────
    @render.ui
    def main_view():
        if current_view() == "detail" and selected_doc_id() is not None:
            return _build_detail_ui(selected_doc_id())
        return _build_browse_ui()

    # ── Browse view ──────────────────────────────────────────────
    def _build_browse_ui():
        return ui.div(
            # Subtitle with logos
            ui.HTML(
                '<div class="main-header">'
                '<div class="title-block">'
                "<h2>Browse 9,700+ sovereign bond prospectuses</h2>"
                '<p class="subtitle">Open-source SovTech infrastructure for '
                "sovereign debt research.</p>"
                "</div>"
                '<div class="supported-by">'
                '<span class="supported-label">Supported by</span>'
                '<img src="naturefinance-logo.png" alt="NatureFinance" '
                'style="max-height: 45px;">'
                "</div>"
                "</div>"
            ),
            # Stats
            ui.layout_columns(
                ui.value_box("Documents", f"{_stats['docs']:,}"),
                ui.value_box("Sources", str(_stats["sources"])),
                ui.value_box("Issuers", f"{_stats['issuers']:,}"),
                col_widths=(4, 4, 4),
            ),
            # About
            ui.accordion(
                ui.accordion_panel("About this project", _about_content()),
                id="about_accordion",
                open=False,
            ),
            # Filters
            ui.input_checkbox("include_hi", "Include high-income countries", False),
            ui.layout_columns(
                ui.input_selectize(
                    "filter_country",
                    "Country",
                    choices=_country_choices,
                    multiple=True,
                ),
                ui.input_selectize(
                    "filter_region",
                    "Region",
                    choices=_region_choices,
                    multiple=True,
                ),
                ui.input_selectize(
                    "filter_income",
                    "Income group",
                    choices=_income_choices,
                    multiple=True,
                ),
                ui.input_selectize(
                    "filter_source",
                    "Source",
                    choices=_source_choices,
                    multiple=True,
                ),
                col_widths=(3, 3, 3, 3),
            ),
            # Document count + table
            ui.output_ui("doc_count_label"),
            ui.output_data_frame("doc_table"),
            # Pagination
            ui.layout_columns(
                ui.input_action_button("prev_page", "\u2190 Previous"),
                ui.div(),
                ui.input_action_button("next_page", "Next \u2192"),
                col_widths=(2, 8, 2),
            ),
        )

    # ── Filter helper ────────────────────────────────────────────
    def _current_filters():
        sources = list(input.filter_source()) if input.filter_source() else None
        regions = list(input.filter_region()) if input.filter_region() else None
        income = list(input.filter_income()) if input.filter_income() else None
        codes = list(input.filter_country()) if input.filter_country() else None
        return {
            "sources": sources,
            "regions": regions,
            "income_groups": income,
            "country_codes": codes,
            "include_high_income": input.include_hi(),
        }

    # ── Document count ───────────────────────────────────────────
    @render.ui
    def doc_count_label():
        filters = _current_filters()
        total = count_documents(_con, **filters)
        page = browse_page()
        offset = page * 50
        end = min(offset + 50, total)
        if total == 0:
            return ui.p(ui.em("No documents match these filters."))
        return ui.p(
            ui.strong(f"{total:,} documents"),
            f", newest first (showing {offset + 1}\u2013{end})",
        )

    # ── Document table ───────────────────────────────────────────
    @render.data_frame
    def doc_table():
        filters = _current_filters()
        page = browse_page()
        df = browse_documents(_con, limit=50, offset=page * 50, **filters)
        if df.empty:
            return render.DataGrid(
                pd.DataFrame({"Issuer": [], "Source": [], "Date": []}),
                width="100%",
            )
        display_df = pd.DataFrame(
            {
                "Issuer": df["display_name"],
                "Source": df["source"].map(source_display),
                "Date": df["publication_date"].apply(
                    lambda d: str(d)[:10] if pd.notna(d) else "undated"
                ),
            }
        )
        return render.DataGrid(
            display_df,
            selection_mode="row",
            width="100%",
        )

    # ── Row click -> detail ──────────────────────────────────────
    @reactive.effect
    def _handle_row_click():
        sel = doc_table.cell_selection()
        if sel and sel.get("rows"):
            row_idx = next(iter(sel["rows"]))
            filters = _current_filters()
            page = browse_page()
            df = browse_documents(_con, limit=50, offset=page * 50, **filters)
            if row_idx < len(df):
                selected_doc_id.set(int(df.iloc[row_idx]["document_id"]))
                current_view.set("detail")

    # ── Pagination ───────────────────────────────────────────────
    @reactive.effect
    @reactive.event(input.prev_page)
    def _prev():
        if browse_page() > 0:
            browse_page.set(browse_page() - 1)

    @reactive.effect
    @reactive.event(input.next_page)
    def _next():
        filters = _current_filters()
        total = count_documents(_con, **filters)
        if (browse_page() + 1) * 50 < total:
            browse_page.set(browse_page() + 1)

    # ── Detail view ──────────────────────────────────────────────
    def _build_detail_ui(doc_id):
        detail = get_document_detail(_con, doc_id)
        if detail is None:
            return ui.div(
                ui.input_action_button("back_missing", "\u2190 Back to browse", class_="back-btn"),
                ui.p("Document not found."),
            )

        meta_parts = [f"**Source:** {source_display(detail['source'])}"]
        pub_date = detail["publication_date"]
        meta_parts.append(f"**Date:** {str(pub_date)[:10]}" if pub_date else "**Date:** undated")
        if detail["doc_type"]:
            meta_parts.append(f"**Type:** {detail['doc_type']}")
        meta_parts.append(f"**Country:** {detail['country_name']}")
        meta_parts.append(f"**Region:** {detail['region']}")

        filing_html = ""
        if detail["filing_url"]:
            filing_html = ext_link(detail["filing_url"], "View original filing")

        return ui.div(
            ui.input_action_button("back_btn", "\u2190 Back to browse", class_="back-btn"),
            ui.h1(detail["display_name"]),
            ui.markdown(" | ".join(meta_parts)),
            ui.HTML(filing_html) if filing_html else ui.div(),
            ui.hr(),
            ui.input_text(
                "doc_search",
                "Search within this document",
                placeholder="Find text in this prospectus...",
            ),
            ui.output_ui("doc_body"),
        )

    # ── Back buttons ─────────────────────────────────────────────
    @reactive.effect
    @reactive.event(input.back_btn)
    def _back():
        current_view.set("browse")
        selected_doc_id.set(None)

    @reactive.effect
    @reactive.event(input.back_missing)
    def _back_missing():
        current_view.set("browse")
        selected_doc_id.set(None)

    # ── Document body ────────────────────────────────────────────
    @render.ui
    def doc_body():
        doc_id = selected_doc_id()
        if doc_id is None:
            return ui.div()

        md_size = get_markdown_size(_con, doc_id)
        max_page = get_max_page(_con, doc_id)
        search_q = input.doc_search() if hasattr(input, "doc_search") else ""

        has_markdown = md_size > 0
        has_pages = max_page > 0
        use_full_md = has_markdown and md_size < MARKDOWN_SIZE_LIMIT

        if not has_markdown and not has_pages:
            detail = get_document_detail(_con, doc_id)
            filing_url = detail["filing_url"] if detail else None
            parts = [
                ui.p(ui.em("Full text not yet available -- this document is being processed."))
            ]
            if filing_url:
                parts.append(
                    ui.HTML(
                        "<p>In the meantime, you can "
                        + ext_link(filing_url, "view the original filing")
                        + ".</p>"
                    )
                )
            return ui.div(*parts)

        if use_full_md:
            return _render_full_md(doc_id, search_q)
        if has_pages:
            return _render_pages(doc_id, max_page, search_q)
        return _render_full_md(doc_id, search_q)

    def _render_full_md(doc_id, search_query):
        md_text = get_markdown(_con, doc_id)
        if not md_text:
            return ui.p(ui.em("No markdown available."))

        parts = []

        # ToC
        headings = re.findall(r"^(#{2,3})\s+(.+)$", md_text, re.MULTILINE)
        if headings:
            toc_items = []
            for marker, title in headings:
                level = len(marker) - 2
                indent = "\u00a0\u00a0\u00a0\u00a0" * level
                toc_items.append(ui.tags.li(f"{indent}{title}"))
            parts.append(
                ui.accordion(
                    ui.accordion_panel("Table of Contents", ui.tags.ul(*toc_items)),
                    open=False,
                )
            )

        if search_query:
            highlighted, count = highlight_text(md_text, search_query, return_count=True)
            if count > 100:
                parts.append(
                    ui.p(ui.em(f"{count} matches found -- showing first 100 highlights."))
                )
            elif count > 0:
                parts.append(ui.p(ui.em(f"{count} matches found.")))
            else:
                parts.append(ui.p(ui.em(f'"{search_query}" not found in this document.')))
            parts.append(ui.HTML(highlighted))
        else:
            parts.append(ui.markdown(md_text))

        return ui.div(*parts)

    def _render_pages(doc_id, max_page, search_query):
        parts = []

        if search_query:
            matching = search_pages_in_document(_con, doc_id, search_query)
            if matching:
                page_list = ", ".join(str(p) for p in matching[:20])
                suffix = "..." if len(matching) > 20 else ""
                parts.append(
                    ui.p(
                        ui.em(
                            f'Found "{search_query}" on {len(matching)} pages: {page_list}{suffix}'
                        )
                    )
                )
            else:
                parts.append(ui.p(ui.em(f'"{search_query}" not found in this document.')))

        page_key = f"page_sel_{doc_id}"
        parts.append(
            ui.input_numeric(
                page_key,
                f"Page (1\u2013{max_page})",
                value=1,
                min=1,
                max=max_page,
            )
        )

        page_num = input[page_key]() if page_key in input else 1
        page_num = max(1, min(page_num, max_page))

        text = get_page_text(_con, doc_id, page_num)
        if text:
            if search_query:
                escaped = html_mod.escape(text)
                highlighted, count = highlight_text(escaped, search_query, return_count=True)
                parts.append(
                    ui.p(
                        ui.strong(f"Page {page_num} of {max_page}"),
                        f" ({count} matches on this page)",
                    )
                )
                if count > 0:
                    parts.append(ui.HTML(highlighted))
                else:
                    parts.append(ui.tags.pre(text))
            else:
                parts.append(ui.p(ui.strong(f"Page {page_num} of {max_page}")))
                parts.append(ui.tags.pre(text))
        else:
            parts.append(ui.p(ui.em(f"No text available for page {page_num}.")))

        return ui.div(*parts)


# ── App ──────────────────────────────────────────────────────────────

_www_dir = Path(__file__).resolve().parent / "www"
app = App(app_ui, server, static_assets=_www_dir)
