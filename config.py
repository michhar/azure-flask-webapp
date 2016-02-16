# General settings

CSRF_ENABLED = True
SECRET_KEY = 'something-secret'
DEBUG = True

import os
BASEDIR = os.path.abspath(os.path.dirname(__file__))

# DocumentDB settings

DOCUMENTDB_HOST = 'https://testingflask.documents.azure.com:443/'
DOCUMENTDB_KEY = 's610r3ylWxHNW87xKJYOmIzPWW/bHJNM7r4JCZ4PmSyJ2gUIEnasqH5wO9qkCY2LFkPV8kMulRa/U8+Ws9csoA=='

DOCDB_DATABASE = 'mladsapp'
DOCDB_COLLECTION_USER = 'user_collection'
DOCDB_COLLECTION_MASTER = 'master_collection'
DOCDB_MASTER_DOC = 'masterdoc'

# Config settings for google docs

SCOPE = ['https://spreadsheets.google.com/feeds']