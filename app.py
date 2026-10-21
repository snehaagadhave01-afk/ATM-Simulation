from flask import Flask, render_template
from config import SECRET_KEY
from extensions import socketio
from routes.auth import auth_bp
from routes.account import account_bp
import sockets  # noqa: F401 -- registers the socket event handlers

app = Flask(__name__)
app.secret_key = SECRET_KEY

# Session hardening
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=1800,  # 30 min auto-logout
)

app.register_blueprint(auth_bp)
app.register_blueprint(account_bp)

socketio.init_app(app)


@app.route("/")
def home():
    return render_template("index.html")


if __name__ == "__main__":
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)