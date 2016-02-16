"""
The flask application package.
"""

from flask import Flask, Blueprint

app = Flask(__name__)
app.config.from_object('config')

from docdbapp.views import mod as mainModule
app.register_blueprint(mainModule)