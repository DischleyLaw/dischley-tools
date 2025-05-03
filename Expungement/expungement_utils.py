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
    print(f"Document saved at: {output_path}")



# Function to extract expungement data from a PDF file
def extract_expungement_data(filepath):
    text = ""

    # First try regular PDF text extraction
    try:
        reader = PdfReader(filepath)
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text
    except Exception:
        pass



    # Extract values from text using regex
    fields = {
        "name": re.search(r"(?:Defendant(?: Name)?|Name\s*of\s*Defendant)\s*:\s*(.+)", text),
        "dob": re.search(r"(?:DOB|Date\s*of\s*Birth)\s*:\s*(\d{2}/\d{2}/\d{4})", text),
        "officer_name": re.search(r"Complainant\s*:\s*([\w\s.,'-]+)", text),
        "arrest_date": re.search(r"Arrest Date\s*:\s*(\d{2}/\d{2}/\d{4})", text),
        "dispo_date": re.search(r"Disposition Date\s*:\s*(\d{2}/\d{2}/\d{4})", text),
        "charge_name": re.search(r"Charge\s*:\s*(.+?)\s*OffenseTracking", text),
        "code_section": re.search(r"Code\s*Section\s*:\s*([\d\.]+-\d+)", text),
        "otn": re.search(r"OffenseTracking/Processing#\s*:\s*(\S+)", text),
        "case_no": re.search(r"Case No\s*:\s*(\S+)", text),
        "final_dispo": re.search(r"Final\s*Disposition\s*:\s*([^\n\r]+)", text),
        "court_dispo": re.search(r"(?i)(General District Court|Circuit Court|Juvenile and Domestic Relations District Court)\s+Online Case Information System\s*-\s*(.+?)\n", text),
    }

    result = {}
    for key, match in fields.items():
        if match:
            val = match.group(1).strip()
            if key == "name":
                val = re.split(r"Amended|Case No|DOB|OTN", val)[0].strip().title()
                result["name_arrest"] = val
            if "date" in key:
                try:
                    val = datetime.strptime(val, "%m/%d/%Y").strftime("%Y-%m-%d")
                except ValueError:
                    pass
            if key == "charge_name":
                val = re.split(r"OffenseTracking|Code\s*Section|Case\s*Type", val)[0].strip()
            if key == "court_dispo":
                parts = match.groups()
                val = f"{parts[1]} {parts[0]}"
            if key == "officer_name":
                val = re.split(r"Amended|Hearing|Disposition", val)[0].strip()
                parts = val.split(",", 1)
                if len(parts) == 2:
                    last, first = parts
                    val = f"{last.strip().title()}, {first.strip().title()}"
                else:
                    val = val.title()
            if key == "otn":
                val = re.sub(r"Summons.*", "", val).strip()
            if key == "final_dispo":
                val = re.split(r"Sentence|Time|Probation|Fine|Costs", val)[0].strip()
            if key == "code_section":
                val = f"Va. Code § {val}"
            result[key] = val

    print("Extracted fields:", result)
    return result
