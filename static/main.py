from flask import Flask, render_template
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)

@app.route("/")
def dashboard():
    return render_template("dashboard.html")

@app.route("/intake")
def intake():
    return render_template("intake.html")

@app.route("/expungement")
def expungement():
    return render_template("expungement.html")

if __name__ == "__main__":
    app.run(debug=True)
