from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash, jsonify
from flask_cors import CORS

# --- Expungement Data Extraction Import ---
from Expungement.expungement_utils import extract_expungement_data

# Ensure app is defined only once and before any @app.route decorators
app = Flask(__name__)
CORS(app)


# --- CLIO CONTACT SEARCH ROUTE ---
@app.route("/clio/contact-search")
def clio_contact_search():
    query = request.args.get("query", "").strip()
    if not query:
        return jsonify({"data": []})

    try:
        access_token = get_valid_token()
        headers = {"Authorization": f"Bearer {access_token}"}
        url = f"https://app.clio.com/api/v4/contacts?query={query}"
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            contacts = []
            for contact in response.json().get("data", []):
                if "name" in contact:
                    contacts.append({
                        "id": contact.get("id"),
                        "name": contact.get("name")
                    })
            return jsonify({"data": contacts})
        else:
            return jsonify({"error": "Failed to fetch contacts", "status": response.status_code}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Expungement Upload Batch Route ---
@app.route('/expungement/upload_batch', methods=['POST'])
def expungement_upload_batch():
    # Accept files with any key starting with "file", e.g., "file", "file_1", "file_2", etc.
    files = [f for key, f in request.files.items() if key.startswith("file")]
    if not files:
        return jsonify({"error": "No files uploaded"}), 400

    from Expungement.expungement_utils import extract_multiple_cases_data
    os.makedirs("temp", exist_ok=True)
    extracted_cases = extract_multiple_cases_data(files[:20])
    
    response_data = {}
    for idx, extracted in enumerate(extracted_cases):
        case_data = {
            "arrest_date": extracted.get("arrest_date", ""),
            "officer_name": extracted.get("officer_name", ""),
            "police_department": extracted.get("police_department", ""),
            "charge_name": extracted.get("charge_name", ""),
            "code_section": extracted.get("code_section", ""),
            "vcc_code": extracted.get("vcc_code", ""),
            "otn": extracted.get("otn", ""),
            "court_dispo": extracted.get("court_dispo", ""),
            "case_no": extracted.get("case_no", ""),
            "dispo_date": extracted.get("dispo_date", "")
        }
        response_data[f"case_{idx+1}"] = case_data

    return jsonify(response_data), 200

import subprocess
import os
from datetime import datetime, timedelta
import subprocess
import os
from datetime import datetime, timedelta

# --- No-Cache Headers Registration ---
def register_after_request(app):
    @app.after_request
    def add_no_cache_headers(response):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response


import logging
from flask.logging import default_handler


# --- Login Required Decorator ---
# This decorator is now a no-op; login is not required for any routes.
def login_required(f):
    return f

app.logger.removeHandler(default_handler)
logging.basicConfig(level=logging.DEBUG)
app.logger.setLevel(logging.DEBUG)


# --- Expungement Generator GET and POST Route ---
@app.route("/expungement/generate", methods=["GET", "POST"])
def generate_expungement():
    if request.method == "POST":
        form_data = request.form.to_dict()
        # --- Merge autofill data from session if present ---
        autofill_data = session.pop("expungement_autofill_data", None)
        if autofill_data:
            app.logger.debug(f"Autofill data from session: {autofill_data}")
            form_data.update(autofill_data)
            form_data["name"] = form_data.get("name", autofill_data.get("name", ""))
            form_data["full_legal_name"] = form_data["name"]
            form_data["dob"] = form_data.get("dob", autofill_data.get("dob", ""))
            form_data["name_arrest"] = form_data.get("name_arrest", autofill_data.get("name_arrest", form_data.get("name", "")))
            raw_dispo = form_data.get("final_dispo", autofill_data.get("final_dispo", ""))
            form_data["final_dispo"] = raw_dispo.split("Sentence")[0].strip() if "Sentence" in raw_dispo else raw_dispo

        # --- PDF Upload Handling for Expungement (multiple files) ---
        uploaded_files = request.files.getlist("file")
        if uploaded_files and any(f.filename.endswith(".pdf") and f.filename for f in uploaded_files):
            os.makedirs("temp", exist_ok=True)
            extracted_cases = extract_multiple_cases_data(uploaded_files[:10])
            for idx, extracted in enumerate(extracted_cases):
                if idx == 0:
                    for key, value in extracted.items():
                        form_data[key] = value
                    form_data["name"] = form_data.get("name", "")
                    form_data["full_legal_name"] = form_data["name"]
                    form_data["dob"] = form_data.get("dob", "")
                    form_data["name_arrest"] = form_data.get("name_arrest", form_data.get("name", ""))
                    raw_dispo = form_data.get("final_dispo", "")
                    form_data["final_dispo"] = raw_dispo.split("Sentence")[0].strip() if "Sentence" in raw_dispo else raw_dispo
                else:
                    for field in ["arrest_date", "officer_name", "police_department", "charge_name", "code_section", "vcc_code", "otn", "court_dispo", "case_no", "dispo_date"]:
                        form_data[f"case_{idx}_{field}"] = extracted.get(field, "")

        # --- Collect all case fields (support multiple) ---
        from collections import defaultdict
        import re
        case_fields = [
            "arrest_date", "officer_name", "police_department", "charge_name", "code_section",
            "vcc_code", "otn", "court_dispo", "case_no", "dispo_date"
        ]
        cases = []
        # First case (unindexed)
        main_case = {}
        for field in case_fields:
            main_case[field] = form_data.get(field, "")
        cases.append(main_case)
        # Additional indexed cases
        indexed_case_data = defaultdict(dict)
        for key, value in form_data.items():
            match = re.match(r"case_(\d+)_(\w+)", key)
            if match:
                idx, field = match.groups()
                if field in case_fields:
                    indexed_case_data[int(idx)][field] = value
        for idx in sorted(indexed_case_data.keys()):
            cases.append(indexed_case_data[idx])

        # Date formatting helpers
        def format_date_long(date_str):
            date_str = date_str.replace("/", "-")
            for fmt in ("%Y-%m-%d", "%m-%d-%Y"):
                try:
                    dt = datetime.strptime(date_str, fmt)
                    if dt.year < 1900:
                        continue
                    return dt.strftime("%B %d, %Y")
                except ValueError:
                    continue
            return date_str

        arrest_date_formatted = format_date_long(form_data.get("arrest_date", ""))
        dispo_date_formatted = format_date_long(form_data.get("dispo_date", ""))

        expungement_type = form_data.get("expungement_type", "")
        manifest_injustice_details = form_data.get("manifest_injustice_details", "")
        if expungement_type == "Expungement of Right":
            type_of_expungement = (
                "The Petitioner has no prior criminal record, the aforementioned arrest was a misdemeanor offense, "
                "and the Commonwealth cannot show good cause to the contrary as to why the petition should not be granted."
            )
        elif expungement_type == "Manifest Injustice":
            type_of_expungement = (
                f"The continued existence and possible dissemination of information relating to the charge(s) set forth herein has caused, "
                f"and may continue to cause, circumstances which constitute a manifest injustice to the Petitioner. The Commonwealth cannot show good cause "
                f"to the contrary as to why the petition should not be granted.\n\n"
                f"To wit: {manifest_injustice_details}"
            )
        else:
            type_of_expungement = ""

        police_department = form_data.get("police_department", "")
        police_department_other = form_data.get("other_police_department", "")
        selected_police_department = police_department if police_department != "Other" else police_department_other

        data = {
            "{NAME}": form_data.get("name", "").upper(),
            "{Full Legal Name}": form_data.get("name", "").upper(),
            "{DOB}": format_date_long(form_data.get("dob", "")),
            "{County2}": form_data.get("county", "").title(),
            "{COUNTY}": form_data.get("county", "").upper(),
            "{Name at Time of Arrest}": form_data.get("name_arrest", form_data.get("name", "")).upper(),
            "{Name at Arrest}": form_data.get("name_arrest", form_data.get("name", "")).upper(),
            "{Type of Expungement}": type_of_expungement,
            "{Date of Arrest}": arrest_date_formatted,
            "{Arresting Officer}": form_data.get("officer_name", ""),
            "{Police Department}": selected_police_department,
            "{Charge Name}": form_data.get("charge_name", ""),
            "{Code Section}": form_data.get("code_section", ""),
            "{VCC Code}": form_data.get("vcc_code", ""),
            "{OTN}": form_data.get("otn", ""),
            "{Court Dispo}": form_data.get("court_dispo", ""),
            "{Case Number}": form_data.get("case_no", ""),
            "{Final Disposition}": form_data.get("final_dispo", ""),
            "{Dispo Date}": dispo_date_formatted,
            "{Prosecutor}": form_data.get("prosecutor", ""),
            "{Prosecutor Title}": form_data.get("prosecutor_title", ""),
            "{Prosecutor Address 1}": form_data.get("prosecutor_address1", ""),
            "{Prosecutor Address 2}": form_data.get("prosecutor_address2", ""),
            "{Month}": form_data.get("month", datetime.now().strftime("%B")),
            "{Year}": form_data.get("year", datetime.now().year),
            "{Attorney}": form_data.get("attorney", ""),
            "{Expungement Type}": expungement_type,
            "{Manifest Injustice Details}": manifest_injustice_details,
            # --- Additional keys added below ---
            "{Arrest Date}": arrest_date_formatted,
            "{Officer Name}": form_data.get("officer_name", ""),
            "{Court of Final Dispo}": form_data.get("court_dispo", ""),
            "{Case No}": form_data.get("case_no", ""),
        }
        data["{NAME}"] = form_data.get("name", "").upper()
        data["{DOB}"] = format_date_long(form_data.get("dob", ""))
        data["{Name at Time of Arrest}"] = form_data.get("name_arrest", form_data.get("name", "")).upper()
        data["{Name at Arrest}"] = form_data.get("name_arrest", form_data.get("name", "")).upper()
        data["{Final Disposition}"] = form_data.get("final_dispo", "")
        data["{additional Cases}"] = ""
        if len(cases) > 1:
            for i, case in enumerate(cases[1:], 1):
                data["{additional Cases}"] += (
                    f"Additional Case {i}:\n"
                    f"Date of Arrest: {format_date_long(case.get('arrest_date', ''))}\n\n"
                    f"Arresting Officer: {case.get('officer_name', '')}\n\n"
                    f"Police Department: {case.get('police_department', '')}\n\n"
                    f"Charge Name: {case.get('charge_name', '')}\n\n"
                    f"Code Section: {case.get('code_section', '')}\n\n"
                    f"VCC Code: {case.get('vcc_code', '')}\n\n"
                    f"OTN: {case.get('otn', '')}\n\n"
                    f"Court of Final Disposition: {case.get('court_dispo', '')}\n\n"
                    f"Case Number: {case.get('case_no', '')}\n\n"
                    f"Disposition Date: {format_date_long(case.get('dispo_date', ''))}\n\n"
                    "\n"
                )

        output_dir = "temp"
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"{data['{NAME}'].replace(' ', '_')}_Draft_Petition.docx")

        template_path = 'static/docs/Exp_Petition_Template.docx'
        populate_document(template_path, output_path, data)

        session["generated_file_path"] = output_path
        app.logger.debug(f"Final form data used for document generation: {form_data}")
        return redirect(url_for("expungement_success"))
    # For GET request, render the expungement form template
    current_month = datetime.now().strftime("%B")
    current_year = datetime.now().year
    from flask import get_flashed_messages
    messages = get_flashed_messages(with_categories=True)
    download_url = None
    autofill_data = session.pop("expungement_autofill_data", {})
    return render_template(
        'expungement.html',
        counties=prosecutor_info.keys(),
        current_month=current_month,
        current_year=current_year,
        messages=messages,
        download_url=download_url,
        autofill_data=autofill_data
    )

from Expungement.expungement_utils import extract_expungement_data, extract_multiple_cases_data, populate_document, prosecutor_info
from flask_mail import Mail, Message
import requests
from dotenv import load_dotenv
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from email.utils import formataddr
from requests_oauthlib import OAuth2Session
from itsdangerous import URLSafeTimedSerializer

load_dotenv()

app.secret_key = "supersecretkey"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///leads.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# Set session expiration to 24 hours of inactivity
from datetime import timedelta
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
# Limit uploads to 16MB
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Limit uploads to 16MB

# Register after-request no-cache headers
register_after_request(app)

# Token serializer for secure lead viewing
serializer = URLSafeTimedSerializer(app.secret_key)

# Email config
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')

mail = Mail(app)
db = SQLAlchemy(app)
migrate = Migrate(app, db)
# with app.app_context():
#     db.create_all()

# --- OAuth2 Integration (Clio) ---
import os
from requests_oauthlib import OAuth2Session

# Example usage: Initialize OAuth2Session for Clio with redirect_uri
client_id = os.getenv("CLIO_CLIENT_ID")
client_secret = os.getenv("CLIO_CLIENT_SECRET")
redirect_uri = "https://tools.dischleylaw.com/callback"
token_url = "https://app.clio.com/oauth/token"
# When using OAuth2Session for Clio, always pass redirect_uri:
# oauth = OAuth2Session(client_id, redirect_uri=redirect_uri, ...)

# --- Admin Leads Dashboard ---
@app.route("/admin/leads")
def admin_leads():
    leads = Lead.query.order_by(Lead.created_at.desc()).all()
    # Enhance: add URLs for each lead's detail page
    leads_with_links = []
    for lead in leads:
        lead_dict = lead.__dict__.copy()
        lead_dict["detail_url"] = url_for("view_lead", lead_id=lead.id)
        leads_with_links.append(lead_dict)
    return render_template("admin_leads.html", leads=leads, leads_with_links=leads_with_links)

# --- Admin Edit Lead ---
@app.route("/admin/lead/<int:lead_id>/edit", methods=["GET", "POST"])
def admin_edit_lead(lead_id):
    lead = Lead.query.get_or_404(lead_id)
    if request.method == "POST":
        lead.name = request.form.get("name", lead.name)
        lead.phone = request.form.get("phone", lead.phone)
        lead.email = request.form.get("email", lead.email)
        lead.charges = request.form.get("charges", lead.charges)
        lead.court_date = request.form.get("court_date", lead.court_date)
        lead.court_time = request.form.get("court_time", lead.court_time)
        lead.court = request.form.get("court", lead.court)
        lead.notes = request.form.get("notes", lead.notes)
        lead.facts = request.form.get("facts", lead.facts)
        lead.homework = request.form.get("homework", lead.homework)
        lead.lead_source = request.form.get("lead_source", lead.lead_source)
        lead.case_type = request.form.get("case_type", lead.case_type)
        lead.staff_member = request.form.get("staff_member", lead.staff_member)
        lead.absence_waiver = 'absence_waiver' in request.form
        db.session.commit()
        return redirect(url_for("admin_leads"))
    return render_template("admin_edit_lead.html", lead=lead)

class Lead(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    court_date = db.Column(db.String(20))
    court_time = db.Column(db.String(20))
    court = db.Column(db.String(200))
    notes = db.Column(db.Text)
    facts = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    send_retainer = db.Column(db.Boolean, default=False)
    retainer_amount = db.Column(db.String(50))
    lvm = db.Column(db.Boolean, default=False)
    not_pc = db.Column(db.Boolean, default=False)
    quote = db.Column(db.String(50), default="")
    lead_source = db.Column(db.String(100))
    case_type = db.Column(db.String(100))
    charges = db.Column(db.Text)
    staff_member = db.Column(db.String(100))
    absence_waiver = db.Column(db.Boolean, default=False)
    homework = db.Column(db.Text, default="")
    # New field: Attorney
    attorney = db.Column(db.String(100))
    # New homework checkboxes/fields (revised list, specified order)
    homework_driving_record = db.Column(db.Boolean, default=False)
    homework_reckless_program = db.Column(db.Boolean, default=False)
    homework_driver_improvement = db.Column(db.Boolean, default=False)
    homework_speedometer = db.Column(db.Boolean, default=False)
    homework_community_service = db.Column(db.Boolean, default=False)
    homework_community_service_hours = db.Column(db.String(20))
    homework_substance_evaluation = db.Column(db.Boolean, default=False)
    homework_asap = db.Column(db.Boolean, default=False)
    homework_shoplifting = db.Column(db.Boolean, default=False)
    homework_medical_conditions = db.Column(db.Boolean, default=False)
    homework_photos = db.Column(db.Boolean, default=False)
    homework_shoplifting_program = db.Column(db.Boolean, default=False)
    homework_military_awards = db.Column(db.Boolean, default=False)
    homework_dd214 = db.Column(db.Boolean, default=False)
    homework_community_involvement = db.Column(db.Boolean, default=False)
    homework_anger_management_courseforcourt = db.Column(db.Boolean, default=False)
    homework_vasap = db.Column(db.Boolean, default=False)
    homework_substance_abuse_treatment = db.Column(db.Boolean, default=False)
    homework_substance_abuse_counseling = db.Column(db.Boolean, default=False)
    homework_transcripts = db.Column(db.Boolean, default=False)
    calling = db.Column(db.Boolean, default=False)
    calling_back = db.Column(db.Boolean, default=False)
    homework_additional = db.Column(db.Boolean, default=False)
    homework_additional_notes = db.Column(db.String(200))
    # New field: NO HW
    homework_no_hw = db.Column(db.Boolean, default=False)
    # New field for plea offer
    plea_offer = db.Column(db.Text)

class CaseResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    defendant_name = db.Column(db.String(120))
    offense = db.Column(db.String(200))
    amended_charge = db.Column(db.String(200))
    disposition = db.Column(db.String(200))
    other_disposition = db.Column(db.String(200))
    jail_time_imposed = db.Column(db.String(50))
    jail_time_suspended = db.Column(db.String(50))
    fine_imposed = db.Column(db.String(50))
    fine_suspended = db.Column(db.String(50))
    license_suspension = db.Column(db.String(100))
    asap_ordered = db.Column(db.String(10))
    probation_type = db.Column(db.String(50))
    probation_term = db.Column(db.String(50))
    was_continued = db.Column(db.String(10))
    continuation_date = db.Column(db.String(20))
    client_email = db.Column(db.String(120))
    notes = db.Column(db.Text)
    date_disposition = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    charges = db.relationship('Charge', backref='case_result', cascade="all, delete-orphan")
    send_review_links = db.Column(db.Boolean, default=False)
    # New fields for license suspension term and restricted license type
    license_suspension_term = db.Column(db.String(100))
    restricted_license_type = db.Column(db.String(100))
    clio_matter_id = db.Column(db.String(100))
    # New field for Clio contact ID
    clio_contact_id = db.Column(db.String(100))
    # New field for plea offer
    plea_offer = db.Column(db.Text)

# --- Charge Model ---
class Charge(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    case_result_id = db.Column(db.Integer, db.ForeignKey('case_result.id'), nullable=False)
    original_charge = db.Column(db.String(200))
    amended_charge = db.Column(db.String(200))
    disposition = db.Column(db.String(100))
    # --- Begin full per-charge data fields ---
    plea = db.Column(db.String(100))
    disposition_paragraph = db.Column(db.Text)
    fine_imposed = db.Column(db.String(50))
    fine_suspended = db.Column(db.String(50))
    jail_time_imposed = db.Column(db.String(50))
    jail_time_suspended = db.Column(db.String(50))
    license_suspension = db.Column(db.String(100))
    license_suspension_term = db.Column(db.String(100))
    restricted_license = db.Column(db.String(100))
    restricted_license_type = db.Column(db.String(100))
    probation_type = db.Column(db.String(100))
    probation_term = db.Column(db.String(100))
    vasap = db.Column(db.String(10))
    vip = db.Column(db.String(10))
    community_service = db.Column(db.String(10))
    anger_management = db.Column(db.String(10))
    asap_ordered = db.Column(db.String(10))
    charge_notes = db.Column(db.Text)


# --- Lead Links Route ---
@app.route("/lead-links")
def lead_links():
    links = []
    for lead in Lead.query.order_by(Lead.created_at.desc()).all():
        links.append({
            "name": lead.name,
            "id": lead.id,
            "manage_url": url_for("view_lead", lead_id=lead.id)
        })
    return render_template("lead-links.html", links=links)



class ClioToken(db.Model):
    __tablename__ = 'clio_tokens'
    id = db.Column(db.Integer, primary_key=True)
    access_token = db.Column(db.String, nullable=False)
    refresh_token = db.Column(db.String, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)

    def is_expired(self):
        return datetime.utcnow() >= self.expires_at






@app.route("/")
def dashboard():
    case_results = CaseResult.query.order_by(CaseResult.created_at.desc()).all()
    # Show admin_tools button only for logged-in admin user
    show_admin_tools = "user" in session and session.get("user") == "admin"
    return render_template("dashboard.html", case_results=case_results, show_admin_tools=show_admin_tools)

@app.route("/leads")
def view_leads():
    leads = Lead.query.order_by(Lead.created_at.desc()).all()
    return render_template("leads.html", leads=leads)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username == "admin" and password == "dischley123":
            session.permanent = True
            session["user"] = username
            return redirect(url_for("dashboard"))
        return render_template("login.html", error="Invalid credentials")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))

@app.route("/intake", methods=["GET", "POST"])
def intake():
    if request.method == "POST":
        data = request.form

        # Retrieve and strip custom_source and lead_source before use.
        custom_source = request.form.get("custom_source", "").strip()
        lead_source = request.form.get("lead_source", "").strip()

        # Extract additional dynamic case-type fields from the form
        case_type = data.get("case_type")

        # DUI fields
        dui_blood_taken = data.get("dui_blood_taken")
        dui_refusal = data.get("dui_refusal")
        dui_prior_offenses = data.get("dui_prior_offenses")
        dui_interlock = data.get("dui_interlock")

        # Protective Order fields
        po_petitioner = data.get("po_petitioner")
        po_relationship = data.get("po_relationship")
        po_order_type = data.get("po_order_type")

        # Expungement fields
        exp_original_charge = data.get("exp_original_charge")
        exp_disposition = data.get("exp_disposition")
        exp_basis = data.get("exp_basis")

        # Civil fields
        civil_opposing_party = data.get("civil_opposing_party")
        civil_dispute = data.get("civil_dispute")
        civil_amount = data.get("civil_amount")

        first_name = data.get("first_name", "").strip()
        last_name = data.get("last_name", "").strip()
        full_name = f"{first_name} {last_name}".strip()

        staff_member = data.get("staff_member")

        new_lead = Lead(
            name=full_name if full_name else "Unknown",
            phone=data.get("phone"),
            email=data.get("email"),
            court_date=data.get("court_date"),
            court_time=data.get("court_time"),
            court=data.get("court"),
            notes=data.get("notes"),
            facts=data.get("facts"),
            send_retainer=False,
            lvm=False,
            not_pc=False,
            quote=None,
            retainer_amount=None,
            lead_source=lead_source,
            case_type=case_type,
            charges=data.get("charges"),
            staff_member=staff_member,
            homework=data.get("homework"),
            calling_back=False,
        )
        db.session.add(new_lead)
        db.session.commit()

        # Generate secure tokenized link for viewing the lead (valid for 24 hours)
        token = serializer.dumps(str(new_lead.id), salt="view-lead")
        lead_url = url_for("view_lead_token", token=token, _external=True)
        update_token = serializer.dumps(str(new_lead.id), salt="view-lead")
        update_url = url_for("update_lead_token", token=update_token, _external=True)

        # Format court_date if available
        formatted_date = ""
        if new_lead.court_date:
            try:
                formatted_date = datetime.strptime(new_lead.court_date, "%Y-%m-%d").strftime("%B %d, %Y")
            except ValueError:
                formatted_date = new_lead.court_date  # fallback if date parsing fails
        else:
            formatted_date = "N/A"

        # Format court_time to 12-hour AM/PM if possible
        formatted_time = ""
        if new_lead.court_time:
            try:
                formatted_time = datetime.strptime(new_lead.court_time, "%H:%M").strftime("%I:%M %p")
            except ValueError:
                formatted_time = new_lead.court_time

        msg = Message(f"PC: {first_name} {last_name}",
                      recipients=["attorneys@dischleylaw.com"],
                      sender=("New Lead", os.getenv('MAIL_DEFAULT_SENDER')))

        # Compose HTML email with all submitted fields if present, using required mapping
        email_html = "<h2 style='font-size:16pt;'>New Lead:</h2>"
        email_html += "<ul style='list-style-type:none;padding-left:0;font-size:16pt;'>"
        field_items = [
            ("Type of Case", case_type),
            ("First Name", first_name),
            ("Last Name", last_name),
            ("Phone Number", new_lead.phone),
            ("Email", new_lead.email),
            ("Charges", new_lead.charges),
            ("Court", new_lead.court),
            ("Court Date", formatted_date if formatted_date != "N/A" else None),
            ("Court Time", formatted_time),
            ("Facts", new_lead.facts),
            ("Notes", new_lead.notes),
            ("Homework", new_lead.homework),
            ("Staff Member", staff_member),
            ("Attorney", data.get("attorney")),
            ("Lead Source", lead_source if lead_source and lead_source != "Other" else None),
            ("Send Retainer", "✅" if new_lead.send_retainer else None),
            ("Retainer Amount", new_lead.retainer_amount),
            ("LVM", "✅" if new_lead.lvm else None),
            ("Not a PC", "✅" if new_lead.not_pc else None),
            ("Quote", new_lead.quote),
            ("Absence Waiver", "✅" if getattr(new_lead, 'absence_waiver', False) else None),
            ("DUI - Blood Taken", data.get("dui_blood_taken")),
            ("DUI - Refusal Charge", data.get("dui_refusal")),
            ("DUI - Prior Offenses", data.get("dui_prior_offenses")),
            ("DUI - Interlock Required", data.get("dui_interlock")),
            ("Protective Order - Petitioner", data.get("po_petitioner")),
            ("Protective Order - Relationship", data.get("po_relationship")),
            ("Protective Order - Type of Order", data.get("po_order_type")),
            ("Expungement - Original Charge", data.get("exp_original_charge")),
            ("Expungement - Disposition", data.get("exp_disposition")),
            ("Expungement - Basis", data.get("exp_basis")),
            ("Civil - Opposing Party", data.get("civil_opposing_party")),
            ("Civil - Nature of Dispute", data.get("civil_dispute")),
            ("Civil - Amount in Controversy", data.get("civil_amount")),
        ]
        for label, value in field_items:
            if value:
                email_html += f"<li style='font-size:16pt;'><strong>{label}:</strong> {value}</li>"
        email_html += "</ul>"
        email_html += f"<p style='font-size:16pt;'><a href='{lead_url}'>Manage Lead</a></p>"
        msg.html = email_html
        mail.send(msg)

        # Clio
        clio_payload = {
            "inbox_lead": {
                "from_first": first_name or "Unknown",
                "from_last": new_lead.name.split()[-1],
                "from_email": new_lead.email,
                "from_phone": new_lead.phone,
                "from_message": (
                    f"Case Type: {case_type}, "
                    f"Charges: {new_lead.charges}, "
                    f"Notes: {new_lead.notes}, "
                    f"Facts: {new_lead.facts}, "
                    f"Homework: {new_lead.homework}"
                ),
                "referring_url": "http://127.0.0.1:5000/intake",
                "from_source": (custom_source or lead_source) or "Unknown"
            },
            "inbox_lead_token": os.getenv("CLIO_TOKEN")
        }

        response = requests.post("https://grow.clio.com/inbox_leads", json=clio_payload)
        if response.status_code != 201:
            print("❌ Clio integration failed:", response.status_code, response.text)
        else:
            print("✅ Clio lead submitted successfully!")

        return redirect(url_for("intake_success"))
    return render_template("intake.html")

@app.route("/success")
def intake_success():
    return render_template("success.html")

@app.route("/lead/<int:lead_id>")
def view_lead(lead_id):
    lead = Lead.query.get_or_404(lead_id)
    return render_template("view_lead.html", lead=lead)


# --- Token-based view for leads (no login required, valid for 24 hours) ---
@app.route("/view_lead_token/<token>")
def view_lead_token(token):
    try:
        lead_id = serializer.loads(token, salt="view-lead", max_age=86400)
        lead = Lead.query.get_or_404(lead_id)
        return render_template("view_lead.html", lead=lead)
    except Exception:
        flash("This link has expired or is invalid.", "danger")
        return redirect(url_for("login"))
@app.route("/update_lead_token/<token>", methods=["GET", "POST"])
def update_lead_token(token):
    try:
        lead_id = serializer.loads(token, salt="view-lead", max_age=86400)
        return update_lead(lead_id)
    except Exception:
        flash("This update link has expired or is invalid.", "danger")
        return redirect(url_for("login"))

@app.route("/lead/<int:lead_id>/update", methods=["POST"])
def update_lead(lead_id):
    lead = Lead.query.get_or_404(lead_id)

    # --- Reset fields to default values before updating from form ---
    lead.calling = False
    lead.absence_waiver = False
    lead.send_retainer = False
    lead.retainer_amount = ""
    lead.lvm = False
    lead.not_pc = False
    lead.quote = ""

    lead.name = request.form.get("name") if request.form.get("name") else lead.name
    lead.phone = request.form.get("phone") if request.form.get("phone") else lead.phone
    lead.email = request.form.get("email") if request.form.get("email") else lead.email
    lead.charges = request.form.get("charges") if request.form.get("charges") else lead.charges
    lead.court_date = request.form.get("court_date") if request.form.get("court_date") else lead.court_date
    lead.court_time = request.form.get("court_time") if request.form.get("court_time") else lead.court_time
    lead.court = request.form.get("court") if request.form.get("court") else lead.court
    lead.notes = request.form.get("notes") if request.form.get("notes") else lead.notes
    # Update plea_offer only if provided and non-empty
    if "plea_offer" in request.form and request.form["plea_offer"].strip():
        lead.plea_offer = request.form["plea_offer"].strip()
    lead.facts = request.form.get("facts") if request.form.get("facts") else lead.facts
    lead.send_retainer = 'send_retainer' in request.form
    if lead.send_retainer:
        lead.retainer_amount = request.form.get("retainer_amount", "").strip()
    else:
        lead.retainer_amount = ""
    lead.lvm = 'lvm' in request.form
    lead.not_pc = 'not_pc' in request.form
    # Update quote: only store if 'toggle_quote' is present in form
    if 'toggle_quote' in request.form:
        quote_input = request.form.get("quote", "")
        lead.quote = quote_input.strip()
    else:
        lead.quote = ""
    lead.lead_source = request.form.get("lead_source") if request.form.get("lead_source") else lead.lead_source
    lead.case_type = request.form.get("case_type") if request.form.get("case_type") else lead.case_type
    lead.staff_member = request.form.get("staff_member") if request.form.get("staff_member") else lead.staff_member
    # Add attorney update
    lead.attorney = request.form.get("attorney", lead.attorney)
    lead.absence_waiver = 'absence_waiver' in request.form
    homework_input = request.form.get("homework")
    if homework_input is not None and homework_input.strip() != "":
        lead.homework = homework_input
    # Ensure homework is preserved even if unchecked in the form
    if homework_input is None:
        lead.homework = ""

    # New homework checkbox fields (revised list, specified order)
    lead.homework_driving_record = 'homework_driving_record' in request.form
    lead.homework_reckless_program = 'homework_reckless_program' in request.form
    lead.homework_driver_improvement = 'homework_driver_improvement' in request.form
    lead.homework_speedometer = 'homework_speedometer' in request.form
    lead.homework_community_service = 'homework_community_service' in request.form
    # Preserve existing hours if not provided
    homework_community_service_hours_val = request.form.get('homework_community_service_hours')
    lead.homework_community_service_hours = homework_community_service_hours_val if homework_community_service_hours_val is not None and homework_community_service_hours_val != "" else lead.homework_community_service_hours
    lead.homework_substance_evaluation = 'homework_substance_evaluation' in request.form
    lead.homework_asap = 'homework_asap' in request.form
    lead.homework_shoplifting = 'homework_shoplifting' in request.form
    lead.homework_medical_conditions = 'homework_medical_conditions' in request.form
    lead.homework_photos = 'homework_photos' in request.form
    lead.homework_shoplifting_program = 'homework_shoplifting_program' in request.form
    lead.homework_military_awards = 'homework_military_awards' in request.form
    lead.homework_dd214 = 'homework_dd214' in request.form
    lead.homework_community_involvement = 'homework_community_involvement' in request.form
    lead.homework_anger_management_courseforcourt = 'homework_anger_management_courseforcourt' in request.form
    lead.homework_vasap = 'homework_vasap' in request.form
    lead.homework_substance_abuse_treatment = 'homework_substance_abuse_treatment' in request.form
    lead.homework_substance_abuse_counseling = 'homework_substance_abuse_counseling' in request.form
    lead.homework_transcripts = 'homework_transcripts' in request.form
    # New: homework_no_hw
    lead.homework_no_hw = 'homework_no_hw' in request.form

    # --- New logic for "Calling" field ---
    if 'calling' in request.form:
        lead.calling = True
    else:
        lead.calling = False
    lead.calling_back = 'calling_back' in request.form

    # --- New logic for homework_additional and notes ---
    lead.homework_additional = 'homework_additional' in request.form
    lead.homework_additional_notes = request.form.get("homework_additional_notes", "").strip()

    db.session.commit()

    # Determine status label
    status_parts = []  # Reset to empty list and clear any previous status values
    if lead.send_retainer:
        if lead.retainer_amount:
            try:
                amount = float(lead.retainer_amount)
                status_parts.append(f"Send Retainer: ${amount:.2f}")
            except ValueError:
                status_parts.append(f"Send Retainer: ${lead.retainer_amount}")
        else:
            status_parts.append("Send Retainer")
    if lead.lvm:
        status_parts.append("LVM")
    if lead.not_pc:
        status_parts.append("Not a PC")
    # Ensure quote is only added if not None, not empty/whitespace, and not "none"
    if lead.quote and lead.quote.strip() and lead.quote.strip().lower() != "none":
        try:
            quote_value = float(lead.quote.strip())
            status_parts.append(f"Quote: ${quote_value:.2f}")
        except ValueError:
            status_parts.append(f"Quote: ${lead.quote.strip()}")
    if lead.calling:
        status_parts.append("Calling")
    if lead.calling_back:
        status_parts.append("PC Calling Back")
    status_str = " | ".join(status_parts)
    first_name, last_name = (lead.name.split(maxsplit=1) + [""])[:2]
    subject_line = f"Lead Updated - {first_name} {last_name}".strip()
    # Prepare update email (HTML)
    msg = Message(subject_line,
                  recipients=["attorneys@dischleylaw.com"],
                  sender=("New Lead", os.getenv('MAIL_DEFAULT_SENDER')))
    email_html = f"<h2 style='font-size:16pt;'>Lead Updated - {status_str if status_str else 'No Status'}</h2><br>"

    email_html += "<h3 style='margin-bottom:5px;font-size:16pt;'><u><b>Client Information:</b></u></h3><ul style='list-style-type:none;padding-left:0;font-size:16pt;'>"
    email_html += f"<li style='font-size:16pt;'><strong>Name:</strong> {lead.name}</li>"
    email_html += f"<li style='font-size:16pt;'><strong>Phone:</strong> {lead.phone}</li>"
    email_html += f"<li style='font-size:16pt;'><strong>Email:</strong> {lead.email}</li>"
    email_html += "</ul>"

    email_html += "<h3 style='margin-bottom:5px;font-size:16pt;'><u><b>Case Information:</b></u></h3><ul style='list-style-type:none;padding-left:0;font-size:16pt;'>"
    # Formatting for court date and time
    formatted_court_date = None
    if lead.court_date:
        try:
            formatted_court_date = datetime.strptime(lead.court_date, "%Y-%m-%d").strftime("%B %d, %Y")
        except ValueError:
            formatted_court_date = lead.court_date
    formatted_time = None
    if lead.court_time:
        try:
            formatted_time = datetime.strptime(lead.court_time, "%H:%M").strftime("%I:%M %p")
        except ValueError:
            formatted_time = lead.court_time
    # Compose using the required mapping, omitting internal-only fields and action/status fields
    field_items = [
        ("Charges", lead.charges),
        ("Court", lead.court),
        ("Court Date", formatted_court_date),
        ("Court Time", formatted_time),
        ("Brief Description of the Facts", lead.facts),
        ("Homework", lead.homework if lead.homework else None),
    ]
    for label, value in field_items:
        if value:
            email_html += f"<li style='font-size:16pt;'><strong>{label}:</strong> {value}</li>"

    # --- Insert Action/Status Section ---
    email_html += "<h3 style='margin-bottom:5px;font-size:16pt;'><u><b>Action/Status:</b></u></h3><ul style='list-style-type:none;padding-left:0;font-size:16pt;'>"
    if lead.send_retainer:
        email_html += "<li style='font-size:16pt;'><strong>Send Retainer:</strong> ✅</li>"
        if lead.retainer_amount:
            try:
                email_html += f"<li style='font-size:16pt;'><strong>Retainer Amount:</strong> ${float(lead.retainer_amount):.2f}</li>"
            except Exception:
                email_html += f"<li style='font-size:16pt;'><strong>Retainer Amount:</strong> {lead.retainer_amount}</li>"
    if lead.lvm:
        email_html += "<li style='font-size:16pt;'><strong>LVM:</strong> ✅</li>"
    if lead.calling:
        email_html += "<li style='font-size:16pt;'><strong>Calling:</strong> ✅</li>"
    if lead.calling_back:
        email_html += "<li style='font-size:16pt;'><strong>PC Calling Back:</strong> ✅</li>"
    if lead.not_pc:
        email_html += "<li style='font-size:16pt;'><strong>Not a PC:</strong> ✅</li>"
    # Quote (if present and not "none")
    if lead.quote and lead.quote.strip() and lead.quote.strip().lower() != "none":
        try:
            email_html += f"<li style='font-size:16pt;'><strong>Quote:</strong> ${float(lead.quote.strip()):.2f}</li>"
        except Exception:
            email_html += f"<li style='font-size:16pt;'><strong>Quote:</strong> {lead.quote.strip()}</li>"
    # Absence Waiver
    if lead.absence_waiver:
        email_html += "<li style='font-size:16pt;'><strong>Absence Waiver:</strong> ✅</li>"
    email_html += "</ul>"

    # --- Dynamic Homework Section ---
    if lead.send_retainer:
        email_html += "<h3 style='margin-bottom:5px;font-size:16pt;'><u><b>Homework:</b></u></h3><ul style='list-style-type:none;padding-left:0;font-size:16pt;'>"
        if lead.homework_driving_record:
            email_html += "<li style='font-size:16pt;'><strong>Driving Record:</strong> ✅</li>"
        if lead.homework_reckless_program:
            email_html += "<li style='font-size:16pt;'><strong>Reckless/Aggressive Driving Program:</strong> ✅</li>"
        if lead.homework_driver_improvement:
            email_html += "<li style='font-size:16pt;'><strong>Driver Improvement Course:</strong> ✅</li>"
        if lead.homework_speedometer:
            email_html += "<li style='font-size:16pt;'><strong>Speedometer Calibration:</strong> ✅</li>"
        if lead.homework_community_service:
            hours = lead.homework_community_service_hours or ""
            email_html += f"<li style='font-size:16pt;'><strong>Community Service:</strong> ✅ ({hours} hours)</li>"
        if lead.homework_substance_evaluation:
            email_html += "<li style='font-size:16pt;'><strong>Substance Abuse Evaluation:</strong> ✅</li>"
        if lead.homework_asap:
            email_html += "<li style='font-size:16pt;'><strong>Pre-enroll in ASAP:</strong> ✅</li>"
        if lead.homework_shoplifting:
            email_html += "<li style='font-size:16pt;'><strong>Shoplifting Class:</strong> ✅</li>"
        if lead.homework_medical_conditions:
            email_html += "<li style='font-size:16pt;'><strong>Medical Conditions / Surgeries List:</strong> ✅</li>"
        if lead.homework_photos:
            email_html += "<li style='font-size:16pt;'><strong>Photographs of Field Sobriety Scene:</strong> ✅</li>"
        if lead.homework_shoplifting_program:
            email_html += "<li style='font-size:16pt;'><strong>Shoplifting Theft Offenders Program:</strong> ✅</li>"
        if lead.homework_military_awards:
            email_html += "<li style='font-size:16pt;'><strong>Copies of Military Awards:</strong> ✅</li>"
        if lead.homework_dd214:
            email_html += "<li style='font-size:16pt;'><strong>Copy of DD-214:</strong> ✅</li>"
        if lead.homework_community_involvement:
            email_html += "<li style='font-size:16pt;'><strong>Community Involvement List:</strong> ✅</li>"
        if lead.homework_anger_management_courseforcourt:
            email_html += "<li style='font-size:16pt;'><strong>Anger Management</strong> ✅</li>"
        if lead.homework_vasap:
            email_html += "<li style='font-size:16pt;'><strong>VASAP:</strong> ✅</li>"
        if lead.homework_substance_abuse_treatment:
            email_html += "<li style='font-size:16pt;'><strong>Substance Abuse Eval/Treatment:</strong> ✅</li>"
        if lead.homework_substance_abuse_counseling:
            email_html += "<li style='font-size:16pt;'><strong>Substance Abuse Counseling:</strong> ✅</li>"
        if lead.homework_transcripts:
            email_html += "<li style='font-size:16pt;'><strong>High School or College Transcripts:</strong> ✅</li>"
        if lead.homework_no_hw:
            email_html += "<li style='font-size:16pt;'><strong>NO HW:</strong> ✅</li>"
        if lead.homework_additional:
            email_html += f"<li style='font-size:16pt;'><strong>Additional Homework:</strong> ✅ {lead.homework_additional_notes}</li>"
        email_html += "</ul>"

    # --- Add Internal Use Only Section if any internal fields are present ---
    internal_fields = [
        getattr(lead, "notes", None),
        getattr(lead, "staff_member", None),
        getattr(lead, "attorney", None),
        getattr(lead, "lead_source", None),
    ]
    # Check if at least one is non-empty (not None and not empty/whitespace)
    if any(f and str(f).strip() for f in internal_fields):
        email_html += (
            "<h3 style='margin-bottom:5px;font-size:16pt;'><u><b>INTERNAL USE ONLY:</b></u></h3>"
            "<ul style='list-style-type:none;padding-left:0;font-size:16pt;'>"
            f"<li style='font-size:16pt;'><strong>Notes:</strong> {lead.notes or ''}</li>"
            f"<li style='font-size:16pt;'><strong>Staff Member:</strong> {lead.staff_member or ''}</li>"
            f"<li style='font-size:16pt;'><strong>Attorney:</strong> {lead.attorney or ''}</li>"
            f"<li style='font-size:16pt;'><strong>Lead Source:</strong> {lead.lead_source or ''}</li>"
        )
        email_html += "</ul>"

    email_html += f"<p style='font-size:16pt;'><a href='{url_for('view_lead', lead_id=lead.id, _external=True)}'>Manage Lead</a></p>"
    msg.html = email_html
    mail.send(msg)

    # Optional: Send auto-email to client if LVM is checked and client email exists
    attorney = request.form.get("attorney", "").strip()
    if not attorney:
        attorney = "David Dischley"
    if lead.lvm and lead.email:
        client_name = lead.name if lead.name else "there"
        # Set callback number and reply email based on explicit attorney name check
        if "patrick o'brien" in attorney.lower():
            callback_number = "(571) 352-1633"
            reply_email = "patrick@dischleylaw.com"
        else:
            callback_number = "703-851-7137"
            reply_email = "david@dischleylaw.com"
        auto_msg = Message(
            "Dischley Law, PLLC:  Thank You for Your Inquiry",
            recipients=[lead.email],
            sender=("Dischley Law, PLLC", os.getenv('MAIL_DEFAULT_SENDER')),
            reply_to=[reply_email, "attorneys@dischleylaw.com"]
        )
        auto_msg.body = f"""Dear {client_name},

Thank you for contacting Dischley Law, PLLC regarding your legal matter. We appreciate the opportunity to assist you.

We attempted to reach you by phone but were unable to connect. At your convenience, please feel free to return our call so we can discuss your case in more detail and answer any questions you may have.

You can reach us at {callback_number}. We look forward to speaking with you.

Best regards,
{attorney}
Dischley Law, PLLC
9255 Center Street, Suite 300B
Manassas, VA 20110
{callback_number}
{reply_email}
"""
        mail.send(auto_msg)

    return redirect(url_for("update_success"))

@app.route("/lead/<int:lead_id>/edit", methods=["GET", "POST"])
def edit_lead(lead_id):
    lead = Lead.query.get_or_404(lead_id)
    if request.method == "POST":
        lead.name = request.form.get("name", lead.name)
        lead.phone = request.form.get("phone", lead.phone)
        lead.email = request.form.get("email", lead.email)
        lead.charge = request.form.get("charge", lead.charge)
        lead.court_date = request.form.get("court_date", lead.court_date)
        lead.notes = request.form.get("notes", lead.notes)
        db.session.commit()
        return redirect(url_for("dashboard"))
    return render_template("edit_lead.html", lead=lead)

@app.route("/case_result/<int:result_id>/edit", methods=["GET", "POST"])
def edit_case_result(result_id):
    result = CaseResult.query.get_or_404(result_id)
    if request.method == "POST":
        result.defendant_name = request.form.get("defendant_name", result.defendant_name)
        result.offense = request.form.get("offense", result.offense)
        result.amended_charge = request.form.get("amended_charge", result.amended_charge)
        result.disposition = request.form.get("disposition", result.disposition)
        result.other_disposition = request.form.get("other_disposition", result.other_disposition)
        result.jail_time_imposed = request.form.get("jail_time_imposed", result.jail_time_imposed)
        result.jail_time_suspended = request.form.get("jail_time_suspended", result.jail_time_suspended)
        result.fine_imposed = request.form.get("fine_imposed", result.fine_imposed)
        result.fine_suspended = request.form.get("fine_suspended", result.fine_suspended)
        result.license_suspension = request.form.get("license_suspension", result.license_suspension)
        result.asap_ordered = request.form.get("asap_ordered", result.asap_ordered)
        result.probation_type = request.form.get("probation_type", result.probation_type)
        result.was_continued = request.form.get("was_continued", result.was_continued)
        result.continuation_date = request.form.get("continuation_date", result.continuation_date)
        result.notes = request.form.get("notes", result.notes)
        db.session.commit()
        return redirect(url_for("dashboard"))
    return render_template("edit_case_result.html", result=result)

@app.route("/update-success")
def update_success():
    return render_template("update_success.html")

@app.route("/case_result", methods=["GET", "POST"])
def case_result():
    # --- AJAX or form-driven search for matters or contacts (GET handler) ---
    if request.method == "GET" and ("search_matter" in request.args or "search_contact" in request.args):
        # Handle matter search
        if "search_matter" in request.args:
            try:
                pass
                access_token = get_valid_token()
                headers = {'Authorization': f'Bearer {access_token}'}
                query = request.args.get("search_matter")
                url = f"https://app.clio.com/api/v4/matters?query={query}&status=open"
                response = requests.get(url, headers=headers)
                if response.status_code == 200:
                    return response.json()
                else:
                    return {"error": "Failed to fetch matter search results"}, response.status_code
            except Exception as e:
                return {"error": f"Search Error: {str(e)}"}, 500
        # Handle contact search
        if "search_contact" in request.args:
            try:
                access_token = get_valid_token()
                headers = {'Authorization': f'Bearer {access_token}'}
                query = request.args.get("search_contact")
                url = f"https://app.clio.com/api/v4/contacts?query={query}"
                response = requests.get(url, headers=headers)
                if response.status_code == 200:
                    people = []
                    for contact in response.json().get("data", []):
                        if contact.get("type", "").lower() == "person":
                            first = contact.get("first_name", "").strip()
                            last = contact.get("last_name", "").strip()
                            full_name = f"{first} {last}".strip()
                            if query.lower() in first.lower() or query.lower() in last.lower() or query.lower() in full_name.lower():
                                people.append({
                                    "id": contact.get("id"),
                                    "type": "Person",
                                    "name": full_name
                                })
                    return {"data": people}
                else:
                    return {"error": "Failed to fetch contact search results"}, response.status_code
            except Exception as e:
                return {"error": f"Contact Search Error: {str(e)}"}, 500
    submitted = False
    if request.method == "POST":
        defendant_name = request.form.get('defendant_name', '').strip()
        # --- CLIO MATTER ID LOOKUP (and defendant name extraction) ---
        clio_matter_id = None
        selected_display_name = request.form.get("search_matter", "").strip()
        if selected_display_name:
            try:
                access_token = get_valid_token()
                headers = {'Authorization': f'Bearer {access_token}'}
                search_url = f"https://app.clio.com/api/v4/matters?status=open&query={selected_display_name}"
                response = requests.get(search_url, headers=headers)
                if response.status_code == 200:
                    for matter in response.json().get("data", []):
                        if matter.get("display_number") and matter.get("display_number") in selected_display_name:
                            clio_matter_id = matter.get("id")
                            if not defendant_name:
                                defendant_name = matter.get("client", {}).get("name", selected_display_name)
                            break
            except Exception as e:
                print("Failed to fetch Clio matter ID:", e)

        # --- REVISED CLIO CONTACT ID LOGIC ---
        clio_contact_id = None
        contact_name_input = request.form.get("search_contact", "").strip()
        if contact_name_input:
            try:
                access_token = get_valid_token()
                headers = {"Authorization": f"Bearer {access_token}"}
                contact_url = f"https://app.clio.com/api/v4/contacts?query={contact_name_input}"
                response = requests.get(contact_url, headers=headers)
                if response.status_code == 200:
                    for contact in response.json().get("data", []):
                        if contact.get("type", "").lower() == "person":
                            first = contact.get("first_name", "").strip()
                            last = contact.get("last_name", "").strip()
                            full_name = f"{first} {last}".strip()
                            if (
                                contact_name_input.lower() == full_name.lower()
                                or contact_name_input.lower() == first.lower()
                                or contact_name_input.lower() == last.lower()
                            ):
                                clio_contact_id = contact.get("id")
                                defendant_name = full_name
                                break
            except Exception as e:
                print("Failed to search Clio contacts:", e)

        # Accept original_charge[] as free-text paragraph input(s) from the frontend.
        original_charges = request.form.getlist('original_charge[]')
        amended_charges = request.form.getlist('amended_charge[]')
        pleas = request.form.getlist('plea[]')
        dispositions = request.form.getlist('disposition[]')

        # NEW: get disposition_paragraphs for custom narrative per charge
        disposition_paragraphs = request.form.getlist('disposition_paragraph[]')

        jail_time_imposed = request.form.getlist('jail_time_imposed[]')
        jail_time_suspended = request.form.getlist('jail_time_suspended[]')
        jail_time_imposed_unit = request.form.getlist('jail_time_imposed_unit[]')
        jail_time_suspended_unit = request.form.getlist('jail_time_suspended_unit[]')
        fine_imposed = request.form.getlist('fine_imposed[]')
        fine_suspended = request.form.getlist('fine_suspended[]')
        license_suspension = request.form.getlist('license_suspension[]')
        restricted_license = request.form.getlist('restricted_license[]')
        # New: Retrieve restricted_license_type and license_suspension_term
        license_suspension_term = request.form.getlist('license_suspension_term[]')
        restricted_license_type = request.form.getlist('restricted_license_type[]')
        asap_ordered = request.form.getlist('asap_ordered[]')
        charge_notes = request.form.getlist('charge_notes[]')
        probation_type = request.form.getlist('probation_type[]')
        probation_term = request.form.getlist('probation_term[]')
        vasap = request.form.getlist('vasap[]')
        vip = request.form.getlist('vip[]')
        community_service = request.form.getlist('community_service[]')
        anger_management = request.form.getlist('anger_management[]')
        was_continued = request.form.get('was_continued', '').strip()
        continuation_date = request.form.get('continuation_date', '').strip()
        continuation_time = request.form.get('continuation_time', '').strip()
        date_disposition = request.form.get('date_disposition', '').strip()
        notes = request.form.get('notes', '').strip()
        send_review_links = 'send_review_links' in request.form

        subject = f"Case Result - {defendant_name}"
        email_html = f"<h2 style='font-size:16pt;'>Case Result – {defendant_name}</h2>"
        court_value = request.form.get("court", "").strip()
        prosecutor_judge_value = request.form.get("prosecutor_judge", "").strip()
        if court_value:
            email_html += f"<p style='font-size:16pt;'><strong>Court:</strong> {court_value}</p>"
        if prosecutor_judge_value:
            email_html += f"<p style='font-size:16pt;'><strong>Prosecutor/Judge:</strong> {prosecutor_judge_value}</p>"
        # --- Add Plea Offer if present ---
        plea_offer = request.form.get("plea_offer", "").strip()
        if plea_offer:
            email_html += f"<p style='font-size:16pt;'><strong>Plea Offer:</strong> {plea_offer}</p>"
        all_charge_fields = [
            original_charges, amended_charges, pleas, dispositions,
            jail_time_imposed, jail_time_suspended, fine_imposed, fine_suspended,
            license_suspension, restricted_license, asap_ordered,
            probation_type, probation_term, vasap, vip,
            community_service, anger_management
        ]
        num_charges = max(len(field) for field in all_charge_fields)
        skip_dispositions = ["Deferred", "298.02", "General Continuance"]
        if num_charges > 0:
            for i in range(num_charges):
                # Instead of "Charge {i+1}", bold and underline the original charge name.
                if i < len(original_charges) and original_charges[i]:
                    email_html += f"<p style='font-size:16pt; font-weight:bold; text-decoration:underline;'>{original_charges[i]}</p>"
                # Ensure all charge detail paragraphs use 16pt
                email_html += "<p style='font-size:16pt; margin-left:20px;'>"
                # The rest of the charge details still display under the bolded original charge.
                if i < len(amended_charges) and amended_charges[i]:
                    email_html += f"<span style='font-size:16pt;'><strong>Amended Charge:</strong> {amended_charges[i]}<br></span>"
                # Insert plea and disposition bullets after amended charge
                if i < len(pleas) and pleas[i]:
                    email_html += f"<span style='font-size:16pt;'>• <strong>Plea:</strong> {pleas[i]}<br></span>"
                # Change "Finding" back to "Disposition" and ensure 16pt font
                if i < len(dispositions) and dispositions[i]:
                    email_html += f"<span style='font-size:16pt;'>• <strong>Disposition:</strong> {dispositions[i]}<br></span>"
                # NEW: If disposition in skip_dispositions, include disposition paragraph
                if i < len(dispositions) and dispositions[i] in skip_dispositions:
                    if i < len(disposition_paragraphs) and disposition_paragraphs[i]:
                        email_html += f"<span style='font-size:16pt;'><strong>Disposition Narrative:</strong> {disposition_paragraphs[i]}<br></span>"
                # Only render jail, fine, probation, license fields if not in skip_dispositions
                if i < len(dispositions) and dispositions[i] not in skip_dispositions:
                    # Show the "Sentence" heading only if at least one jail or fine value exists (not all are empty or missing)
                    if (
                        (i < len(jail_time_imposed) and jail_time_imposed[i]) or
                        (i < len(jail_time_suspended) and jail_time_suspended[i]) or
                        (i < len(fine_imposed) and fine_imposed[i]) or
                        (i < len(fine_suspended) and fine_suspended[i])
                    ):
                        email_html += "<span style='font-size:16pt; font-weight:bold;'>Sentence:<br></span>"
                    # Jail and Fine output per new requirements
                    imposed_unit = jail_time_imposed_unit[i] if i < len(jail_time_imposed_unit) else "days"
                    suspended_unit = jail_time_suspended_unit[i] if i < len(jail_time_suspended_unit) else "days"
                    if i < len(jail_time_imposed) and jail_time_imposed[i]:
                        if i < len(jail_time_suspended) and jail_time_suspended[i]:
                            email_html += f"<span style='font-size:16pt; font-weight:bold;'>• {jail_time_imposed[i]} {imposed_unit} in jail with {jail_time_suspended[i]} {suspended_unit} suspended<br></span>"
                        else:
                            email_html += f"<span style='font-size:16pt; font-weight:bold;'>• {jail_time_imposed[i]} {imposed_unit} in jail<br></span>"
                    if i < len(fine_imposed) and fine_imposed[i]:
                        if i < len(fine_suspended) and fine_suspended[i]:
                            email_html += f"<span style='font-size:16pt; font-weight:bold;'>• A fine of ${fine_imposed[i]} with ${fine_suspended[i]} suspended<br></span>"
                        else:
                            email_html += f"<span style='font-size:16pt; font-weight:bold;'>• A fine of ${fine_imposed[i]}<br></span>"
                    # License Suspension: Only show check if "Yes"
                    # (Moved after restricted license block below)
                    # Compose restricted license info: include type and term if granted
                    if i < len(restricted_license) and restricted_license[i] and restricted_license[i].strip().lower() == "yes":
                        restricted_info = "<strong>Restricted License:</strong> Yes"
                        details = []
                        if i < len(restricted_license_type) and restricted_license_type[i]:
                            details.append(f"Type: {restricted_license_type[i]}")
                        if i < len(license_suspension_term) and license_suspension_term[i]:
                            details.append(f"Term: {license_suspension_term[i]}")
                        if details:
                            restricted_info += f" ({'; '.join(details)})"
                        email_html += f"<span style='font-size:16pt;'>{restricted_info}<br></span>"
                    # License Suspension: Only show check if "Yes" (now after restricted license)
                    if i < len(license_suspension) and license_suspension[i] and license_suspension[i].strip().lower() == "yes":
                        email_html += "<span style='font-size:16pt;'><strong>License Suspension:</strong> ✅<br></span>"
                    # ASAP Ordered: Only show if "Yes"
                    if i < len(asap_ordered) and asap_ordered[i] and asap_ordered[i].strip().lower() == "yes":
                        email_html += "<span style='font-size:16pt;'><strong>ASAP Ordered:</strong> ✅<br></span>"
                    # Probation
                    probation_lines = []
                    if i < len(probation_type) and probation_type[i]:
                        probation_lines.append(f"<strong>Probation Type:</strong> {probation_type[i]}")
                    if i < len(probation_term) and probation_term[i]:
                        probation_lines.append(f"<strong>Probation Term:</strong> {probation_term[i]}")
                    if i < len(vasap) and vasap[i] and vasap[i].strip().lower() == "yes":
                        probation_lines.append(f"<strong>VASAP:</strong> ✅")
                    if i < len(vip) and vip[i].strip().lower() == "yes":
                        probation_lines.append(f"<strong>VIP:</strong> ✅")
                    if i < len(community_service) and community_service[i].strip().lower() == "yes":
                        probation_lines.append(f"<strong>Community Service:</strong> ✅")
                    if i < len(anger_management) and anger_management[i].strip().lower() == "yes":
                        probation_lines.append(f"<strong>Anger Management:</strong> ✅")
                    if probation_lines:
                        email_html += "<span style='font-size:16pt;'><strong>Conditions of Probation:</strong><br>"
                        for line in probation_lines:
                            email_html += f"&nbsp;&nbsp;{line}<br>"
                        email_html += "</span>"
                # Add charge notes if present
                if i < len(charge_notes) and charge_notes[i].strip():
                    email_html += f"<span style='font-size:16pt;'><strong>Charge Notes:</strong> {charge_notes[i].strip()}<br></span>"
                email_html += "</p>"

        # Extra fields
        summary_fields = []

        if was_continued:
            if continuation_date:
                try:
                    formatted_continuation_date = datetime.strptime(continuation_date, "%Y-%m-%d").strftime("%B %d, %Y")
                except ValueError:
                    formatted_continuation_date = continuation_date
                if continuation_time:
                    try:
                        formatted_continuation_time = datetime.strptime(continuation_time, "%H:%M").strftime("%I:%M %p")
                    except ValueError:
                        formatted_continuation_time = continuation_time
                    summary_fields.append(f"<p style='font-size:16pt;'><strong>Case continued to</strong> {formatted_continuation_date} at {formatted_continuation_time}</p>")
                else:
                    summary_fields.append(f"<p style='font-size:16pt;'><strong>Case continued to</strong> {formatted_continuation_date}</p>")
            else:
                summary_fields.append("<p style='font-size:16pt;'><strong>Case Continued</strong></p>")

        if date_disposition:
            try:
                formatted_disposition_date = datetime.strptime(date_disposition, "%Y-%m-%d").strftime("%B %d, %Y")
            except ValueError:
                formatted_disposition_date = date_disposition
            summary_fields.append(f"<p style='font-size:16pt;'><strong>Disposition Date:</strong> {formatted_disposition_date}</p>")

        if notes:
            summary_fields.append(f"<p style='font-size:16pt;'><strong>Notes:</strong> {notes.replace(chr(10), '<br>')}</p>")

        if send_review_links:
            summary_fields.append("<p style='font-size:16pt;'><strong>Review Links Requested:</strong> Yes</p>")

        if summary_fields:
            email_html += "".join(summary_fields)
        msg = Message(subject, recipients=["attorneys@dischleylaw.com"])
        msg.html = email_html
        mail.send(msg)

        # Save to database, including send_review_links and new fields
        # Store the first non-empty disposition_paragraph[] in other_disposition
        disposition_narrative = ""
        for paragraph in disposition_paragraphs:
            if paragraph:
                disposition_narrative = paragraph
                break
        case_result_obj = CaseResult(
            defendant_name=defendant_name,
            notes=notes,
            date_disposition=date_disposition,
            was_continued=was_continued,
            continuation_date=continuation_date,
            send_review_links=send_review_links,
            license_suspension_term=", ".join(filter(None, license_suspension_term)) if license_suspension_term else None,
            restricted_license_type=", ".join(filter(None, restricted_license_type)) if restricted_license_type else None,
            other_disposition=disposition_narrative,
            clio_matter_id=clio_matter_id,
            clio_contact_id=clio_contact_id,
            plea_offer=plea_offer,
        )
        db.session.add(case_result_obj)
        db.session.commit()

        submitted = True
        return redirect(url_for('update_success'))
    return render_template('case_result.html', submitted=submitted)

@app.route("/case_result_success")
def case_result_success():
    return render_template("case_results_success.html")

def init_db():
    with app.app_context():
        db.drop_all()
        db.create_all()



# Route to reset the database
@app.route("/reset-db")
def reset_db():
    with app.app_context():
        db.drop_all()
        db.create_all()
    return "Database has been reset!"





# --- Expungement Generator Integration ---
# (already imported above)

@app.route("/expungement", methods=["GET", "POST"])
def expungement_form():
    # --- Update Stafford County prosecutor details ---
    if "Stafford County" in prosecutor_info:
        prosecutor_info["Stafford County"] = {
            "name": "Eric Olsen, Esq.",
            "title": "Stafford County Commonwealth's Attorney",
            "address1": "1245 Courthouse Road",
            "address2": "Stafford, VA 22555"
        }

    current_month = datetime.now().strftime("%B")
    current_year = datetime.now().year

    # Check for generated file in session to provide download link
    download_url = None
    generated_path = session.pop("generated_file_path", None)
    if generated_path and os.path.isfile(generated_path):
        filename = os.path.basename(generated_path)
        download_url = url_for("download_generated_file", filename=filename)

    # Get flashed messages for display
    from flask import get_flashed_messages
    messages = get_flashed_messages(with_categories=True)

    if request.method == "POST":
        form_data = request.form.to_dict()

        # Check for PDF file upload for extraction (AJAX or direct POST)
        file = request.files.get("file")
        if file and file.filename.endswith(".pdf"):
            from Expungement.expungement_utils import extract_expungement_data
            file_path = os.path.join("temp", file.filename)
            os.makedirs("temp", exist_ok=True)
            file.save(file_path)
            extracted_data = extract_expungement_data(file_path)
            # Explicitly map required keys into form_data for form population
            form_data['name'] = extracted_data.get('name', '')
            form_data['name_arrest'] = extracted_data.get('name_arrest', '')
            form_data['dob'] = extracted_data.get('dob', '')
            form_data['final_dispo'] = extracted_data.get('final_dispo', '')

        # Add attorney dropdown value
        attorney = form_data.get("attorney", "")

        # Law enforcement agency dropdown and "Other" textbox
        police_department = form_data.get("police_department", "")
        police_department_other = form_data.get("police_department_other", "")
        selected_police_department = police_department
        if police_department == "Other":
            selected_police_department = police_department_other

        # Date formatting helpers
        def format_date_long(date_str):
            for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y"):
                try:
                    return datetime.strptime(date_str, fmt).strftime("%B %d, %Y")
                except ValueError:
                    continue
            return date_str

        expungement_type = form_data.get("expungement_type", "")
        manifest_injustice_details = form_data.get("manifest_injustice_details", "")
        # Compose {Type of Expungement} logic as required
        if expungement_type == "Manifest Injustice":
            type_of_expungement = (
                f"The continued existence and possible dissemination of information relating to the charge(s) set forth herein has caused, "
                f"and may continue to cause, circumstances which constitute a manifest injustice to the Petitioner. "
                f"(to wit: {manifest_injustice_details})"
            )
        elif expungement_type == "Expungement of Right":
            type_of_expungement = (
                "The Petitioner has no prior criminal record, the aforementioned arrest was a misdemeanor offense, "
                "and the Commonwealth cannot show good cause to the contrary as to why the petition should not be granted."
            )
        elif expungement_type == "Automatic Expungement":
            type_of_expungement = "Automatic Expungement"
        else:
            type_of_expungement = (
                "The Petitioner has no prior criminal record, the aforementioned arrest was a misdemeanor offense, "
                "and the Commonwealth cannot show good cause to the contrary as to why the petition should not be granted."
            )

        # --- Collect all case fields (support multiple) ---
        # Detect all keys that match the pattern case_{i}_fieldname
        from collections import defaultdict
        import re
        case_fields = [
            "arrest_date", "officer_name", "police_department", "charge_name", "code_section",
            "vcc_code", "otn", "court_dispo", "case_no", "dispo_date"
        ]
        # We'll collect cases as a list of dicts
        cases = []
        # First, add the main case (no index) as case 0
        main_case = {}
        for field in case_fields:
            main_case[field] = form_data.get(field, "")
        cases.append(main_case)
        # Now, look for additional cases by index
        # Find all case_{i}_arrest_date, etc.
        indexed_case_data = defaultdict(dict)
        for key, value in form_data.items():
            match = re.match(r"case_(\d+)_(\w+)", key)
            if match:
                idx, field = match.groups()
                if field in case_fields:
                    indexed_case_data[int(idx)][field] = value
        # Add additional cases, in order
        for idx in sorted(indexed_case_data.keys()):
            cases.append(indexed_case_data[idx])

        # Optionally: Merge multiple sets of charges into the generated document.
        # For now, we will only use the first case for main document fields, but
        # include all cases in a list in data for potential use in document generation.
        # (To merge all cases into a single document, pass the list to populate_document if supported.)
        # Use the first case as the main one:
        first_case = cases[0] if cases else {}
        arrest_date_formatted = format_date_long(first_case.get("arrest_date", ""))
        dispo_date_formatted = format_date_long(first_case.get("dispo_date", ""))

        # Map form fields to template fields
        data = {
            "{NAME}": form_data.get("name", "").upper(),
            "{DOB}": format_date_long(form_data.get("dob", "")),
            "{County2}": form_data.get("county", "").title(),
            "{COUNTY}": form_data.get("county", "").upper(),
            "{Name at Time of Arrest}": form_data.get("name_arrest", form_data.get("name", "")),
            "{Name at Arrest}": form_data.get("name_arrest", form_data.get("name", "")),
            "{Type of Expungement}": type_of_expungement,
            "{Date of Arrest}": arrest_date_formatted,
            "{Arresting Officer}": first_case.get("officer_name", ""),
            "{Police Department}": selected_police_department,
            "{Charge Name}": first_case.get("charge_name", ""),
            "{Code Section}": first_case.get("code_section", ""),
            "{VCC Code}": first_case.get("vcc_code", ""),
            "{OTN}": first_case.get("otn", ""),
            "{Court Dispo}": first_case.get("court_dispo", ""),
            "{Case Number}": first_case.get("case_no", ""),
            "{Final Disposition}": form_data.get("final_dispo", ""),
            "{Dispo Date}": dispo_date_formatted,
            "{Prosecutor}": form_data.get("prosecutor", ""),
            "{Prosecutor Title}": form_data.get("prosecutor_title", ""),
            "{Prosecutor Address 1}": form_data.get("prosecutor_address1", ""),
            "{Prosecutor Address 2}": form_data.get("prosecutor_address2", ""),
            "{Month}": form_data.get("month", current_month),
            "{Year}": form_data.get("year", current_year),
            "{Attorney}": attorney,
            "{Expungement Type}": expungement_type,
            "{Manifest Injustice Details}": manifest_injustice_details,
            # --- Additional keys added below ---
            "{Arrest Date}": arrest_date_formatted,
            "{Officer Name}": first_case.get("officer_name", ""),
            "{Court of Final Dispo}": first_case.get("court_dispo", ""),
            "{Case No}": first_case.get("case_no", ""),
            # Add all cases for further processing if needed
            "cases": cases,
        }
        # Add {additional Cases} field for Word template
        data["{additional Cases}"] = ""
        if len(cases) > 1:
            for i, case in enumerate(cases[1:], 1):
                data["{additional Cases}"] += (
                    f"Additional Case {i}:\n"
                    f"Date of Arrest: {case.get('arrest_date', '')}\n"
                    f"Arresting Officer: {case.get('officer_name', '')}\n"
                    f"Police Department: {case.get('police_department', '')}\n"
                    f"Charge Name: {case.get('charge_name', '')}\n"
                    f"Code Section: {case.get('code_section', '')}\n"
                    f"VCC Code: {case.get('vcc_code', '')}\n"
                    f"OTN: {case.get('otn', '')}\n"
                    f"Court of Final Disposition: {case.get('court_dispo', '')}\n"
                    f"Case Number: {case.get('case_no', '')}\n"
                    f"Disposition Date: {case.get('dispo_date', '')}\n"
                    "\n"
                )

        output_dir = "temp"
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"{data['{NAME}'].replace(' ', '_')}_Expungement.docx")

        template_path = 'static/docs/Exp_Petition_Template.docx'
        populate_document(template_path, output_path, data)

        # Instead of sending the file directly, save file path to session and redirect to success page
        session["generated_file_path"] = output_path
        return redirect(url_for("expungement_success"))

    # Default response for GET requests or if no redirect has occurred
    autofill_data = session.pop("expungement_autofill_data", {})
    return render_template(
        'expungement.html',
        counties=prosecutor_info.keys(),
        current_month=current_month,
        current_year=current_year,
        messages=messages,
        download_url=download_url,
        autofill_data=autofill_data
    )


# --- Expungement Success Route ---
@app.route("/expungement/success")
def expungement_success():
    return render_template("success.html")



# --- API endpoint used by JS "Add Additional Case" button ---
# This endpoint supports the dynamic "Add Additional Case" functionality in the expungement form.
@app.route("/expungement/next_case_index", methods=["GET"])
def get_next_case_index():
    count = session.get("case_index", 1)
    session["case_index"] = count + 1
    return jsonify(index=count)


# --- Download generated expungement file route ---
@app.route("/download/<filename>")
def download_generated_file(filename):
    filepath = os.path.join("temp", filename)
    if os.path.exists(filepath):
        response = send_file(filepath, as_attachment=True)
        try:
            os.remove(filepath)
        except Exception as e:
            print(f"Failed to delete file: {filepath} — {e}")
        return response
    else:
        flash("File not found.", "danger")
        return redirect(url_for("expungement_form"))




# --- General PDF Upload and Case Parsing Route ---
from flask import request, render_template, jsonify
from pdfminer.high_level import extract_text
import re

def parse_case_info(text):
    cases = []
    pattern = re.compile(
        r"Case No\.\s*(?P<case_no>\S+).*?"
        r"Name:\s*(?P<name>[\w\s,]+).*?"
        r"Charge Name:\s*(?P<charge_name>.+?)\s+"
        r"Offense Date:\s*(?P<offense_date>\d{2}/\d{2}/\d{4}).*?"
        r"Final Disposition:\s*(?P<disposition>.+?)\s+"
        r"Disposition Date:\s*(?P<disposition_date>\d{2}/\d{2}/\d{4})",
        re.DOTALL
    )
    for match in pattern.finditer(text):
        cases.append(match.groupdict())
    return cases

@app.route('/upload', methods=['POST'])
def upload():
    file = request.files['file']
    if not file:
        return jsonify({'error': 'No file uploaded'}), 400
    text = extract_text(file)
    cases = parse_case_info(text)
    print("Parsed cases:", cases)
    if cases:
        # Use the first case for autofill
        parsed_case = cases[0]
        formatted_data = {
            "arrest_date": parsed_case.get("offense_date", ""),
            "charge_name": parsed_case.get("charge_name", ""),
            "case_no": parsed_case.get("case_no", ""),
            "court_dispo": parsed_case.get("disposition", ""),
            "dispo_date": parsed_case.get("disposition_date", "")
        }
        session["expungement_autofill_data"] = formatted_data
        return jsonify(formatted_data), 200
    return jsonify({}), 200


@app.route('/expungement/upload', methods=['POST'])
def expungement_upload():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if file and file.filename.endswith('.pdf'):
        from Expungement.expungement_utils import extract_expungement_data
        temp_path = os.path.join("temp", file.filename)
        os.makedirs("temp", exist_ok=True)
        file.save(temp_path)
        try:
            extracted_data = extract_expungement_data(temp_path)
            # Store the extracted data in session for autofill in UI
            session["expungement_autofill_data"] = extracted_data
            return jsonify(extracted_data), 200
        except Exception as e:
            app.logger.exception(f"Expungement upload failed during extraction: {str(e)}")
            return jsonify({'error': f'Failed to extract data from PDF: {str(e)}'}), 500
    return jsonify({'error': 'Invalid file type'}), 400


# --- Admin Tools Route ---
@app.route("/admin_tools")
def admin_tools():
    return render_template("admin_tools.html")

@app.route('/expungement/upload_batch', methods=['POST'])
def upload_batch():
    try:
        if not request.files:
            return jsonify({"status": "error", "message": "No files provided"}), 400
        files = request.files.getlist('files')
        results = []
        from Expungement.expungement_utils import extract_expungement_data
        for file in files:
            if file and file.filename.endswith('.pdf'):
                temp_path = os.path.join("temp", file.filename)
                os.makedirs("temp", exist_ok=True)
                file.save(temp_path)
                try:
                    data = extract_expungement_data(temp_path)
                    results.append({"filename": file.filename, "data": data})
                except Exception as e:
                    app.logger.exception(f"Failed to process file {file.filename}")
                    results.append({"filename": file.filename, "error": str(e)})
        return jsonify({"status": "success", "results": results}), 200
    except Exception as e:
        app.logger.exception("Unhandled error in batch upload")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/clio/authorize")
def clio_authorize():
    client_id = os.getenv("CLIO_CLIENT_ID")
    # Hardcode the redirect_uri to match the registered Clio callback
    scope = "read:contacts read:matters"
    oauth = OAuth2Session(client_id, redirect_uri="https://tools.dischleylaw.com/callback", scope=scope)
    authorization_url, state = oauth.authorization_url("https://app.clio.com/oauth/authorize")
    session["oauth_state"] = state
    return redirect(authorization_url)


# Only one /clio/callback route definition should exist.
@app.route("/clio/callback")
def clio_callback():
    client_id = os.getenv("CLIO_CLIENT_ID")
    client_secret = os.getenv("CLIO_CLIENT_SECRET")
    # Hardcode the redirect_uri to match the registered Clio callback
    oauth = OAuth2Session(client_id, redirect_uri="https://tools.dischleylaw.com/callback", state=session.get("oauth_state"))
    token = oauth.fetch_token(
        "https://app.clio.com/oauth/token",
        client_secret=client_secret,
        authorization_response=request.url
    )
    # Store token in database
    access_token = token.get("access_token")
    refresh_token = token.get("refresh_token")
    expires_in = token.get("expires_in")
    expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
    # Remove any existing token (assume singleton for this app)
    ClioToken.query.delete()
    db.session.commit()
    clio_token = ClioToken(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=expires_at
    )
    db.session.add(clio_token)
    db.session.commit()
    flash("Clio authorization successful.", "success")
    return redirect(url_for("dashboard"))


def get_valid_token():
    token = ClioToken.query.first()
    if token and not token.is_expired():
        return token.access_token
    # Refresh the token
    client_id = os.getenv("CLIO_CLIENT_ID")
    client_secret = os.getenv("CLIO_CLIENT_SECRET")
    refresh_token = token.refresh_token if token else None
    if not refresh_token:
        raise Exception("No refresh token available.")
    extra = {"client_id": client_id, "client_secret": client_secret}
    oauth = OAuth2Session(client_id, token={"refresh_token": refresh_token, "token_type": "Bearer", "expires_in": -30})
    new_token = oauth.refresh_token("https://app.clio.com/oauth/token", **extra)
    token.access_token = new_token.get("access_token")
    token.refresh_token = new_token.get("refresh_token")
    token.expires_at = datetime.utcnow() + timedelta(seconds=new_token.get("expires_in"))
    db.session.commit()
    return token.access_token
# --- OAuth2 Callback Route for Clio ---
# Place this near other route definitions
from flask import request
@app.route("/callback")
def callback():
    from urllib.parse import urlparse, parse_qs
    from requests_oauthlib import OAuth2Session
    import os

    client_id = os.getenv("CLIO_CLIENT_ID")
    client_secret = os.getenv("CLIO_CLIENT_SECRET")
    redirect_uri = "https://tools.dischleylaw.com/callback"
    token_url = "https://app.clio.com/oauth/token"

    oauth = OAuth2Session(client_id, redirect_uri=redirect_uri)
    authorization_response = request.url

    try:
        token = oauth.fetch_token(
            token_url,
            authorization_response=authorization_response,
            client_secret=client_secret
        )
        # Store token in the database (optional)
        clio_token = ClioToken(
            access_token=token.get("access_token"),
            refresh_token=token.get("refresh_token"),
            expires_at=datetime.utcnow() + timedelta(seconds=token.get("expires_in", 3600))
        )
        db.session.add(clio_token)
        db.session.commit()
        return "Authorization successful! You may close this window."
    except Exception as e:
        return f"Authorization failed: {str(e)}"