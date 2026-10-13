
import re
from urllib.parse import urljoin, urlparse, quote_plus

import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup

try:
    import pdfplumber
except ImportError:
    pdfplumber = None


# ==================================================
# PAGE CONFIG
# ==================================================
st.set_page_config(
    page_title="CampusScope | College Intelligence",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ==================================================
# CUSTOM DASHBOARD THEME
# ==================================================
st.markdown("""
<style>
.stApp {
    background: #f4f7f5;
    color: #172b2a;
}
.block-container {
    padding-top: 1.6rem;
    padding-bottom: 3rem;
}
h1, h2, h3, h4, p, label {
    color: #172b2a;
}
[data-testid="stSidebar"] {
    background: #e7efeb;
    border-right: 1px solid #cad9d1;
}
.hero {
    padding: 30px 34px;
    border-radius: 22px;
    background: linear-gradient(
        115deg, #123c36, #167d70, #56a68d
    );
    margin-bottom: 22px;
}
.hero h1 {
    color: white !important;
    font-size: 2.35rem;
    margin: 0;
}
.hero p {
    color: #e5fff4 !important;
    margin-top: 10px;
}
div[data-testid="stMetric"] {
    background: white;
    border: 1px solid #dce7e1;
    border-radius: 16px;
    padding: 16px;
}
.stButton > button,
.stDownloadButton > button,
.stLinkButton > a {
    border-radius: 11px !important;
    font-weight: 650 !important;
}
.stButton > button[kind="primary"] {
    background: #167d70 !important;
    color: white !important;
}
.stButton > button[kind="primary"] * {
    color: white !important;
}
.stTextInput input {
    background: white !important;
    color: #172b2a !important;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero">
    <h1>🧭 CampusScope</h1>
    <p>
        Karnataka Engineering College Intelligence Dashboard
        <br>
        Discover institutions, explore official websites,
        and analyze your college directory.
    </p>
</div>
""", unsafe_allow_html=True)


# ==================================================
# HELPERS
# ==================================================
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/125.0 Safari/537.36"
    )
}

TIMEOUT = 12
MAX_PAGES = 8


def normalize(value):
    return re.sub(
        r"[^a-z0-9]+", "", str(value).lower().strip()
    )


def find_column(df, aliases):
    columns = {normalize(c): c for c in df.columns}

    for alias in aliases:
        if normalize(alias) in columns:
            return columns[normalize(alias)]

    for column in df.columns:
        for alias in aliases:
            if normalize(alias) in normalize(column):
                return column

    return None


def get_value(row, column):
    if not column:
        return ""

    value = row.get(column, "")

    if pd.isna(value):
        return ""

    return str(value).strip()


def valid_url(url):
    try:
        parsed = urlparse(str(url).strip())
        return (
            parsed.scheme in ("http", "https")
            and bool(parsed.netloc)
            and "." in parsed.netloc
        )
    except Exception:
        return False


def maps_url(name, address=""):
    query = quote_plus(f"{name} {address}")
    return (
        "https://www.google.com/maps/search/"
        f"?api=1&query={query}"
    )


# ==================================================
# WEBSITE SCRAPER
# ==================================================
TOPICS = {
    "Institution Profile": [
        "about", "history", "profile", "vision", "mission"
    ],
    "Departments and Courses": [
        "department", "courses", "academics",
        "programmes", "programs", "computer science"
    ],
    "Admissions and Intake": [
        "admission", "intake", "seats", "admissions"
    ],
    "Affiliation and Accreditation": [
        "affiliation", "autonomous", "accreditation",
        "university", "naac", "nba"
    ],
    "Placement Information": [
        "placement", "recruiter", "career",
        "training", "package", "recruitment"
    ],
    "Recruiters": [
        "recruiter", "companies", "company",
        "infosys", "wipro", "accenture", "tcs"
    ],
}


def fetch_page(url):
    try:
        response = requests.get(
            url, headers=HEADERS, timeout=TIMEOUT
        )
        response.raise_for_status()
    except requests.RequestException:
        return "", []

    soup = BeautifulSoup(response.text, "html.parser")
    links = []

    for anchor in soup.find_all("a", href=True):
        link = urljoin(response.url, anchor["href"])
        label = anchor.get_text(" ", strip=True)

        if valid_url(link):
            links.append((label, link))

    for tag in soup([
        "script", "style", "nav", "footer",
        "header", "noscript", "svg"
    ]):
        tag.decompose()

    text = re.sub(
        r"\s+", " ", soup.get_text(" ", strip=True)
    )

    return text, links


def scrape_website(website, topic):
    if not valid_url(website):
        return [], ["Invalid official website URL."]

    visited = set()
    queue = [website]
    pages = []
    warnings = []

    keywords = TOPICS[topic]

    while queue and len(visited) < MAX_PAGES:
        current_url = queue.pop(0)

        if current_url in visited:
            continue

        visited.add(current_url)
        text, links = fetch_page(current_url)

        if text:
            pages.append({
                "url": current_url,
                "text": text
            })
        else:
            warnings.append(
                f"Could not read {current_url}"
            )

        base_domain = (
            urlparse(website).netloc.lower().replace("www.", "")
        )

        candidates = []

        for label, link in links:
            if link in visited:
                continue

            link_domain = (
                urlparse(link).netloc.lower().replace("www.", "")
            )

            if link_domain != base_domain:
                continue

            combined = f"{label} {link}".lower()

            score = sum(
                keyword in combined
                for keyword in keywords
            )

            if score:
                candidates.append((score, link))

        candidates.sort(reverse=True)

        for _, link in candidates:
            if link not in visited and link not in queue:
                queue.append(link)

    return pages, warnings


def show_relevant_text(pages, topic):
    keywords = TOPICS[topic]
    found = 0

    for page in pages:
        sentences = re.split(
            r"(?<=[.!?])\s+", page["text"]
        )

        matches = []

        for sentence in sentences:
            sentence = sentence.strip()

            if len(sentence) < 35:
                continue

            if any(
                keyword in sentence.lower()
                for keyword in keywords
            ):
                if sentence not in matches:
                    matches.append(sentence)

        if matches:
            found += len(matches)

            with st.container(border=True):
                st.markdown(
                    f"**Source:** [{page['url']}]"
                    f"({page['url']})"
                )

                for sentence in matches[:7]:
                    st.write("• " + sentence[:700])

    if found == 0:
        st.info(
            "No matching text detected. "
            "Open the official source to check manually."
        )


# ==================================================
# SIDEBAR — UPLOAD AND FILTERS
# ==================================================
with st.sidebar:
    st.markdown("## 🗂️ Workspace")
    uploaded_file = st.file_uploader(
        "Upload college Excel file",
        type=["xlsx", "xls"]
    )

if uploaded_file is None:
    st.markdown("## Welcome to CampusScope")

    col1, col2, col3 = st.columns(3)
    col1.metric("Directory", "Excel")
    col2.metric("Research", "Web")
    col3.metric("Export", "CSV")

    st.info(
        "Upload your engineering-colleges Excel workbook "
        "using the sidebar to start."
    )

    st.markdown("""
    ### Features
    - District and taluk filtering
    - College search
    - Principal contact details
    - Official website and map links
    - Website research
    - Filtered CSV download
    """)

    st.stop()


# ==================================================
# READ EXCEL FILE
# ==================================================
try:
    excel = pd.ExcelFile(uploaded_file)

    sheet = (
        "Engineering Colleges"
        if "Engineering Colleges" in excel.sheet_names
        else excel.sheet_names[0]
    )

    df = pd.read_excel(
        uploaded_file, sheet_name=sheet
    ).dropna(how="all").copy()

except Exception as error:
    st.error(f"Excel reading failed: {error}")
    st.stop()


name_col = find_column(
    df, ["Clg name", "College Name", "Institution Name", "College"]
)
district_col = find_column(df, ["dist", "district"])
city_col = find_column(df, ["city"])
taluk_col = find_column(df, ["TQ", "Taluk"])
website_col = find_column(df, ["website", "Official Website"])
email_col = find_column(df, ["principal email", "email"])
principal_col = find_column(df, ["principal name", "principal"])
address_col = find_column(df, ["address", "location"])
wiki_col = find_column(df, ["wikipedia"])
source_col = find_column(df, ["url", "source URL"])

if not name_col:
    st.error(
        "College name column not found. "
        f"Available columns: {list(df.columns)}"
    )
    st.stop()

df[name_col] = (
    df[name_col].fillna("").astype(str).str.strip()
)
df = df[df[name_col] != ""].copy()

if df.empty:
    st.warning("No college records found.")
    st.stop()


# ==================================================
# FILTER CONTROLS
# ==================================================
with st.sidebar:
    districts = (
        sorted(df[district_col].dropna().astype(str).unique())
        if district_col else []
    )

    taluks = (
        sorted(df[taluk_col].dropna().astype(str).unique())
        if taluk_col else []
    )

    selected_district = st.selectbox(
        "District", ["All districts"] + districts
    )

    selected_taluk = st.selectbox(
        "Taluk", ["All taluks"] + taluks
    )

    search = st.text_input(
        "Search college", placeholder="College name..."
    )

    missing_website = st.checkbox(
        "Only colleges without websites"
    )


filtered = df.copy()

if district_col and selected_district != "All districts":
    filtered = filtered[
        filtered[district_col].astype(str) == selected_district
    ]

if taluk_col and selected_taluk != "All taluks":
    filtered = filtered[
        filtered[taluk_col].astype(str) == selected_taluk
    ]

if search:
    filtered = filtered[
        filtered[name_col].str.contains(
            search, case=False, na=False
        )
    ]

if missing_website and website_col:
    filtered = filtered[
        ~filtered[website_col].apply(
            lambda value: valid_url(str(value))
        )
    ]


# ==================================================
# DASHBOARD METRICS
# ==================================================
total = len(df)

district_count = (
    df[district_col].nunique()
    if district_col else 0
)

website_count = (
    sum(valid_url(str(v)) for v in df[website_col].fillna(""))
    if website_col else 0
)

email_count = (
    sum(
        bool(str(v).strip())
        and str(v).lower() != "nan"
        for v in df[email_col].fillna("")
    )
    if email_col else 0
)

st.markdown("## 📊 Directory Overview")

m1, m2, m3, m4 = st.columns(4)
m1.metric("Total colleges", total)
m2.metric("Districts", district_count)
m3.metric("Websites listed", website_count)
m4.metric("Principal emails", email_count)

st.caption(
    f"{len(filtered)} college records match your filters."
)

directory_tab, profile_tab, research_tab = st.tabs([
    "🗂️ College Directory",
    "🏫 College Profile",
    "🔎 Website Research"
])


# ==================================================
# DIRECTORY TAB
# ==================================================
with directory_tab:
    st.markdown("### College Directory")

    st.dataframe(
        filtered,
        use_container_width=True,
        hide_index=True,
        height=420
    )

    st.download_button(
        "⬇️ Download filtered CSV",
        data=filtered.to_csv(
            index=False
        ).encode("utf-8-sig"),
        file_name="campusscope_colleges.csv",
        mime="text/csv",
        use_container_width=True
    )


if filtered.empty:
    st.warning(
        "No matching colleges. Change your filters."
    )
    st.stop()


# ==================================================
# SELECT COLLEGE
# ==================================================
selected_college = st.selectbox(
    "Select a college to inspect",
    filtered[name_col].drop_duplicates().tolist()
)

row = filtered[
    filtered[name_col] == selected_college
].iloc[0]

city = get_value(row, city_col) or "Not listed"
district = get_value(row, district_col) or "Not listed"
taluk = get_value(row, taluk_col) or "Not listed"
website = get_value(row, website_col)
email = get_value(row, email_col)
principal = get_value(row, principal_col)
address = get_value(row, address_col)
wiki = get_value(row, wiki_col)
source = get_value(row, source_col)


# ==================================================
# COLLEGE PROFILE TAB
# ==================================================
with profile_tab:
    st.markdown(f"### 🎓 {selected_college}")
    st.caption(f"{city} · {district} · {taluk}")

    c1, c2, c3 = st.columns(3)
    c1.metric(
        "Website",
        "Available" if valid_url(website) else "Missing"
    )
    c2.metric(
        "Principal name",
        "Available" if principal else "Not listed"
    )
    c3.metric(
        "Principal email",
        "Available" if email else "Not listed"
    )

    left, right = st.columns([2, 1])

    with left:
        st.markdown("#### Institution details")
        st.write("**City:**", city)
        st.write("**District:**", district)
        st.write("**Taluk:**", taluk)
        st.write("**Principal:**", principal or "Not listed")
        st.write("**Principal email:**", email or "Not listed")
        st.write("**Address:**", address or "Not listed")

        if valid_url(source):
            st.markdown(f"[Source record]({source})")

    with right:
        st.markdown("#### Quick links")

        if valid_url(website):
            st.link_button(
                "🌐 Official Website",
                website,
                use_container_width=True
            )

        st.link_button(
            "📍 Google Maps",
            maps_url(selected_college, address),
            use_container_width=True
        )

        if valid_url(wiki):
            st.link_button(
                "📚 Wikipedia",
                wiki,
                use_container_width=True
            )


# ==================================================
# WEBSITE RESEARCH TAB
# ==================================================
with research_tab:
    st.markdown("### Official Website Research")

    topic = st.selectbox(
        "Choose a research topic",
        list(TOPICS.keys())
    )

    st.caption(
        "The app reads accessible pages on the selected "
        "college website and identifies matching text."
    )

    if not valid_url(website):
        st.warning(
            "This college has no valid website URL in the Excel file."
        )

    else:
        if st.button(
            "🔍 Fetch College Information",
            type="primary",
            use_container_width=True
        ):
            with st.spinner(
                "Reading accessible website pages..."
            ):
                pages, warnings = scrape_website(
                    website, topic
                )

            st.session_state["pages"] = pages
            st.session_state["warnings"] = warnings
            st.session_state["college"] = selected_college
            st.session_state["topic"] = topic

        if (
            st.session_state.get("college") == selected_college
            and st.session_state.get("topic") == topic
        ):
            pages = st.session_state.get("pages", [])
            warnings = st.session_state.get("warnings", [])

            if pages:
                st.success(
                    f"Successfully read {len(pages)} page(s)."
                )

                show_relevant_text(pages, topic)

                with st.expander("View source pages"):
                    for page in pages:
                        st.markdown(
                            f"- [{page['url']}]({page['url']})"
                        )

                if warnings:
                    with st.expander("Pages not accessible"):
                        for warning in warnings:
                            st.write(warning)

            else:
                st.error(
                    "The website could not be read automatically. "
                    "It may block scraping or require JavaScript."
                )

                st.link_button(
                    "Open Official Website",
                    website
                )


# ==================================================
# FOOTER
# ==================================================
st.divider()

st.caption(
    "CampusScope | Karnataka College Intelligence | "
    "Verify extracted information against official sources."
)
