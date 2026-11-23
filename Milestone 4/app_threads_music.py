import json
import re
import duckdb
import pandas as pd
import streamlit as st

DB_PATH = "kdrama_reddit.duckdb"
SHOW_CSV = "show_titles.csv"   # built by make_show_titles.py (English + Korean titles)

# ---- The ONLY line that differs between app_threads_music.py and
# ---- app_threads_control.py is the next one.
GROUP = "music"
OUT_DB = f"{GROUP}_kdrama_threads.duckdb"   # the new database this app builds

@st.cache_resource
def get_db_connection():
    return duckdb.connect(DB_PATH, read_only=True)

@st.cache_data
def load_shows(group):
    """Show list for this group, read from the CSV (replaces typing a keyword)."""
    df = pd.read_csv(SHOW_CSV).fillna("")
    df = df[df["group"] == group].copy()
    return df.reset_index(drop=True)

# --- helpers added for batch searching ---------------------------------------
def like_clause(column, n):
    """(LOWER(col) LIKE LOWER(?) OR ...) -- same LIKE as the original, one per show."""
    return "(" + " OR ".join([f"LOWER({column}) LIKE LOWER(?)"] * n) + ")"

def ost_cond(column):
    """OST / soundtrack as a whole word (so 'most', 'post', 'host' don't match)."""
    return f"regexp_matches({column}, '(?i)\\b(ost|soundtrack)\\b')"

HANGUL = re.compile(r"[\uac00-\ud7a3]")

def build_terms(shows, use_korean, use_alt):
    """Every title we search for: English, plus (optionally) Korean and alternate titles."""
    rows = []
    for r in shows.itertuples():
        rows.append((r.show, r.title, "english"))
        if use_korean and r.title_korean:
            rows.append((r.show, r.title_korean, "korean"))
        if use_alt and r.alt_titles:
            rows += [(r.show, a, "alt") for a in r.alt_titles.split("|") if a]
    return pd.DataFrame(rows, columns=["show", "term", "kind"])

def term_pattern(term):
    if HANGUL.search(term):
        # Korean attaches particles to nouns (미라클은), so no word boundary here
        return re.compile(re.escape(term))
    # lookarounds (not \b) so titles ending in ! or ? like "Doona!" still match
    return re.compile(r"(?<!\w)" + re.escape(term) + r"(?!\w)", re.I)

def label_shows(df, terms, drop_unmatched):
    """The query returns threads; this works out WHICH show each thread is about
    (and whether it matched via the English, Korean or alternate title).
    The SQL LIKE is substring-only, so we also check the title as a whole word."""
    pats = [(r.show, r.kind, term_pattern(r.term)) for r in terms.itertuples()]
    rows, dropped = [], 0
    for rec in df.to_dict("records"):
        hits = {}
        for show, kind, p in pats:
            if p.search(rec["thread_title"]):
                hits.setdefault(show, set()).add(kind)
        if hits:
            for show, kinds in hits.items():
                rows.append({**rec, "show_name": show, "matched_via": "+".join(sorted(kinds)),
                             "n_shows_matched": len(hits)})
        elif drop_unmatched:
            dropped += 1
        else:
            rows.append({**rec, "show_name": "(matched in text/comments)", "matched_via": "",
                         "n_shows_matched": 0})
    out = pd.DataFrame(rows)
    if not out.empty:
        out["group"] = GROUP
        out["thread_type"] = out["thread_title"].apply(
            lambda t: "ost" if re.search(r"\b(ost|soundtrack)\b", t, re.I | re.A) else "episode")
        out["clean_post_id"] = out["post_id"].astype(str).str.replace("^t3_", "", regex=True)
    return out, dropped

def save_new_database(results_df):
    """Write matched threads + ALL comments in those threads to a NEW DuckDB file."""
    out = duckdb.connect(OUT_DB)
    try:
        return _write_tables(out, results_df)
    finally:
        out.close()

def _write_tables(out, results_df):
    out.execute(f"ATTACH '{DB_PATH}' AS src (READ_ONLY)")
    out.register("matched", results_df)
    out.execute("CREATE OR REPLACE TABLE threads AS SELECT * FROM matched")
    out.execute("""
        CREATE OR REPLACE TABLE comments AS
        SELECT m.show_name, m."group", m.thread_identifier, m.thread_type, c.*
        FROM src.comments c
        JOIN (SELECT DISTINCT clean_post_id, thread_identifier, show_name, "group", thread_type
              FROM matched) m
          ON CASE WHEN c.post_id LIKE 't3_%' THEN SUBSTR(c.post_id, 4)
                  ELSE c.post_id END = m.clean_post_id
    """)
    n_t = out.execute("SELECT COUNT(DISTINCT thread_identifier) FROM threads").fetchone()[0]
    n_c = out.execute("SELECT COUNT(*) FROM comments").fetchone()[0]
    return n_t, n_c

st.set_page_config(page_title=f"KDRAMA Reddit Search Engine ({GROUP})", layout="wide")

st.title(f"🎬 KDRAMA Reddit Search Engine: {GROUP} dramas")
st.write("Search threads across titles, submission content, or individual comment threads "
         f"for every {GROUP} show in the list at once.")

# 1. Show list (replaces the single search bar)
shows_all = load_shows(GROUP)
selected = st.multiselect(
    f"Shows to search ({len(shows_all)} {GROUP} shows in {SHOW_CSV}):",
    options=shows_all["show"].tolist(),
    default=shows_all["show"].tolist(),
    help="Remove shows here to run a small pilot."
)
use_korean = st.checkbox("Also search the Korean (Hangul) titles", value=True)
use_alt = st.checkbox("Also search alternate / romanized titles ('Also Known As'; noisier, e.g. 'Idol')", value=False)
require_ost = st.checkbox("Only threads with OST / soundtrack in the thread title", value=True)
save_db = st.checkbox(f"Save matches and all their comments to a new database ({OUT_DB})", value=True)

# 2. Search Mode Radio Buttons
search_mode = st.radio(
    "Select Search Scope & Ranking:",
    options=[
        "Search Thread Title (Ranked by Total Thread Score)",
        "Search Submission Title + Text (Ranked by Total Thread Score)",
        "Search Any Comment in Thread (Ranked by Matching Comments)"
    ],
    index=0
)

# Button only: the original also ran on page load, which would launch every show.
if st.button("🔍 Search Database", type="primary"):
    if not selected:
        st.warning("Please select at least one show.")
        st.stop()

    con = get_db_connection()
    shows = shows_all[shows_all["show"].isin(selected)]
    terms = build_terms(shows, use_korean, use_alt)
    search_terms = [f"%{t}%" for t in terms["term"].str.lower().unique()]
    n = len(search_terms)

    # Setup Progress Bar UI
    progress_bar = st.progress(0, text="Initializing query execution...")

    # -------------------------------------------------------------------------
    # MODE 1: Search Thread Title Only
    # -------------------------------------------------------------------------
    if search_mode == "Search Thread Title (Ranked by Total Thread Score)":
        progress_bar.progress(30, text="Searching thread titles...")

        query = f"""
            SELECT 
                thread_identifier,
                post_id,
                thread_title,
                subreddit,
                submission_author,
                comment_count,
                submission_score,
                total_thread_score,
                is_missing_submission,
                to_timestamp(start_timestamp::BIGINT)::VARCHAR AS start_time,
                to_timestamp(end_timestamp::BIGINT)::VARCHAR AS end_time
            FROM threads
            WHERE {like_clause('thread_title', n)}
              {"AND " + ost_cond('thread_title') if require_ost else ""}
            ORDER BY total_thread_score DESC
        """
        results_df = con.execute(query, search_terms).fetchdf()
        progress_bar.progress(100, text="Done!")

    # -------------------------------------------------------------------------
    # MODE 2: Search Submission Title + Body Text (selftext)
    # -------------------------------------------------------------------------
    elif search_mode == "Search Submission Title + Text (Ranked by Total Thread Score)":
        progress_bar.progress(20, text="Scanning submissions and thread titles...")

        query = f"""
            SELECT DISTINCT
                t.thread_identifier,
                t.post_id,
                t.thread_title,
                t.subreddit,
                t.submission_author,
                t.comment_count,
                t.submission_score,
                t.total_thread_score,
                t.is_missing_submission,
                to_timestamp(t.start_timestamp::BIGINT)::VARCHAR AS start_time,
                to_timestamp(t.end_timestamp::BIGINT)::VARCHAR AS end_time
            FROM threads t
            LEFT JOIN submissions s ON t.post_id = s.post_id
            WHERE ({like_clause('t.thread_title', n)}
               OR {like_clause("COALESCE(s.selftext, '')", n)})
              {"AND " + ost_cond('t.thread_title') if require_ost else ""}
            ORDER BY t.total_thread_score DESC
        """
        results_df = con.execute(query, search_terms + search_terms).fetchdf()
        progress_bar.progress(100, text="Done!")

    # -------------------------------------------------------------------------
    # MODE 3: Search Any Comment in Thread (Ranked by Matching Comments)
    # -------------------------------------------------------------------------
    else:
        progress_bar.progress(15, text="Aggregating comment matches across threads (this may take a moment)...")

        query = f"""
            WITH comment_matches AS (
                SELECT 
                    CASE 
                        WHEN post_id LIKE 't3_%' THEN SUBSTR(post_id, 4) 
                        ELSE post_id 
                    END AS clean_post_id,
                    1 AS match_count
                FROM comments
                WHERE {like_clause('comment_body', n)}
            ),
            thread_mention_counts AS (
                SELECT 
                    clean_post_id,
                    SUM(match_count) AS total_term_mentions
                FROM comment_matches
                GROUP BY clean_post_id
            )
            SELECT 
                t.thread_identifier,
                t.post_id,
                t.thread_title,
                tmc.total_term_mentions,
                t.subreddit,
                t.submission_author,
                t.comment_count,
                t.submission_score,
                t.total_thread_score,
                t.is_missing_submission,
                to_timestamp(t.start_timestamp::BIGINT)::VARCHAR AS start_time,
                to_timestamp(t.end_timestamp::BIGINT)::VARCHAR AS end_time
            FROM thread_mention_counts tmc
            JOIN threads t ON tmc.clean_post_id = t.post_id
            WHERE TRUE {"AND " + ost_cond('t.thread_title') if require_ost else ""}
            ORDER BY tmc.total_term_mentions DESC, t.total_thread_score DESC
        """
        results_df = con.execute(query, search_terms).fetchdf()
        progress_bar.progress(100, text="Done!")

    progress_bar.empty() # Remove progress bar on completion

    # Work out which show each thread belongs to (one row per thread x show)
    mode_is_title = search_mode.startswith("Search Thread Title")
    results_df, dropped = label_shows(results_df, terms, drop_unmatched=mode_is_title)
    if dropped:
        st.info(f"Dropped {dropped:,} thread(s) that only matched inside a longer word.")

    total_found = results_df["thread_identifier"].nunique() if len(results_df) else 0

    if total_found > 0:
        st.success(f"Found **{total_found:,}** matching thread(s) across "
                   f"**{results_df['show_name'].nunique():,}** show(s).")

        # Shows with zero hits usually need an alternate title
        missing = [s for s in selected if s not in set(results_df["show_name"])]
        with st.expander(f"Threads per show, and shows with no threads ({len(missing)})"):
            st.write("Threads per show:")
            st.dataframe(results_df.groupby("show_name")["thread_identifier"].nunique()
                         .rename("threads").sort_values(ascending=False))
            st.write("Matched via (thread x show pairs):")
            st.dataframe(results_df["matched_via"].value_counts().rename("pairs"))
            if missing:
                st.write("No threads found (may need an alternate title):", missing)
        if (results_df["n_shows_matched"] > 1).any():
            st.caption("Some threads matched more than one show title (n_shows_matched > 1); "
                       "check these for overlapping titles.")

        if save_db:
            with st.spinner(f"Writing {OUT_DB} (threads + all their comments)..."):
                n_t, n_c = save_new_database(results_df)
            st.success(f"Saved **{OUT_DB}**: {n_t:,} threads, {n_c:,} comments "
                       "(tables: `threads`, `comments`).")

        # Download Button for ALL results as JSONL
        jsonl_data = results_df.to_json(orient="records", lines=True)
        download_filename = f"threads_{GROUP}.jsonl"

        st.download_button(
            label=f"📥 Download All {total_found:,} Matching Threads (.jsonl)",
            data=jsonl_data,
            file_name=download_filename,
            mime="application/x-ndjson"
        )

        st.divider()
        st.subheader("Top 50 Matching Threads")
        st.caption("Click any column header to re-sort results.")

        top_50_df = results_df.drop(columns=["clean_post_id"]).head(50)

        # Configure column display based on mode
        column_config = {
            "thread_identifier": "Thread ID",
            "thread_title": "Title",
            "show_name": "Show",
            "thread_type": "Type",
            "matched_via": "Matched Via",
            "subreddit": "Subreddit",
            "submission_author": "Author Code",
            "comment_count": st.column_config.NumberColumn("Comments", format="%d"),
            "submission_score": st.column_config.NumberColumn("Post Score", format="%d"),
            "total_thread_score": st.column_config.NumberColumn("Total Score", format="%d"),
            "is_missing_submission": "Missing Post?",
            "start_time": "Start Date",
            "end_time": "Last Comment Date"
        }

        if "total_term_mentions" in top_50_df.columns:
            column_config["total_term_mentions"] = st.column_config.NumberColumn(
                "Matching Comments", format="%d"
            )

        st.dataframe(
            top_50_df,
            use_container_width=True,
            hide_index=True,
            column_config=column_config
        )
    else:
        st.warning("No matching threads found for the selected shows.")
