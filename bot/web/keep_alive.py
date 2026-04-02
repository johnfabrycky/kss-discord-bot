from threading import Thread

from flask import Flask

app = Flask('')


@app.route('/')
def home():
    """Return a simple healthcheck response for uptime monitors."""
    return "I'm alive!"


def run():
    """Run the lightweight Flask server used by the hosting platform."""
    app.run(host='0.0.0.0', port=8080)


def keep_alive():
    """Start the healthcheck web server in a background thread."""
    t = Thread(target=run)
    t.start()
