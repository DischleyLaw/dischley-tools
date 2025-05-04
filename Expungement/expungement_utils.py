import os
from docx import Document

# Additional imports for PDF parsing and regex
import re
import pdfplumber
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
def extract_expungement_data(filepath, case_index=None):
    text = ""

    # First try regular PDF text extraction
    import logging
    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text

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
            r"Charge\s*:\s*([^\n\r]+)"
        ]),
        ("code_section", [
            r"Code\s*Section\s*:\s*([\d\.]+-\d+)"
        ]),
        ("otn", [
            r"OffenseTracking/Processing#\s*:\s*(\S+)"
        ]),
        ("case_no", [
            r"Case\s*(?:No|#|Number)\s*[:\-]?\s*([A-Z0-9\-]+)",
            r"Case\s*#\s*:\s*(\S+)",
            r"Case #:\s*(GC\d{8}-\d{2})",
        ]),
        ("final_dispo", [
            r"Disposition:\s*([A-Z\s]+)"
        ]),
        ("court_dispo", [
            r"^([A-Z][a-z]+ (County|City) (Juvenile and Domestic Relations District Court|General District Court|Circuit Court))",
            r"Return to Search Results\s*([\w\s]+(?:General District Court|Circuit Court|Juvenile and Domestic Relations District Court))",
            r"(\w+\s+(?:County|City)\s+(?:General District Court|Circuit Court|Juvenile and Domestic Relations District Court))",
            r"((?:General District Court|Circuit Court|Juvenile and Domestic Relations District Court)\s*[-–]?\s*\w+)",
            r"(\w+\s+Juvenile and Domestic Relations District Court)",
            r"(Fairfax County Juvenile and Domestic Relations District Court)"
        ]),
        # Additional patterns for Virginia Judiciary Online Case Information System PDF output
        ("dob", [
            r"DOB:\s*(\d{2}/\d{2}/\*{4})"
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
        val = match.group(1).strip() if match else ""
        # arrest_date fallback logic: move fallback outside of "if match"
        if key == "arrest_date":
            if val:
                val = val.replace("&", "&amp;")
                if case_index is not None:
                    result[f"case_{case_index}_{key}"] = val
                else:
                    result[key] = val
            else:
                # Fallback logic if val is empty: search entire text for arrest date-like patterns
                arrest_fallback = re.search(r"Arrest(?:ed)? Date\s*[:\-]?\s*(\d{2}/\d{2}/\d{4})", text, re.IGNORECASE)
                if arrest_fallback:
                    fallback_val = arrest_fallback.group(1).strip()
                    fallback_val = fallback_val.replace("&", "&amp;")
                    if case_index is not None:
                        result[f"case_{case_index}_{key}"] = fallback_val
                    else:
                        result[key] = fallback_val
                else:
                    if case_index is not None:
                        result[f"case_{case_index}_{key}"] = ""
                    else:
                        result[key] = ""
            continue
        if match:
            # val already set above
            if key == "name":
                if case_index is not None:
                    # skip assigning name for additional cases
                    continue
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
                val = formatted_name
                val = val.replace("&", "&amp;")
                result[key] = val
                result["name_arrest"] = val
            elif key == "dob":
                if case_index is not None:
                    # skip assigning dob for additional cases
                    continue
                try:
                    val = datetime.strptime(val, "%m/%d/%Y").strftime("%Y-%m-%d")
                except ValueError:
                    pass
                val = val.replace("&", "&amp;")
                result[key] = val
            elif key == "charge_name":
                val = re.split(r"Offense Tracking|OffenseTracking|Process|Code\s*Section|Case\s*Type", val)[0].strip()
                # Capitalize each word like a name
                val = " ".join(word.capitalize() for word in val.split())
                val = val.replace("&", "&amp;")
                if case_index is not None:
                    result[f"case_{case_index}_{key}"] = val
                else:
                    result[key] = val
            elif key == "court_dispo":
                val = val.strip()
                val = val.replace('\n', ' ').strip()
                val = val.replace("&", "&amp;")
                if case_index is not None:
                    result[f"case_{case_index}_{key}"] = val
                else:
                    result[key] = val
                # Fallback for court_dispo if not matched and case_index is not None
                if not val and case_index is not None:
                    fallback_court = re.search(r"([A-Z][a-z]+ (County|City) Juvenile and Domestic Relations District Court)", text)
                    if fallback_court:
                        result[f"case_{case_index}_{key}"] = fallback_court.group(1).strip()
            elif key == "officer_name":
                val = re.split(r"Amended|Hearing|Disposition", val)[0].strip()
                parts = val.split(",", 1)
                if len(parts) == 2:
                    last, first = parts
                    val = f"{last.strip().title()}, {first.strip().title()}"
                else:
                    val = val.title()
                val = val.replace("&", "&amp;")
                if case_index is not None:
                    result[f"case_{case_index}_{key}"] = val
                else:
                    result[key] = val
            elif key == "otn":
                val = re.sub(r"Summons.*", "", val).strip()
                val = re.split(r"Case", val)[0].strip()
                val = val.replace("&", "&amp;")
                if case_index is not None:
                    result[f"case_{case_index}_{key}"] = val
                else:
                    result[key] = val
            elif key == "final_dispo":
                val = re.split(r"Sentence|Time|Probation|Fine|Costs", val)[0].strip()
                # Capitalize each word like a name
                val = " ".join(word.capitalize() for word in val.split())
                val = val.replace("&", "&amp;")
                if case_index is not None:
                    result[f"case_{case_index}_{key}"] = val
                else:
                    result[key] = val
            elif key == "code_section":
                val = re.split(r"Charge", val)[0].strip()
                if not val.startswith("Va. Code"):
                    val = f"Va. Code § {val}"
                val = val.replace("&", "&amp;")
                if case_index is not None:
                    result[f"case_{case_index}_{key}"] = val
                else:
                    result[key] = val
            elif key == "dispo_date":
                if case_index is not None:
                    val = val.replace("&", "&amp;")
                    result[f"case_{case_index}_{key}"] = val
                else:
                    val = val.replace("&", "&amp;")
                    result[key] = val
                # Fallback logic if val is empty: collect all hearing dates in Hearing Information section
                if not val:
                    hearing_section = re.search(r"Hearing Information(.*?)Disposition Information", text, re.DOTALL | re.IGNORECASE)
                    if hearing_section:
                        dates = re.findall(r"\b(\d{2}/\d{2}/\d{4})\b", hearing_section.group(1))
                        if dates:
                            val_dates = ", ".join(dates)
                            if case_index is not None:
                                result[f"case_{case_index}_{key}"] = val_dates
                            else:
                                result[key] = val_dates
            else:
                val = val.replace("&", "&amp;")
                if case_index is not None:
                    result[f"case_{case_index}_{key}"] = val
                else:
                    result[key] = val
        else:
            if key == "officer_name":
                # Fallback: try alternate officer/complainant extraction if main pattern fails
                if not val:
                    fallback = re.search(r"Complainant\s*[:\-]?\s*([A-Z][a-z]+,\s*[A-Z]\s*[A-Z]?)", text)
                    if fallback:
                        val = fallback.group(1).strip()
                parts = val.split(",", 1)
                if len(parts) == 2:
                    last, first = parts
                    val = f"{last.strip().title()}, {first.strip().title()}"
                else:
                    val = val.title()
                val = val.replace("&", "&amp;")
                if case_index is not None:
                    result[f"case_{case_index}_{key}"] = val
                else:
                    result[key] = val
            elif key != "arrest_date":  # already handled above
                if case_index is not None:
                    if key in ["name", "name_arrest", "dob"]:
                        # Skip assigning these keys for additional cases
                        pass
                    else:
                        result[f"case_{case_index}_{key}"] = ""
                else:
                    result[key] = ""


    # Final fallback for court_dispo: extract the court name preceding "(details)" from the top of the first page of the PDF.
    if case_index is not None and f"case_{case_index}_court_dispo" not in result:
        try:
            with pdfplumber.open(filepath) as pdf:
                first_page_text = pdf.pages[0].extract_text()
                if first_page_text:
                    for line in first_page_text.split("\n"):
                        if "(details" in line.lower():
                            court_name = line.split("(details")[0].strip()
                            if "court" in court_name.lower():
                                result[f"case_{case_index}_court_dispo"] = court_name
                            break
        except Exception as e:
            logging.warning(f"Fallback court_dispo scan failed: {e}")

    # If case_index is set, remove any keys without the case_{case_index}_ prefix and skip name, dob, and name_arrest keys
    if case_index is not None:
        filtered_result = {}
        for k, v in result.items():
            if k.startswith(f"case_{case_index}_"):
                filtered_result[k] = v
        return filtered_result

    return {"status": "ok", "data": result}
