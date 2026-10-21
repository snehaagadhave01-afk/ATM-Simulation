"""
sockets.py
WebSocket event handlers. Each logged-in user joins a private room
named after their user_id, so balance updates only ever broadcast
to that user's own open tabs/devices -- never to other accounts.
"""
from flask import session
from flask_socketio import join_room

from extensions import socketio


@socketio.on("connect")
def handle_connect():
    user_id = session.get("user_id")
    if user_id:
        join_room(f"user_{user_id}")


@socketio.on("disconnect")
def handle_disconnect():
    pass