# Note: Uses pandas (not polars) because Shiny's render.DataTable works best
# with pandas DataFrames.

from __future__ import annotations

import csv
import re
from pathlib import Path

import pandas as pd
from shiny import App, Inputs, Outputs, Session, reactive, render, ui

DATA_DIR = Path(__file__).parent / "data"
CANDIDATES_PATH = DATA_DIR / "grep_candidates.csv"
FEEDBACK_PATH = DATA_DIR / "feedback_log.csv"

PATTERN_LABELS: dict[str, str] = {
    "collective_action": "Collective Action (CAC)",
    "pari_passu": "Pari Passu",
    "feature__governing_law": "Governing Law",
}


def load_candidates() -> pd.DataFrame:
    df = pd.read_csv(CANDIDATES_PATH, dtype=str).fillna("")
    return df


def get_display_label(pattern_name: str) -> str:
    return PATTERN_LABELS.get(pattern_name, pattern_name)


ALL_CANDIDATES = load_candidates()

# Build pattern options from data — only include patterns present in the data
_patterns_in_data = ALL_CANDIDATES["pattern_name"].unique().tolist()
PATTERN_CHOICES: dict[str, str] = {
    k: v for k, v in PATTERN_LABELS.items() if k in _patterns_in_data
}
# Add any patterns in data not in our map
for _p in _patterns_in_data:
    if _p not in PATTERN_CHOICES:
        PATTERN_CHOICES[_p] = _p

app_ui = ui.page_sidebar(
    ui.sidebar(
        ui.h5("Clause Eval Explorer"),
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
            choices=PATTERN_CHOICES,
            selected=next(iter(PATTERN_CHOICES.keys())) if PATTERN_CHOICES else None,
        ),
        ui.hr(),
        ui.p(
            ui.strong("How to use:"),
            ui.tags.ol(
                ui.tags.li("Select a clause type above."),
                ui.tags.li("Click a row in the table to inspect it."),
                ui.tags.li("Rate the match with thumbs up / down."),
            ),
            style="font-size: 0.85em;",
        ),
        width=280,
    ),
    ui.card(
        ui.card_header("Grep Candidates"),
        ui.output_data_frame("candidates_table"),
    ),
    ui.card(
        ui.card_header("Match Context"),
        ui.output_ui("context_panel"),
    ),
    ui.card(
        ui.card_header("Feedback"),
        ui.output_ui("feedback_panel"),
    ),
    title="Clause Eval Explorer",
    theme=ui.Theme("bootstrap"),
)


def server(input: Inputs, output: Outputs, session: Session) -> None:
    selected_row: reactive.Value[int | None] = reactive.Value(None)

    @reactive.Calc
    def filtered_df() -> pd.DataFrame:
        pattern = input.clause_family()
        df = ALL_CANDIDATES[ALL_CANDIDATES["pattern_name"] == pattern].copy()
        df = df.reset_index(drop=True)
        return df

    @reactive.Calc
    def display_df() -> pd.DataFrame:
        df = filtered_df()
        result = pd.DataFrame(
            {
                "Country": df["country"],
                "Document": df["document_title"].str[:80],
                "Page": df["page_number"],
                "Match": df["matched_text"].str[:80],
            }
        )
        return result

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
    def context_panel() -> ui.TagList:
        row_idx = selected_row()
        if row_idx is None:
            return ui.TagList(
                ui.p(
                    "Click a row in the table above to see context.",
                    style="color: #888; font-style: italic;",
                )
            )
        df = filtered_df()
        if row_idx >= len(df):
            return ui.TagList(ui.p("Row out of range."))
        row = df.iloc[row_idx]

        page_text = str(row.get("page_text", "") or "")
        matched = str(row.get("matched_text", "") or "")
        country = str(row.get("country", "") or "Unknown")
        doc_title = str(row.get("document_title", "") or row.get("storage_key", ""))
        page_num = str(row.get("page_number", "") or "?")

        # Highlight matched text within page text
        if page_text and matched:
            # Create a pattern that matches the text with flexible whitespace
            escaped = re.escape(matched)
            flex_pattern = re.sub(r"\\ ", r"\\s+", escaped)
            highlighted = re.sub(
                f"({flex_pattern})",
                r'<mark style="background-color: #fff3cd; padding: 2px 4px; font-weight: bold;">\1</mark>',
                page_text,
                count=0,
                flags=re.IGNORECASE,
            )
            display_html = highlighted.replace("\n\n", "</p><p>").replace("\n", " ")
            display_html = f"<p>{display_html}</p>"
        elif page_text:
            display_html = page_text.replace("\n\n", "</p><p>").replace("\n", " ")
            display_html = f"<p>{display_html}</p>"
        else:
            # Fallback to old context_before/after display
            ctx_before = str(row.get("context_before", "") or "")
            ctx_after = str(row.get("context_after", "") or "")
            display_html = (
                f'<p style="color: #666;">{ctx_before}</p>'
                f'<p><mark style="background-color: #fff3cd; padding: 2px 4px; font-weight: bold;">{matched}</mark></p>'
                f'<p style="color: #666;">{ctx_after}</p>'
            )

        return ui.TagList(
            ui.tags.h6(
                f"{country} — {doc_title} (page {page_num})",
                style="margin-bottom: 12px;",
            ),
            ui.tags.div(
                ui.HTML(display_html),
                style=(
                    "font-family: Georgia, 'Times New Roman', serif; "
                    "font-size: 14px; line-height: 1.7; "
                    "max-height: 500px; overflow-y: auto; "
                    "padding: 16px; background: #fafafa; "
                    "border: 1px solid #eee; border-radius: 4px;"
                ),
            ),
            ui.tags.hr(),
            ui.tags.small(
                f"{row['storage_key']} · Pattern: {row['pattern_name']}",
                class_="text-muted",
            ),
            ui.tags.p(
                ui.tags.em(
                    "In a production version, each candidate would link "
                    "to the original source document."
                ),
                class_="text-muted small mt-2",
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

        return ui.TagList(
            ui.layout_columns(
                ui.input_action_button(
                    "thumbs_up",
                    ui.HTML("&#128077; Relevant"),
                    class_="btn btn-success btn-sm",
                ),
                ui.input_action_button(
                    "thumbs_down",
                    ui.HTML("&#128078; Not relevant"),
                    class_="btn btn-danger btn-sm",
                ),
                col_widths=[2, 2, 8],
            ),
            ui.div(
                ui.input_text(
                    "why_not",
                    "Why not? (optional)",
                    placeholder="e.g. false positive, wrong clause type...",
                    width="100%",
                ),
                id="why_not_div",
            ),
            ui.output_text("feedback_status"),
        )

    @reactive.Effect
    @reactive.event(input.thumbs_up)
    def _on_thumbs_up() -> None:
        _write_feedback("relevant")

    @reactive.Effect
    @reactive.event(input.thumbs_down)
    def _on_thumbs_down() -> None:
        _write_feedback("not_relevant", input.why_not())

    feedback_msg: reactive.Value[str] = reactive.Value("")

    def _write_feedback(verdict: str, why: str = "") -> None:
        row_idx = selected_row()
        if row_idx is None:
            return
        df = filtered_df()
        if row_idx >= len(df):
            return
        row = df.iloc[row_idx]
        storage_key = row.get("storage_key", "")
        pattern_name = row.get("pattern_name", "")
        page = row.get("page_number", "")

        FEEDBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
        write_header = not FEEDBACK_PATH.exists()
        with FEEDBACK_PATH.open("a", newline="") as f:
            writer = csv.writer(f)
            if write_header:
                writer.writerow(["storage_key", "pattern_name", "page_number", "verdict", "why"])
            writer.writerow([storage_key, pattern_name, page, verdict, why])

        label = "Marked relevant" if verdict == "relevant" else "Marked not relevant"
        feedback_msg.set(f"{label} — {storage_key} p.{page}")

    @render.text
    def feedback_status() -> str:
        return feedback_msg()


app = App(app_ui, server)
