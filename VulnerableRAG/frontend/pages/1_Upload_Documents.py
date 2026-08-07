"""Upload Documents — add PDFs to the corpus and inspect what was indexed.

The chunk inspector is the useful part. It shows exactly what text was extracted and stored,
including PDF metadata and anything rendered invisibly in the original file. A hidden instruction is
invisible in a PDF viewer and obvious here.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

import frontend._bootstrap as bootstrap
from frontend import theme  # noqa: F401  - must be first; fixes sys.path
from frontend.components.api_client import ApiClient, ApiError
from frontend.components.widgets import profile_banner, show_api_error

settings = bootstrap.get_settings()
api = ApiClient(bootstrap.api_base_url(settings))

st.set_page_config(
    page_title=bootstrap.page_title(settings, "Upload"),
    page_icon="📄",
    layout="wide",
)

# Stylesheet first: anything drawn before it appears unstyled for a frame.
palette = theme.apply(settings)
st.title("Upload Documents")
profile_banner(settings.profile)

# ------------------------------------------------------------------------------------------------
# Upload
# ------------------------------------------------------------------------------------------------
st.subheader("Add a PDF")

uploaded = st.file_uploader(
    "Choose a PDF",
    type=settings.ingestion.supported_types,
    help=f"Up to {settings.ingestion.max_upload_mb} MB. Text is extracted, chunked, and embedded.",
)

if uploaded is not None and st.button("Ingest", type="primary"):
    with st.spinner(f"Ingesting {uploaded.name}…"):
        try:
            result = api.upload(uploaded.name, uploaded.getvalue())
        except ApiError as exc:
            show_api_error(exc)
        else:
            document = result["document"]
            st.success(
                f"Ingested **{document['filename']}** — {document['page_count']} pages, "
                f"{result['chunk_count']} chunks."
            )
            if result.get("duplicate_of"):
                st.info(
                    f"An identical file was already ingested (`{result['duplicate_of']}`). "
                    "The upload still went through — refusing it would be a security control, and "
                    "ingesting a document twice is how corpus flooding is demonstrated."
                )
            if document.get("pdf_metadata"):
                st.warning(
                    "This PDF carries metadata, and metadata is ingested as text. It is invisible "
                    "in a PDF viewer, which makes it a natural place to hide an instruction.",
                    icon="🔍",
                )
                st.json(document["pdf_metadata"])

st.divider()

# ------------------------------------------------------------------------------------------------
# Corpus
# ------------------------------------------------------------------------------------------------
st.subheader("Ingested documents")

try:
    listing = api.documents()
except ApiError as exc:
    show_api_error(exc)
    st.stop()

documents = listing["documents"]

if not documents:
    st.info(
        "Nothing ingested yet. Upload a PDF above, or seed the sample corpus:\n\n"
        "```bash\npython scripts/seed_corpus.py\n```"
    )
    st.stop()

st.caption(f"{listing['count']} documents · {listing['total_chunks']} chunks indexed")

table = pd.DataFrame(
    [
        {
            "Filename": d["filename"],
            "Pages": d["page_count"],
            "Chunks": d["chunk_count"],
            "Size (KB)": round(d["size_bytes"] / 1024, 1),
            "Metadata fields": len(d.get("pdf_metadata", {})),
            "Uploaded": d["uploaded_at"][:19].replace("T", " "),
            "ID": d["id"],
        }
        for d in documents
    ]
)
st.dataframe(table, width="stretch", hide_index=True)

st.divider()

# ------------------------------------------------------------------------------------------------
# Inspect / delete
# ------------------------------------------------------------------------------------------------
st.subheader("Inspect a document")

labels = {f"{d['filename']}  ({d['id'][:8]})": d for d in documents}
choice = st.selectbox("Document", list(labels))
selected = labels[choice]

inspect, remove = st.columns([3, 1])

with inspect:
    if st.button("Show stored chunks"):
        try:
            chunks = api.document_chunks(selected["id"])
        except ApiError as exc:
            show_api_error(exc)
        else:
            st.caption(
                f"{chunks['count']} chunks, exactly as indexed. Anything hidden in the original "
                f"file is plain text here."
            )
            for chunk in chunks["chunks"]:
                with st.expander(f"Chunk #{chunk['index']} · page {chunk['page']}"):
                    st.text(chunk["text"])

    if selected.get("pdf_metadata"):
        with st.expander("PDF metadata (ingested as text)"):
            st.json(selected["pdf_metadata"])

with remove:
    if st.button("Delete", type="secondary"):
        try:
            result = api.delete_document(selected["id"])
        except ApiError as exc:
            show_api_error(exc)
        else:
            st.success(f"Deleted. {result['chunks_removed']} chunks removed.")
            st.rerun()

# The theme switch lives in the sidebar on every page, so an operator who lands on a theme they
# cannot read never has to navigate somewhere else to fix it.
with st.sidebar:
    st.divider()
    theme.render_theme_toggle()
