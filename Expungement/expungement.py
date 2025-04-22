import os
os.environ['TK_SILENCE_DEPRECATION'] = '1'
import tkinter as tk
from tkinter import filedialog, ttk
from docx import Document
from Expungement.expungement_utils import populate_document, prosecutor_info

def generate_document():
    template_path = filedialog.askopenfilename(title="Select Template", filetypes=[("Word files", "*.docx")])
    output_path = filedialog.asksaveasfilename(defaultextension=".docx", filetypes=[("Word files", "*.docx")])
    county = county_combo.get()
    final_disposition = dismissal_combo.get()
    expungement_type = expungement_combo.get()

    # Expungement clause logic
    if expungement_type == "Expungement of Right":
        expungement_clause = "The Petitioner has no prior criminal record, the aforementioned arrest was a misdemeanor offense, and the Commonwealth cannot show good cause to the contrary as to why the petition should not be granted."
        manifest_injustice = ""
    elif expungement_type == "Manifest Injustice":
        manifest_injustice = manifest_entry.get()
        expungement_clause = f"The continued existence and possible dissemination of information relating to the charge(s) set forth herein has caused, and may continue to cause, circumstances which constitute a manifest injustice to the Petitioner, and the Commonwealth cannot show good cause to the contrary as to why the petition should not be granted. (to wit: {manifest_injustice})."
    else:
        expungement_clause = ""
        manifest_injustice = ""

    # Automatically fill prosecutor details based on county
    prosecutor = prosecutor_info[county]["name"]
    prosecutor_title = prosecutor_info[county]["title"]
    prosecutor_address1 = prosecutor_info[county]["address1"]
    prosecutor_address2 = prosecutor_info[county]["address2"]

    replacements = {key: entry.get() for key, entry in entries.items()}
    replacements["{NAME}"] = replacements["{NAME}"].upper()
    replacements["{COUNTY}"] = county.upper()
    replacements["{County2}"] = county.title()
    replacements["{Prosecutor}"] = prosecutor
    replacements["{Prosecutor Title}"] = prosecutor_title
    replacements["{Prosecutor Address 1}"] = prosecutor_address1
    replacements["{Prosecutor Address 2}"] = prosecutor_address2
    replacements["{Final Disposition}"] = final_disposition
    replacements["{Dispo Date}"] = entries["{Dispo Date}"].get()
    replacements["{Type of Expungement}"] = expungement_clause

    if template_path and output_path:
        populate_document(template_path, output_path, replacements)

if __name__ == "__main__":
    root = tk.Tk()
    root.title("Expungement Petition Generator")
    root.geometry("600x900")

    # Create a canvas with a scrollbar
    main_frame = tk.Frame(root)
    main_frame.pack(fill="both", expand=True)

    canvas = tk.Canvas(main_frame)
    scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
    scrollable_frame = tk.Frame(canvas)

    # Configure the scrollbar
    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(
            scrollregion=canvas.bbox("all")
        )
    )

    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    def _on_mouse_wheel(event):
        canvas.yview_scroll(-1 * int((event.delta / 120)), "units")

    canvas.bind_all("<MouseWheel>", _on_mouse_wheel)

    fields = ["{NAME}", "{DOB}", "{Name at Arrest}", "{Arrest Date}", "{Officer Name}", "{Police Department}", "{Charge Name}", "{Code Section}", "{VCC Code}", "{OTN}", "{Court of Final Dispo}", "{Case No}", "{Dispo Date}"]
    entries = {}

    # Drop-down for County
    county_label = tk.Label(scrollable_frame, text="Select County:")
    county_label.pack()
    county_combo = ttk.Combobox(scrollable_frame, values=list(prosecutor_info.keys()))
    county_combo.pack(pady=5)

    # Drop-down for Dismissal Basis
    dismissal_label = tk.Label(scrollable_frame, text="Select Final Disposition:")
    dismissal_label.pack()
    dismissal_combo = ttk.Combobox(scrollable_frame, values=["Nolle Prosequi", "Not Guilty", "Otherwise Dismissed"])
    dismissal_combo.pack(pady=5)

    # Drop-down for Expungement Type
    expungement_label = tk.Label(scrollable_frame, text="Select Type of Expungement:")
    expungement_label.pack()
    expungement_combo = ttk.Combobox(scrollable_frame, values=["Expungement of Right", "Manifest Injustice"])
    expungement_combo.pack(pady=5)

    # Manifest Injustice Entry
    manifest_frame = tk.Frame(scrollable_frame)
    manifest_label = tk.Label(manifest_frame, text="Manifest Injustice Details:")
    manifest_entry = tk.Entry(manifest_frame, width=50)
    manifest_label.pack(side="left")
    manifest_entry.pack(side="left", padx=5)
    manifest_frame.pack(pady=5, fill="x")

    for field in fields:
        frame = tk.Frame(scrollable_frame)
        label = tk.Label(frame, text=field.replace("_", " ").title())
        label.pack(side="left", padx=5, pady=5)
        entry = tk.Entry(frame, width=50)
        entry.pack(side="left", padx=5, pady=5)
        frame.pack(pady=2, fill="x")
        entries[field] = entry

    submit_btn = tk.Button(scrollable_frame, text="Generate Document", command=generate_document)
    submit_btn.pack(pady=20)

    case_count = 1
    additional_cases = []

    def add_case():
        nonlocal case_count
        case_count += 1
        frame = tk.Frame(scrollable_frame)
        case_label = tk.Label(frame, text=f"Additional Case {case_count}")
        case_label.pack(pady=5)

        new_case_fields = ["{Arrest Date}", "{Officer Name}", "{Police Department}", "{Charge Name}", "{Code Section}", "{VCC Code}", "{OTN}", "{Court of Final Dispo}", "{Case No}", "{Dispo Date}"]
        case_entries = {}
        for field in new_case_fields:
            entry_frame = tk.Frame(frame)
            label = tk.Label(entry_frame, text=field.replace("_", " ").title())
            label.pack(side="left", padx=5, pady=5)
            entry = tk.Entry(entry_frame, width=50)
            entry.pack(side="left", padx=5, pady=5)
            entry_frame.pack(pady=2, fill="x")
            case_entries[field] = entry
        frame.pack(pady=5, fill="x")
        additional_cases.append(case_entries)

    root.mainloop()
