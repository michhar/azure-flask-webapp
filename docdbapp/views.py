"""
Routes and views for the flask application.
"""

from datetime import datetime
from flask import render_template, Blueprint, redirect, url_for, request
from docdbapp import app

from forms import SetupForm, Form
import config
import pydocumentdb.document_client as document_client

import json
import os
import gspread
from oauth2client.client import SignedJwtAssertionCredentials

import pandas as pd
import numpy as np
from collections import defaultdict
import pprint as pp
from pandas.io.json import read_json
from flask_wtf.form import Form

mod = Blueprint('mod', __name__, template_folder = 'templates')

@mod.route('/about')
def about():
    """Renders the about page."""
    return render_template(
        'about.html',
        title='About',
        year=datetime.now().year,
        message='Your application description page.'
    )

@mod.route('/contact')
def contact():
    """Renders the contact page."""
    return render_template(
        'contact.html',
        title='Contact',
        year=datetime.now().year,
        message='Your contact page.'
    )

@mod.route('/')
@mod.route('/home')
def home():
    """Renders the home page."""
    return render_template('index.html',
                           title='Home Page',
                           year=datetime.now().year)

@mod.route('/collaborate', methods = ['GET', 'POST'])
def collaborate():
    form = SetupForm()
    if form.validate_on_submit():
        # gather user info
        if request.method == 'POST':
            creds = request.files['credfile']
            email = form.email.data
        else:
            return render_template('collaborate.html',
                                   form = form,
                                   title = 'Collaborate',
                                   year = datetime.now().year)

        try:
            # create connection to google doc
            json_key = json.loads(creds.read())
            credentials = SignedJwtAssertionCredentials(json_key['client_email'], json_key['private_key'].encode(), config.SCOPE)
            gc = gspread.authorize(credentials)
            wksheet = gc.open(form.docname.data).worksheet('crop master')

            # get contents as a list of dicts
            contents = wksheet.get_all_values()

            df = pd.DataFrame(contents)

            # Tidy up
            #   - make some columns names based on first 5 rows
            #   - grab data and label columns
            headers = df.iloc[3:5,:]
            newheaders = headers.sum(axis=0)
            newdf = df.iloc[7:-1, :].copy()
            newdf.columns = newheaders

            # TODO: tidy up more
            #  - unnecessary columns
            #  - add user/farmer name as a multiindex

            # convert to json
            # records orientation will result in list like [{column -> value}, ... , {column -> value}]
            jsonrecord = newdf.to_json(orient = 'values')

            # going to use 'individuals' collection
            # does it exist?  if not make it, if so just add this doc

            # make a client connection
            client = document_client.DocumentClient(config.DOCUMENTDB_HOST, {'masterKey': config.DOCUMENTDB_KEY})

            # Read databases and get our working database
            db = next((data for data in client.ReadDatabases() if data['id'] == config.DOCDB_DATABASE))

            # Read collections and get the "user collection"
            coll_user = next((coll for coll in client.ReadCollections(db['_self']) if coll['id'] == config.DOCDB_COLLECTION_USER))

            # create or update user using upsert API
            doc = client.UpsertDocument(coll_user['_self'],
                                        { 'id': form.email.data,
                                          'timestamp': datetime.now().strftime('%c'),
                                          'data': jsonrecord,
                                          'data_headers': newheaders.to_json(orient = 'values')})

            # Read collections and get the "master collection"
            coll_master = next((coll for coll in client.ReadCollections(db['_self']) 
                                if coll['id'] == config.DOCDB_COLLECTION_MASTER))

            doc_definition = { 'id': config.DOCDB_MASTER_DOC,
                               'timestamp': datetime.now().strftime('%c'),
                               'data_headers': newheaders.to_json(orient = 'values')}

            # get all user docs
            user_docs = client.ReadDocuments(coll_user['_self'])

            # gather data in user docs into one dataframe
            user_data_dfs = []
            for doc in user_docs:
                user_data_dfs.append(pd.DataFrame(read_json(doc['data'])))
            user_data_concatd = pd.concat(user_data_dfs)

            # convert to json
            master_records = user_data_concatd.to_json(orient = 'values')

            # add data to the doc definition
            doc_definition['data'] = master_records

            # upsert master with the doc definition
            doc = client.UpsertDocument(coll_master['_self'], doc_definition)


        except gspread.SpreadsheetNotFound, e:
            return render_template('error_page.html',
                                   title = 'Something went wrong!',
                                   year = datetime.now().year,
                                   message = '''The spreadsheet was not found.
                                   Please ensure you have enabled Google Drive API and
                                   created a new set of credentials.''',
                                   link = 'http://gspread.readthedocs.org/en/latest/oauth2.html')
                                   
        return redirect(url_for('.publish'))
    else:
        return render_template('collaborate.html',
                               form = form,
                               title = 'Collaborate',
                               year = datetime.now().year)

@mod.route('/publish', methods = ['GET', 'POST'])
def publish():
    form = Form()
    if form.validate_on_submit():
        try:
            # TODO: add this to config instead
            json_filepath = os.path.join('C:\\', 'Users', 'michhar', 'Documents', 'MLADS', 'data', 'MessyDoc-8f814e3f2a78.json')
            json_key = json.load(open(json_filepath))

            credentials = SignedJwtAssertionCredentials(json_key['client_email'], json_key['private_key'].encode(), config.SCOPE)

            gc = gspread.authorize(credentials)

            # TODO: create a worksheet if not there, also put this in config
            wksheet = gc.open("SSF_Crop_Master_2012_Master_crop_master").worksheet('latest')

            # make a client connection
            client = document_client.DocumentClient(config.DOCUMENTDB_HOST, {'masterKey': config.DOCUMENTDB_KEY})

            # Read databases and get our working database
            db = next((data for data in client.ReadDatabases() if data['id'] == config.DOCDB_DATABASE))

            # Read collections and get the "user collection"
            coll_master = next((coll for coll in client.ReadCollections(db['_self']) if coll['id'] == config.DOCDB_COLLECTION_MASTER))


            master_doc = next((doc for doc in client.ReadDocuments(coll_master['_self']) if doc['id'] == config.DOCDB_MASTER_DOC))
            master_data_df = read_json(master_doc['data'])
            headers = read_json(master_doc['data_headers'])
            master_data_df.columns = headers

            # update all cells in master google doc with data in master doc from db
            # this takes a minute or two (maybe put into a separate view function)
            update_worksheet(wksheet, master_data_df)

            return render_template('results.html',
                        masterlink = 'https://docs.google.com/spreadsheets/d/1MKcDtjI5E-iNv9tU2KcA5yJWWgaSTh5j2IjPYOp9lic/pubhtml',
                        title = 'Results',
                        year = datetime.now().year,
                        message = 'Success! Your data has been stored and the master sheet updated here ')

        except gspread.SpreadsheetNotFound, e:

            return render_template('error_page.html',
                                   title = 'Something went wrong!',
                                   year = datetime.now().year,
                                   message = '''The spreadsheet was not found.
                                   Please ensure you have enabled Google Drive API and
                                   created a new set of credentials.''',
                                   link = 'http://gspread.readthedocs.org/en/latest/oauth2.html')

    return render_template('publish.html',
                           title = 'Publish',
                           form = form,
                        year = datetime.now().year,
                        message = 'Publish master data to master google doc.')

@mod.route('/report')
def report():
    return render_template('index.html',
                           title='Home Page',
                           year=datetime.now().year)


@mod.route('/download')
def download():
    return render_template('index.html',
                           title='Home Page',
                           year=datetime.now().year)

@mod.route('/query')
def query():
    client = document_client.DocumentClient(config.DOCUMENTDB_HOST, {'masterKey': config.DOCUMENTDB_KEY})

    # Read databases and take the first since the id should not be duplicated.
    db = next((data for data in client.ReadDatabases() if data['id'] == config.DOCUMENTDB_DATABASE))

    # Read collections and take the first since the id should not be duplicated.
    coll = next((coll for coll in client.ReadCollections(db['_self']) if coll['id'] == config.DOCUMENTDB_COLLECTION))

    # Read documents and take the first since the id should not be duplicated.
    doc = next((doc for doc in client.ReadDocuments(coll['_self']) if doc['id'] == config.DOCUMENTDB_DOCUMENT))

    res = client.QueryDocuments(coll['_self'], query = "select *")

    return redirect(url_for('.home'))

def numberToLetters(q):
    '''This converts a number,q,  into proper column name format for spreadsheet (e.g. R1C28 -> AB1).'''
    q = q - 1
    result = ''
    while q >= 0:
        remain = q % 26
        result = chr(remain+65) + result;
        q = q//26 - 1
    return result

def update_worksheet(wksheet, df):
    '''This function updates a given worksheet (wksheet)
    with the values in the dataframe (df).'''

    # TODO: confirm there are enough columns in existing doc to match query

    columns = df.columns.values.tolist()
    # selection of the range that will be updated
    cell_list = wksheet.range('A1:'+numberToLetters(len(columns))+'1')

    # modifying the values in the range
    for cell in cell_list:
        val = columns[cell.col-1]
        if type(val) is str:
            val = val.decode('utf-8')
        cell.value = val
    # update in batch
    wksheet.update_cells(cell_list)

    #number of lines and columns
    num_lines, num_columns = df.shape
    # selection of the range that will be updated
    cell_list = wksheet.range('A2:'+numberToLetters(num_columns)+str(num_lines+1))
    # modifying the values in the range
    for cell in cell_list:
        val = df.iloc[cell.row-2,cell.col-1]
        if type(val) is str:
            val = val.decode('utf-8')
        elif isinstance(val, (int, long, float, complex)):
            # note that we round all numbers
            val = int(round(val))
        cell.value = val
    # update in batch
    wksheet.update_cells(cell_list)