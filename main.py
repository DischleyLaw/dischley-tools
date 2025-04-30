from flask import Flask, render_template, request, redirect, url_for, session, send_file
from flask_mail import Mail, Message
from functools import wraps

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function
import requests
import os
from dotenv import load_dotenv
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from datetime import datetime, timedelta
from email.utils import formataddr
from requests_oauthlib import OAuth2Session

load_dotenv()

app = Flask(__name__)
app.secret_key = "supersecretkey"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///leads.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

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
@login_required
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
@login_required
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
    quote = db.Column(db.String(50))
    lead_source = db.Column(db.String(100))
    custom_source = db.Column(db.String(100))
    case_type = db.Column(db.String(100))
    charges = db.Column(db.Text)
    staff_member = db.Column(db.String(100))
    absence_waiver = db.Column(db.Boolean, default=False)
    homework = db.Column(db.Text)

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
@login_required
def dashboard():
    case_results = CaseResult.query.order_by(CaseResult.created_at.desc()).all()
    return render_template("dashboard.html", case_results=case_results)

@app.route("/leads")
@login_required
def view_leads():
    leads = Lead.query.order_by(Lead.created_at.desc()).all()
    return render_template("leads.html", leads=leads)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username == "admin" and password == "dischley123":
            session["user"] = username
            return redirect(url_for("dashboard"))
        return render_template("login.html", error="Invalid credentials")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))

@app.route("/intake", methods=["GET", "POST"])
@login_required
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

        lead_url = url_for("view_lead", lead_id=new_lead.id, _external=True)

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

        msg = Message(f"PC: {last_name}, {first_name}",
                      recipients=["attorneys@dischleylaw.com"],
                      sender=("New Lead", os.getenv('MAIL_DEFAULT_SENDER')))

        # Compose HTML email with all submitted fields if present, using required mapping
        email_html = "<h2>New Lead Information</h2>"
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
                "from_first": new_lead.name.split()[0],
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
                "from_source": custom_source or lead_source
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
@login_required
def view_lead(lead_id):
    print(f"Loading view_lead for ID: {lead_id}")
    lead = Lead.query.get_or_404(lead_id)
    return render_template("view_lead.html", lead=lead)

@app.route("/lead/<int:lead_id>/update", methods=["POST"])
@login_required
def update_lead(lead_id):
    lead = Lead.query.get_or_404(lead_id)

    lead.name = request.form.get("name", lead.name)
    lead.phone = request.form.get("phone", lead.phone)
    lead.email = request.form.get("email", lead.email)
    lead.charges = request.form.get("charges", lead.charges)
    lead.court_date = request.form.get("court_date", lead.court_date)
    lead.court_time = request.form.get("court_time", lead.court_time)
    lead.court = request.form.get("court", lead.court)
    lead.notes = request.form.get("notes", lead.notes)
    lead.facts = request.form.get("facts", lead.facts)
    lead.send_retainer = 'send_retainer' in request.form
    lead.retainer_amount = request.form.get("retainer_amount") if lead.send_retainer else None
    lead.lvm = 'lvm' in request.form
    lead.not_pc = 'not_pc' in request.form
    lead.quote = request.form.get("quote")
    lead.lead_source = request.form.get("lead_source", lead.lead_source)
    lead.custom_source = request.form.get("custom_source", lead.custom_source)
    lead.staff_member = request.form.get("staff_member", lead.staff_member)
    lead.absence_waiver = 'absence_waiver' in request.form
    lead.homework = request.form.get("homework", lead.homework)

    db.session.commit()

    # Prepare update email (HTML)
    msg = Message(f"Lead Updated: {lead.name}",
                  recipients=["attorneys@dischleylaw.com"],
                  sender=("New Lead", os.getenv('MAIL_DEFAULT_SENDER')))
    email_html = "<h2>Lead Updated</h2>"
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
        ("Homework", lead.homework),
        ("Staff Member", lead.staff_member),
        ("Attorney", request.form.get("attorney")),
        ("Lead Source", lead.lead_source if lead.lead_source and lead.lead_source != "Other" else None),
        ("Custom Source", lead.custom_source if lead.custom_source else None),
        ("Send Retainer", "✅" if lead.send_retainer else None),
        ("Retainer Amount", lead.retainer_amount),
        ("LVM", "✅" if lead.lvm else None),
        ("Not a PC", "✅" if lead.not_pc else None),
        ("Quote", lead.quote),
        ("Absence Waiver", "✅" if getattr(lead, 'absence_waiver', False) else None),
    ]
    for label, value in field_items:
        if value:
            email_html += f"<li><strong>{label}:</strong> {value}</li>"
    email_html += "</ul>"
    email_html += f"<p><a href='{url_for('view_lead', lead_id=lead.id, _external=True)}'>Manage Lead</a></p>"
    msg.html = email_html
    mail.send(msg)

    # Optional: Send auto-email to client if LVM is checked and client email exists
    if lead.lvm and lead.email:
        client_name = lead.name if lead.name else "there"
        # Extract attorney from form, stripping whitespace
        attorney = request.form.get("attorney", "An Attorney").strip()
        # Set callback number and reply email based on explicit attorney name check
        if "patrick o'brien" in attorney.lower():
            callback_number = "(571) 352-1633"
            reply_email = "patrick@dischleylaw.com"
        else:
            callback_number = "703-851-7137"
            reply_email = "david@dischleylaw.com"
        auto_msg = Message(
            "Thank You for Your Inquiry",
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
{callback_number}
"""
        mail.send(auto_msg)

    return redirect(url_for("update_success"))

@app.route("/lead/<int:lead_id>/edit", methods=["GET", "POST"])
@login_required
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
@login_required
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
@login_required
def case_result():
    submitted = False
    if request.method == "POST":
        defendant_name = request.form.get('defendant_name')
        original_charges = request.form.getlist('original_charge')
        amended_charges = request.form.getlist('amended_charge')
        pleas = request.form.getlist('plea')
        dispositions = request.form.getlist('disposition')

        jail_time_imposed = request.form.getlist('jail_time_imposed[]')
        jail_time_suspended = request.form.getlist('jail_time_suspended[]')
        fine_imposed = request.form.getlist('fine_imposed[]')
        fine_suspended = request.form.getlist('fine_suspended[]')
        license_suspension = request.form.getlist('license_suspension[]')
        restricted_license = request.form.getlist('restricted_license[]')
        asap_ordered = request.form.getlist('asap_ordered[]')
        probation_type = request.form.getlist('probation_type[]')
        probation_term = request.form.getlist('probation_term[]')
        vasap = request.form.getlist('vasap[]')
        vip = request.form.getlist('vip[]')
        community_service = request.form.getlist('community_service[]')
        anger_management = request.form.getlist('anger_management[]')
        absence_waiver = request.form.getlist('absence_waiver[]')
        was_continued = request.form.get('was_continued', '').strip()
        continuation_date = request.form.get('continuation_date', '').strip()
        date_disposition = request.form.get('date_disposition', '').strip()
        notes = request.form.get('notes', '').strip()

        subject = f"Case Result - {defendant_name}"
        email_html = "<h2>Case Result</h2>"
        email_html += f"<p><strong>Defendant:</strong> {defendant_name}</p>"
        num_charges = max(len(original_charges), len(amended_charges), len(pleas), len(dispositions))
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
                if i < len(license_suspension) and license_suspension[i]:
                    email_html += f"<li><strong>License Suspension:</strong> {license_suspension[i]}</li>"
                if i < len(restricted_license) and restricted_license[i]:
                    email_html += f"<li><strong>Restricted License:</strong> {restricted_license[i]}</li>"
                if i < len(asap_ordered) and asap_ordered[i]:
                    email_html += f"<li><strong>ASAP Ordered:</strong> {asap_ordered[i]}</li>"
                # Probation
                probation_fields = []
                if i < len(probation_type) and probation_type[i]:
                    probation_fields.append(f"<li><strong>Probation Type:</strong> {probation_type[i]}</li>")
                if i < len(probation_term) and probation_term[i]:
                    probation_fields.append(f"<li><strong>Probation Term:</strong> {probation_term[i]}</li>")
                if i < len(vasap) and vasap[i]:
                    probation_fields.append(f"<li><strong>VASAP:</strong> Yes</li>")
                if i < len(vip) and vip[i]:
                    probation_fields.append(f"<li><strong>VIP:</strong> Yes</li>")
                if i < len(community_service) and community_service[i]:
                    probation_fields.append(f"<li><strong>Community Service:</strong> Yes</li>")
                if i < len(anger_management) and anger_management[i]:
                    probation_fields.append(f"<li><strong>Anger Management:</strong> Yes</li>")
                if i < len(absence_waiver) and absence_waiver[i]:
                    probation_fields.append(f"<li><strong>Absence Waiver:</strong> Yes</li>")
                if probation_fields:
                    email_html += "<li><strong>Conditions of Probation:</strong><ul>"
                    email_html += "".join(probation_fields)
                    email_html += "</ul></li>"
                email_html += "</ul></li>"
            email_html += "</ul>"
        # Add summary-level fields if present and not already included above
        summary_fields = []
        if was_continued:
            if continuation_date:
                try:
                    formatted_continuation_date = datetime.strptime(continuation_date, "%Y-%m-%d").strftime("%B %d, %Y")
                except ValueError:
                    formatted_continuation_date = continuation_date
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
        # If no charges, add any sentencing/probation fields from index 0 if present
        if num_charges == 0:
            if len(jail_time_imposed) > 0 and jail_time_imposed[0]:
                if len(jail_time_suspended) > 0 and jail_time_suspended[0]:
                    summary_fields.append(f"<li><strong>Jail:</strong> {jail_time_imposed[0]} days with {jail_time_suspended[0]} days suspended</li>")
                else:
                    summary_fields.append(f"<li><strong>Jail:</strong> {jail_time_imposed[0]} days</li>")
            elif len(jail_time_suspended) > 0 and jail_time_suspended[0]:
                summary_fields.append(f"<li><strong>Jail Suspended:</strong> {jail_time_suspended[0]} days</li>")
            if len(fine_imposed) > 0 and fine_imposed[0]:
                if len(fine_suspended) > 0 and fine_suspended[0]:
                    summary_fields.append(f"<li><strong>Fine:</strong> ${fine_imposed[0]} with ${fine_suspended[0]} suspended</li>")
                else:
                    summary_fields.append(f"<li><strong>Fine:</strong> ${fine_imposed[0]}</li>")
            elif len(fine_suspended) > 0 and fine_suspended[0]:
                summary_fields.append(f"<li><strong>Fine Suspended:</strong> ${fine_suspended[0]}</li>")
            if len(license_suspension) > 0 and license_suspension[0]:
                summary_fields.append(f"<li><strong>License Suspension:</strong> {license_suspension[0]}</li>")
            if len(restricted_license) > 0 and restricted_license[0]:
                summary_fields.append(f"<li><strong>Restricted License:</strong> {restricted_license[0]}</li>")
            if len(asap_ordered) > 0 and asap_ordered[0]:
                summary_fields.append(f"<li><strong>ASAP Ordered:</strong> {asap_ordered[0]}</li>")
            # Conditions of Probation
            probation_fields = []
            if len(probation_type) > 0 and probation_type[0]:
                probation_fields.append(f"<li><strong>Probation Type:</strong> {probation_type[0]}</li>")
            if len(probation_term) > 0 and probation_term[0]:
                probation_fields.append(f"<li><strong>Probation Term:</strong> {probation_term[0]}</li>")
            if len(vasap) > 0 and vasap[0]:
                probation_fields.append(f"<li><strong>VASAP:</strong> Yes</li>")
            if len(vip) > 0 and vip[0]:
                probation_fields.append(f"<li><strong>VIP:</strong> Yes</li>")
            if len(community_service) > 0 and community_service[0]:
                probation_fields.append(f"<li><strong>Community Service:</strong> Yes</li>")
            if len(anger_management) > 0 and anger_management[0]:
                probation_fields.append(f"<li><strong>Anger Management:</strong> Yes</li>")
            if len(absence_waiver) > 0 and absence_waiver[0]:
                probation_fields.append(f"<li><strong>Absence Waiver:</strong> Yes</li>")
            if probation_fields:
                summary_fields.append("<li><strong>Conditions of Probation:</strong><ul>")
                summary_fields.extend(probation_fields)
                summary_fields.append("</ul></li>")
        if summary_fields:
            email_html += "<ul>"
            email_html += "".join(summary_fields)
            email_html += "</ul>"
        msg = Message(subject, recipients=["attorneys@dischleylaw.com"])
        msg.html = email_html
        mail.send(msg)
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
@login_required
def expungement_form():
    if request.method == "POST":
        data = request.form.to_dict()

        county = data.get('county')
        expungement_type = data.get('expungement_type')

        if expungement_type == "Expungement of Right":
            expungement_clause = "The Petitioner has no prior criminal record, the aforementioned arrest was a misdemeanor offense, and the Commonwealth cannot show good cause to the contrary as to why the petition should not be granted."
        elif expungement_type == "Manifest Injustice":
            manifest_injustice = data.get('manifest_injustice')
            expungement_clause = f"The continued existence and possible dissemination of information relating to the charge(s) set forth herein has caused, and may continue to cause, circumstances which constitute a manifest injustice to the Petitioner, and the Commonwealth cannot show good cause to the contrary as to why the petition should not be granted. (to wit: {manifest_injustice})."
        else:
            expungement_clause = ""

        prosecutor = prosecutor_info[county]
        data.update({
            "{Prosecutor}": prosecutor['name'],
            "{Prosecutor Title}": prosecutor['title'],
            "{Prosecutor Address 1}": prosecutor['address1'],
            "{Prosecutor Address 2}": prosecutor['address2'],
            "{COUNTY}": county.upper(),
            "{County2}": county.title(),
            "{Type of Expungement}": expungement_clause
        })

        template_path = 'ExpungementTemplate.docx'
        output_path = f'temp/{data["{NAME}"]}_Expungement.docx'

        os.makedirs('temp', exist_ok=True)
        populate_document(template_path, output_path, data)

        return send_file(output_path, as_attachment=True)

    return render_template('expungement_form.html', counties=prosecutor_info.keys())


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
    response = requests.get('https://app.clio.com/api/v4/matters', headers=headers)

    if response.status_code == 200:
        matters = response.json()['data']
        return {"matters": matters}
    else:
        return {
            "error": "Failed to fetch matters",
            "status_code": response.status_code,
            "details": response.text
        }, response.status_code


if __name__ == "__main__":
    app.run(debug=True)
