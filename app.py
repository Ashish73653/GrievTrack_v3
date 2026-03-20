from flask import Flask, redirect, render_template, url_for


app = Flask(__name__)


@app.route("/")
def index():
    return redirect(url_for("dashboard"))


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


@app.route("/submit")
def submit():
    return render_template("submit.html")


@app.route("/update")
def update():
    return render_template("update.html")


@app.route("/timeline/")
def timeline():
    return render_template("timeline.html")


@app.route("/audit")
def audit():
    return render_template("audit.html")


@app.route("/benchmark")
def benchmark():
    return render_template("benchmark.html")


@app.route("/reset")
def reset():
    return render_template("reset.html")


if __name__ == "__main__":
    app.run(debug=True)
