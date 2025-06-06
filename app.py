import os
import shutil
import pathlib
import zipfile
import json
from flask import Flask, jsonify, render_template, redirect, url_for, request
from werkzeug.utils import secure_filename
import logging
import logging.config
import sqlite3
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


# Global variables
studies = {}
file_types = ['subdiv']


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

# Get the data form the database
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

# Clickable subzone
def folium_subdiv(poly, colorfill=False, text=None):
    # Transform the coordinates
    geo = gpd.GeoSeries([poly])
    coord = geo.get_coordinates()
    coord.x, coord.y = coord.y, coord.x
    
    # Get the fill
    if not(colorfill):
        fill_opactity = 0
        fill_color = 'black'
    else:
        fill_opactity = 0.3
        fill_color = colorfill
    
    # Object
    obj = folium.Polygon(
        locations = coord,
        color = 'black',
        fill = True,
        fill_opacity = fill_opactity,
        fill_color = fill_color,
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
        con.close()
        logger.error(f'An error has occured while trying to create the study: {e}.')
        return jsonify({'status':'error'})
    
    # Get the id
    studyID = cursor.lastrowid
    studyID = int(studyID)
    
    # Create the directory
    dir_path = os.path.join('data', f'{studyID} - {name}')
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
            studyID
        ))
        con.commit()
        
    except Exception as e:
        # Delete from the db
        cursor.execute('''
            DELETE FROM studies
            WHERE id = ?
        ''', (
            studyID,
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
            temp_file_folder = os.path.join(temp_folder, os.listdir(temp_folder)[0])
        else:
            temp_file_folder = temp_folder
        # Copy paste the files
        outline_path = os.path.join(dir_path, 'outline')
        os.makedirs(outline_path, exist_ok=False)
        for file in os.listdir(temp_file_folder):
            shutil.copy2(
                os.path.join(temp_file_folder, file),
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
            studyID,
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
    studies[studyID] = {}
    studies[studyID]['name'] = name 
    studies[studyID]['desc'] = desc 
    studies[studyID]['lat'] = lat
    studies[studyID]['lon'] = lon
    studies[studyID]['dir_path'] = dir_path
    studies[studyID]['visibility'] = False
    
    # Return the success
    logger.info(f'The study "{name}" was created succesfuly.')
    return jsonify({'status':'success', 'id':studyID})
    
    

#####
# View and modify a study
#####

# Give the general data of a study
@app.route('/study/<studyID>')
def study(studyID):
    studyID = int(studyID)
    
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
@app.route('/study/<studyID>/map')
def study_map(studyID):
    studyID = int(studyID)
    
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
        logger.error(f'An error has occured while trying to retrieve the map for the study with ID {studyID}: {e}.')
        return jsonify({'status':'error'})


# Give the files of a study
@app.route('/study/<studyID>/files')
def study_files(studyID):
    studyID = int(studyID)
        
    # Check if the study exists
    global studies
    if studyID not in studies:
        logger.info(f'No existing data for the study with ID {studyID}.')
        return jsonify({'status':'error'})
    name = studies[studyID]['name']
    
    try: 
        # Connect to the files database
        dir_path = os.path.join('data', f'{studyID} - {name}')
        study_db_path = os.path.join(dir_path, 'files.db')
        con = sqlite3.connect(study_db_path)
        cursor = con.cursor()
        
        # Get the files
        global file_types
        total_files = {}
        for type in file_types:
            files = {}
            for row in cursor.execute(f'SELECT * FROM {type}'):
                files[row[0]] = row[1]
            con.close()
            total_files[type] = files
        
        # Return the files
        return jsonify({'status': 'success', 'types':file_types, 'files':total_files})
    
    except Exception as e:
        logger.error(f'An error has occured while trying to retrieve the files for the study with ID {studyID}: {e}.')
        return jsonify({'status':'error'})
    

# Modify a study
@app.route('/study/<studyID>/modify', methods=['POST'])
def study_modify(studyID):
    studyID = int(studyID)
    
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
@app.route('/study/<studyID>/visibility', methods=['POST'])
def study_visibility(studyID):
    studyID = int(studyID)
    
    global studies
    if studyID not in studies:
        logger.info(f'Cannot change the visibility, no study with ID {studyID}.')
        return jsonify({'status':'error'})
    
    else:
        try:
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
        
        except Exception as e:
            logger.error(f'An error has occured while trying to modify the visibility of the study with ID {studyID}: {e}.')
            return jsonify({'status':'error', 'visibility':studies[studyID]['visibility']})


# Delete the study
@app.route('/study/<studyID>/delete', methods=['POST'])
def study_delete(studyID):
    studyID = int(studyID)
    
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
    
    

#####
# Add files to a study - subdiv
#####

# Subdivision in zones - Pre-process
@app.route('/study/<studyID>/add_file/subdiv/preprocess', methods=['POST'])
def study_add_file_subdiv_preprocess(studyID):
    studyID = int(studyID)
    
    # Check if the study exists
    global studies
    if studyID not in studies:
        logger.info(f'No existing data for the study with ID {studyID}.')
        return jsonify({'status':'error'})
    name = studies[studyID]['name']
    
    # Get the form data
    try:
        subdiv_file = request.files.get('fileFile')
        
    except Exception as e:
        # Return the error
        logger.error(f'An error has occured while getting the request: {e}.')
        return jsonify({'status':'error'})
    
    # Download the shapefile
    try:
        # Download the zipfile
        dir_path = os.path.join('data', f'{studyID} - {name}')
        temp_zip = os.path.join(dir_path, 'temp', 'subdiv.zip')
        subdiv_file.save(temp_zip)
        # Unzip it
        temp_folder = os.path.join(dir_path, 'temp', 'subdiv')
        with zipfile.ZipFile(temp_zip, 'r') as zip_file:
            zip_file.extractall(temp_folder)
        # Take the files only, and not the potential folder with the files within
        if len([f for f in os.listdir(temp_folder) if f.endswith('.shp')]) == 0:
            temp_file_folder = os.path.join(temp_folder, os.listdir(temp_folder)[0])
        else:
            temp_file_folder = temp_folder
        
    except Exception as e:
        # Remove the temps
        os.remove(temp_zip)
        shutil.rmtree(temp_folder)
        # Return the error
        logger.error(f'An error has occured while trying to download the file: {e}.')
        return jsonify({'status':'error'})
    
    # Read the columns headers
    try:
        shp_files = [f for f in os.listdir(temp_file_folder) if f.endswith('.shp')]
        shx_files = [f for f in os.listdir(temp_file_folder) if f.endswith('.shx')]
        dbf_files = [f for f in os.listdir(temp_file_folder) if f.endswith('.dbf')]
        # Check if the folder as a single shapefile and the mandatory files
        count = len(shp_files) + len(shx_files) + len(dbf_files)
        nb_mandatory_files = 3 # shp, shx and dbf
        if count > nb_mandatory_files:
            raise Exception('There are multiple shapefiles within the zipfile.')
        elif count < nb_mandatory_files:
            raise Exception('The shapefile is incomplete.')
        
        # Read the file
        shapefile = os.path.join(temp_file_folder, shp_files[0])
        data_subdiv = gpd.read_file(shapefile)
        data_subdiv.to_crs(epsg=4326, inplace=True)
        
        # Get the columns headers
        columns = list(data_subdiv.columns)
        
        # Remove the temps
        os.remove(temp_zip)
        shutil.rmtree(temp_folder)
        
        # Return the headers
        return jsonify({'status':'success', 'columns': columns})
        
    except Exception as e:
        # Remove the temps
        os.remove(temp_zip)
        shutil.rmtree(temp_folder)
        # Return the error
        logger.error(f'An error has occured while pre-processing the file: {e}.')
        return jsonify({'status':'error', 'message': e.args})


# Subdivision in zones - Process
@app.route('/study/<studyID>/add_file/subdiv/process', methods=['POST'])
def study_add_file_subdiv_process(studyID):
    studyID = int(studyID)
    
    # Check if the study exists
    global studies
    if studyID not in studies:
        logger.info(f'No existing data for the study with ID {studyID}.')
        return jsonify({'status':'error'})
    name = studies[studyID]['name']
    
    # Get the form data
    try:
        subdiv_file = request.files.get('fileFile')
        file_name = request.form.get('fileName')
        headers = request.form.get('fileHeaders')
        headers = json.loads(headers)
        
    except Exception as e:
        # Return the error
        logger.error(f'An error has occured while getting the request: {e}.')
        return jsonify({'status':'error'})
    
    # Add the study to the database 1/2
    try:
        dir_path = os.path.join('data', f'{studyID} - {name}')
        study_db_path = os.path.join(dir_path, 'files.db')
        con = sqlite3.connect(study_db_path)
        cursor = con.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subdiv (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                file_path TEXT,
                geometry TEXT,
                subdiv_id TEXT,
                subdiv_name TEXT
            )
        ''')
        con.commit()
        cursor.execute('''
            INSERT INTO subdiv (
                name
            ) VALUES (?)
        ''', (
            str(file_name),
        ))
        con.commit()
        
    except Exception as e:
        # Return the error
        con.close()
        logger.error(f'An error has occured while trying to add the file: {e}.')
        return jsonify({'status':'error'})
    
    # Get the id
    fileID = cursor.lastrowid
    fileID = int(fileID)
    
    # Create the directory
    subdiv_path = os.path.join(dir_path, 'subdiv')
    os.makedirs(subdiv_path, exist_ok=True)
    
    # Download the shapefile
    try:
        # Download the zipfile
        temp_zip = os.path.join(dir_path, 'temp', 'subdiv.zip')
        subdiv_file.save(temp_zip)
        # Unzip it
        temp_folder = os.path.join(dir_path, 'temp', 'subdiv')
        with zipfile.ZipFile(temp_zip, 'r') as zip_file:
            zip_file.extractall(temp_folder)
        # Take the files only, and not the potential folder with the files within
        if len([f for f in os.listdir(temp_folder) if f.endswith('.shp')]) == 0:
            temp_file_folder = os.path.join(temp_folder, os.listdir(temp_folder)[0])
        else:
            temp_file_folder = temp_folder
        # Copy paste the files
        file_path = os.path.join(subdiv_path, f'{fileID}-{file_name}')
        os.makedirs(file_path, exist_ok=False)
        for file in os.listdir(temp_file_folder):
            shutil.copy2(
                os.path.join(temp_file_folder, file),
                file_path
            )
        # Remove the temps
        os.remove(temp_zip)
        shutil.rmtree(temp_folder)
    
    except Exception as e:
        # Delete from the db
        cursor.execute('''
            DELETE FROM subdiv
            WHERE id = ?
        ''', (
            fileID,
        ))
        cursor.commit()
        con.close()
        # Delete the directory
        shutil.rmtree(file_path)
        # Return the error
        logger.error(f'An error has occured while trying to download the file: {e}.')
        return jsonify({'status':'error'})
    
    # Add the study to the database 2/2
    try:
        cursor.execute('''
            UPDATE subdiv
            SET file_path = ?,
                geometry = ?,
                subdiv_id = ?,
                subdiv_name = ?
            WHERE id = ?
        ''', (
            file_path,
            str(headers['Geometry']),
            str(headers['Subzone ID']),
            str(headers['Subzone name']),
            fileID,
        ))
        con.commit()
        
    except Exception as e:
        # Delete from the db
        cursor.execute('''
            DELETE FROM subdiv
            WHERE id = ?
        ''', (
            fileID,
        ))
        con.commit()
        con.close()
        # Delete the directory
        shutil.rmtree(file_path)
        # Return the error
        logger.error(f'An error has occured while trying to add the file: {e}.')
        return jsonify({'status':'error'})
    
    # Return the success
    con.close()
    logger.info(f'The file "{file_name}" was created succesfuly.')
    return jsonify({'status':'success'})


# View the file
@app.route('/study/<studyID>/subdiv/<fileID>', methods=['POST'])
def study_subdiv(studyID, fileID):
    studyID = int(studyID)
    fileID = int(fileID)
    
    try:
        # Get the path in the database
        global studies
        dir_path = studies[studyID]['dir_path']
        db_path = os.path.join(dir_path, 'files.db')
        con = sqlite3.connect(db_path)
        cursor = con.cursor()
        for row in cursor.execute(f'SELECT * FROM subdiv WHERE id = {fileID}'):
            file_path = row[2]
            col_geometry = row[3]
            col_id = row[4]
            col_name = row[5]
        con.close()
        
        # Open the file
        shape = gpd.read_file(file_path)
        shape.to_crs(epsg=4326, inplace=True)
        
    except Exception as e:
        logger.error(f'Either the file of type subdiv with ID {fileID} or the study with ID {studyID} does not exist.')
        return jsonify({'status': 'error'})
    
    try:
        # Get the request
        data = json.loads(request.get_data())
        first_map = data['first_map']
        
        if first_map:
            coord = [studies[studyID]['lat'], studies[studyID]['lon']]
            zoom = 18 # default folium zoom
            selected = -1
        else:
            center = data['center']
            coord = [center['lat'], center['lng']]
            zoom = data['zoom']
            selected = data['selected']
        
    except Exception as e:
        logger.error(f'An error has occured while getting the request: {e}.')
        return jsonify({'status': 'error'})
    
    try:
        
        # Create the map
        map = folium.Map(location=coord, zoom_start=zoom)
        map_name = map.get_name()
        
        # Display the zone
        zones = {}
        for _, zone in shape.iterrows():
            
            # Put in color if the zone is selected
            if zone[col_id] == selected:
                color = 'green'
            else:
                color = False
            
            # Plot geometries
            if zone[col_geometry].geom_type == 'Polygon':
                poly = folium_subdiv(zone[col_geometry], colorfill=color, text=f'{zone[col_id]} - {zone[col_name]}')
                poly.add_to(map)
                names = [poly.get_name()]
            elif zone[col_geometry].geom_type == 'MultiPolygon':
                names = []
                for subzone in list(zone[col_geometry].geoms):
                    poly = folium_subdiv(subzone, colorfill=color, text=f'{zone[col_id]} - {zone[col_name]}')
                    poly.add_to(map)
                    names.append(poly.get_name())
                    
            # Zones dict data
            zones[zone[col_id]] = {}
            zones[zone[col_id]]['geometry'] = names
            zones[zone[col_id]]['name'] = zone[col_name]           

        iframe = map.get_root()._repr_html_()
        iframe = iframe.replace('<iframe ', '<iframe id="mapDisplay" ')
        return jsonify({'status':'success', 'mapName': map_name, 'iframe':str(iframe), 'zones': zones})
            
    except Exception as e:
        logger.error(f'Cannot access the file of type subdiv with ID {fileID} for the study with ID {studyID}.')
        return jsonify({'status': 'error'})