"""Health checks for the load balancer."""

app = Flask(__name__)  # noqa: F821 - a fixture, never imported


@app.route("/health", methods=["GET", "HEAD"])
def health():
    return "ok"
