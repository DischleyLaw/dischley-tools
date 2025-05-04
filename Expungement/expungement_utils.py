import os
from docx import Document

# Additional imports for PDF parsing and regex
import re
from PyPDF2 import PdfReader
from datetime import datetime

# Predefined prosecutor information based on county
prosecutor_info = {
    "Fairfax County": {"name": "Steve Descano, Esq.", "title": "Fairfax County Commonwealth's Attorney", "address1": "4110 Chain Bridge Road", "address2": "Fairfax, VA 22030"},
    "Arlington County": {"name": "Parisa Tafti, Esq.", "title": "Arlington County Commonwealth's Attorney", "address1": "1425 N. Courthouse Rd", "address2": "Arlington, VA 22201"},
    "Prince William County": {"name": "Amy Ashworth, Esq.", "title": "Prince William County Commonwealth's Attorney", "address1": "9311 Lee Ave", "address2": "Manassas, VA 20110"},
    "Loudoun County": {"name": "Robert Anderson, Esq.", "title": "Loudoun County Commonwealth's Attorney", "address1": "20 E Market St", "address2": "Leesburg, VA 20176"},
    "City of Alexandria": {"name": "Bryan Porter, Esq.", "title": "Alexandria City Commonwealth's Attorney", "address1": "520 King Street", "address2": "Alexandria, VA 22314"},
    "Stafford County": {"name": "Eric Olsen, Esq.", "title": "Stafford County Commonwealth's Attorney", "address1": "", "address2": ""},
    "Fauquier County": {"name": "Scott Hook, Esq.", "title": "Fauquier County Commonwealth's Attorney", "address1": "29 Ashby Street", "address2": "Warrenton, VA 20186"}
}

def populate_document(template_path, output_path, replacements):
    doc = Document(template_path)
    for paragraph in doc.paragraphs:
        for key, value in replacements.items():
            if key in paragraph.text:
                paragraph.text = paragraph.text.replace(key, value)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for key, value in replacements.items():
                    if key in cell.text:
                        cell.text = cell.text.replace(key, value)
    doc.save(output_path)



# Function to extract expungement data from a PDF file
def extract_expungement_data(filepath):
    text = ""

    # First try regular PDF text extraction
    import logging
    try:
        reader = PdfReader(filepath)
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text
    except Exception as e:
        logging.warning(f"PDF parsing failed: {e}")

    field_patterns = [
        ("name", [
            r"Defendant:\s*([^\n\r]+)"
        ]),
        ("dob", [
            r"DOB:\s*(\d{2}/\d{2}/\d{4})",
            r"DOB:\s*(\d{2}/\d{2}/\*{4})"
        ]),
        ("officer_name", [
            r"Complainant\s*:\s*([\w\s.,'-]+)"
        ]),
        ("arrest_date", [
            r"Arrest Date\s*:\s*(\d{2}/\d{2}/\d{4})"
        ]),
        ("dispo_date", [
            r"Disposition Date\s*:\s*(\d{2}/\d{2}/\d{4})"
        ]),
        ("charge_name", [
            r"Charge\s*:\s*(.+?)\s*OffenseTracking"
        ]),
        ("code_section", [
            r"Code\s*Section\s*:\s*([\d\.]+-\d+)"
        ]),
        ("otn", [
            r"OffenseTracking/Processing#\s*:\s*(\S+)"
        ]),
        ("case_no", [
            r"Case No\s*:\s*(\S+)"
        ]),
        ("final_dispo", [
            r"Disposition:\s*([A-Z\s]+)"
        ]),
        ("court_dispo", [
            r"Return to Search Results\s*([A-Za-z\s]+(?:County|City)?(?: General District Court| Circuit Court))"
        ]),
        # Additional patterns for Virginia Judiciary Online Case Information System PDF output
        ("case_no", [
            r"Case #:\s*(GC\d{8}-\d{2})"
        ]),
        ("dob", [
            r"DOB:\s*(\d{2}/\d{2}/\*{4})"
        ]),
        ("charge_name", [
            r"Charge:\s*(.*?)\s*Offense Tracking"
        ]),
        ("code_section", [
            r"Code Section:\s*(.+)"
        ]),
        ("officer_name", [
            r"Complainant:\s*([^\n\r]+)"
        ]),
        ("arrest_date", [
            r"Arrest Date:\s*(\d{2}/\d{2}/\d{4})"
        ]),
        ("final_dispo", [
            r"Disposition:\s*(NOLLE PROSEQUI|DISMISSED|GUILTY|NOT GUILTY)"
        ]),
        ("otn", [
            r"Offense Tracking/Process #:\s*(\S+)"
        ])
    ]

    result = {}
    for key, patterns in field_patterns:
        match = None
        for pattern in patterns:
            match = re.search(pattern, text, re.MULTILINE)
            if match:
                break
        if match:
            val = match.group(1).strip()
            if key == "name":
                # Handle names in format: Last, First Middle
                if "," in val:
                    last, rest = val.split(",", 1)
                    name_parts = rest.strip().split()
                    formatted_name = " ".join(name_parts + [last.strip()])
                else:
                    formatted_name = val.strip()
                # Convert each word to title case
                if formatted_name:
                    formatted_name = " ".join(word.capitalize() for word in formatted_name.split())
                result["name"] = formatted_name
                result["name_arrest"] = formatted_name
            elif key == "dob":
                try:
                    val = datetime.strptime(val, "%m/%d/%Y").strftime("%Y-%m-%d")
                except ValueError:
                    pass
                result[key] = val
            elif key == "charge_name":
                val = re.split(r"OffenseTracking|Code\s*Section|Case\s*Type", val)[0].strip()
                # Capitalize each word like a name
                val = " ".join(word.capitalize() for word in val.split())
                result[key] = val
            elif key == "court_dispo":
                val = val.strip()
                result[key] = val
            elif key == "officer_name":
                val = re.split(r"Amended|Hearing|Disposition", val)[0].strip()
                parts = val.split(",", 1)
                if len(parts) == 2:
                    last, first = parts
                    val = f"{last.strip().title()}, {first.strip().title()}"
                else:
                    val = val.title()
                result[key] = val
            elif key == "otn":
                val = re.sub(r"Summons.*", "", val).strip()
                val = re.split(r"Case", val)[0].strip()
                result[key] = val
            elif key == "final_dispo":
                val = re.split(r"Sentence|Time|Probation|Fine|Costs", val)[0].strip()
                # Capitalize each word like a name
                val = " ".join(word.capitalize() for word in val.split())
                result[key] = val
            elif key == "code_section":
                val = re.split(r"Charge", val)[0].strip()
                result[key] = val
            elif key == "dispo_date":
                result[key] = val
                # Fallback logic if val is empty: collect all hearing dates in Hearing Information section
                if not val:
                    hearing_section = re.search(r"Hearing Information(.*?)Disposition Information", text, re.DOTALL | re.IGNORECASE)
                    if hearing_section:
                        dates = re.findall(r"\b(\d{2}/\d{2}/\d{4})\b", hearing_section.group(1))
                        if dates:
                            result[key] = ", ".join(dates)
            else:
                result[key] = val
        else:
            result[key] = ""

    return result


