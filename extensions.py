"""
extensions.py
Shared extension instances, kept separate from app.py to avoid
circular imports between app.py and the route blueprints.
"""
from flask_socketio import SocketIO

socketio = SocketIO(cors_allowed_origins="*", async_mode="threading")