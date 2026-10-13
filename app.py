import re
from urllib.parse import urljoin, urlparse, quote_plus

import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup
from collections import Counter

# =========================================================
# 1. PAGE CONFIGURATION
# =========================================================
st.set_page_config(
    page_title="CampusScope | College Intelligence",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =========================================================
# 2. DASHBOARD DESIGN
# =========================================================
st.markdown("""
<style>
.stApp {
    background: #f4f8f6;
    color: #19352f;
}
.block-container {
    padding-top: 1.5rem;
    padding-bottom: 3rem;
}
h1, h2, h3, h4, p, label {
    color: #19352f;
}
[data-testid="stSidebar"] {
    background: #e7f1ec;
    border-right: 1px solid #cddfd5;
}
.hero {
    padding: 28px 32px;
    border-radius: 20px;
    background: linear-gradient(120deg, #103b32, #087f6b, #43a68a);
    margin-bottom: 22px;
}
.hero h1 {
    color: #ffffff !important;
    font-size: 2.35rem;
    margin: 0;
}
.hero p {
    color: #e3fff4 !important;
    font-size: 1rem;
}
div[data-testid="stMetric"] {
    background: #ffffff;
    border: 1px solid #d6e5dd;
    border-radius: 15px;
    padding: 15px;
}
div[data-testid="stMetric"] label,
div[data-testid="stMetricValue"] {
    color: #19352f !important;
}
.stButton > button,
.stDownloadButton > button,
.stLinkButton > a {
    background-color: #087f6b !important;
    color: #ffffff !important;
    border: 1px solid #087f6b !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
}
.stButton > button *,
.stDownloadButton > button *,
.stLinkButton > a * {
    color: #ffffff !important;
}
.stButton > button:hover,
.stDownloadButton > button:hover,
.stLinkButton > a:hover {
    background-color: #075e50 !important;
    border-color: #075e50 !important;
}
.stTextInput input,
.stSelectbox input {
    background: #ffffff !important;
    color: #19352f !important;
}
a {
    color: #087f6b !important;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero">
    <h1>🎓 CampusScope</h1>
    <p>Karnataka Engineering College Intelligence Platform</p>
    <p>Explore colleges, find contact emails, discover courses,
    and research official college websites.</p>
</div>
""", unsafe_allow_html=True)

# =========================================================
# 3. CONFIGURATION
# =========================================================
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/125.0 Safari/537.36"
    )
}
TIMEOUT = 12
MAX_PAGES = 8

TOPICS = {
    "Institution Profile": [
        "about", "history", "profile", "vision", "mission"
    ],
    "Departments and Courses": [
        "department", "departments", "course", "courses",
        "academics", "programmes", "programs", "engineering",
        "curriculum", "undergraduate", "postgraduate",
        "bachelor", "diploma", "syllabus"
    ],
    "Admissions and Intake": [
        "admission", "admissions", "intake", "seats",
        "eligibility", "fee", "fees"
    ],
    "Affiliation and Accreditation": [
        "affiliation", "autonomous", "accreditation",
        "university", "naac", "nba"
    ],
    "Placement Information": [
        "placement", "placements", "training",
        "career", "recruitment", "placement report"
    ],
    "Recruiters": [
        "recruiter", "recruiters", "companies",
        "company", "hiring", "placement"
    ],
}

EMAIL_REGEX = re.compile(
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
)


# =========================================================
# 4. GENERAL HELPERS
# =========================================================
def normalize(value):
    return re.sub(
        r"[^a-z0-9]+", "", str(value).lower().strip()
    )


def find_column(df, aliases):
    mapping = {normalize(c): c for c in df.columns}

    for alias in aliases:
        if normalize(alias) in mapping:
            return mapping[normalize(alias)]

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


def clean_text(text):
    return re.sub(r"\s+", " ", text or "").strip()


def google_maps_url(name, address=""):
    query = quote_plus(f"{name} {address}")
    return (
        "https://www.google.com/maps/search/"
        f"?api=1&query={query}"
    )


def same_domain(base_url, target_url):
    base = urlparse(base_url).netloc.lower().replace("www.", "")
    target = urlparse(target_url).netloc.lower().replace("www.", "")
    return base == target


# =========================================================
# 5. READ WEBSITE CONTENT PROPERLY
# =========================================================
def read_website(url):
    """
    Extract headings, paragraphs, list items and links separately.
    This avoids combining the entire homepage into one huge sentence.
    """
    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException:
        return None

    soup = BeautifulSoup(response.text, "html.parser")

    links = []

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()

        if href.startswith(("mailto:", "tel:", "javascript:")):
            continue

        absolute_url = urljoin(response.url, href)
        label = clean_text(anchor.get_text(" ", strip=True))

        if valid_url(absolute_url):
            links.append((label, absolute_url))

    # Remove non-content elements.
    for tag in soup([
        "script", "style", "nav", "footer",
        "header", "noscript", "svg", "iframe"
    ]):
        tag.decompose()

    blocks = []

    for tag in soup.find_all([
        "h1", "h2", "h3", "h4",
        "p", "li", "td", "th"
    ]):
        text = clean_text(tag.get_text(" ", strip=True))

        if len(text) >= 12:
            blocks.append({
                "tag": tag.name,
                "text": text,
                "url": response.url,
            })

    # Fallback if the page uses unusual HTML.
    if not blocks:
        text = clean_text(soup.get_text(" ", strip=True))
        if text:
            blocks.append({
                "tag": "text",
                "text": text,
                "url": response.url,
            })

    return {
        "url": response.url,
        "blocks": blocks,
        "links": links,
    }


# =========================================================
# 6. EMAIL DISCOVERY
# =========================================================
def discover_emails(website):
    """
    Search accessible official pages for email addresses.
    These are website contact emails, not automatically
    verified principal email addresses.
    """
    if not valid_url(website):
        return [], []

    contact_words = [
        "contact", "about", "administration",
        "principal", "office", "staff", "faculty"
    ]

    visited = set()
    queue = [website]
    emails = set()
    sources = []

    while queue and len(visited) < 5:
        url = queue.pop(0)

        if url in visited:
            continue

        visited.add(url)
        page = read_website(url)

        if not page:
            continue

        # Scan readable text.
        for block in page["blocks"]:
            found = EMAIL_REGEX.findall(block["text"])
            for email in found:
                emails.add(email.lower())
                sources.append((email.lower(), page["url"]))

        # Scan mailto links and relevant internal pages.
        for label, link in page["links"]:
            if link.lower().startswith("mailto:"):
                continue

            if link in visited:
                continue

            if not same_domain(website, link):
                continue

            combined = (label + " " + link).lower()

            if any(word in combined for word in contact_words):
                if link not in queue:
                    queue.append(link)

    return sorted(emails), sources


# =========================================================
# 7. TOPIC-SPECIFIC WEBSITE SCRAPER
# =========================================================
def score_link(label, url, keywords):
    combined = (label + " " + url).lower().replace("-", " ")
    return sum(keyword in combined for keyword in keywords)


def scrape_topic(website, topic):
    if not valid_url(website):
        return [], ["Invalid official website URL."]

    keywords = TOPICS[topic]
    queue = [(website, "Official homepage")]
    visited = set()
    pages = []
    warnings = []

    while queue and len(visited) < MAX_PAGES:
        url, reason = queue.pop(0)

        if url in visited:
            continue

        visited.add(url)
        page = read_website(url)

        if not page:
            warnings.append(f"Could not read {url}")
            continue

        pages.append({
            "url": page["url"],
            "reason": reason,
            "blocks": page["blocks"],
        })

        candidates = []

        for label, link in page["links"]:
            if link in visited:
                continue

            if not same_domain(website, link):
                continue

            # Ignore common files and non-page resources.
            path = urlparse(link).path.lower()

            if path.endswith((
                ".jpg", ".jpeg", ".png", ".gif",
                ".zip", ".doc", ".docx", ".xlsx"
            )):
                continue

            score = score_link(label, link, keywords)

            if score > 0:
                candidates.append((score, label, link))

        candidates.sort(key=lambda item: item[0], reverse=True)

        for score, label, link in candidates:
            if link not in visited and not any(
                queued_url == link for queued_url, _ in queue
            ):
                queue.append((
                    link,
                    f"Relevant page: {label or link}"
                ))

        # Put the most relevant candidate pages first.
        queue.sort(
            key=lambda item: score_link(
                item[1], item[0], keywords
            ),
            reverse=True,
        )

    return pages, warnings


def display_topic_results(pages, topic):
    keywords = TOPICS[topic]
    shown = set()
    total = 0

    for page in pages:
        relevant_blocks = []

        for block in page["blocks"]:
            text = block["text"]
            lowered = text.lower()

            if not any(keyword in lowered for keyword in keywords):
                continue

            # Ignore generic navigation labels.
            if len(text) < 25:
                continue

            if text in shown:
                continue

            shown.add(text)
            relevant_blocks.append(block)

        if relevant_blocks:
            total += len(relevant_blocks)

            with st.container(border=True):
                st.markdown(
                    f"**Source page:** [{page['url']}]"
                    f"({page['url']})"
                )

                for block in relevant_blocks[:15]:
                    if block["tag"].startswith("h"):
                        st.markdown(f"**{block['text']}**")
                    else:
                        st.write("• " + block["text"][:700])

    if total == 0:
        st.info(
            "No matching information was detected on accessible "
            "pages. Open the official course or department page "
            "to check manually."
        )


# =========================================================
# 8. EXCEL UPLOAD
# =========================================================
with st.sidebar:
    st.markdown("## 📂 College Directory")

    uploaded_file = st.file_uploader(
        "Upload your college Excel workbook",
        type=["xlsx", "xls"],
    )

if uploaded_file is None:
    st.markdown("## Welcome to CampusScope")

    c1, c2, c3 = st.columns(3)
    c1.metric("Directory", "Excel")
    c2.metric("Research", "Website")
    c3.metric("Export", "CSV")

    st.info(
        "Upload your engineering college workbook in the sidebar."
    )

    st.markdown("""
    ### Available features
    - District-dependent taluk filtering
    - Search by college name using Enter or Search
    - College contact details and website email discovery
    - Course and department research
    - Official website and Google Maps links
    - Download filtered college records
    """)

    st.stop()

try:
    excel = pd.ExcelFile(uploaded_file)

    sheet_name = (
        "Engineering Colleges"
        if "Engineering Colleges" in excel.sheet_names
        else excel.sheet_names[0]
    )

    df = pd.read_excel(
        uploaded_file,
        sheet_name=sheet_name,
    ).dropna(how="all").copy()

except Exception as error:
    st.error(f"Could not read Excel file: {error}")
    st.stop()


# =========================================================
# 9. RECOGNIZE YOUR EXCEL COLUMNS
# =========================================================
city_col = find_column(df, ["city"])
district_col = find_column(df, ["dist", "district"])
taluk_col = find_column(df, ["TQ", "taluk", "taluk/location"])

name_col = find_column(
    df, ["Clg name", "College Name", "Institution Name", "College"]
)

website_col = find_column(
    df, ["website", "Official Website", "Website URL"]
)

email_col = find_column(
    df, ["principal email", "principal_email", "email"]
)

principal_col = find_column(
    df, ["principal name", "principal"]
)

address_col = find_column(
    df, ["address", "location"]
)

wiki_col = find_column(
    df, ["wikipedia", "wikipedia url"]
)

source_col = find_column(
    df, ["url", "source url"]
)

if not name_col:
    st.error(
        "College name column not found. Available columns: "
        + ", ".join(map(str, df.columns))
    )
    st.stop()

df[name_col] = df[name_col].fillna("").astype(str).str.strip()
df = df[df[name_col] != ""].copy()

if df.empty:
    st.warning("No college records were found.")
    st.stop()


# =========================================================
# 10. DISTRICT -> TALUK FILTER
# =========================================================
with st.sidebar:
    st.markdown("---")
    st.markdown("### 🔎 Search and Filter")

    district_values = (
        sorted(df[district_col].dropna().astype(str).unique())
        if district_col else []
    )

    selected_district = st.selectbox(
        "Select district",
        ["All districts"] + district_values,
    )

    # Taluk options depend on selected district.
    if district_col and taluk_col and selected_district != "All districts":
        district_rows = df[
            df[district_col].astype(str) == selected_district
        ]

        taluk_values = sorted(
            district_rows[taluk_col]
            .dropna()
            .astype(str)
            .unique()
        )
    elif taluk_col:
        taluk_values = sorted(
            df[taluk_col].dropna().astype(str).unique()
        )
    else:
        taluk_values = []

    selected_taluk = st.selectbox(
        "Select taluk",
        ["All taluks"] + taluk_values,
    )

    # Search form: Enter and Search button both submit.
    with st.form("college_search_form"):
        search_text = st.text_input(
            "College name",
            placeholder="Type college name...",
        )

        search_submitted = st.form_submit_button(
            "🔍 Search Colleges",
            use_container_width=True,
        )

    if st.button("Reset filters", use_container_width=True):
        st.session_state.pop("cs_search", None)
        st.rerun()

    if search_submitted:
        st.session_state["cs_search"] = search_text.strip()

    current_search = st.session_state.get("cs_search", "")


# =========================================================
# 11. APPLY FILTERS
# =========================================================
filtered = df.copy()

if district_col and selected_district != "All districts":
    filtered = filtered[
        filtered[district_col].astype(str) == selected_district
    ]

if taluk_col and selected_taluk != "All taluks":
    filtered = filtered[
        filtered[taluk_col].astype(str) == selected_taluk
    ]

if current_search:
    filtered = filtered[
        filtered[name_col].str.contains(
            current_search,
            case=False,
            na=False,
            regex=False,
        )
    ]


# =========================================================
# 12. DASHBOARD METRICS
# =========================================================
total_colleges = len(df)

total_districts = (
    df[district_col].nunique()
    if district_col else 0
)

websites_listed = (
    sum(
        valid_url(value)
        for value in df[website_col].fillna("").astype(str)
    )
    if website_col else 0
)

emails_in_excel = (
    sum(
        bool(str(value).strip())
        and str(value).lower() != "nan"
        for value in df[email_col].fillna("")
    )
    if email_col else 0
)

st.markdown("## 📊 College Analytics")

m1, m2, m3, m4 = st.columns(4)

m1.metric("Total colleges", total_colleges)
m2.metric("Districts", total_districts)
m3.metric("Websites listed", websites_listed)
m4.metric("Emails in Excel", emails_in_excel)

st.caption(
    f"{len(filtered)} matching records · "
    f"Workbook sheet: {sheet_name}"
)


# =========================================================
# 13. DIRECTORY TABLE
# =========================================================
directory_tab, profile_tab, research_tab = st.tabs([
    "🗂️ Directory",
    "🏫 College Profile",
    "🔍 Website Research",
])

with directory_tab:
    st.markdown("### College records")

    if filtered.empty:
        st.warning(
            "No colleges match the current filters. "
            "Change your district, taluk or search."
        )
    else:
        st.dataframe(
            filtered,
            use_container_width=True,
            hide_index=True,
            height=420,
        )

        st.download_button(
            "⬇️ Download filtered CSV",
            data=filtered.to_csv(
                index=False
            ).encode("utf-8-sig"),
            file_name="campusscope_colleges.csv",
            mime="text/csv",
            use_container_width=True,
        )

if filtered.empty:
    st.stop()


# =========================================================
# 14. COLLEGE SELECTION
# =========================================================
college_options = filtered[name_col].drop_duplicates().tolist()

selected_college = st.selectbox(
    "Choose college to inspect",
    college_options,
    key="cs_selected_college",
)

row = filtered[
    filtered[name_col] == selected_college
].iloc[0]

city = get_value(row, city_col) or "Not listed"
district = get_value(row, district_col) or "Not listed"
taluk = get_value(row, taluk_col) or "Not listed"
website = get_value(row, website_col)
principal = get_value(row, principal_col)
email_from_excel = get_value(row, email_col)
address = get_value(row, address_col)
wiki = get_value(row, wiki_col)
source = get_value(row, source_col)


# =========================================================
# 15. COLLEGE PROFILE
# =========================================================
with profile_tab:
    st.markdown(f"### 🎓 {selected_college}")
    st.caption(f"{city} · {district} · {taluk}")

    a, b, c = st.columns(3)

    a.metric(
        "Official website",
        "Available" if valid_url(website) else "Missing",
    )

    b.metric(
        "Principal name",
        "Listed" if principal else "Not listed",
    )

    c.metric(
        "Principal email",
        "Listed" if email_from_excel else "Not listed",
    )

    left, right = st.columns([2, 1])

    with left:
        st.markdown("#### College details")

        st.write("**City:**", city)
        st.write("**District:**", district)
        st.write("**Taluk:**", taluk)
        st.write("**Principal name:**", principal or "Not listed in Excel")
        st.write(
            "**Principal email:**",
            email_from_excel or "Not listed in Excel",
        )
        st.write("**Address:**", address or "Not listed in Excel")

        if valid_url(source):
            st.markdown(f"[Source record]({source})")

    with right:
        st.markdown("#### Quick links")

        if valid_url(website):
            st.link_button(
                "🌐 Official Website",
                website,
                use_container_width=True,
            )

        st.link_button(
            "📍 Google Maps",
            google_maps_url(selected_college, address),
            use_container_width=True,
        )

        if valid_url(wiki):
            st.link_button(
                "📚 Wikipedia",
                wiki,
                use_container_width=True,
            )

    st.markdown("#### Find website contact emails")

    st.caption(
        "This checks accessible official pages for email addresses. "
        "A general contact email is not automatically the principal's email."
    )

    if valid_url(website):
        if st.button(
            "✉️ Find Contact Emails",
            key="find_contact_emails",
            use_container_width=True,
        ):
            with st.spinner("Checking official contact pages..."):
                found_emails, email_sources = discover_emails(website)

            st.session_state["cs_emails"] = found_emails
            st.session_state["cs_email_sources"] = email_sources
            st.session_state["cs_email_college"] = selected_college

        if st.session_state.get("cs_email_college") == selected_college:
            found_emails = st.session_state.get("cs_emails", [])
            email_sources = st.session_state.get("cs_email_sources", [])

            if found_emails:
                st.success(
                    f"Found {len(found_emails)} email address(es) "
                    "on accessible official pages."
                )

                for email in found_emails:
                    st.write(f"✉️ {email}")

                with st.expander("Email source pages"):
                    for email, email_url in email_sources:
                        st.markdown(f"- `{email}` — [{email_url}]({email_url})")
            else:
                st.info(
                    "No email address was detected. The website may "
                    "load its contact information using JavaScript."
                )


# =========================================================
# 16. DEPARTMENTS, COURSES AND OTHER RESEARCH
# =========================================================
with research_tab:
    st.markdown("### 🔍 Official Website Research")

    topic = st.selectbox(
        "Select information category",
        list(TOPICS.keys()),
        key="cs_research_topic",
    )

    st.caption(
        "The scraper prioritizes relevant internal pages and displays "
        "matching headings and text blocks separately."
    )

    if not valid_url(website):
        st.warning(
            "This college has no valid official website URL in the workbook."
        )
    else:
        if st.button(
            "Fetch Information",
            type="primary",
            use_container_width=True,
        ):
            with st.spinner(
                f"Searching official pages for {topic.lower()}..."
            ):
                pages, warnings = scrape_topic(website, topic)

            st.session_state["cs_pages"] = pages
            st.session_state["cs_warnings"] = warnings
            st.session_state["cs_topic_college"] = selected_college
            st.session_state["cs_topic_name"] = topic

        if (
            st.session_state.get("cs_topic_college") == selected_college
            and st.session_state.get("cs_topic_name") == topic
        ):
            pages = st.session_state.get("cs_pages", [])
            warnings = st.session_state.get("cs_warnings", [])

            if pages:
                st.success(
                    f"Read {len(pages)} accessible page(s)."
                )

                display_topic_results(pages, topic)

                with st.expander("View source pages"):
                    for page in pages:
                        st.markdown(
                            f"- [{page['reason']}]({page['url']})"
                        )

                if warnings:
                    with st.expander("Pages that could not be read"):
                        for warning in warnings:
                            st.write("• " + warning)
            else:
                st.error(
                    "The website could not be read automatically. "
                    "It may block requests or require JavaScript."
                )

                st.link_button(
                    "Open official website",
                    website,
                )


# =========================================================
# 17. FOOTER
# =========================================================
st.divider()

st.caption(
    "CampusScope | Karnataka College Intelligence | "
    "Verify information against the original official source."
)
