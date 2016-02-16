from flask.ext.wtf import Form
from wtforms.fields import StringField, FileField
from wtforms.validators import DataRequired

class SetupForm(Form):
    email = StringField(u'Your email', validators = [DataRequired()])
    credfile = FileField(validators = [DataRequired()])
    docname = StringField(u'Your Document Name', validators = [DataRequired()])