import os
import shutil
import pathlib
from flask import Flask, jsonify, render_template, redirect, url_for, request
import logging
import logging.config
import sqlite3
import zipfile
import folium
import pandas as pd
import geopandas as gpd



#####
# Set up
#####

# Set up the logging
os.makedirs('logs', exist_ok=True)
logging_config = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '%(asctime)s [%(levelname)s] %(message)s'
        },
        'detailed': {
            'format': '%(asctime)s [%(levelname)s] %(filename)s:%(lineno)d - %(message)s'
        },
    },
    'handlers': {
        'file_handler_error': {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': 'WARNING',
            'formatter': 'detailed',
            'filename': 'logs/error_log.log',
            'maxBytes': 5*1024*1024,
            'backupCount': 5,
        },
        'file_handler_debug': {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': 'DEBUG',
            'formatter': 'detailed',
            'filename': 'logs/debug_log.log',
            'maxBytes': 5*1024*1024,
            'backupCount': 5,
        },
        'console_handler': {
            'class': 'logging.StreamHandler',
            'level': 'INFO',
            'formatter': 'standard',
        },
    },
    'root': {
        'handlers': ['file_handler_error', 'file_handler_debug', 'console_handler'],
        'level': 'DEBUG',
    },
}
logging.config.dictConfig(logging_config)
logger = logging.getLogger(__name__)
logger.debug('Logging is configured.')

# Connect to the studies database
try:
    os.makedirs('data', exist_ok=True)
    studies_db_path = os.path.join('data', 'studies.db')
    con = sqlite3.connect(studies_db_path)
    cursor = con.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS studies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            desc TEXT,
            lat FLOAT,
            lon FLOAT,
            dir_path TEXT,
            db_path TEXT,
            shapefile_path TEXT,
            studyVisible BOOL
        )
    ''')
    con.commit()
    logger.info('Connection to the history database established.')
except Exception as e:
    logger.error(f'An error has occured while trying to connect to the database: {e}.')

# Get the data
studies = {}
try:
    for row in cursor.execute('SELECT * FROM studies'):
        studies[row[0]] = {}
        studies[row[0]]['name'] = row[1]
        studies[row[0]]['desc'] = row[2]
        studies[row[0]]['lat'] = row[3]
        studies[row[0]]['lon'] = row[4]
        studies[row[0]]['dir_path'] = row[5]
        studies[row[0]]['db_path'] = row[6]
        studies[row[0]]['shapefile_path'] = row[7]
        studies[row[0]]['studyVisible'] = (row[8] == 1)
    con.close()
    logger.info('Studies data retrieved succesfuly from the database.')
except Exception as e:
    logger.error(f'An error has occured while retrieving the studies data: {e}.')
    
# Set up the app
app = Flask('Data Dashboard', static_folder='static', template_folder='templates')



#####
# Visualization dashboard
#####
@app.route('/')
def dashboard():
    map = folium.Map()
    iframe = map.get_root()._repr_html_()
    return render_template('dashboard.html', iframe=iframe)



#####
# Studies manager
#####

# List of the studies
@app.route('/studies_manager')
def studies_manager():
    global studies
    # Map
    map = folium.Map()
    for study in studies.keys():
        folium.Marker(
            location=[studies[study]['lat'], studies[study]['lon']],
            tooltip=studies[study]['name'],
            icon=folium.Icon(color='red')
        ).add_to(map)
    iframe = map.get_root()._repr_html_()
    # List of studies
    studiesList = [{'id':study, 'name':studies[study]['name'], 'visible':studies[study]['studyVisible']} for study in studies.keys()]
    return render_template('studies_manager.html', iframe=iframe, studies=studiesList)


# Give the studies to the JavaScript to animate the list of studies
@app.route('/studies_manager/init')
def studies_manager_init():
    global studies
    return jsonify(list(studies.keys()))


# Page for the creation of a study
@app.route('/studies_manager/add')
def studies_manager_add():
    return render_template('studies_manager_add.html')


# Create the study and register it in the dictionnary and the database
@app.route('/studies_manager/create', methods=['POST'])
def studies_manager_create():
    try:
        # Get the form data
        name = request.form.get('studyName')
        desc = request.form.get('studyDesc')
        lat = request.form.get('studyLat')
        lon = request.form.get('studyLon')
        shapefile = request.files.get('studyShapefile')
        
        # Add the study to the database 1/2
        studies_db_path = os.path.join('data', 'studies.db')
        con = sqlite3.connect(studies_db_path)
        cursor = con.cursor()
        cursor.execute('''
            INSERT INTO studies (
                name,
                desc,
                lat,
                lon
            ) VALUES (?, ?, ?, ?)
        ''', (
            name,
            desc.lstrip(),
            lat,
            lon
        ))
        con.commit()
        
        # Get the id
        study_id = cursor.lastrowid
        
        # Create the directories
        dir_path = os.path.join('data', f'{study_id} - {name}')
        os.makedirs(dir_path, exist_ok=False)
        os.makedirs(os.path.join(dir_path, 'files'))
        db_path = os.path.join(dir_path, f'{study_id} - {name}.db')
        
        # Download and unzip the shapefile
        zip_path = os.path.join(dir_path, f'shapefile{name}.zip')
        shapefile_path = os.path.join(dir_path, f'shapefile{name}')
        shapefile.save(zip_path)
        with zipfile.ZipFile(zip_path, 'r') as zip_file:
            zip_file.extractall(shapefile_path)
        os.remove(zip_path)
        logger.info(f'Shapefile saved for {name}.')
        if len([f for f in os.listdir(shapefile_path) if f.endswith('.shp')]) == 0: # The zipfile does not contains directly the files
            shapefile_path = os.path.join(shapefile_path, os.listdir(shapefile_path)[0])
        
        # Add the study to the dictionnary
        global studies
        studies[study_id] = {}
        studies[study_id]['name'] = name 
        studies[study_id]['desc'] = desc.lstrip() 
        studies[study_id]['lat'] = lat
        studies[study_id]['lon'] = lon
        studies[study_id]['dir_path'] = dir_path
        studies[study_id]['db_path'] = db_path
        studies[study_id]['shapefile_path'] = shapefile_path
        studies[study_id]['studyVisible'] = False
        
        # Add the study to the database 2/2
        cursor.execute('''
            UPDATE studies
            SET dir_path = ?,
                db_path = ?,
                shapefile_path = ?,
                studyVisible = ?
            WHERE id = ?
        ''', (
            dir_path,
            db_path,
            shapefile_path,
            False,
            study_id
        ))
        con.commit()
        con.close()
        
        logger.info(f'The study "{name}" was created succesfuly.')
        return jsonify({'status':'success', 'study':study_id})
    
    except Exception as e:
        logger.info(f'An error has occured while trying to create the study: {e}.')
        return jsonify({'status':'error'})
    

# Modify a study
@app.route('/studies_manager/modify/<study>', methods=['GET'])
def studies_manager_modify(study):
    study = int(study)
    
    global studies
    name = studies[study]['name']
    desc = studies[study]['desc']
    lat = studies[study]['lat']
    lon = studies[study]['lon']
    shapefile = studies[study]['shapefile_path']
    return render_template('study_modify.html', name=name, desc=desc, lat=lat, lon=lon, shapefile=shapefile)


# Submit the modifications
@app.route('/studies_manager/submit_modif/<study>', methods=['POST'])
def studies_manager_submit_modif(study):
    study = int(study)
    
    try:
        # Get the form data
        desc = request.form.get('studyDesc')
        lat = request.form.get('studyLat')
        lon = request.form.get('studyLon')
        
        # Modify the study in the dictionnary
        global studies
        studies[study]['desc'] = desc.lstrip()
        studies[study]['lat'] = lat
        studies[study]['lon'] = lon
        
        # Modify the study in the database
        studies_db_path = os.path.join('data', 'studies.db')
        con = sqlite3.connect(studies_db_path)
        cursor = con.cursor()
        cursor.execute('''
            UPDATE studies
            SET desc = ?,
                lat = ?,
                lon = ?
            WHERE id = ?
        ''', (
            desc.lstrip(),
            lat,
            lon,
            study
        ))
        con.commit()
        con.close()
        
        logger.info(f'The study "{study}" was modified succesfuly.')
        return jsonify({'status':'success', 'study':study})
    
    except Exception as e:
        logger.info(f'An error has occured while trying to modify the study: {e}.')
        return jsonify({'status':'error'})


# Manage the visibility
@app.route('/studies_manager/visibility/<study>')
def studies_manager_visibility(study):
    study = int(study)
    
    global studies
    if study not in studies:
        return jsonify({'status':'error'})
    else:
        
        new_state = not(studies[study]['studyVisible'])
        # Change in the dictionnary
        studies[study]['studyVisible'] = new_state
        # Change in the database
        studies_db_path = os.path.join('data', 'studies.db')
        con = sqlite3.connect(studies_db_path)
        cursor = con.cursor()
        cursor.execute('''
            UPDATE studies
            SET studyVisible = ?
            WHERE id = ?
        ''', (
            new_state,
            study
        ))
        con.commit()
        con.close()
        
        return jsonify({'status':'success', 'state':new_state})


# Delete the study
@app.route('/studies_manager/delete/<study>', methods=['POST'])
def studies_manager_delete(study):
    study = int(study)
    
    global studies
    if study not in studies:
        return jsonify({'status':'error'})
    else:
            
        # Delete from the database
        studies_db_path = os.path.join('data', 'studies.db')
        con = sqlite3.connect(studies_db_path)
        cursor = con.cursor()
        cursor.execute('''
            DELETE FROM studies
            WHERE id = ?
        ''', (
            study,
        ))
        con.commit()
        con.close()
        
        # Delete the folder
        dir_path = studies[study]['dir_path']
        shutil.rmtree(dir_path)
        
        # Delete from the dictionnary
        name = studies[study]['name']
        studies.pop(study)

        logger.info(f'The study {name} has been deleted successfuly.')
        return jsonify({'status':'success'})



#####
# View and modify a study
#####

# View a study
@app.route('/study/<study>')
def study(study):
    study = int(study)
    
    # Check if the study exists
    global studies
    if study not in studies:
        redirect('/studies_manager')
    
    # Get the information
    name = studies[study]['name']
    desc = studies[study]['desc']
    lat = studies[study]['lat']
    lon = studies[study]['lon']
    studyVisible = studies[study]['studyVisible']
    
    # Map
    map = folium.Map(location=[lat,lon])
    shapefile_path = studies[study]['shapefile_path']
    files = [f for f in os.listdir(shapefile_path) if f.endswith(('.shp','.shx'))]
    for file in files:
        shape = gpd.read_file(os.path.join(shapefile_path, file))
        folium.GeoJson(data=shape).add_to(map)
    iframe = map.get_root()._repr_html_()
    
    return render_template('study.html', name=name, lat=lat, lon=lon, desc=desc, studyVisible=studyVisible, iframe=iframe)