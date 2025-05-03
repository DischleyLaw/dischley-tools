import fitz
import json

pdf_path = "Statute_Listing.pdf"
doc = fitz.open(pdf_path)

entries = []

for page_num, page in enumerate(doc):
    # Skip cover pages
    if page_num < 6:
        continue
    text = page.get_text()
    lines = text.split("\n")
    for line in lines:
        parts = line.strip().split(maxsplit=2)
        if len(parts) == 3:
            statute, vcc_code, description = parts
            entries.append({
                "statute": statute,
                "code": vcc_code,
                "description": description
            })

print(f"Total entries parsed: {len(entries)}")

with open("vcc_codes.json", "w") as f:
    json.dump(entries, f, indent=2)