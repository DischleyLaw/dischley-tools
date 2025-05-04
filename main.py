from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash

# --- Login Required Decorator ---
# This decorator is now a no-op; login is not required for any routes.
def login_required(f):
    return f

app = Flask(__name__)

# --- Expungement Generator POST Route ---
@app.route("/expungement/generate", methods=["POST"])
def generate_expungement():
    from datetime import datetime
    form_data = request.form.to_dict()

    # Format dates
    def format_date(date_str):
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").strftime("%B %d, %Y")
        except ValueError:
            return date_str

    arrest_date_formatted = format_date(form_data.get("arrest_date", ""))
    dispo_date_formatted = format_date(form_data.get("dispo_date", ""))

    expungement_type = form_data.get("expungement_type", "")
    manifest_injustice_details = form_data.get("manifest_injustice_details", "")
    if expungement_type == "Manifest Injustice":
        type_of_expungement = f"The continued existence... constitutes a manifest injustice... (to wit: {manifest_injustice_details})."
    else:
        type_of_expungement = "The Petitioner has no prior criminal record..."

    police_department = form_data.get("police_department", "")
    police_department_other = form_data.get("other_police_department", "")
    selected_police_department = police_department if police_department != "Other" else police_department_other

    data = {
        "{NAME}": form_data.get("name", ""),
        "{DOB}": form_data.get("dob", ""),
        "{County2}": form_data.get("county", "").title(),
        "{COUNTY}": form_data.get("county", "").upper(),
        "{Name at Time of Arrest}": form_data.get("name_arrest", ""),
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
        "{Manifest Injustice Details}": manifest_injustice_details
    }

    output_dir = "temp"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{data['{NAME}'].replace(' ', '_')}_Draft_Petition.docx")

    template_path = 'static/data/Exp_Petition (Template).docx'
    from Expungement.expungement_utils import populate_document
    populate_document(template_path, output_path, data)

    print("✅ Expungement document generated and ready to download:", output_path)
    return send_file(output_path, as_attachment=True)

from Expungement.expungement_utils import extract_expungement_data
from flask_mail import Mail, Message

import requests
import os
from dotenv import load_dotenv
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from datetime import datetime, timedelta
from email.utils import formataddr
from requests_oauthlib import OAuth2Session

from itsdangerous import URLSafeTimedSerializer

load_dotenv()

app = Flask(__name__)
app.secret_key = "supersecretkey"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///leads.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# Set session expiration to 24 hours of inactivity
from datetime import timedelta
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)

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
    custom_source = db.Column(db.String(100))
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
    homework_additional = db.Column(db.Boolean, default=False)
    homework_additional_notes = db.Column(db.String(200))
    # New field: NO HW
    homework_no_hw = db.Column(db.Boolean, default=False)

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

# --- Charge Model ---
class Charge(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    case_result_id = db.Column(db.Integer, db.ForeignKey('case_result.id'), nullable=False)
    original_charge = db.Column(db.String(200))
    amended_charge = db.Column(db.String(200))
    disposition = db.Column(db.String(100))
    jail_time_imposed = db.Column(db.String(50))
    jail_time_suspended = db.Column(db.String(50))
    fine_imposed = db.Column(db.String(50))
    fine_suspended = db.Column(db.String(50))
    license_suspension = db.Column(db.String(100))
    restricted_license = db.Column(db.String(100))


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


# --- Clio Token Model ---
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
    # Show admin_tools button for all logged-in users (or restrict to admin if needed)
    show_admin_tools = True
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

        lead_source = data.get("lead_source")
        custom_source = data.get("custom_source") if lead_source == "Other" else None

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
            custom_source=custom_source,
            case_type=case_type,
            charges=data.get("charges"),
            staff_member=staff_member,
            homework=data.get("homework"),
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
        email_html = "<h2>New Lead:</h2>"
        email_html += "<ul style='list-style-type:none;padding-left:0;'>"
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
            ("Custom Source", custom_source if custom_source else None),
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
                email_html += f"<li><strong>{label}:</strong> {value}</li>"
        email_html += "</ul>"
        email_html += f"<p><a href='{lead_url}'>Manage Lead</a></p>"
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
    print(f"Loading view_lead for ID: {lead_id}")
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
    lead.quote = ""  # Reset quote string

    lead.name = request.form.get("name") if request.form.get("name") else lead.name
    lead.phone = request.form.get("phone") if request.form.get("phone") else lead.phone
    lead.email = request.form.get("email") if request.form.get("email") else lead.email
    lead.charges = request.form.get("charges") if request.form.get("charges") else lead.charges
    lead.court_date = request.form.get("court_date") if request.form.get("court_date") else lead.court_date
    lead.court_time = request.form.get("court_time") if request.form.get("court_time") else lead.court_time
    lead.court = request.form.get("court") if request.form.get("court") else lead.court
    lead.notes = request.form.get("notes") if request.form.get("notes") else lead.notes
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
    lead.custom_source = request.form.get("custom_source") if request.form.get("custom_source") else lead.custom_source
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
    status_str = " | ".join(status_parts)
    first_name, last_name = (lead.name.split(maxsplit=1) + [""])[:2]
    subject_line = f"Lead Updated - {first_name} {last_name}".strip()
    # Prepare update email (HTML)
    msg = Message(subject_line,
                  recipients=["attorneys@dischleylaw.com"],
                  sender=("New Lead", os.getenv('MAIL_DEFAULT_SENDER')))
    email_html = f"<h2>Lead Updated - {status_str if status_str else 'No Status'}</h2>"
    email_html += "<ul style='list-style-type:none;padding-left:0;'>"
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
    # Compose using the required mapping
    field_items = [
        ("Type of Case", lead.case_type),
        ("Name", lead.name),
        ("Phone", lead.phone),
        ("Email", lead.email),
        ("Charges", lead.charges),
        ("Court", lead.court),
        ("Court Date", formatted_court_date),
        ("Court Time", formatted_time),
        ("Brief Description of the Facts", lead.facts),
        ("Notes", lead.notes),
        ("Staff Member", lead.staff_member),
        ("Attorney", request.form.get("attorney")),
        ("Lead Source", lead.lead_source if lead.lead_source and lead.lead_source != "Other" else None),
        ("Custom Source", lead.custom_source if lead.custom_source else None),
        ("Send Retainer", "✅" if lead.send_retainer else None),
        ("Retainer Amount", f"${float(lead.retainer_amount):.2f}" if lead.retainer_amount and lead.retainer_amount.replace('.', '', 1).isdigit() else lead.retainer_amount),
        ("LVM", "✅" if lead.lvm else None),
        ("Not a PC", "✅" if lead.not_pc else None),
        ("Quote", f"${float(lead.quote.strip()):.2f}" if lead.quote and lead.quote.strip().lower() != "none" and lead.quote.strip().replace('.', '', 1).isdigit() else lead.quote.strip() if lead.quote else None),
        ("Absence Waiver", "✅" if lead.absence_waiver else None),
        ("Homework", lead.homework if lead.homework else None),
        ("Calling", "✅" if lead.calling else None),
    ]
    for label, value in field_items:
        if value:
            email_html += f"<li><strong>{label}:</strong> {value}</li>"
    # Add homework checkboxes to email
    if getattr(lead, "homework_reckless_program", None): email_html += "<li><strong>Reckless/Aggressive Driving Program:</strong> ✅</li>"
    if lead.homework_driver_improvement: email_html += "<li><strong>Driver Improvement Course:</strong> ✅</li>"
    if lead.homework_community_service:
        email_html += "<li><strong>Community Service:</strong> ✅"
        if lead.homework_community_service_hours:
            email_html += f" ({lead.homework_community_service_hours} hours)"
        email_html += "</li>"
    if lead.homework_substance_evaluation: email_html += "<li><strong>Substance Abuse Evaluation:</strong> ✅</li>"
    if lead.homework_driving_record: email_html += "<li><strong>Driving Record:</strong> ✅</li>"
    if lead.homework_asap: email_html += "<li><strong>Pre-enroll in ASAP:</strong> ✅</li>"
    if lead.homework_shoplifting: email_html += "<li><strong>Shoplifting Class:</strong> ✅</li>"
    # Additional homework fields for email
    if getattr(lead, "homework_speedometer", None): email_html += "<li><strong>Speedometer Calibration:</strong> ✅</li>"
    if getattr(lead, "homework_medical_conditions", None): email_html += "<li><strong>Medical Conditions / Surgeries List:</strong> ✅</li>"
    if getattr(lead, "homework_photos", None): email_html += "<li><strong>Photographs of Field Sobriety Scene:</strong> ✅</li>"
    if getattr(lead, "homework_shoplifting_program", None): email_html += "<li><strong>Shoplifting Theft Offenders Program:</strong> ✅</li>"
    if getattr(lead, "homework_military_awards", None): email_html += "<li><strong>Copies of Military Awards:</strong> ✅</li>"
    if getattr(lead, "homework_dd214", None): email_html += "<li><strong>Copy of DD-214:</strong> ✅</li>"
    if getattr(lead, "homework_community_involvement", None): email_html += "<li><strong>Community Involvement List:</strong> ✅</li>"
    if getattr(lead, "homework_anger_management_courseforcourt", None): email_html += "<li><strong>Anger Management (Courseforcourt.com):</strong> ✅</li>"
    if getattr(lead, "homework_vasap", None): email_html += "<li><strong>Pre-Enroll in VASAP:</strong> ✅</li>"
    if getattr(lead, "homework_substance_abuse_treatment", None): email_html += "<li><strong>Substance Abuse Eval/Treatment:</strong> ✅</li>"
    if getattr(lead, "homework_substance_abuse_counseling", None): email_html += "<li><strong>Substance Abuse Counseling:</strong> ✅</li>"
    if getattr(lead, "homework_transcripts", None): email_html += "<li><strong>High School or College Transcripts:</strong> ✅</li>"
    # New: NO HW
    if getattr(lead, "homework_no_hw", None): email_html += "<li><strong>NO HW:</strong> ✅</li>"
    # Additional Homework (with notes)
    if getattr(lead, "homework_additional", None):
        note = lead.homework_additional_notes or ""
        email_html += f"<li><strong>Additional Homework:</strong> ✅ {note}</li>"
    email_html += "</ul>"
    email_html += f"<p><a href='{url_for('view_lead', lead_id=lead.id, _external=True)}'>Manage Lead</a></p>"
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
                            full_name = f"{contact.get('first_name', '').strip()} {contact.get('last_name', '').strip()}".strip()
                            if contact_name_input.lower() in full_name.lower():
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
        fine_imposed = request.form.getlist('fine_imposed[]')
        fine_suspended = request.form.getlist('fine_suspended[]')
        license_suspension = request.form.getlist('license_suspension[]')
        restricted_license = request.form.getlist('restricted_license[]')
        # New: Retrieve restricted_license_type and license_suspension_term
        license_suspension_term = request.form.getlist('license_suspension_term[]')
        restricted_license_type = request.form.getlist('restricted_license_type[]')
        asap_ordered = request.form.getlist('asap_ordered[]')
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
        email_html = "<h2>Case Result</h2>"
        email_html += f"<p><strong>Defendant:</strong> {defendant_name}</p>"
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
            email_html += "<ul>"
            for i in range(num_charges):
                email_html += f"<li><strong>Charge {i+1}:</strong><ul>"
                if i < len(original_charges) and original_charges[i]:
                    email_html += f"<li><strong>Original Charge:</strong> {original_charges[i]}</li>"
                if i < len(amended_charges) and amended_charges[i]:
                    email_html += f"<li><strong>Amended Charge:</strong> {amended_charges[i]}</li>"
                if i < len(pleas) and pleas[i]:
                    email_html += f"<li><strong>Plea:</strong> {pleas[i]}</li>"
                if i < len(dispositions) and dispositions[i]:
                    email_html += f"<li><strong>Disposition:</strong> {dispositions[i]}</li>"
                # NEW: If disposition in skip_dispositions, include disposition paragraph
                if i < len(dispositions) and dispositions[i] in skip_dispositions:
                    if i < len(disposition_paragraphs) and disposition_paragraphs[i]:
                        email_html += f"<li><strong>Disposition Narrative:</strong> {disposition_paragraphs[i]}</li>"
                # Only render jail, fine, probation, license fields if not in skip_dispositions
                if i < len(dispositions) and dispositions[i] not in skip_dispositions:
                    # Per-charge sentencing/probation fields:
                    if i < len(jail_time_imposed) and jail_time_imposed[i]:
                        if i < len(jail_time_suspended) and jail_time_suspended[i]:
                            email_html += f"<li><strong>Jail:</strong> {jail_time_imposed[i]} days with {jail_time_suspended[i]} days suspended</li>"
                        else:
                            email_html += f"<li><strong>Jail:</strong> {jail_time_imposed[i]} days</li>"
                    if i < len(fine_imposed) and fine_imposed[i]:
                        if i < len(fine_suspended) and fine_suspended[i]:
                            email_html += f"<li><strong>Fine:</strong> ${fine_imposed[i]} with ${fine_suspended[i]} suspended</li>"
                        else:
                            email_html += f"<li><strong>Fine:</strong> ${fine_imposed[i]}</li>"
                    # License Suspension: Only show check if "Yes"
                    if i < len(license_suspension) and license_suspension[i].strip().lower() == "yes":
                        email_html += "<li><strong>License Suspension:</strong> ✅</li>"
                    # Compose restricted license info: include type and term if granted
                    if i < len(restricted_license) and restricted_license[i].strip().lower() == "yes":
                        restricted_info = "<li><strong>Restricted License Granted:</strong> Yes"
                        details = []
                        if i < len(restricted_license_type) and restricted_license_type[i]:
                            details.append(f"Type: {restricted_license_type[i]}")
                        if i < len(license_suspension_term) and license_suspension_term[i]:
                            details.append(f"Term: {license_suspension_term[i]}")
                        if details:
                            restricted_info += f" ({'; '.join(details)})"
                        restricted_info += "</li>"
                        email_html += restricted_info
                    # ASAP Ordered: Only show if "Yes"
                    if i < len(asap_ordered) and asap_ordered[i].strip().lower() == "yes":
                        email_html += "<li><strong>ASAP Ordered:</strong> ✅</li>"
                    # Probation
                    probation_fields = []
                    if i < len(probation_type) and probation_type[i]:
                        probation_fields.append(f"<li><strong>Probation Type:</strong> {probation_type[i]}</li>")
                    if i < len(probation_term) and probation_term[i]:
                        probation_fields.append(f"<li><strong>Probation Term:</strong> {probation_term[i]}</li>")
                    if i < len(vasap) and vasap[i].strip().lower() == "yes":
                        probation_fields.append(f"<li><strong>VASAP:</strong> ✅</li>")
                    if i < len(vip) and vip[i].strip().lower() == "yes":
                        probation_fields.append(f"<li><strong>VIP:</strong> ✅</li>")
                    if i < len(community_service) and community_service[i].strip().lower() == "yes":
                        probation_fields.append(f"<li><strong>Community Service:</strong> ✅</li>")
                    if i < len(anger_management) and anger_management[i].strip().lower() == "yes":
                        probation_fields.append(f"<li><strong>Anger Management:</strong> ✅</li>")
                    if probation_fields:
                        email_html += "<li><strong>Conditions of Probation:</strong><ul>"
                        email_html += "".join(probation_fields)
                        email_html += "</ul></li>"
                email_html += "</ul></li>"
            email_html += "</ul>"

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
                    summary_fields.append(f"<li><strong>Case Continued To:</strong> {formatted_continuation_date} at {formatted_continuation_time}</li>")
                else:
                    summary_fields.append(f"<li><strong>Case Continued To:</strong> {formatted_continuation_date}</li>")
            else:
                summary_fields.append("<li><strong>Case Continued</strong></li>")

        if date_disposition:
            try:
                formatted_disposition_date = datetime.strptime(date_disposition, "%Y-%m-%d").strftime("%B %d, %Y")
            except ValueError:
                formatted_disposition_date = date_disposition
            summary_fields.append(f"<li><strong>Disposition Date:</strong> {formatted_disposition_date}</li>")

        if notes:
            summary_fields.append(f"<li><strong>Notes:</strong> {notes.replace(chr(10), '<br>')}</li>")

        if send_review_links:
            summary_fields.append("<li><strong>Review Links Requested:</strong> Yes</li>")

        if summary_fields:
            email_html += "<ul>"
            email_html += "".join(summary_fields)
            email_html += "</ul>"
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
from Expungement.expungement_utils import populate_document, prosecutor_info

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

    from datetime import datetime
    current_month = datetime.now().strftime("%B")
    current_year = datetime.now().year

    if request.method == "POST":
        form_data = request.form.to_dict()

        # Add attorney dropdown value
        attorney = form_data.get("attorney", "")

        # Law enforcement agency dropdown and "Other" textbox
        police_department = form_data.get("police_department", "")
        police_department_other = form_data.get("police_department_other", "")
        selected_police_department = police_department
        if police_department == "Other":
            selected_police_department = police_department_other

        # Format dates to "January 1, 2025"
        def format_date(date_str):
            try:
                return datetime.strptime(date_str, "%Y-%m-%d").strftime("%B %d, %Y")
            except ValueError:
                return date_str

        arrest_date_formatted = format_date(form_data.get("arrest_date", ""))
        dispo_date_formatted = format_date(form_data.get("dispo_date", ""))

        expungement_type = form_data.get("expungement_type", "")
        manifest_injustice_details = form_data.get("manifest_injustice_details", "")
        # Compose {Type of Expungement} logic as required
        if expungement_type == "Manifest Injustice":
            type_of_expungement = f"The continued existence... constitutes a manifest injustice... (to wit: {manifest_injustice_details})."
        else:
            type_of_expungement = "The Petitioner has no prior criminal record..."

        # Map form fields to template fields
        data = {
            "{NAME}": form_data.get("name", ""),
            "{DOB}": form_data.get("dob", ""),
            "{County2}": form_data.get("county", "").title(),
            "{COUNTY}": form_data.get("county", "").upper(),
            "{Name at Time of Arrest}": form_data.get("name_arrest", ""),
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
            "{Month}": form_data.get("month", current_month),
            "{Year}": form_data.get("year", current_year),
            "{Attorney}": attorney,
            "{Expungement Type}": expungement_type,
            "{Manifest Injustice Details}": manifest_injustice_details
        }

        output_dir = "temp"
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"{data['{NAME}'].replace(' ', '_')}_Expungement.docx")

        template_path = 'static/data/Exp_Petition (Template).docx'
        populate_document(template_path, output_path, data)

        return send_file(output_path, as_attachment=True)

    return render_template(
        'expungement.html',
        counties=prosecutor_info.keys(),
        current_month=current_month,
        current_year=current_year
    )



# --- Expungement PDF Upload and Parsing Route ---
@app.route("/expungement/upload", methods=["POST"])
def expungement_upload():
    uploaded_file = request.files.get("file")
    if not uploaded_file or uploaded_file.filename == "":
        flash("No file uploaded.", "danger")
        return redirect(url_for("expungement_form"))

    # Save the uploaded file to a temporary location
    temp_path = os.path.join("temp", uploaded_file.filename)
    os.makedirs("temp", exist_ok=True)
    uploaded_file.save(temp_path)

    from Expungement.expungement_utils import extract_expungement_data
    import re
    try:
        form_data = extract_expungement_data(temp_path)
        if not form_data or not any(form_data.values()):
            raise ValueError("Empty form_data from PDF parser.")
    except Exception as e:
        flash("Failed to extract data from PDF. Please ensure the file is a valid expungement report.", "danger")
        return redirect(url_for("expungement_form"))

    # --- Ensure name, name_arrest, and dob fields are filled and cleaned from extracted data ---
    form_data["name"] = form_data.get("name", "").strip()
    form_data["name_arrest"] = form_data.get("name_arrest", form_data["name"]).strip()
    form_data["dob"] = form_data.get("dob", "").strip()

    # Extract a clean arresting officer name
    raw_officer = form_data.get("officer_name", "")
    officer_match = re.search(r"([A-Z]+,\s?[A-Z])", raw_officer)
    if officer_match:
        form_data["officer_name"] = officer_match.group(1).title()

    # --- Clean up charge_name, otn, and code_section fields ---
    raw_charge = form_data.get("charge_name", "")
    match = re.search(r"^(.*?)OffenseTracking", raw_charge)
    if match:
        form_data["charge_name"] = match.group(1).strip()

    raw_otn = re.search(r"OffenseTracking/Processing#\s*:\s*([A-Z0-9]+)", raw_charge)
    if raw_otn:
        form_data["otn"] = raw_otn.group(1)

    # Extract code section and prepend "Va. Code § " if found
    raw_code = re.search(r"CodeSection\s*:\s*(\S+)", raw_charge)
    if raw_code:
        form_data["code_section"] = f"Va. Code § {raw_code.group(1)}"


    # Clean up final_dispo field for cleaner output.
    form_data["final_dispo"] = form_data.get("final_dispo", "")
    if "SentenceTime" in form_data["final_dispo"]:
        form_data["final_dispo"] = form_data["final_dispo"].split("SentenceTime")[0].strip()

    # Print cleaned form_data for verification
    print("Final cleaned form_data for autofill:", form_data)

    # Ensure name_arrest and dob are populated if missing
    if not form_data.get("name_arrest"):
        form_data["name_arrest"] = form_data.get("name", "")
    if not form_data.get("name"):
        form_data["name"] = form_data.get("name_arrest", "")
    if not form_data.get("dob"):
        form_data["dob"] = ""

    from datetime import datetime
    return render_template(
        "expungement.html",
        name=form_data.get("name", ""),
        dob=form_data.get("dob", ""),
        county=form_data.get("county", ""),
        name_arrest=form_data.get("name_arrest", ""),
        expungement_type=form_data.get("expungement_type", ""),
        manifest_injustice_details=form_data.get("manifest_injustice_details", ""),
        arrest_date=form_data.get("arrest_date", ""),
        officer_name=form_data.get("officer_name", ""),
        police_department=form_data.get("police_department", ""),
        charge_name=form_data.get("charge_name", ""),
        code_section=form_data.get("code_section", ""),
        vcc_code=form_data.get("vcc_code", ""),
        otn=form_data.get("otn", ""),
        court_dispo=form_data.get("court_dispo") or "Court not extracted",
        case_no=form_data.get("case_no", ""),
        final_dispo=form_data.get("final_dispo", ""),
        dispo_date=form_data.get("dispo_date", ""),
        prosecutor=form_data.get("prosecutor", ""),
        prosecutor_title=form_data.get("prosecutor_title", ""),
        prosecutor_address1=form_data.get("prosecutor_address1", ""),
        prosecutor_address2=form_data.get("prosecutor_address2", ""),
        current_month=datetime.now().strftime("%B"),
        current_year=datetime.now().year,
        counties=prosecutor_info.keys()
    )


# Run the Flask app

# --- Clio OAuth Integration ---
client_id = os.getenv('CLIO_CLIENT_ID')
client_secret = os.getenv('CLIO_CLIENT_SECRET')
redirect_uri = os.getenv('CLIO_REDIRECT_URI')

authorization_base_url = 'https://app.clio.com/oauth/authorize'
token_url = 'https://app.clio.com/oauth/token'

@app.route('/clio/authorize')
def clio_authorize():
    clio = OAuth2Session(client_id, redirect_uri=redirect_uri, scope=['read:matters'])
    authorization_url, state = clio.authorization_url(authorization_base_url)
    return redirect(authorization_url)

@app.route('/callback')
def clio_callback():
    clio = OAuth2Session(client_id, redirect_uri=redirect_uri)
    token = clio.fetch_token(token_url, client_secret=client_secret,
                             authorization_response=request.url)

    expires_in = token.get('expires_in')
    expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

    existing_token = ClioToken.query.first()
    if existing_token:
        db.session.delete(existing_token)
        db.session.commit()

    new_token = ClioToken(
        access_token=token['access_token'],
        refresh_token=token['refresh_token'],
        expires_at=expires_at
    )
    db.session.add(new_token)
    db.session.commit()

    return "Clio Authorization Successful!"

def get_valid_token():
    token_entry = ClioToken.query.first()
    if not token_entry:
        raise Exception("Clio not authorized. Visit /clio/authorize first.")

    if token_entry.is_expired():
        extra = {'client_id': client_id, 'client_secret': client_secret}
        clio = OAuth2Session(client_id, token={
            'refresh_token': token_entry.refresh_token,
            'token_type': 'Bearer',
            'access_token': token_entry.access_token,
            'expires_in': -30
        })
        new_token = clio.refresh_token(token_url, **extra)

        expires_in = new_token.get('expires_in')
        token_entry.access_token = new_token['access_token']
        token_entry.refresh_token = new_token['refresh_token']
        token_entry.expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
        db.session.commit()

    return token_entry.access_token


@app.route('/clio/matters')
def get_matters():
    try:
        access_token = get_valid_token()
    except Exception as e:
        return {"error": f"Token Error: {str(e)}"}, 500

    headers = {'Authorization': f'Bearer {access_token}'}
    # Filter only open matters
    base_url = 'https://app.clio.com/api/v4/matters?status=open'
    all_matters = []
    url = base_url

    while url:
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            return {
                "error": "Failed to fetch matters",
                "status_code": response.status_code,
                "details": response.text
            }, response.status_code

        data = response.json()
        all_matters.extend(data.get('data', []))
        url = data.get('links', {}).get('next')  # Get the next page URL

    return {"matters": all_matters}


# --- Clio Contact Search Route ---
@app.route('/clio/contact-search')
def clio_contact_search():
    query = request.args.get('query', '').strip().lower()
    try:
        access_token = get_valid_token()
        headers = {'Authorization': f'Bearer {access_token}'}
        response = requests.get(f'https://app.clio.com/api/v4/contacts?query={query}', headers=headers)
        if response.status_code != 200:
            return {"data": []}

        contacts = response.json().get("data", [])
        people = []
        # Only return results if query is non-empty
        if query:
            for contact in contacts:
                if contact.get("type", "").lower() == "person":
                    first = contact.get("first_name", "") or ""
                    last = contact.get("last_name", "") or ""
                    name_fallback = contact.get("name", "").strip()
                    full_name = f"{first} {last}".strip() or name_fallback

                    # Skip contacts with empty names
                    if not full_name:
                        continue

                    if query in full_name.lower():
                        people.append({
                            "id": contact.get("id"),
                            "type": "Person",
                            "name": full_name,
                            "email": contact.get("email", "")
                        })
        return {"data": people}
    except Exception as e:
        return {"data": [], "error": str(e)}, 500



# --- Clio Test Contacts Route ---
@app.route("/clio/test-contacts")
def test_clio_contacts():
    try:
        access_token = get_valid_token()
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get("https://app.clio.com/api/v4/contacts", headers=headers)
        return response.json()  # Show raw Clio contact data
    except Exception as e:
        return {"error": str(e)}, 500

if __name__ == "__main__":
    from post_deploy import run_post_deploy
    run_post_deploy()
    app.run(debug=True)


# --- Admin Tools Page ---
@app.route("/admin_tools")
def admin_tools():
    return render_template("admin_tools.html")