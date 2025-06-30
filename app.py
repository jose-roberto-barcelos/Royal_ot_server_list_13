import os
import subprocess
from flask import Flask, jsonify, send_from_directory

app = Flask(__name__, static_folder="public", static_url_path="")

# Rota para coletar/ranking
@app.route("/run_tasks", methods=["GET"])
def run_tasks():
    try:
        subprocess.run(["./run_all.sh"], check=True)
        return jsonify({"status": "ok"}), 200
    except subprocess.CalledProcessError as e:
        return jsonify({"status": "error", "detail": str(e)}), 500

# Serve front-end em public/
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve(path):
    if path and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, "index.html")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
