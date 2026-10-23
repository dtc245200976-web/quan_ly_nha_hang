import os 
import time
import psycopg
from flask import Flask, jsonify

app = Flask(__name__)

def get_connection():
    for _ in range(30):
        try:
            return psycopg.connect(
                host=os.getenv("DB_HOST", "db"),
                dbname=os.getenv("POSTGRES_DB", "restaurant"),
                user=os.getenv("POSTGRES_USER", "restaurant"),
                password=os.getenv("POSTGRES_PASSWORD", "change-this-password"),
            )
        except psycopg.OperationalError:
            time.sleep(2)
    raise RuntimeError("Database connection failed")

@app.get("/")
def home():
    return "<h1>Restaurant Manager</h1><p>Website is running.</p>"

@app.get("/health")
def health():
    with get_connection() as connection:
        connection.execute("SELECT 1")
    return jsonify(status="ok", database="connected")

app.run(host="0.0.0.0", port=8000)
