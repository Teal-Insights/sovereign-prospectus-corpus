# Note: Uses pandas (not polars) because Shiny's render.DataTable works best
# with pandas DataFrames.

from __future__ import annotations

import csv
import datetime
import json
from pathlib import Path

import pandas as pd
from shiny import App, Inputs, Outputs, Session, reactive, render, ui

DATA_DIR = Path(__file__).parent / ".." / "data"
CANDIDATES_PATH = DATA_DIR / "clause_candidates_v2.csv"
FEEDBACK_PATH = DATA_DIR / "feedback_log_v2.csv"

CLAUSE_FAMILY_LABELS: dict[str, str] = {
    "collective_action": "Collective Action Clause (CAC)",
    "pari_passu": "Pari Passu",
}

CONFIDENCE_LABELS: dict[str, str] = {
    "": "All",
    "high": "High",
    "medium": "Medium",
}

VERBATIM_LABELS: dict[str, str] = {
    "": "All",
    "verified": "Verified",
    "failed": "Failed",
}

FEEDBACK_OPTIONS: dict[str, str] = {
    "correct": "Correct",
    "wrong_boundaries": "Wrong Boundaries",
    "not_a_clause": "Not a Clause",
    "partial": "Partial",
    "needs_second_look": "Needs Second Look",
}


def load_candidates() -> pd.DataFrame:
    df = pd.read_csv(CANDIDATES_PATH, dtype=str).fillna("")
    return df


ALL_CANDIDATES = load_candidates()

# Build clause family choices from data
_families_in_data = ALL_CANDIDATES["clause_family"].unique().tolist()
CLAUSE_FAMILY_CHOICES: dict[str, str] = {}
for _f in sorted(_families_in_data):
    CLAUSE_FAMILY_CHOICES[_f] = CLAUSE_FAMILY_LABELS.get(_f, _f)


app_ui = ui.page_sidebar(
    ui.sidebar(
        ui.h5("Clause Eval Explorer v2"),
        ui.p(
            ui.em(
                "Proof of concept for the #PublicDebtIsPublic roundtable. "
                "Findings are preliminary."
            ),
            style="font-size: 0.85em; color: #666;",
        ),
        ui.hr(),
        ui.input_select(
            "clause_family",
            "Clause Family",
            choices=CLAUSE_FAMILY_CHOICES,
            selected=next(iter(CLAUSE_FAMILY_CHOICES.keys())) if CLAUSE_FAMILY_CHOICES else None,
        ),
        ui.input_select(
            "confidence_filter",
            "LLM Confidence",
            choices=CONFIDENCE_LABELS,
            selected="",
        ),
        ui.input_select(
            "verbatim_filter",
            "Verbatim Status",
            choices=VERBATIM_LABELS,
            selected="",
        ),
        ui.hr(),
        ui.output_text("record_count"),
        ui.hr(),
        ui.p(
            ui.strong("How to use:"),
            ui.tags.ol(
                ui.tags.li("Select a clause type and filters above."),
                ui.tags.li("Click a row to inspect the extracted clause."),
                ui.tags.li("Rate the extraction using the feedback buttons."),
            ),
            style="font-size: 0.85em;",
        ),
        width=300,
    ),
    ui.card(
        ui.card_header("Extracted Clauses"),
        ui.output_data_frame("candidates_table"),
    ),
    ui.card(
        ui.card_header("Extracted Clause"),
        ui.output_ui("clause_panel"),
    ),
    ui.card(
        ui.card_header("Section Context"),
        ui.output_ui("context_panel"),
    ),
    ui.card(
        ui.card_header("Validation Feedback"),
        ui.output_ui("feedback_panel"),
    ),
    title="Clause Eval Explorer v2",
    theme=ui.Theme("bootstrap"),
)


def server(input: Inputs, output: Outputs, session: Session) -> None:
    selected_row: reactive.Value[int | None] = reactive.Value(None)
    feedback_msg: reactive.Value[str] = reactive.Value("")

    @reactive.Calc
    def filtered_df() -> pd.DataFrame:
        family = input.clause_family()
        conf = input.confidence_filter()
        verbatim = input.verbatim_filter()

        df = ALL_CANDIDATES[ALL_CANDIDATES["clause_family"] == family].copy()

        if conf:
            df = df[df["llm_confidence"] == conf]
        if verbatim:
            df = df[df["verbatim_status"] == verbatim]

        df = df.reset_index(drop=True)
        return df

    @reactive.Calc
    def display_df() -> pd.DataFrame:
        df = filtered_df()
        result = pd.DataFrame(
            {
                "Storage Key": df["storage_key"].str[-30:],
                "Section": df["section_heading"].str[:60],
                "Clause Family": df["clause_family"].map(lambda x: CLAUSE_FAMILY_LABELS.get(x, x)),
                "Confidence": df["llm_confidence"].str.capitalize(),
                "Verbatim": df["verbatim_status"].str.capitalize(),
                "Clause Preview": df["clause_text"].str[:150],
            }
        )
        return result

    @render.text
    def record_count() -> str:
        n = len(filtered_df())
        return f"{n} extraction(s) shown"

    @render.data_frame
    def candidates_table() -> render.DataGrid:
        return render.DataGrid(
            display_df(),
            selection_mode="row",
            width="100%",
            height="320px",
        )

    @reactive.Effect
    def _sync_selection() -> None:
        sel = candidates_table.cell_selection()
        rows = sel.get("rows", []) if sel else []
        if rows:
            selected_row.set(rows[0])
        else:
            selected_row.set(None)

    @render.ui
    def clause_panel() -> ui.TagList:
        row_idx = selected_row()
        if row_idx is None:
            return ui.TagList(
                ui.p(
                    "Click a row in the table above to view the extracted clause.",
                    style="color: #888; font-style: italic;",
                )
            )

        df = filtered_df()
        if row_idx >= len(df):
            return ui.TagList(ui.p("Row out of range."))

        row = df.iloc[row_idx]
        from html import escape as _esc

        candidate_id = str(row.get("candidate_id", "") or "")
        storage_key = str(row.get("storage_key", "") or "")
        section_heading = str(row.get("section_heading", "") or "")
        clause_text = str(row.get("clause_text", "") or "")
        confidence = str(row.get("llm_confidence", "") or "")
        reasoning = str(row.get("llm_reasoning", "") or "")
        verbatim_status = str(row.get("verbatim_status", "") or "")
        verbatim_sim = str(row.get("verbatim_similarity", "") or "")
        completeness_raw = str(row.get("completeness", "") or "{}")
        quality_flags = str(row.get("quality_flags", "") or "")
        clause_family = str(row.get("clause_family", "") or "")
        page_start = str(row.get("page_start", "") or "")
        page_end = str(row.get("page_end", "") or "")

        # Format page range
        if page_start or page_end:
            page_label = (
                f"pp. {page_start}–{page_end}" if page_end != page_start else f"p. {page_start}"
            )
        else:
            page_label = "page unknown"

        # Parse completeness
        try:
            completeness = json.loads(completeness_raw)
        except (json.JSONDecodeError, TypeError):
            completeness = {}

        # Build completeness badges
        badge_items = []
        for component, present in completeness.items():
            color = "#28a745" if present else "#dc3545"
            icon = "✓" if present else "✗"
            badge_items.append(
                f'<span style="display:inline-block;margin:2px 4px;padding:2px 8px;'
                f'border-radius:4px;background:{color};color:white;font-size:0.8em;">'
                f"{icon} {_esc(component)}</span>"
            )
        completeness_html = " ".join(badge_items) if badge_items else ""

        # Confidence badge color
        conf_color = {"high": "#28a745", "medium": "#ffc107", "low": "#dc3545"}.get(
            confidence, "#6c757d"
        )

        # Verbatim badge color
        verb_color = {"verified": "#28a745", "failed": "#dc3545"}.get(verbatim_status, "#6c757d")

        # Format clause text as HTML preserving paragraphs
        safe_clause = _esc(clause_text)
        clause_html = safe_clause.replace("\n\n", "</p><p>").replace("\n", "<br>")
        clause_html = f"<p>{clause_html}</p>"

        family_label = CLAUSE_FAMILY_LABELS.get(clause_family, clause_family)

        return ui.TagList(
            # Header row: key metadata
            ui.tags.div(
                ui.tags.h6(
                    f"{family_label} — {_esc(section_heading[:80])}",
                    style="margin-bottom: 6px;",
                ),
                ui.HTML(
                    f'<p style="font-size:0.85em;color:#555;margin-bottom:8px;">'
                    f"{_esc(storage_key)} &middot; {page_label} &middot; "
                    f'<span style="background:{conf_color};color:white;padding:1px 6px;'
                    f'border-radius:3px;font-size:0.9em;">{_esc(confidence)} confidence</span>'
                    f" &middot; "
                    f'<span style="background:{verb_color};color:white;padding:1px 6px;'
                    f'border-radius:3px;font-size:0.9em;">{_esc(verbatim_status)}</span>'
                    f"</p>"
                ),
                style="border-bottom: 1px solid #eee; padding-bottom: 8px; margin-bottom: 12px;",
            ),
            # Primary: extracted clause text
            ui.tags.div(
                ui.HTML(clause_html),
                style=(
                    "font-family: Georgia, 'Times New Roman', serif; "
                    "font-size: 14px; line-height: 1.7; "
                    "max-height: 450px; overflow-y: auto; "
                    "padding: 16px; background: #f8f9fa; "
                    "border: 1px solid #dee2e6; border-radius: 4px;"
                ),
            ),
            # Completeness components
            ui.tags.div(
                ui.HTML(
                    f'<div style="margin-top:10px;"><strong style="font-size:0.85em;">Components:</strong> '
                    f"{completeness_html}</div>"
                )
                if completeness_html
                else ui.tags.span("")
            ),
            # Quality flags
            ui.tags.div(
                ui.tags.small(
                    f"Quality flags: {quality_flags}",
                    style="color: #dc3545;",
                )
                if quality_flags
                else ui.tags.span("")
            ),
            # LLM reasoning (collapsed details)
            ui.tags.details(
                ui.tags.summary(
                    "LLM Reasoning",
                    style="cursor:pointer;font-size:0.85em;color:#555;margin-top:8px;",
                ),
                ui.tags.p(
                    _esc(reasoning),
                    style="font-size:0.85em;color:#555;padding:6px 0;",
                ),
            ),
            ui.tags.small(
                f"Candidate ID: {_esc(candidate_id)} · Verbatim similarity: {verbatim_sim}",
                class_="text-muted",
                style="display:block;margin-top:8px;",
            ),
        )

    @render.ui
    def context_panel() -> ui.TagList:
        row_idx = selected_row()
        if row_idx is None:
            return ui.TagList(
                ui.p(
                    "Select a row to view section context.",
                    style="color: #888; font-style: italic;",
                )
            )

        df = filtered_df()
        if row_idx >= len(df):
            return ui.TagList(ui.p("Row out of range."))

        row = df.iloc[row_idx]
        from html import escape as _esc

        section_text = str(row.get("section_text", "") or "")
        clause_text = str(row.get("clause_text", "") or "")

        if not section_text:
            return ui.TagList(
                ui.p(
                    "No section context available.",
                    style="color: #888; font-style: italic;",
                )
            )

        # Highlight clause_text within section_text if present
        import re

        safe_section = _esc(section_text)
        if clause_text:
            safe_clause = _esc(clause_text[:200])  # match on first 200 chars only
            escaped = re.escape(safe_clause)
            flex_pattern = re.sub(r"\\?\s+", r"\\s+", escaped)
            highlighted = re.sub(
                f"({flex_pattern})",
                r'<mark style="background-color: #fff3cd; padding: 1px 3px;">\1</mark>',
                safe_section,
                count=1,
                flags=re.IGNORECASE | re.DOTALL,
            )
        else:
            highlighted = safe_section

        display_html = highlighted.replace("\n\n", "</p><p>").replace("\n", " ")
        display_html = f"<p>{display_html}</p>"

        return ui.TagList(
            ui.tags.div(
                ui.HTML(display_html),
                style=(
                    "font-family: Georgia, 'Times New Roman', serif; "
                    "font-size: 13px; line-height: 1.6; "
                    "max-height: 300px; overflow-y: auto; "
                    "padding: 14px; background: #fafafa; "
                    "border: 1px solid #eee; border-radius: 4px;"
                ),
            ),
            ui.tags.small(
                "Yellow highlight marks the start of the extracted clause text.",
                class_="text-muted",
                style="display:block;margin-top:6px;",
            ),
        )

    @render.ui
    def feedback_panel() -> ui.TagList:
        row_idx = selected_row()
        if row_idx is None:
            return ui.TagList(
                ui.p(
                    "Select a row to enable feedback.",
                    style="color: #888; font-style: italic;",
                )
            )

        df = filtered_df()
        if row_idx >= len(df):
            return ui.TagList(ui.p("Row out of range."))

        row = df.iloc[row_idx]
        candidate_id = str(row.get("candidate_id", "") or "")

        buttons = []
        for verdict_key, verdict_label in FEEDBACK_OPTIONS.items():
            btn_class = {
                "correct": "btn btn-success btn-sm",
                "wrong_boundaries": "btn btn-warning btn-sm",
                "not_a_clause": "btn btn-danger btn-sm",
                "partial": "btn btn-secondary btn-sm",
                "needs_second_look": "btn btn-outline-secondary btn-sm",
            }.get(verdict_key, "btn btn-secondary btn-sm")
            buttons.append(
                ui.input_action_button(
                    f"feedback_{verdict_key}",
                    verdict_label,
                    class_=btn_class,
                )
            )

        return ui.TagList(
            ui.tags.p(
                f"Rating extraction for candidate: {candidate_id}",
                style="font-size:0.85em;color:#555;margin-bottom:8px;",
            ),
            ui.layout_columns(
                *buttons,
                col_widths=[2, 2, 2, 2, 3, 1],
            ),
            ui.input_text(
                "feedback_notes",
                "Notes (optional)",
                placeholder="e.g. clause ends one paragraph too early...",
                width="100%",
            ),
            ui.output_ui("feedback_status_ui"),
        )

    @reactive.Effect
    @reactive.event(input.feedback_correct)
    def _on_correct() -> None:
        _write_feedback("correct")

    @reactive.Effect
    @reactive.event(input.feedback_wrong_boundaries)
    def _on_wrong_boundaries() -> None:
        _write_feedback("wrong_boundaries")

    @reactive.Effect
    @reactive.event(input.feedback_not_a_clause)
    def _on_not_a_clause() -> None:
        _write_feedback("not_a_clause")

    @reactive.Effect
    @reactive.event(input.feedback_partial)
    def _on_partial() -> None:
        _write_feedback("partial")

    @reactive.Effect
    @reactive.event(input.feedback_needs_second_look)
    def _on_needs_second_look() -> None:
        _write_feedback("needs_second_look")

    def _write_feedback(verdict: str) -> None:
        row_idx = selected_row()
        if row_idx is None:
            return
        df = filtered_df()
        if row_idx >= len(df):
            return
        row = df.iloc[row_idx]

        candidate_id = str(row.get("candidate_id", "") or "")
        storage_key = str(row.get("storage_key", "") or "")
        clause_family = str(row.get("clause_family", "") or "")
        notes = input.feedback_notes() if hasattr(input, "feedback_notes") else ""
        timestamp = datetime.datetime.now(datetime.UTC).isoformat()

        FEEDBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
        write_header = not FEEDBACK_PATH.exists()
        with FEEDBACK_PATH.open("a", newline="") as f:
            writer = csv.writer(f)
            if write_header:
                writer.writerow(
                    [
                        "timestamp",
                        "candidate_id",
                        "storage_key",
                        "clause_family",
                        "verdict",
                        "notes",
                    ]
                )
            writer.writerow([timestamp, candidate_id, storage_key, clause_family, verdict, notes])

        label = FEEDBACK_OPTIONS.get(verdict, verdict)
        feedback_msg.set(f"Saved: {label} — {candidate_id} at {timestamp[:19]}")

    @render.ui
    def feedback_status_ui() -> ui.TagList:
        msg = feedback_msg()
        if not msg:
            return ui.TagList()
        return ui.TagList(
            ui.tags.p(
                msg,
                style="color: #28a745; font-size: 0.85em; margin-top: 6px;",
            )
        )


app = App(app_ui, server)
