import os
import shutil
import pathlib
from flask import Flask, jsonify, render_template, redirect, url_for, request
from werkzeug.utils import secure_filename
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

# Set up the logger
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
            visibility BOOL
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
        studies[row[0]]['visibility'] = (row[6] == 1)
    con.close()
    logger.info('Studies data retrieved succesfuly from the database.')
except Exception as e:
    logger.error(f'An error has occured while retrieving the studies data: {e}.')

 
# Set up the app
app = Flask('Data Dashboard')



#####
# Folium elements
#####

# Outline of a study
def folium_outline(poly, text=None):
    # Transform the coordinates
    geo = gpd.GeoSeries([poly])
    coord = geo.get_coordinates()
    coord.x, coord.y = coord.y, coord.x
    
    # 
    obj = folium.Polygon(
        locations = coord,
        color = 'black',
        fill = True,
        fill_opacity = 0,
        tooltip = text
    )
    return obj



#####
# Visualization dashboard
#####

# Empty map
@app.route('/dashboard')
def dashboard():
    map = folium.Map()
    iframe = map._repr_html_()
    return jsonify({'iframe': str(iframe)})



#####
# Studies manager
#####

# List of the studies and map with the points
@app.route('/studies_manager')
def studies_manager():
    global studies
    
    try:
        # Map
        map = folium.Map()
        for study in studies.keys():
            folium.Marker(
                location=[studies[study]['lat'], studies[study]['lon']],
                tooltip=studies[study]['name'],
                icon=folium.Icon(color='green')
            ).add_to(map)
        iframe = map.get_root()._repr_html_()
        
        # List of studies
        studiesList = [{'id':study, 'name':studies[study]['name'], 'visibility':studies[study]['visibility']} for study in studies.keys()]
        return jsonify({'status':'success', 'iframe':str(iframe), 'studies':studiesList})

    except Exception as e:
        logger.error(f'Failed to retrieve the data for the studies manager: {e}.')
        return jsonify({'status':'error'})


# Create the study and register it in the dictionnary and the database
@app.route('/studies_manager/create', methods=['POST'])
def studies_manager_create():

    # Get the form data
    try:
        name = request.form.get('studyName')
        desc = request.form.get('studyDesc')
        lat = request.form.get('studyLat')
        lon = request.form.get('studyLon')
        outline_file = request.files.get('studyOutline')
        
    except Exception as e:
        # Return the error
        logger.error(f'An error has occured while getting the request: {e}.')
        return jsonify({'status':'error'})
    
    # Add the study to the database 1/2
    try:
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
            desc,
            lat,
            lon
        ))
        con.commit()
        
    except Exception as e:
        # Return the error
        logger.error(f'An error has occured while trying to create the study: {e}.')
        return jsonify({'status':'error'})
    
    # Get the id
    study_id = cursor.lastrowid
    study_id = int(study_id)
    
    # Create the directory
    dir_path = os.path.join('data', f'{study_id} - {name}')
    os.makedirs(dir_path, exist_ok=False)
    os.makedirs(os.path.join(dir_path, 'temp'), exist_ok=True)
    
    # Add the study to the database 2/2
    try:
        cursor.execute('''
            UPDATE studies
            SET dir_path = ?,
                visibility = ?
            WHERE id = ?
        ''', (
            dir_path,
            False,
            study_id
        ))
        con.commit()
        
    except Exception as e:
        # Delete from the db
        cursor.execute('''
            DELETE FROM studies
            WHERE id = ?
        ''', (
            study_id,
        ))
        con.commit()
        con.close()
        # Delete the directory
        shutil.rmtree(dir_path)
        # Return the error
        logger.error(f'An error has occured while trying to create the study: {e}.')
        return jsonify({'status':'error'})
    
    # Download the shapefile
    try:
        # Download the zipfile
        temp_zip = os.path.join(dir_path, 'temp', 'outline.zip')
        outline_file.save(temp_zip)
        # Unzip it
        temp_folder = os.path.join(dir_path, 'temp', 'outline')
        with zipfile.ZipFile(temp_zip, 'r') as zip_file:
            zip_file.extractall(temp_folder)
        # Take the files only, and not the potential folder with the files within
        if len([f for f in os.listdir(temp_folder) if f.endswith('.shp')]) == 0:
            temp_folder = os.path.join(temp_folder, os.listdir(temp_folder)[0])
        # Copy paste the files
        outline_path = os.path.join(dir_path, 'outline')
        os.makedirs(outline_path, exist_ok=False)
        for file in os.listdir(temp_folder):
            shutil.copy2(
                os.path.join(temp_folder, file),
                outline_path
            )
        # Remove the temps
        os.remove(temp_zip)
        shutil.rmtree(temp_folder)
    
    except Exception as e:
        # Delete from the db
        cursor.execute('''
            DELETE FROM studies
            WHERE id = ?
        ''', (
            study_id,
        ))
        con.commit()
        con.close()
        # Delete the directory
        shutil.rmtree(dir_path)
        # Return the error
        logger.error(f'An error has occured while trying to download the file: {e}.')
        return jsonify({'status':'error'})
    
    con.close()
    
    # Add the study to the dictionnary
    global studies
    studies[study_id] = {}
    studies[study_id]['name'] = name 
    studies[study_id]['desc'] = desc 
    studies[study_id]['lat'] = lat
    studies[study_id]['lon'] = lon
    studies[study_id]['dir_path'] = dir_path
    studies[study_id]['visibility'] = False
    
    # Return the success
    logger.info(f'The study "{name}" was created succesfuly.')
    return jsonify({'status':'success', 'id':study_id})
    
    

#####
# View and modify a study
#####

# Give the data of a study
@app.route('/study/<study>')
def study(study):
    studyID = int(study)
    
    try: 
        # Check if the study exists
        global studies
        if studyID not in studies:
            logger.info(f'No existing data for the study with ID {studyID}.')
            return jsonify({'status':'error'})
        
        # Get the information
        name = studies[studyID]['name']
        desc = studies[studyID]['desc']
        lat = studies[studyID]['lat']
        lon = studies[studyID]['lon']
        visibility = studies[studyID]['visibility']
        
        return jsonify({'status':'success', 'name':name, 'lat':lat, 'lon':lon, 'desc':desc, 'visibility':visibility})
    
    except Exception as e:
        logger.error(f'An error has occured while trying to retrieve data for the study with ID {studyID}: {e}.')
        return jsonify({'status':'error'})
    
    
# Give the map of a study
@app.route('/study/<study>/map')
def study_map(study):
    studyID = int(study)
    
    try:
        # Check if the study exists
        global studies
        if studyID not in studies:
            logger.info(f'No existing data for the study with ID {studyID}.')
            return jsonify({'status':'error'})
        
        # Get the information
        name = studies[studyID]['name']
        lat = studies[studyID]['lat']
        lon = studies[studyID]['lon']
        
        # Map
        map = folium.Map(location=[lat,lon])
        folder = os.path.join(studies[studyID]['dir_path'], 'outline')
        file = [f for f in os.listdir(folder) if f.endswith('.shp')][0]
        shape = gpd.read_file(os.path.join(folder, file))
        shape.to_crs(epsg=4326, inplace=True)
        
        # Display the zone
        for _, zone in shape.iterrows():
            if zone.geometry.geom_type == 'Polygon':
                poly = folium_outline(zone.geometry, text=name)
                poly.add_to(map)
            elif zone.geometry.geom_type == 'MultiPolygon':
                for subzone in list(zone.geometry.geoms):
                    poly = folium_outline(subzone, text=name)
                    poly.add_to(map)
                    
        iframe = map.get_root()._repr_html_()
        return jsonify({'status':'success', 'iframe':str(iframe)})
                    
    except Exception as e:
        logger.error(f'An error has occured while trying to retrieve data for the study with ID {studyID}: {e}.')
        return jsonify({'status':'error'})


# Modify a study
@app.route('/study/<study>/modify', methods=['POST'])
def study_modify(study):
    studyID = int(study)
    
    try:
        # Get the form data
        name = request.form.get('studyName')
        desc = request.form.get('studyDesc')
        lat = request.form.get('studyLat')
        lon = request.form.get('studyLon')
        
        # Modify the study in the dictionnary
        global studies
        studies[studyID]['name'] = name
        studies[studyID]['desc'] = desc
        studies[studyID]['lat'] = lat
        studies[studyID]['lon'] = lon
        
        # Modify the study in the database
        studies_db_path = os.path.join('data', 'studies.db')
        con = sqlite3.connect(studies_db_path)
        cursor = con.cursor()
        cursor.execute('''
            UPDATE studies
            SET name = ?,
                desc = ?,
                lat = ?,
                lon = ?
            WHERE id = ?
        ''', (
            name,
            desc,
            lat,
            lon,
            studyID
        ))
        con.commit()
        con.close()
        
        logger.info(f'The study with ID {studyID} was modified succesfuly.')
        return jsonify({'status':'success'})
    
    except Exception as e:
        logger.error(f'An error has occured while trying to modify the study with ID {studyID}: {e}.')
        return jsonify({'status':'error'})


# Manage the visibility
@app.route('/study/<study>/visibility', methods=['POST'])
def study_visibility(study):
    studyID = int(study)
    
    global studies
    if studyID not in studies:
        logger.info(f'Cannot change the visibility, no study with ID {studyID}.')
        return jsonify({'status':'error'})
    
    else:
        new_state = not(studies[studyID]['visibility'])
        # Change in the dictionnary
        studies[studyID]['visibility'] = new_state
        # Change in the database
        studies_db_path = os.path.join('data', 'studies.db')
        con = sqlite3.connect(studies_db_path)
        cursor = con.cursor()
        cursor.execute('''
            UPDATE studies
            SET visibility = ?
            WHERE id = ?
        ''', (
            new_state,
            studyID
        ))
        con.commit()
        con.close()
        
        return jsonify({'status':'success', 'visibility':new_state})


# Delete the study
@app.route('/study/<study>/delete', methods=['POST'])
def study_delete(study):
    studyID = int(study)
    
    global studies
    if studyID not in studies:
        logger.info(f'Cannot delete, no study with ID {studyID}.')
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
            studyID,
        ))
        con.commit()
        con.close()
        
        # Delete the folder
        dir_path = studies[studyID]['dir_path']
        shutil.rmtree(dir_path)
        
        # Delete from the dictionnary
        studies.pop(studyID)

        logger.info(f'The study with ID {studyID} has been deleted successfuly.')
        return jsonify({'status':'success'})