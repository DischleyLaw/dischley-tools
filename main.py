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
from datetime import datetime
from email.utils import formataddr

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

with app.app_context():
    db.create_all()

# --- Admin Leads Dashboard ---
@app.route("/admin/leads")
@login_required
def admin_leads():
    leads = Lead.query.order_by(Lead.created_at.desc()).all()
    return render_template("admin_leads.html", leads=leads)

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
    homework = db.Column(db.Text)
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
            homework=data.get("homework"),
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

        msg = Message(f"New Lead - PC: {last_name}, {first_name}",
                      recipients=["attorneys@dischleylaw.com"],
                      sender=("New Lead", os.getenv('MAIL_DEFAULT_SENDER')))

        email_lines = ["NEW LEAD INFORMATION\n"]

        if case_type:
            email_lines.append(f"Type of Case: {case_type}\n")

        if first_name:
            email_lines.append(f"First Name: {first_name}\n")

        if last_name:
            email_lines.append(f"Last Name: {last_name}\n")

        if new_lead.phone:
            email_lines.append(f"Phone Number: {new_lead.phone}\n")

        if new_lead.email:
            email_lines.append(f"Email: {new_lead.email}\n")

        if new_lead.charges:
            email_lines.append(f"Charges: {new_lead.charges}\n")

        if new_lead.court:
            email_lines.append(f"Court: {new_lead.court}\n")

        if formatted_date != "N/A":
            email_lines.append(f"Court Date: {formatted_date}\n")

        if new_lead.court_time:
            email_lines.append(f"Court Time: {new_lead.court_time}\n")

        if new_lead.homework:
            email_lines.append(f"Brief Description of the Facts: {new_lead.homework}\n")

        if new_lead.notes:
            email_lines.append(f"Notes: {new_lead.notes}\n")

        if staff_member:
            email_lines.append(f"Staff Member: {staff_member}\n")
        if data.get("attorney"):
            email_lines.append(f"Attorney: {data.get('attorney')}\n")

        if lead_source or custom_source:
            source_display = lead_source if lead_source != 'Other' else custom_source
            email_lines.append(f"Lead Source: {source_display}\n")

        email_lines.append(f"\nManage Lead: {lead_url}")

        msg.body = "\n".join(email_lines)
        mail.send(msg)

        # Clio
        clio_payload = {
            "inbox_lead": {
                "from_first": new_lead.name.split()[0],
                "from_last": new_lead.name.split()[-1],
                "from_email": new_lead.email,
                "from_phone": new_lead.phone,
                "from_message": f"Case Type: {case_type}, Charges: {new_lead.charges}, Notes: {new_lead.notes}, Homework: {new_lead.homework}",
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
    lead.homework = request.form.get("homework", lead.homework)
    lead.send_retainer = 'send_retainer' in request.form
    lead.retainer_amount = request.form.get("retainer_amount") if lead.send_retainer else None
    lead.lvm = 'lvm' in request.form
    lead.not_pc = 'not_pc' in request.form
    lead.quote = request.form.get("quote")
    lead.lead_source = request.form.get("lead_source", lead.lead_source)
    lead.custom_source = request.form.get("custom_source", lead.custom_source)
    lead.staff_member = request.form.get("staff_member", lead.staff_member)
    lead.absence_waiver = 'absence_waiver' in request.form

    db.session.commit()

    # Prepare update email
    msg = Message(f"Lead Updated: {lead.name}",
                  recipients=["attorneys@dischleylaw.com"],
                  sender=("New Lead", os.getenv('MAIL_DEFAULT_SENDER')))
    update_lines = ["LEAD UPDATED\n"]

    if lead.case_type:
        update_lines.append(f"Type of Case: {lead.case_type}\n")

    if lead.name:
        update_lines.append(f"Name: {lead.name}\n")

    if lead.phone:
        update_lines.append(f"Phone: {lead.phone}\n")

    if lead.email:
        update_lines.append(f"Email: {lead.email}\n")

    if lead.charges:
        update_lines.append(f"Charges: {lead.charges}\n")

    if lead.court:
        update_lines.append(f"Court: {lead.court}\n")

    if lead.court_date:
        update_lines.append(f"Court Date: {lead.court_date}\n")

    if lead.court_time:
        update_lines.append(f"Court Time: {lead.court_time}\n")

    if lead.homework:
        update_lines.append(f"Brief Description of the Facts: {lead.homework}\n")

    if lead.notes:
        update_lines.append(f"Notes: {lead.notes}\n")

    if lead.staff_member:
        update_lines.append(f"Staff Member: {lead.staff_member}\n")

    if request.form.get("attorney"):
        update_lines.append(f"Attorney: {request.form.get('attorney')}\n")

    if lead.lead_source or lead.custom_source:
        source_display = lead.lead_source if lead.lead_source != 'Other' else lead.custom_source
        update_lines.append(f"Lead Source: {source_display}\n")

    update_lines.append(f"Send Retainer: {'✅' if lead.send_retainer else '❌'} {f'(${lead.retainer_amount})' if lead.send_retainer else ''}\n")
    update_lines.append(f"LVM: {'✅' if lead.lvm else '❌'}\n")
    update_lines.append(f"Not a PC: {'✅' if lead.not_pc else '❌'}\n")
    update_lines.append(f"Quote: ${lead.quote or 'N/A'}\n")
    update_lines.append(f"Absence Waiver: {'✅' if lead.absence_waiver else '❌'}\n")
    update_lines.append(f"\nView Lead: {url_for('view_lead', lead_id=lead.id, _external=True)}")

    msg.body = "\n".join(update_lines)
    mail.send(msg)

    # Optional: Send auto-email to client if LVM is checked and client email exists
    if lead.lvm and lead.email:
        client_name = lead.name if lead.name else "there"
        auto_msg = Message(
            "Thank You for Your Inquiry",
            recipients=[lead.email],
            sender=("Dischley Law, PLLC", os.getenv('MAIL_DEFAULT_SENDER'))
        )
        auto_msg.body = f"""
Dear {client_name},

Thank you for contacting Dischley Law, PLLC regarding your legal matter. We appreciate the opportunity to assist you.

We attempted to reach you by phone but were unable to connect. At your convenience, please feel free to return our call so we can discuss your case in more detail and answer any questions you may have.

You can reach us at (703) 635-2424. We look forward to speaking with you.

Best regards,
Dischley Law, PLLC
(703) 635-2424
attorneys@dischleylaw.com
www.dischleylaw.com
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
    if request.method == "POST":
        data = request.form
        
        # Process multiple charges with fallback to prevent IndexError
        offenses = request.form.getlist("offense[]") or [request.form.get("offense")]
        amended_charges = request.form.getlist("amended_charge[]") or [request.form.get("amended_charge")]
        dispositions = request.form.getlist("disposition[]") or [request.form.get("disposition")]
        fines_imposed = request.form.getlist("fine_imposed[]") or [request.form.get("fine_imposed")]
        jail_time_imposed = request.form.getlist("jail_time_imposed[]") or [request.form.get("jail_time_imposed")]
        jail_time_suspended = request.form.getlist("jail_time_suspended[]") or [request.form.get("jail_time_suspended")]
        license_suspension = request.form.getlist("license_suspension[]") or [request.form.get("license_suspension")]
        
        msg_body_lines = ["CASE RESULT\n"]
        if data.get("defendant_name"):
            msg_body_lines.append(f"Defendant: {data.get('defendant_name')}\n")
        if data.get("court"):
            msg_body_lines.append(f"Court: {data.get('court')}\n")
        if data.get("was_continued"):
            msg_body_lines.append(f"Was Case Continued?: {data.get('was_continued')}\n")
            continuation_date = data.get("continuation_date")
            continuation_time = data.get("continuation_time")
            if continuation_date:
                try:
                    formatted_date = datetime.strptime(continuation_date, "%Y-%m-%d").strftime("%B %d, %Y")
                except ValueError:
                    formatted_date = continuation_date
                if continuation_time:
                    # Format time to h:mm a.m./p.m.
                    try:
                        formatted_time = datetime.strptime(continuation_time, "%H:%M").strftime("%I:%M %p").lstrip("0").replace("AM", "a.m.").replace("PM", "p.m.")
                    except ValueError:
                        formatted_time = continuation_time
                    msg_body_lines.append(f"Continuation Date: {formatted_date} at {formatted_time}\n")
                else:
                    msg_body_lines.append(f"Continuation Date: {formatted_date}\n")

        for i in range(len(offenses)):
            # Show all original charges (including additional offenses)
            if offenses[i]:
                msg_body_lines.append(f"Original Charge: {offenses[i]}\n")
            # Show amended charge if present
            if amended_charges[i]:
                msg_body_lines.append(f"Final Amended Charge: {amended_charges[i]}\n")
            # Show disposition if present
            if dispositions[i]:
                msg_body_lines.append(f"Final Disposition: {dispositions[i]}\n")

            # Fine formatting
            fine_imposed = fines_imposed[i] if i < len(fines_imposed) else ""
            fine_suspended_list = data.getlist("fine_suspended[]")
            fine_suspended = fine_suspended_list[i] if i < len(fine_suspended_list) else ""
            if fine_imposed:
                fine_text = f"${fine_imposed} fine"
                if fine_suspended:
                    fine_text += f" with ${fine_suspended} suspended"
                msg_body_lines.append(f"Fine: {fine_text}\n")

            # Jail formatting
            jail_imposed = jail_time_imposed[i] if i < len(jail_time_imposed) else ""
            jail_suspended_list = data.getlist("jail_time_suspended[]")
            jail_suspended = jail_suspended_list[i] if i < len(jail_suspended_list) else ""
            if jail_imposed:
                jail_text = f"{jail_imposed} days in jail"
                if jail_suspended:
                    jail_text += f" with {jail_suspended} days suspended"
                msg_body_lines.append(f"Jail Sentence: {jail_text}\n")

            # License suspension
            lic_susp = license_suspension[i] if i < len(license_suspension) else ""
            if lic_susp:
                msg_body_lines.append(f"License Suspension: {lic_susp}\n")

        if data.get("asap_ordered"):
            msg_body_lines.append(f"ASAP Ordered: {data.get('asap_ordered')}\n")

        if data.get("other_disposition"):
            msg_body_lines.append(f"Other Disposition Notes: {data.get('other_disposition')}\n")
        if data.get("restricted_license"):
            msg_body_lines.append(f"Restricted License: {data.get('restricted_license')}\n")
        if data.get("interlock_type"):
            msg_body_lines.append(f"Interlock Type: {data.get('interlock_type')}\n")
        if data.get("vip_ordered"):
            msg_body_lines.append(f"VIP Ordered: {data.get('vip_ordered')}\n")
        if data.get("community_service"):
            msg_body_lines.append(f"Community Service: {data.get('community_service')}\n")
        if data.get("anger_management"):
            msg_body_lines.append(f"Anger Management: {data.get('anger_management')}\n")
        if data.get("probation_type"):
            msg_body_lines.append(f"Probation Type: {data.get('probation_type')}\n")
        if data.get("probation_term"):
            msg_body_lines.append(f"Probation Term: {data.get('probation_term')}\n")
        if data.get("date_disposition"):
            msg_body_lines.append(f"Disposition Date: {data.get('date_disposition')}\n")
        if data.get("notes"):
            msg_body_lines.append(f"Notes: {data.get('notes')}\n")

        msg_body = "\n".join(msg_body_lines)
        
        result = CaseResult(
            defendant_name=data.get("defendant_name"),
            offense=offenses[0],  # Store only the first offense in the database
            amended_charge=amended_charges[0],  # Store only the first amended charge in the database
            disposition=dispositions[0],  # Store only the first disposition in the database
            other_disposition=data.get("other_disposition"),
            jail_time_imposed=data.get("jail_time_imposed"),
            jail_time_suspended=data.get("jail_time_suspended"),
            fine_imposed=data.get("fine_imposed"),
            fine_suspended=data.get("fine_suspended"),
            license_suspension=data.get("license_suspension"),
            asap_ordered=data.get("asap_ordered"),
            probation_type=data.get("probation_type"),
            probation_term=data.get("probation_term"),
            was_continued=data.get("was_continued"),
            continuation_date=data.get("continuation_date"),
            client_email=data.get("client_email"),
            notes=data.get("notes"),
            date_disposition=data.get("date_disposition"),
        )
        db.session.add(result)
        db.session.commit()

        msg = Message(
            subject=f"Case Result - {data.get('defendant_name')}",
            recipients=["attorneys@dischleylaw.com"],
            sender=formataddr(("Case Result", os.getenv('MAIL_DEFAULT_SENDER')))
        )
        msg.body = msg_body
        mail.send(msg)

        return redirect(url_for("case_result_success"))
    return render_template("case_result.html")

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
if __name__ == "__main__":
    app.run(debug=True)
