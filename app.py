import os
from flask import Flask, jsonify, render_template, redirect, url_for, request
import logging
import logging.config
import sqlite3
import folium



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



# Connect to the sites database
try:
    os.makedirs('data', exist_ok=True)
    sites_db_path = os.path.join('data', 'sites.db')
    con = sqlite3.connect(sites_db_path)
    cursor = con.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sites (
            name TEXT PRIMARY KEY,
            desc TEXT,
            lat FLOAT,
            lon FLOAT,
            dir_path TEXT,
            db_path TEXT,
            siteVisible BOOL
        )
    ''')
    con.commit()
    logger.info('Connection to the history database established.')
except Exception as e:
    logger.error(f'An error has occured while trying to connect to the database: {e}.')

# Get the data
sites = {}
try:
    for row in cursor.execute('SELECT * FROM sites'):
        sites[row[0]] = {}
        sites[row[0]]['desc'] = row[1]
        sites[row[0]]['lat'] = row[2]
        sites[row[0]]['lon'] = row[3]
        sites[row[0]]['dir_path'] = row[4]
        sites[row[0]]['db_path'] = row[5]
        sites[row[0]]['siteVisible'] = row[6]
    con.close()
    logger.info('Sites data retrieved succesfuly from the database.')
except Exception as e:
    logger.error(f'An error has occured while retrieving the sites data: {e}.')
    


# Set up the app
app = Flask('Data Dashboard', static_folder='static', template_folder='templates')



###
# Dashboard
###
@app.route('/')
def dashboard():
    map = folium.Map()
    iframe = map.get_root()._repr_html_()
    return render_template('dashboard.html', iframe=iframe)



###
# Sites manager
###

# List of the sites
@app.route('/sites_manager')
def sites_manager():
    global sites
    # Map
    map = folium.Map()
    for site in sites.keys():
        folium.Marker(
            location=[sites[site]['lat'], sites[site]['lat']],
            tooltip=site,
            icon=folium.Icon(color='red')
        ).add_to(map)
    iframe = map.get_root()._repr_html_()
    # List of sites
    sitesList = [{'name':site, 'visible':sites[site]['siteVisible']} for site in sites.keys()]
    return render_template('sites_manager.html', iframe=iframe, sites=sitesList)


# Give the site to the JavaScript to animate the list
@app.route('/sites_manager/init')
def sites_manager_init():
    global sites
    sitesVisible = {site: sites[site]['siteVisible'] for site in sites.keys()}
    return jsonify(sitesVisible)


# Page for the creation of a site
@app.route('/sites_manager/add')
def sites_manager_add():
    return render_template('sites_manager_add.html')


# Create the site and register it in the dictionnary and the database
@app.route('/sites_manager/create', methods=['POST'])
def sites_manager_create():
    try:
        # Get the form data
        name = request.form.get('siteName')
        desc = request.form.get('siteDesc')
        lat = request.form.get('siteLat')
        lon = request.form.get('siteLon')
        print(name, desc, lat, lon)
        
        # Create the directory
        dir_path = os.path.join('data', name)
        os.makedirs(dir_path)
        os.makedirs(os.path.join(dir_path, 'files'))
        db_path = os.path.join(dir_path, f'{name}.db')
        
        # Add the site to the dictionnary
        global sites
        sites[name] = {}
        sites[name]['desc'] = desc
        sites[name]['lat'] = lat
        sites[name]['lon'] = lon
        sites[name]['dir_path'] = dir_path
        sites[name]['db_path'] = db_path
        sites[name]['siteVisible'] = False
        
        # Add the site to the database
        sites_db_path = os.path.join('data', 'sites.db')
        con = sqlite3.connect(sites_db_path)
        cursor = con.cursor()
        cursor.execute('''
            INSERT INTO sites (
                name,
                desc,
                lat,
                lon,
                dir_path,
                db_path,
                siteVisible
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            name,
            desc,
            lat,
            lon,
            dir_path,
            db_path,
            False
        ))
        con.commit()
        con.close()
        
        logger.info(f'The site "{name}" was created succesfuly.')
        return jsonify({'status':'success', 'site':name})
    
    except Exception as e:
        logger.info(f'An error has occured while trying to create the site: {e}.')
        return jsonify({'status':'error'})
    

# Manage the visibility
@app.route('/sites_manager/visibility/<site>')
def sites_manager_visibility(site):
    global sites
    new_state = not(sites[site]['siteVisible'])
    # Change in the dictionnary
    sites[site]['siteVisible'] = new_state
    # Change in the database
    sites_db_path = os.path.join('data', 'sites.db')
    con = sqlite3.connect(sites_db_path)
    cursor = con.cursor()
    cursor.execute('''
        UPDATE sites
        SET siteVisible = ?
        WHERE name = ?
    ''', (
        new_state,
        site
    ))
    con.commit()
    con.close()
    return jsonify({'status':'success', 'state':new_state})


# Delete the site
@app.route('/sites_manager/delete/<site>')
def sites_manager_delete(site):
    return



###
# View and modify a site
###

# View a site
@app.route('/site/<site>')
def site(site):
    global sites
    lat = sites[site]['lat']
    lon = sites[site]['lon']
    desc = sites[site]['desc']
    siteVisible = sites[site]['siteVisible']
    return render_template('site.html', name=site, lat=lat, lon=lon, desc=desc, siteVisible=siteVisible)
