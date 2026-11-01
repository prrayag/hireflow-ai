# wsgi.py - Web Server Gateway Interface entry point
from app import app

# In production, Flask's built-in development server is not strong enough
# to handle multiple real users efficiently, and it's not secure.
# Instead, we use Gunicorn (a production-grade WSGI HTTP server) to run
# the app. Gunicorn will look at this file and serve the `app` object.

if __name__ == "__main__":
    app.run()
