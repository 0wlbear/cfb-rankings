from flask import Flask, render_template, request, redirect, url_for, flash, session, render_template_string
import json
import math
from datetime import datetime
from collections import defaultdict
from functools import wraps
import os


app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-here')
app.permanent_session_lifetime = 86400  # Session lasts 24 hours

# Data directory for persistence
DATA_DIR = os.environ.get('DATA_DIR', './data')
os.makedirs(DATA_DIR, exist_ok=True)

# Conference Teams
ACC_TEAMS = [
    'Boston College', 'California', 'Clemson', 'Duke', 'Florida State',
    'Georgia Tech', 'Louisville', 'Miami', 'NC State', 'North Carolina',
    'Pittsburgh', 'SMU', 'Stanford', 'Syracuse', 'Virginia', 'Virginia Tech',
    'Wake Forest'
]

BIG_TEN_TEAMS = [
    'Illinois', 'Indiana', 'Iowa', 'Maryland', 'Michigan', 'Michigan State',
    'Minnesota', 'Nebraska', 'Northwestern', 'Ohio State', 'Oregon',
    'Penn State', 'Purdue', 'Rutgers', 'UCLA', 'USC', 'Washington', 'Wisconsin'
]

BIG_XII_TEAMS = [
    'Arizona', 'Arizona State', 'Baylor', 'BYU', 'Cincinnati', 'Colorado',
    'Houston', 'Iowa State', 'Kansas', 'Kansas State', 'Oklahoma State',
    'TCU', 'Texas Tech', 'UCF', 'Utah', 'West Virginia'
]

PAC_12_TEAMS = [
    'Oregon State', 'Washington State'
]

SEC_TEAMS = [
    'Alabama', 'Arkansas', 'Auburn', 'Florida', 'Georgia', 'Kentucky',
    'LSU', 'Mississippi State', 'Missouri', 'Oklahoma', 'Ole Miss',
    'South Carolina', 'Tennessee', 'Texas', 'Texas A&M', 'Vanderbilt'
]

INDEPENDENT_TEAMS = [
    'Connecticut', 'Notre Dame', 'FCS'
]

AMERICAN_TEAMS = [
    'Army', 'Charlotte', 'East Carolina', 'Florida Atlantic', 'Memphis',
    'Navy', 'North Texas', 'Rice', 'South Florida', 'Temple',
    'Tulane', 'Tulsa', 'UAB', 'UTSA'
]

CONFERENCE_USA_TEAMS = [
    'Delaware', 'Florida Intl', 'Jacksonville State', 'Kennesaw State',
    'LA Tech', 'Liberty', 'Middle Tennessee', 'Missouri State',
    'New Mexico St', 'Sam Houston', 'UTEP', 'Western Kentucky'
]

MAC_TEAMS = [
    'Akron', 'Ball State', 'Bowling Green', 'Buffalo', 'Central Michigan',
    'Eastern Michigan', 'Kent State', 'UMass', 'Miami (OH)',
    'Northern Illinois', 'Ohio', 'Toledo', 'Western Michigan'
]

MOUNTAIN_WEST_TEAMS = [
    'Air Force', 'Boise State', 'Colorado State', 'Fresno State',
    'Hawaii', 'Nevada', 'New Mexico', 'San Diego State',
    'San Jose State', 'UNLV', 'Utah State', 'Wyoming'
]

SUN_BELT_TEAMS = [
    'Appalachian St', 'Arkansas State', 'Coastal Carolina', 'Georgia Southern',
    'Georgia State', 'James Madison', 'UL Monroe', 'Louisiana',
    'Marshall', 'Old Dominion', 'South Alabama', 'Southern Miss',
    'Texas State', 'Troy'
]

# ESPN Team ID mapping for logos
TEAM_LOGOS = {
   # ACC
    'Boston College': '103',
    'California': '25', 
    'Clemson': '228',
    'Duke': '150',
    'Florida State': '52',
    'Georgia Tech': '59',
    'Louisville': '97',
    'Miami': '2390',
    'NC State': '152',
    'North Carolina': '153',
    'Pittsburgh': '221',
    'SMU': '2567',
    'Stanford': '24',
    'Syracuse': '183',
    'Virginia': '258',
    'Virginia Tech': '259',
    'Wake Forest': '154',
    
    # Big Ten
    'Illinois': '356',
    'Indiana': '84',
    'Iowa': '2294',
    'Maryland': '120',
    'Michigan': '130',
    'Michigan State': '127',
    'Minnesota': '135',
    'Nebraska': '158',
    'Northwestern': '77',
    'Ohio State': '194',
    'Oregon': '2483',
    'Penn State': '213',
    'Purdue': '2509',
    'Rutgers': '164',
    'UCLA': '26',
    'USC': '30',
    'Washington': '264',
    'Wisconsin': '275',
    
    # Big XII
    'Arizona': '12',
    'Arizona State': '9',
    'Baylor': '239',
    'BYU': '252',
    'Cincinnati': '2132',
    'Colorado': '38',
    'Houston': '248',
    'Iowa State': '66',
    'Kansas': '2305',
    'Kansas State': '2306',
    'Oklahoma State': '197',
    'TCU': '2628',
    'Texas Tech': '2641',
    'UCF': '2116',
    'Utah': '254',
    'West Virginia': '277',
    
    # SEC
    'Alabama': '333',
    'Arkansas': '8',
    'Auburn': '2',
    'Florida': '57',
    'Georgia': '61',
    'Kentucky': '96',
    'LSU': '99',
    'Mississippi State': '344',
    'Missouri': '142',
    'Oklahoma': '201',
    'Ole Miss': '145',
    'South Carolina': '2579',
    'Tennessee': '2633',
    'Texas': '251',
    'Texas A&M': '245',
    'Vanderbilt': '238',
    
    # Pac 12
    'Oregon State': '204',
    'Washington State': '265',
    
    # American
    'Army': '349',
    'Charlotte': '2429',
    'East Carolina': '151',
    'Florida Atlantic': '2226',
    'Memphis': '235',
    'Navy': '2426',
    'North Texas': '249',
    'Rice': '242',
    'South Florida': '58',
    'Temple': '218',
    'Tulane': '2655',
    'Tulsa': '202',
    'UAB': '2429',
    'UTSA': '2902',
    
    # Conference USA
    'Delaware': '48',
    'Florida Intl': '2229',
    'Jacksonville State': '55',
    'Kennesaw State': '2390',
    'LA Tech': '2348',
    'Liberty': '2335',
    'Middle Tennessee': '2393',
    'Missouri State': '2623',
    'New Mexico St': '166',
    'Sam Houston': '2534',
    'UTEP': '2638',
    'Western Kentucky': '98',
    
    # MAC
    'Akron': '2006',
    'Ball State': '2050',
    'Bowling Green': '189',
    'Buffalo': '2084',
    'Central Michigan': '2117',
    'Eastern Michigan': '2199',
    'Kent State': '2309',
    'UMass': '113',
    'Miami (OH)': '193',
    'Northern Illinois': '2459',
    'Ohio': '195',
    'Toledo': '2649',
    'Western Michigan': '2711',
    
    # Mountain West
    'Air Force': '2005',
    'Boise State': '68',
    'Colorado State': '36',
    'Fresno State': '278',
    'Hawaii': '62',
    'Nevada': '2440',
    'New Mexico': '167',
    'San Diego State': '21',
    'San Jose State': '23',
    'UNLV': '2439',
    'Utah State': '328',
    'Wyoming': '2751',
    
    # Sun Belt
    'Appalachian St': '2026',
    'Arkansas State': '2032',
    'Coastal Carolina': '324',
    'Georgia Southern': '290',
    'Georgia State': '2247',
    'James Madison': '256',
    'UL Monroe': '2433',
    'Louisiana': '309',
    'Marshall': '276',
    'Old Dominion': '295',
    'South Alabama': '6',
    'Southern Miss': '2572',
    'Texas State': '326',
    'Troy': '2653',
    
    # Independent
    'Connecticut': '41',
    'Notre Dame': '87',

}

# Comprehensive team variations - GLOBAL
TEAM_VARIATIONS = {
    # SEC
            'Alabama': ['Alabama', 'Bama', 'Crimson Tide'],
            'Arkansas': ['Arkansas', 'Ark', 'Razorbacks'],
            'Auburn': ['Auburn', 'Tigers'],
            'Florida': ['Florida', 'UF', 'Gators'],
            'Georgia': ['Georgia', 'UGA', 'Bulldogs'],
            'Kentucky': ['Kentucky', 'UK', 'Wildcats'],
            'LSU': ['LSU', 'Louisiana State', 'Tigers'],
            'Mississippi State': ['Mississippi State', 'MSU', 'Miss State', 'Bulldogs'],
            'Missouri': ['Missouri', 'Mizzou', 'Tigers'],
            'Oklahoma': ['Oklahoma', 'OU', 'Sooners'],
            'Ole Miss': ['Ole Miss', 'Mississippi', 'Rebels'],
            'South Carolina': ['South Carolina', 'Gamecocks'],
            'Tennessee': ['Tennessee', 'Tenn', 'UT', 'Volunteers', 'Vols'],
            'Texas': ['Texas', 'UT', 'Longhorns'],
            'Texas A&M': ['Texas A&M', 'TAMU', 'A&M', 'Aggies', 'Texas AM'],
            'Vanderbilt': ['Vanderbilt', 'Vandy', 'Commodores'],

            # Big Ten
            'Illinois': ['Illinois', 'Illini', 'Fighting Illini'],
            'Indiana': ['Indiana', 'IU', 'Hoosiers'],
            'Iowa': ['Iowa', 'Hawkeyes'],
            'Maryland': ['Maryland', 'UMD', 'Terrapins', 'Terps'],
            'Michigan': ['Michigan', 'UM', 'Wolverines'],
            'Michigan State': ['Michigan State', 'MSU', 'Mich State', 'Spartans'],
            'Minnesota': ['Minnesota', 'Gophers', 'Golden Gophers'],
            'Nebraska': ['Nebraska', 'Huskers', 'Cornhuskers'],
            'Northwestern': ['Northwestern', 'NU', 'Wildcats'],
            'Ohio State': ['Ohio State', 'OSU', 'tOSU', 'Buckeyes'],
            'Oregon': ['Oregon', 'Ducks'],
            'Penn State': ['Penn State', 'PSU', 'Nittany Lions'],
            'Purdue': ['Purdue', 'Boilermakers'],
            'Rutgers': ['Rutgers', 'RU', 'Scarlet Knights'],
            'UCLA': ['UCLA', 'Bruins'],
            'USC': ['USC', 'Southern Cal', 'Southern California', 'Trojans'],
            'Washington': ['Washington', 'UW', 'Huskies'],
            'Wisconsin': ['Wisconsin', 'Badgers'],

            # ACC
            'Boston College': ['Boston College', 'BC', 'Eagles'],
            'California': ['California', 'Cal', 'Berkeley', 'Golden Bears'],
            'Clemson': ['Clemson', 'Tigers'],
            'Duke': ['Duke', 'Blue Devils'],
            'Florida State': ['Florida State', 'FSU', 'Seminoles'],
            'Georgia Tech': ['Georgia Tech', 'GT', 'Yellow Jackets'],
            'Louisville': ['Louisville', 'Cards', 'Cardinals'],
            'Miami': ['Miami', 'UM', 'Miami (FL)', 'Miami Florida', 'Miami FL', 'Hurricanes', 'The U'],
            'NC State': ['NC State', 'North Carolina State', 'NCSU', 'Wolfpack'],
            'North Carolina': ['North Carolina', 'UNC', 'Tar Heels', 'Carolina'],
            'Pittsburgh': ['Pittsburgh', 'Pitt', 'Panthers'],
            'SMU': ['SMU', 'Southern Methodist', 'Mustangs'],
            'Stanford': ['Stanford', 'Cardinal'],
            'Syracuse': ['Syracuse', 'Cuse', 'Orange'],
            'Virginia': ['Virginia', 'UVA', 'Cavaliers'],
            'Virginia Tech': ['Virginia Tech', 'VT', 'Hokies'],
            'Wake Forest': ['Wake Forest', 'Wake', 'Demon Deacons'],

            # Big 12
            'Arizona': ['Arizona', 'Wildcats'],
            'Arizona State': ['Arizona State', 'ASU', 'Sun Devils'],
            'Baylor': ['Baylor', 'Bears'],
            'BYU': ['BYU', 'Brigham Young', 'Cougars'],
            'Cincinnati': ['Cincinnati', 'UC', 'Bearcats'],
            'Colorado': ['Colorado', 'CU', 'Buffaloes', 'Buffs'],
            'Houston': ['Houston', 'UH', 'Cougars'],
            'Iowa State': ['Iowa State', 'ISU', 'Cyclones'],
            'Kansas': ['Kansas', 'KU', 'Jayhawks'],
            'Kansas State': ['Kansas State', 'KSU', 'K-State', 'Wildcats'],
            'Oklahoma State': ['Oklahoma State', 'OSU', 'Cowboys'],
            'TCU': ['TCU', 'Texas Christian', 'Horned Frogs'],
            'Texas Tech': ['Texas Tech', 'TTU', 'Red Raiders'],
            'UCF': ['UCF', 'Central Florida', 'Knights'],
            'Utah': ['Utah', 'Utes'],
            'West Virginia': ['West Virginia', 'WVU', 'Mountaineers'],

            # Pac-12 (remaining)
            'Oregon State': ['Oregon State', 'OSU', 'Beavers'],
            'Washington State': ['Washington State', 'WSU', 'Cougars'],

            # American Athletic Conference
            'Army': ['Army', 'Black Knights'],
            'Charlotte': ['Charlotte', '49ers'],
            'East Carolina': ['East Carolina', 'ECU', 'Pirates'],
            'Florida Atlantic': ['Florida Atlantic', 'FAU', 'Owls'],
            'Memphis': ['Memphis', 'Tigers'],
            'Navy': ['Navy', 'Midshipmen'],
            'North Texas': ['North Texas', 'UNT', 'Mean Green'],
            'Rice': ['Rice', 'Owls'],
            'South Florida': ['South Florida', 'USF', 'Bulls'],
            'Temple': ['Temple', 'Owls'],
            'Tulane': ['Tulane', 'Green Wave'],
            'Tulsa': ['Tulsa', 'Golden Hurricane'],
            'UAB': ['UAB', 'Alabama Birmingham', 'Blazers'],
            'UTSA': ['UTSA', 'Texas San Antonio', 'Roadrunners'],

            # Conference USA
            'Delaware': ['Delaware', 'Blue Hens'],
            'Florida Intl': ['Florida Intl', 'FIU', 'Florida International', 'Panthers'],
            'Jacksonville State': ['Jacksonville State', 'JSU', 'Gamecocks'],
            'Kennesaw State': ['Kennesaw State', 'Owls'],
            'LA Tech': ['LA Tech', 'Louisiana Tech', 'Bulldogs'],
            'Liberty': ['Liberty', 'Flames'],
            'Middle Tennessee': ['Middle Tennessee', 'MTSU', 'Blue Raiders'],
            'Missouri State': ['Missouri State', 'Bears'],
            'New Mexico St': ['New Mexico St', 'New Mexico State', 'NMSU', 'Aggies'],
            'Sam Houston': ['Sam Houston', 'Sam Houston State', 'SHSU', 'Bearkats'],
            'UTEP': ['UTEP', 'Texas El Paso', 'Miners'],
            'Western Kentucky': ['Western Kentucky', 'WKU', 'Hilltoppers'],

            # MAC
            'Akron': ['Akron', 'Zips'],
            'Ball State': ['Ball State', 'Cardinals'],
            'Bowling Green': ['Bowling Green', 'BGSU', 'Falcons'],
            'Buffalo': ['Buffalo', 'Bulls'],
            'Central Michigan': ['Central Michigan', 'CMU', 'Chippewas'],
            'Eastern Michigan': ['Eastern Michigan', 'EMU', 'Eagles'],
            'Kent State': ['Kent State', 'Golden Flashes'],
            'UMass': ['UMass', 'Massachusetts', 'Minutemen'],
            'Miami (OH)': ['Miami (OH)', 'Miami Ohio', 'Miami "Ohio"', 'Miami (Ohio)', 'RedHawks'],
            'Northern Illinois': ['Northern Illinois', 'NIU', 'Huskies'],
            'Ohio': ['Ohio', 'Bobcats'],
            'Toledo': ['Toledo', 'Rockets'],
            'Western Michigan': ['Western Michigan', 'WMU', 'Broncos'],

            # Mountain West
            'Air Force': ['Air Force', 'Falcons'],
            'Boise State': ['Boise State', 'Broncos'],
            'Colorado State': ['Colorado State', 'CSU', 'Rams'],
            'Fresno State': ['Fresno State', 'Bulldogs'],
            'Hawaii': ['Hawaii', 'Rainbow Warriors'],
            'Nevada': ['Nevada', 'Wolf Pack'],
            'New Mexico': ['New Mexico', 'UNM', 'Lobos'],
            'San Diego State': ['San Diego State', 'SDSU', 'Aztecs'],
            'San Jose State': ['San Jose State', 'SJSU', 'Spartans'],
            'UNLV': ['UNLV', 'Rebels'],
            'Utah State': ['Utah State', 'USU', 'Aggies'],
            'Wyoming': ['Wyoming', 'Cowboys'],

            # Sun Belt
            'Appalachian St': ['Appalachian St', 'Appalachian State', 'App State', 'Mountaineers'],
            'Arkansas State': ['Arkansas State', 'A-State', 'Red Wolves'],
            'Coastal Carolina': ['Coastal Carolina', 'Chanticleers'],
            'Georgia Southern': ['Georgia Southern', 'Eagles'],
            'Georgia State': ['Georgia State', 'Panthers'],
            'James Madison': ['James Madison', 'JMU', 'Dukes'],
            'UL Monroe': ['UL Monroe', 'ULM', 'Louisiana Monroe', 'Warhawks'],
            'Louisiana': ['Louisiana', 'UL', 'Ragin Cajuns', 'Louisiana Lafayette'],
            'Marshall': ['Marshall', 'Thundering Herd'],
            'Old Dominion': ['Old Dominion', 'ODU', 'Monarchs'],
            'South Alabama': ['South Alabama', 'USA', 'Jaguars'],
            'Southern Miss': ['Southern Miss', 'Southern Mississippi', 'USM', 'Golden Eagles'],
            'Texas State': ['Texas State', 'Bobcats'],
            'Troy': ['Troy', 'Trojans'],

            # Independents
            'Connecticut': ['Connecticut', 'UConn', 'Huskies'],
            'Notre Dame': ['Notre Dame', 'ND', 'Fighting Irish'],
}



# Bowl game definitions with tie-ins and selection order
BOWL_GAMES = {
    # College Football Playoff (handled separately)
    'cfp_national_championship': {
        'name': 'CFP National Championship',
        'tier': 'CFP',
        'location': 'TBD',
        'teams': 2,
        'selection': 'CFP #1 vs CFP #2',
        'payout': '$20M'
    },
    
    # New Year's Six Bowls
    'rose_bowl': {
        'name': 'Rose Bowl',
        'tier': 'NY6',
        'location': 'Pasadena, CA',
        'teams': 2,
        'primary_tie_ins': ['Big Ten', 'Pac 12'],
        'selection_order': 1,
        'payout': '$4M'
    },
    'sugar_bowl': {
        'name': 'Sugar Bowl',
        'tier': 'NY6', 
        'location': 'New Orleans, LA',
        'teams': 2,
        'primary_tie_ins': ['SEC', 'Big XII'],
        'selection_order': 2,
        'payout': '$4M'
    },
    'orange_bowl': {
        'name': 'Orange Bowl',
        'tier': 'NY6',
        'location': 'Miami Gardens, FL',
        'teams': 2,
        'primary_tie_ins': ['ACC', 'SEC/Big Ten/Notre Dame'],
        'selection_order': 3,
        'payout': '$4M'
    },
    'cotton_bowl': {
        'name': 'Cotton Bowl',
        'tier': 'NY6',
        'location': 'Arlington, TX',
        'teams': 2,
        'primary_tie_ins': ['Big XII', 'SEC/Big Ten'],
        'selection_order': 4,
        'payout': '$4M'
    },
    'fiesta_bowl': {
        'name': 'Fiesta Bowl',
        'tier': 'NY6',
        'location': 'Glendale, AZ',
        'teams': 2,
        'primary_tie_ins': ['Big XII', 'At-Large'],
        'selection_order': 5,
        'payout': '$4M'
    },
    'peach_bowl': {
        'name': 'Peach Bowl',
        'tier': 'NY6',
        'location': 'Atlanta, GA',
        'teams': 2,
        'primary_tie_ins': ['ACC', 'At-Large'],
        'selection_order': 6,
        'payout': '$4M'
    },
    
    # Major Conference Bowls
    'citrus_bowl': {
        'name': 'Citrus Bowl',
        'tier': 'Major',
        'location': 'Orlando, FL',
        'teams': 2,
        'primary_tie_ins': ['SEC', 'Big Ten'],
        'selection_order': 7,
        'payout': '$2.75M'
    },
    'outback_bowl': {
        'name': 'Outback Bowl',
        'tier': 'Major',
        'location': 'Tampa, FL',
        'teams': 2,
        'primary_tie_ins': ['SEC', 'Big Ten'],
        'selection_order': 8,
        'payout': '$2.5M'
    },
    'alamo_bowl': {
        'name': 'Alamo Bowl',
        'tier': 'Major',
        'location': 'San Antonio, TX',
        'teams': 2,
        'primary_tie_ins': ['Big XII', 'Pac 12'],
        'selection_order': 9,
        'payout': '$2.4M'
    },
    'holiday_bowl': {
        'name': 'Holiday Bowl',
        'tier': 'Major',
        'location': 'San Diego, CA',
        'teams': 2,
        'primary_tie_ins': ['Pac 12', 'ACC'],
        'selection_order': 10,
        'payout': '$2.2M'
    },
    'gator_bowl': {
        'name': 'Gator Bowl',
        'tier': 'Major',
        'location': 'Jacksonville, FL',
        'teams': 2,
        'primary_tie_ins': ['ACC', 'SEC'],
        'selection_order': 11,
        'payout': '$2.1M'
    },
    'sun_bowl': {
        'name': 'Sun Bowl',
        'tier': 'Major',
        'location': 'El Paso, TX',
        'teams': 2,
        'primary_tie_ins': ['Pac 12', 'ACC'],
        'selection_order': 12,
        'payout': '$2M'
    },
    
    # Conference Tie-In Bowls
    'music_city_bowl': {
        'name': 'Music City Bowl',
        'tier': 'Conference',
        'location': 'Nashville, TN',
        'teams': 2,
        'primary_tie_ins': ['SEC', 'Big Ten'],
        'selection_order': 13,
        'payout': '$1.8M'
    },
    'las_vegas_bowl': {
        'name': 'Las Vegas Bowl',
        'tier': 'Conference',
        'location': 'Las Vegas, NV',
        'teams': 2,
        'primary_tie_ins': ['Pac 12', 'SEC'],
        'selection_order': 14,
        'payout': '$1.7M'
    },
    'texas_bowl': {
        'name': 'Texas Bowl',
        'tier': 'Conference',
        'location': 'Houston, TX',
        'teams': 2,
        'primary_tie_ins': ['Big XII', 'SEC'],
        'selection_order': 15,
        'payout': '$1.6M'
    },
    'duke_mayo_bowl': {
        'name': "Duke's Mayo Bowl",
        'tier': 'Conference',
        'location': 'Charlotte, NC',
        'teams': 2,
        'primary_tie_ins': ['ACC', 'Big Ten'],
        'selection_order': 16,
        'payout': '$1.5M'
    },
    'liberty_bowl': {
        'name': 'Liberty Bowl',
        'tier': 'Conference',
        'location': 'Memphis, TN',
        'teams': 2,
        'primary_tie_ins': ['Big XII', 'SEC'],
        'selection_order': 17,
        'payout': '$1.4M'
    },
    'armed_forces_bowl': {
        'name': 'Armed Forces Bowl',
        'tier': 'Conference',
        'location': 'Fort Worth, TX',
        'teams': 2,
        'primary_tie_ins': ['Big XII', 'American'],
        'selection_order': 18,
        'payout': '$1.3M'
    },
    
    # G5 and Lower Tier Bowls
    'new_mexico_bowl': {
        'name': 'New Mexico Bowl',
        'tier': 'G5',
        'location': 'Albuquerque, NM',
        'teams': 2,
        'primary_tie_ins': ['Mountain West', 'Conference USA'],
        'selection_order': 25,
        'payout': '$1M'
    },
    'boca_raton_bowl': {
        'name': 'Boca Raton Bowl',
        'tier': 'G5',
        'location': 'Boca Raton, FL',
        'teams': 2,
        'primary_tie_ins': ['American', 'MAC'],
        'selection_order': 26,
        'payout': '$1M'
    },
    'frisco_bowl': {
        'name': 'Frisco Bowl',
        'tier': 'G5',
        'location': 'Frisco, TX',
        'teams': 2,
        'primary_tie_ins': ['American', 'Mountain West'],
        'selection_order': 27,
        'payout': '$1M'
    },
    'cure_bowl': {
        'name': 'Cure Bowl',
        'tier': 'G5',
        'location': 'Orlando, FL',
        'teams': 2,
        'primary_tie_ins': ['American', 'Sun Belt'],
        'selection_order': 28,
        'payout': '$1M'
    },
    'gasparilla_bowl': {
        'name': 'Gasparilla Bowl',
        'tier': 'G5',
        'location': 'St. Petersburg, FL',
        'teams': 2,
        'primary_tie_ins': ['American', 'ACC'],
        'selection_order': 29,
        'payout': '$1M'
    },
    'camellia_bowl': {
        'name': 'Camellia Bowl',
        'tier': 'G5',
        'location': 'Montgomery, AL',
        'teams': 2,
        'primary_tie_ins': ['MAC', 'Sun Belt'],
        'selection_order': 30,
        'payout': '$1M'
    }
}

# Define major college football rivalries
RIVALRIES = {
    # SEC Rivalries
    'Alabama': ['Auburn', 'Tennessee', 'LSU'],
    'Auburn': ['Alabama', 'Georgia'],
    'Georgia': ['Auburn', 'Florida', 'Georgia Tech'],
    'Florida': ['Georgia', 'Florida State', 'Miami'],
    'LSU': ['Alabama', 'Arkansas', 'Ole Miss'],
    'Arkansas': ['LSU', 'Texas', 'Missouri'],
    'Tennessee': ['Alabama', 'Kentucky', 'Vanderbilt'],
    'Kentucky': ['Tennessee', 'Louisville'],
    'Vanderbilt': ['Tennessee'],
    'Mississippi State': ['Ole Miss'],
    'Ole Miss': ['Mississippi State', 'LSU'],
    'Missouri': ['Arkansas', 'Kansas'],
    'South Carolina': ['Clemson', 'North Carolina'],
    'Texas': ['Arkansas', 'Texas A&M', 'Oklahoma'],
    'Texas A&M': ['Texas', 'LSU'],
    
    # Big Ten Rivalries
    'Ohio State': ['Michigan', 'Penn State'],
    'Michigan': ['Ohio State', 'Michigan State'],
    'Michigan State': ['Michigan', 'Penn State'],
    'Penn State': ['Ohio State', 'Michigan State'],
    'Wisconsin': ['Minnesota', 'Iowa'],
    'Minnesota': ['Wisconsin', 'Iowa'],
    'Iowa': ['Wisconsin', 'Minnesota', 'Iowa State'],
    'Illinois': ['Northwestern', 'Indiana'],
    'Northwestern': ['Illinois'],
    'Indiana': ['Illinois', 'Purdue'],
    'Purdue': ['Indiana'],
    'Nebraska': ['Iowa', 'Wisconsin'],
    'Maryland': ['Virginia', 'Penn State'],
    'Rutgers': ['Penn State'],
    
    # Big XII Rivalries
    'Oklahoma': ['Texas', 'Oklahoma State'],
    'Oklahoma State': ['Oklahoma'],
    'Texas Tech': ['Texas', 'Baylor'],
    'Baylor': ['Texas Tech', 'TCU'],
    'TCU': ['Baylor', 'SMU'],
    'West Virginia': ['Virginia Tech', 'Pittsburgh'],
    'Kansas': ['Kansas State', 'Missouri'],
    'Kansas State': ['Kansas'],
    'Iowa State': ['Iowa'],
    'Cincinnati': ['Louisville'],
    'Houston': ['Rice'],
    'UCF': ['South Florida'],
    
    # ACC Rivalries
    'Clemson': ['South Carolina', 'Georgia Tech'],
    'Florida State': ['Florida', 'Miami'],
    'Miami': ['Florida State', 'Florida'],
    'North Carolina': ['NC State', 'Duke', 'South Carolina'],
    'NC State': ['North Carolina', 'Wake Forest'],
    'Duke': ['North Carolina', 'Wake Forest'],
    'Wake Forest': ['NC State', 'Duke'],
    'Virginia': ['Virginia Tech', 'Maryland'],
    'Virginia Tech': ['Virginia', 'West Virginia'],
    'Pittsburgh': ['West Virginia', 'Penn State'],
    'Georgia Tech': ['Georgia', 'Clemson'],
    'Louisville': ['Kentucky', 'Cincinnati'],
    'Boston College': ['Syracuse'],
    'Syracuse': ['Boston College'],
    
    # Pac 12 / West Coast
    'Stanford': ['California'],
    'California': ['Stanford'],
    'Oregon': ['Oregon State', 'Washington'],
    'Oregon State': ['Oregon'],
    'Washington': ['Oregon', 'Washington State'],
    'Washington State': ['Washington'],
    'UCLA': ['USC'],
    'USC': ['UCLA'],
    
    # Independent
    'Notre Dame': ['USC', 'Michigan', 'Navy', 'Stanford'],
    'Navy': ['Notre Dame', 'Army'],
    'Army': ['Navy'],
    
    # G5 Major Rivalries
    'SMU': ['TCU', 'Rice', 'Houston'],
    'Rice': ['SMU', 'Houston'],
    'Memphis': ['UAB', 'Tulane'],
    'UAB': ['Memphis'],
    'Tulane': ['Memphis', 'Louisiana'],
    'Louisiana': ['Tulane'],
    'Boise State': ['Fresno State'],
    'Fresno State': ['Boise State'],
    'Air Force': ['Army', 'Navy'],
    'Colorado State': ['Colorado'],
    'Wyoming': ['Colorado State'],
    'Marshall': ['West Virginia'],
    'Troy': ['South Alabama'],
    'South Alabama': ['Troy'],
    'App State': ['Georgia Southern'],
    'Georgia Southern': ['App State'],
    'Miami (OH)': ['Cincinnati', 'Ohio'],
    'Ohio': ['Miami (OH)'],
    'Toledo': ['Bowling Green'],
    'Bowling Green': ['Toledo'],
    'Northern Illinois': ['Western Michigan'],
    'Western Michigan': ['Northern Illinois'],
}

# Add this date formatting filter
@app.template_filter('format_date')
def format_date(date_string):
    """Format date string for display"""
    if not date_string:
        return ""
    
    try:
        # Parse the date string (YYYY-MM-DD format)
        date_obj = datetime.strptime(date_string, '%Y-%m-%d')
        
        # Format as "Sat, Aug 23"
        return date_obj.strftime('%a, %b %d')
    except:
        return date_string  # Return original if parsing fails

@app.template_filter('format_date_header')
def format_date_header(date_string):
    """Format date string for section headers"""
    if not date_string or date_string == 'No Date':
        return "Date TBD"
    
    try:
        # Parse the date string (YYYY-MM-DD format)
        date_obj = datetime.strptime(date_string, '%Y-%m-%d')
        
        # Format as "Saturday, August 23"
        return date_obj.strftime('%A, %B %d')
    except:
        return date_string  # Return original if parsing fails


def get_bowl_eligible_teams():
    """Get all teams with 6+ wins (bowl eligible) - FCS wins don't count"""
    bowl_eligible = []
    
    for conf_name, teams in CONFERENCES.items():
        for team in teams:
            stats = calculate_comprehensive_stats(team)
            
            # Calculate REAL wins (excluding FCS)
            real_wins = 0
            for game in team_stats[team]['games']:
                if game['result'] == 'W' and not is_fcs_opponent(game['opponent']):
                    real_wins += 1
            
            # Bowl eligible = 6+ real wins (not counting FCS)
            if real_wins >= 6:
                team_data = {
                    'team': team,
                    'conference': conf_name,
                    'wins': real_wins,  # Real wins only
                    'total_wins': stats['total_wins'],  # Total wins including FCS
                    'losses': stats['total_losses'],
                    'adjusted_total': stats['adjusted_total']
                }
                bowl_eligible.append(team_data)
    
    # Sort by adjusted total (best teams first)
    bowl_eligible.sort(key=lambda x: x['adjusted_total'], reverse=True)
    return bowl_eligible

def get_conference_bowl_teams():
    """Get available teams by conference for bowl selection"""
    bowl_teams_by_conf = {}
    
    # Get conference champions and bowl eligible teams
    champions = get_conference_champions()
    bowl_eligible = get_bowl_eligible_teams()
    
    # Organize teams by conference (excluding CFP teams)
    cfp_bracket = generate_cfp_bracket()
    cfp_team_names = {team['team'] for team in cfp_bracket['all_teams']}
    
    for conf_name in CONFERENCES.keys():
        conf_teams = [team for team in bowl_eligible 
                     if team['conference'] == conf_name and team['team'] not in cfp_team_names]
        bowl_teams_by_conf[conf_name] = conf_teams[:8]  # Max 8 bowl teams per conference
    
    return bowl_teams_by_conf, champions

def generate_bowl_projections():
    """Generate complete bowl projections"""
    # Get CFP bracket (already have this)
    cfp_bracket = generate_cfp_bracket()
    
    # Get available teams for bowls
    bowl_teams_by_conf, champions = get_conference_bowl_teams()
    
    # Get all bowl eligible teams not in CFP
    cfp_team_names = {team['team'] for team in cfp_bracket['all_teams']}
    at_large_pool = [team for team in get_bowl_eligible_teams() 
                     if team['team'] not in cfp_team_names]
    
    bowl_projections = []
    used_teams = set()
    
    # Process bowls in selection order
    sorted_bowls = sorted(BOWL_GAMES.items(), key=lambda x: x[1].get('selection_order', 99))
    
    for bowl_id, bowl_info in sorted_bowls:
        if bowl_info['tier'] == 'CFP':
            continue  # Skip CFP, handled separately
            
        projection = {
            'id': bowl_id,
            'name': bowl_info['name'],
            'tier': bowl_info['tier'],
            'location': bowl_info['location'],
            'payout': bowl_info['payout'],
            'teams': [],
            'tie_ins': bowl_info.get('primary_tie_ins', [])
        }
        
        # Try to fill based on tie-ins
        teams_needed = bowl_info['teams']
        for tie_in in bowl_info.get('primary_tie_ins', []):
            if teams_needed <= 0:
                break
                
            if tie_in in bowl_teams_by_conf:
                available_teams = [t for t in bowl_teams_by_conf[tie_in] if t['team'] not in used_teams]
                if available_teams:
                    selected_team = available_teams[0]
                    projection['teams'].append(selected_team)
                    used_teams.add(selected_team['team'])
                    teams_needed -= 1
        
        # Fill remaining spots with at-large teams
        while teams_needed > 0:
            available_at_large = [t for t in at_large_pool if t['team'] not in used_teams]
            if not available_at_large:
                break
            selected_team = available_at_large[0]
            projection['teams'].append(selected_team)
            used_teams.add(selected_team['team'])
            teams_needed -= 1
        
        # Only add bowl if it has at least one team
        if projection['teams']:
            bowl_projections.append(projection)
    
    # Add conference championships
    conf_championships = []
    for conf_name, champion in champions.items():
        if conf_name not in ['Independent', 'Pac 12']:  # Skip independents and Pac 12
            # Get second place team
            conf_teams = [team for team in get_bowl_eligible_teams() 
                         if team['conference'] == conf_name and team['team'] != champion['team']]
            runner_up = conf_teams[0] if conf_teams else None
            
            conf_championships.append({
                'name': f'{conf_name} Championship',
                'teams': [champion, runner_up] if runner_up else [champion],
                'tier': 'Championship'
            })
    
    return {
        'cfp_bracket': cfp_bracket,
        'bowl_projections': bowl_projections,
        'conference_championships': conf_championships,
        'total_bowl_teams': len(used_teams) + len(cfp_bracket['all_teams'])
    }

def is_rivalry_game(team1, team2):
    """Check if two teams are rivals"""
    return (team2 in RIVALRIES.get(team1, []) or 
            team1 in RIVALRIES.get(team2, []))

def get_rivalry_bonus(team_name, opponent_name):
    """
    Calculate rivalry bonus for beating a rival.
    Returns bonus points to add to victory value.
    """
    if not is_rivalry_game(team_name, opponent_name):
        return 0.0
    
    # Different tiers of rivalry bonuses based on intensity
    major_rivalries = {
        # Tier 1: Historic, intense rivalries (1.0 bonus)
        ('Alabama', 'Auburn'): 1.0,
        ('Ohio State', 'Michigan'): 1.0,
        ('Texas', 'Oklahoma'): 1.0,
        ('Florida', 'Georgia'): 1.0,
        ('USC', 'UCLA'): 1.0,
        ('Army', 'Navy'): 1.0,
        ('Florida State', 'Miami'): 1.0,
        ('Clemson', 'South Carolina'): 1.0,
        ('North Carolina', 'NC State'): 1.0,
        ('Notre Dame', 'USC'): 1.0,
        ('Virginia', 'Virginia Tech'): 1.0,
        ('Stanford', 'California'): 1.0,
        ('Oregon', 'Oregon State'): 1.0,
        ('Washington', 'Washington State'): 1.0,
        
        # Add more Tier 1 rivalries as needed
    }
    
    # Check if this is a Tier 1 rivalry (order doesn't matter)
    rivalry_pair = tuple(sorted([team_name, opponent_name]))
    for (team_a, team_b), bonus in major_rivalries.items():
        if rivalry_pair == tuple(sorted([team_a, team_b])):
            return bonus
    
    # Default rivalry bonus for other rivalries
    return 0.6  # Standard rivalry bonus

def calculate_victory_value_with_rivalry(game, team_name):
    """
    Calculate victory value with special FCS penalty
    """
    if game['result'] != 'W':
        return 0.0
    
    opponent = game['opponent']
    team_score = game['team_score']
    opp_score = game['opp_score']
    margin = team_score - opp_score
    location = game['home_away']
    
    # Check if this is an FCS game for special handling
    is_fcs_game = (opponent == 'FCS' or opponent.upper() == 'FCS')
    
    # 1. Base Opponent Quality (0.5 for FCS, 1-10 for others)
    opponent_quality = get_current_opponent_quality(opponent)
    
    # 2. Location Multiplier (no bonus for FCS games)
    if is_fcs_game:
        location_mult = 1.0  # No location bonus for beating FCS teams
    else:
        location_multipliers = {
            'Home': 1.0,
            'Away': 1.3,    # Road wins worth 30% more
            'Neutral': 1.15  # Neutral site wins worth 15% more
        }
        location_mult = location_multipliers.get(location, 1.0)
    
    # 3. Margin Bonus (severely limited for FCS)
    if is_fcs_game:
        # FCS games get minimal margin bonus regardless of score
        margin_bonus = min(0.2, margin * 0.02)  # Max 0.2 bonus, very small scaling
    else:
        # Normal margin bonus for real opponents
        if margin <= 0:
            margin_bonus = 0
        elif margin <= 7:
            margin_bonus = margin * 0.1  # Linear up to 7 points
        elif margin <= 14:
            margin_bonus = 0.7 + (margin - 7) * 0.08  # Slower growth 7-14
        elif margin <= 21:
            margin_bonus = 1.26 + (margin - 14) * 0.04  # Even slower 14-21
        else:
            margin_bonus = 1.54 + (margin - 21) * 0.02  # Minimal benefit beyond 21
    
    # 4. Conference Context Bonus (none for FCS)
    if is_fcs_game:
        conf_bonus = 0  # No conference bonus for FCS games
    else:
        team_conf = get_team_conference(team_name)
        opp_conf = get_team_conference(opponent)
        
        conf_bonus = 0
        if team_conf in P4_CONFERENCES and opp_conf in P4_CONFERENCES:
            conf_bonus = 0.3  # P4 vs P4 bonus
        elif team_conf in G5_CONFERENCES and opp_conf in P4_CONFERENCES:
            conf_bonus = 0.5  # G5 beating P4 major bonus
    
    # 5. Rivalry Bonus (FCS can't be rivals)
    if is_fcs_game:
        rivalry_bonus = 0  # No rivalry bonus for FCS
    else:
        rivalry_bonus = get_rivalry_bonus(team_name, opponent)
    
    # 6. Calculate Final Victory Value
    base_value = opponent_quality * location_mult
    total_value = base_value + margin_bonus + conf_bonus + rivalry_bonus
    
    # 7. Extra FCS penalty - cap maximum value
    if is_fcs_game:
        total_value = min(total_value, 1.0)  # FCS wins can never be worth more than 1.0 point
    
    return round(total_value, 2)


def get_team_logo_url(team_name):
    """Get ESPN logo URL for a team"""
    team_id = TEAM_LOGOS.get(team_name)
    if team_id:
        return f"https://a.espncdn.com/i/teamlogos/ncaa/500/{team_id}.png"
    return None

# All conferences organized
CONFERENCES = {
    'ACC': ACC_TEAMS,
    'Big Ten': BIG_TEN_TEAMS,
    'Big XII': BIG_XII_TEAMS,
    'Pac 12': PAC_12_TEAMS,
    'SEC': SEC_TEAMS,
    'Independent': INDEPENDENT_TEAMS,
    'American': AMERICAN_TEAMS,
    'Conference USA': CONFERENCE_USA_TEAMS,
    'MAC': MAC_TEAMS,
    'Mountain West': MOUNTAIN_WEST_TEAMS,
    'Sun Belt': SUN_BELT_TEAMS
}

# Scheduled games storage
scheduled_games = []

# Team name mappings for unknown teams
team_mappings = {}

# All teams combined
TEAMS = (ACC_TEAMS + BIG_TEN_TEAMS + BIG_XII_TEAMS + PAC_12_TEAMS + SEC_TEAMS + 
         INDEPENDENT_TEAMS + AMERICAN_TEAMS + CONFERENCE_USA_TEAMS + MAC_TEAMS + 
         MOUNTAIN_WEST_TEAMS + SUN_BELT_TEAMS)

WEEKS = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', '13', '14', '15', '16', 'Bowls', 'CFP']
GAME_TYPES = ['P4', 'G5', 'None']

# P4 and G5 Conference Classifications
P4_CONFERENCES = ['ACC', 'Big Ten', 'Big XII', 'Pac 12', 'SEC']
G5_CONFERENCES = ['American', 'Conference USA', 'MAC', 'Mountain West', 'Sun Belt']
P4_INDEPENDENT_TEAMS = ['Notre Dame']
G5_INDEPENDENT_TEAMS = ['Connecticut']
NONE_INDEPENDENT_TEAMS = ['FCS']

# In-memory storage for games and rankings
games_data = []
team_stats = defaultdict(lambda: {
    'wins': 0, 'losses': 0, 'points_for': 0, 'points_against': 0,
    'p4_wins': 0, 'p4_losses': 0, 'g5_wins': 0, 'g5_losses': 0,
    'home_wins': 0, 'road_wins': 0, 'margin_of_victory_total': 0,
    'games': []
})

def get_team_conference(team_name):
    """Get the conference for a given team"""
    for conf_name, teams in CONFERENCES.items():
        if team_name in teams:
            return conf_name
    return 'Unknown'

def is_p4_team(team_name):
    """Determine if a team is P4"""
    if team_name in P4_INDEPENDENT_TEAMS:
        return True
    conference = get_team_conference(team_name)
    return conference in P4_CONFERENCES

def is_g5_team(team_name):
    """Determine if a team is G5"""
    if team_name in G5_INDEPENDENT_TEAMS:
        return True
    conference = get_team_conference(team_name)
    return conference in G5_CONFERENCES

def get_auto_game_type(team_name):
    """Get the automatic game type for a team"""
    if is_p4_team(team_name):
        return 'P4'
    elif is_g5_team(team_name):
        return 'G5'
    else:
        return 'None'

# Admin credentials from environment variables
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'changeme')

def is_admin():
    """Check if user is logged in as admin"""
    return session.get('admin_logged_in', False)

@app.context_processor
def inject_user():
    return dict(
        is_admin=session.get('admin_logged_in', False),
        get_team_logo_url=get_team_logo_url
    )


def login_required(f):
    """Decorator to require admin login for routes"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_admin():
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function        

# Data persistence functions
def save_data():
    """Save game data and team stats to JSON files"""
    try:
        # Save games data
        games_file = os.path.join(DATA_DIR, 'games_data.json')
        with open(games_file, 'w') as f:
            json.dump(games_data, f, indent=2)
        
        # Convert team_stats defaultdict to regular dict for JSON serialization
        team_stats_dict = {}
        for team, stats in team_stats.items():
            team_stats_dict[team] = dict(stats)
        
        stats_file = os.path.join(DATA_DIR, 'team_stats.json')
        with open(stats_file, 'w') as f:
            json.dump(team_stats_dict, f, indent=2)
        
        print("Data saved successfully!")
    except Exception as e:
        print(f"Error saving data: {e}")

def save_scheduled_games():
    """Save scheduled games to JSON file"""
    try:
        scheduled_file = os.path.join(DATA_DIR, 'scheduled_games.json')
        with open(scheduled_file, 'w') as f:
            json.dump(scheduled_games, f, indent=2)
    except Exception as e:
        print(f"Error saving scheduled games: {e}")

def load_scheduled_games():
    """Load scheduled games from JSON file"""
    global scheduled_games
    try:
        scheduled_file = os.path.join(DATA_DIR, 'scheduled_games.json')
        with open(scheduled_file, 'r') as f:
            scheduled_games = json.load(f)
        print(f"Loaded {len(scheduled_games)} scheduled games")
    except FileNotFoundError:
        print("No scheduled games file found, starting fresh")
        scheduled_games = []
    except Exception as e:
        print(f"Error loading scheduled games: {e}")
        scheduled_games = []


def load_data():
    """Load game data and team stats from JSON files"""
    global games_data, team_stats
    try:
        # Load games data
        try:
            games_file = os.path.join(DATA_DIR, 'games_data.json')
            with open(games_file, 'r') as f:
                games_data = json.load(f)
            print(f"Loaded {len(games_data)} games from saved data")
        except FileNotFoundError:
            print("No saved games data found, starting fresh")
            games_data = []
        
        # Load team stats
        try:
            stats_file = os.path.join(DATA_DIR, 'team_stats.json')
            with open(stats_file, 'r') as f:
                saved_stats = json.load(f)
            
            # Convert back to defaultdict
            team_stats = defaultdict(lambda: {
                'wins': 0, 'losses': 0, 'points_for': 0, 'points_against': 0,
                'home_wins': 0, 'road_wins': 0, 'margin_of_victory_total': 0,
                'games': []
            })
            
            for team, stats in saved_stats.items():
                team_stats[team] = stats
            
            print(f"Loaded stats for {len(saved_stats)} teams")
        except FileNotFoundError:
            print("No saved team stats found, starting fresh")

        # Load historical data
        load_historical_data()
        
        # Load scheduled games
        load_scheduled_games()

        # Load team mappings
        load_team_mappings()
            
    except Exception as e:
        print(f"Error loading data: {e}")
        print("Starting with fresh data")


def get_conference_champions():
    """Determine conference champions based on current standings"""
    champions = {}
    
    for conf_name, teams in CONFERENCES.items():
        if conf_name in ['Independent', 'Pac 12']:  # Skip independents and Pac 12
            continue
            
        # Get all teams in conference with their stats
        conf_teams = []
        for team in teams:
            stats = calculate_comprehensive_stats(team)
            stats['team'] = team
            stats['conference'] = conf_name
            conf_teams.append(stats)
        
        # Sort by adjusted total (highest first)
        conf_teams.sort(key=lambda x: x['adjusted_total'], reverse=True)
        
        if conf_teams:
            champions[conf_name] = conf_teams[0]
    
    return champions

def generate_cfp_bracket():
    """Generate 12-team CFP bracket based on current rankings - FIXED VERSION"""
    try:
        # Get all teams ranked by adjusted total
        all_teams = []
        for conf_name, teams in CONFERENCES.items():
            for team in teams:
                stats = calculate_comprehensive_stats(team)
                
                # Calculate real wins (excluding FCS) for display
                real_wins = 0
                total_wins = stats['total_wins']
                if team in team_stats:
                    for game in team_stats[team]['games']:
                        if game['result'] == 'W' and not is_fcs_opponent(game['opponent']):
                            real_wins += 1
                else:
                    real_wins = total_wins  # Fallback if no game data
                
                team_data = {
                    'team': team,
                    'conference': conf_name,
                    'total_wins': total_wins,
                    'total_losses': stats['total_losses'],
                    'real_wins': real_wins,
                    'adjusted_total': stats['adjusted_total']
                }
                all_teams.append(team_data)
        
        # Sort by adjusted total (highest first)
        all_teams.sort(key=lambda x: x['adjusted_total'], reverse=True)
        
        # Get conference champions (using existing function)
        champions = get_conference_champions()
        
        # Ensure we have at least some teams to work with
        if len(all_teams) < 4:
            # Return minimal bracket if not enough teams
            return {
                'first_round_byes': all_teams[:4] if len(all_teams) >= 4 else all_teams,
                'first_round_games': [],
                'all_teams': all_teams[:12] if len(all_teams) >= 12 else all_teams,
                'automatic_qualifiers': [],
                'at_large_display': [],
                'conference_champions': champions if champions else {}
            }
        
        # Step 1: Get the top 5 ranked conference champions (automatic qualifiers)
        automatic_qualifiers = []
        for team in all_teams:
            if team['conference'] in champions and champions[team['conference']]['team'] == team['team']:
                automatic_qualifiers.append(team)
                if len(automatic_qualifiers) == 5:
                    break
        
        # Step 2: Get the top 12 teams overall
        top_12_teams = all_teams[:12].copy() if len(all_teams) >= 12 else all_teams.copy()
        
        # Step 3: Ensure all auto-qualifiers are in the playoff
        auto_qualifier_names = {team['team'] for team in automatic_qualifiers}
        
        # Find auto-qualifiers not in top 12
        missing_auto_qualifiers = [team for team in automatic_qualifiers if team['team'] not in [t['team'] for t in top_12_teams]]
        
        # Replace lowest-ranked non-auto-qualifiers with missing auto-qualifiers
        for missing_team in missing_auto_qualifiers:
            # Find the lowest-ranked team in top_12 that's not an auto-qualifier
            for i in range(len(top_12_teams) - 1, -1, -1):  # Start from bottom
                if top_12_teams[i]['team'] not in auto_qualifier_names:
                    top_12_teams[i] = missing_team
                    break
        
        # Step 4: Sort the final teams and assign seeds 1-12
        playoff_teams = top_12_teams
        playoff_teams.sort(key=lambda x: x['adjusted_total'], reverse=True)
        
        for i, team in enumerate(playoff_teams):
            team['seed'] = i + 1
        
        # Step 5: First Round Byes go to TOP 4 TEAMS (seeds 1-4)
        first_round_byes = playoff_teams[:4]
        
        # At-Large Display: Seeds 5-12
        at_large_display = playoff_teams[4:] if len(playoff_teams) > 4 else []
        
        # Generate first round games if we have enough teams
        first_round_games = []
        if len(playoff_teams) >= 8:
            first_round_games = [
                {'higher_seed': playoff_teams[4], 'lower_seed': playoff_teams[11], 'game_num': 1} if len(playoff_teams) > 11 else None,
                {'higher_seed': playoff_teams[5], 'lower_seed': playoff_teams[10], 'game_num': 2} if len(playoff_teams) > 10 else None,
                {'higher_seed': playoff_teams[6], 'lower_seed': playoff_teams[9], 'game_num': 3} if len(playoff_teams) > 9 else None,
                {'higher_seed': playoff_teams[7], 'lower_seed': playoff_teams[8], 'game_num': 4} if len(playoff_teams) > 8 else None,
            ]
            # Remove None entries
            first_round_games = [game for game in first_round_games if game is not None]
        
        # Generate bracket structure
        bracket = {
            'first_round_byes': first_round_byes,
            'first_round_games': first_round_games,
            'all_teams': playoff_teams,
            'automatic_qualifiers': automatic_qualifiers,
            'at_large_display': at_large_display,
            'conference_champions': champions if champions else {}
        }
        
        return bracket
        
    except Exception as e:
        print(f"Error in generate_cfp_bracket: {e}")
        # Return safe fallback bracket
        return {
            'first_round_byes': [],
            'first_round_games': [],
            'all_teams': [],
            'automatic_qualifiers': [],
            'at_large_display': [],
            'conference_champions': {}
        }


# ===============================================
# MODULE 1: OPPONENT QUALITY ENGINE
# ===============================================

def calculate_team_base_strength(team_name, iteration=0, max_iterations=3):
    """
    Calculate a team's base strength using iterative opponent quality.
    Returns value between 1-10 (10 = elite, 5 = average, 1 = terrible)
    """
    if iteration >= max_iterations:
        # Base case: use simple metrics
        stats = team_stats[team_name]
        total_games = stats['wins'] + stats['losses']
        if total_games == 0:
            return 5.0  # Neutral rating for teams with no games
        
        win_pct = stats['wins'] / total_games
        return 2.0 + (win_pct * 6.0)  # Scale 2-8 based on win percentage
    
    stats = team_stats[team_name]
    total_games = stats['wins'] + stats['losses']
    
    if total_games == 0:
        return 5.0
    
    # Calculate base win percentage component
    win_pct = stats['wins'] / total_games
    base_score = 2.0 + (win_pct * 4.0)  # 2-6 range from win percentage
    
    # Add opponent-adjusted component
    opponent_quality_sum = 0
    game_count = 0
    
    for game in stats['games']:
        opponent = game['opponent']
        if opponent in team_stats and opponent != team_name:
            # Recursive call with iteration limit
            opp_strength = calculate_team_base_strength(opponent, iteration + 1, max_iterations)
            
            # Weight by game result and margin
            if game['result'] == 'W':
                # Beating strong opponents adds more, beating weak opponents adds less
                quality_bonus = (opp_strength - 5.0) * 0.3  # Scale opponent strength impact
                margin_factor = min(1.0, abs(game['team_score'] - game['opp_score']) / 14.0)
                opponent_quality_sum += quality_bonus * margin_factor
            else:
                # Losing to strong opponents hurts less, losing to weak opponents hurts more
                quality_penalty = (5.0 - opp_strength) * 0.4
                margin_factor = min(1.0, abs(game['team_score'] - game['opp_score']) / 21.0)
                opponent_quality_sum -= quality_penalty * margin_factor
            
            game_count += 1
    
    if game_count > 0:
        avg_opponent_adjustment = opponent_quality_sum / game_count
        final_strength = base_score + avg_opponent_adjustment
    else:
        final_strength = base_score
    
    # Bound the result between 1-10
    return max(1.0, min(10.0, final_strength))

def get_current_opponent_quality(opponent_name):
    """Get current quality rating for an opponent (1-10 scale) with FCS independence"""
    
    # Special handling for FCS - ALWAYS return fixed quality regardless of record
    if opponent_name == 'FCS' or opponent_name.upper() == 'FCS':
        return 0.5  # Fixed quality - never changes regardless of FCS "record"
    
    # Handle other non-FBS opponents
    if opponent_name not in team_stats:
        return 1.5  # Lower default for unknown opponents
    
    base_strength = calculate_team_base_strength(opponent_name)
    
    # Adjust for recent form (last 4 games) - only for real teams
    recent_games = team_stats[opponent_name]['games'][-4:]
    if len(recent_games) >= 2:
        recent_wins = sum(1 for g in recent_games if g['result'] == 'W')
        recent_form_bonus = (recent_wins / len(recent_games) - 0.5) * 1.0
        base_strength += recent_form_bonus
    
    return max(1.0, min(10.0, base_strength))

# ===============================================
# MODULE 2: VICTORY VALUE CALCULATOR  
# ===============================================

def calculate_victory_value(game, team_name):
    """
    Calculate the value of a single victory.
    Returns a score typically between 0-15 (excellent wins can exceed 10)
    """
    if game['result'] != 'W':
        return 0.0
    
    opponent = game['opponent']
    team_score = game['team_score']
    opp_score = game['opp_score']
    margin = team_score - opp_score
    location = game['home_away']
    
    # 1. Base Opponent Quality (1-10 scale)
    opponent_quality = get_current_opponent_quality(opponent)
    
    # 2. Location Multiplier
    location_multipliers = {
        'Home': 1.0,
        'Away': 1.3,    # Road wins worth 30% more
        'Neutral': 1.15  # Neutral site wins worth 15% more
    }
    location_mult = location_multipliers.get(location, 1.0)
    
    # 3. Margin Bonus with Diminishing Returns
    # Peak efficiency at 14-point wins, diminishing returns after that
    if margin <= 0:
        margin_bonus = 0
    elif margin <= 7:
        margin_bonus = margin * 0.1  # Linear up to 7 points
    elif margin <= 14:
        margin_bonus = 0.7 + (margin - 7) * 0.08  # Slower growth 7-14
    elif margin <= 21:
        margin_bonus = 1.26 + (margin - 14) * 0.04  # Even slower 14-21
    else:
        margin_bonus = 1.54 + (margin - 21) * 0.02  # Minimal benefit beyond 21
    
    # 4. Conference Context Bonus
    team_conf = get_team_conference(team_name)
    opp_conf = get_team_conference(opponent)
    
    conf_bonus = 0
    if team_conf in P4_CONFERENCES and opp_conf in P4_CONFERENCES:
        conf_bonus = 0.3  # P4 vs P4 bonus
    elif team_conf in G5_CONFERENCES and opp_conf in P4_CONFERENCES:
        conf_bonus = 0.5  # G5 beating P4 major bonus
    
    # 5. Calculate Final Victory Value
    base_value = opponent_quality * location_mult
    total_value = base_value + margin_bonus + conf_bonus
    
    return round(total_value, 2)

# Add helper function to show bowl eligibility status:

def get_team_bowl_status(team_name):
    """Get detailed bowl eligibility status for a team"""
    if team_name not in team_stats:
        return None
    
    stats = team_stats[team_name]
    total_wins = stats['wins']
    total_losses = stats['losses']
    
    # Count real wins (non-FCS)
    real_wins = 0
    fcs_wins = 0
    for game in stats['games']:
        if game['result'] == 'W':
            if is_fcs_opponent(game['opponent']):
                fcs_wins += 1
            else:
                real_wins += 1
    
    bowl_eligible = real_wins >= 6
    
    return {
        'total_wins': total_wins,
        'real_wins': real_wins,
        'fcs_wins': fcs_wins,
        'losses': total_losses,
        'bowl_eligible': bowl_eligible,
        'wins_needed': max(0, 6 - real_wins) if not bowl_eligible else 0
    }

def calculate_total_victory_value(team_name):
    """Sum up all victory values for a team - UPDATED for rivalry bonus"""
    total_value = 0
    victory_details = []
    
    for game in team_stats[team_name]['games']:
        if game['result'] == 'W':
            value = calculate_victory_value_with_rivalry(game, team_name)  # Use new function
            total_value += value
            
            # Check if this was a rivalry win for display
            is_rival = is_rivalry_game(team_name, game['opponent'])
            rivalry_bonus = get_rivalry_bonus(team_name, game['opponent']) if is_rival else 0
            
            victory_details.append({
                'opponent': game['opponent'],
                'value': value,
                'margin': game['team_score'] - game['opp_score'],
                'location': game['home_away'],
                'is_rivalry': is_rival,
                'rivalry_bonus': rivalry_bonus
            })
    
    return total_value, victory_details

# ===============================================
# MODULE 3: LOSS QUALITY ASSESSMENT
# ===============================================

def calculate_loss_penalty(game, team_name):
    """
    Calculate penalty for a single loss based on quality and context.
    Returns a penalty value (positive number = bad for ranking)
    """
    if game['result'] != 'L':
        return 0.0
    
    opponent = game['opponent']
    team_score = game['team_score']
    opp_score = game['opp_score']
    margin = opp_score - team_score  # How much they lost by
    location = game['home_away']
    is_overtime = game.get('overtime', False)  # NEW: Check for overtime
    
    # 1. Base Loss Penalty
    base_penalty = 3.0  # Every loss starts with 3-point penalty
    
    # 2. Opponent Quality Adjustment
    opponent_quality = get_current_opponent_quality(opponent)
    
    # Losing to good teams hurts less, losing to bad teams hurts more
    if opponent_quality >= 7.0:  # Top tier opponent
        quality_adjustment = -1.5  # Reduce penalty
    elif opponent_quality >= 5.5:  # Decent opponent  
        quality_adjustment = -0.5  # Slight penalty reduction
    elif opponent_quality >= 4.0:  # Below average opponent
        quality_adjustment = 0.5   # Slight penalty increase
    else:  # Bad opponent
        quality_adjustment = 2.0   # Major penalty increase
    
    # 3. Margin Penalty - Blowout losses hurt more
    if margin <= 3:
        margin_penalty = 0  # Close losses don't add extra penalty
    elif margin <= 7:
        margin_penalty = 0.5
    elif margin <= 14:
        margin_penalty = 1.0
    elif margin <= 21:
        margin_penalty = 2.0
    else:
        margin_penalty = 3.0  # Blowout losses hurt a lot
    
    # 4. Location Adjustment
    location_adjustments = {
        'Home': 0.5,     # Losing at home hurts more
        'Away': -0.3,    # Losing on road hurts less
        'Neutral': 0.0   # Neutral baseline
    }
    location_adj = location_adjustments.get(location, 0.0)
    
    # 5. Calculate Total Penalty
    total_penalty = base_penalty + quality_adjustment + margin_penalty + location_adj
    
    # 6. NEW: Overtime Loss Reduction
    if is_overtime:
        total_penalty *= 0.7  # 30% reduction for overtime losses
    
    # Ensure penalty is never negative (losses should always hurt something)
    return max(0.5, total_penalty)

def calculate_total_loss_penalty(team_name):
    """Sum up all loss penalties for a team"""
    total_penalty = 0
    loss_details = []    
    for game in team_stats[team_name]['games']:
        if game['result'] == 'L':
            penalty = calculate_loss_penalty(game, team_name)
            total_penalty += penalty
            loss_details.append({
                'opponent': game['opponent'],
                'penalty': penalty,
                'margin': game['opp_score'] - game['team_score'],
                'location': game['home_away']
            })
    
    return total_penalty, loss_details

# ===============================================
# MODULE 4: TEMPORAL WEIGHTING ENGINE
# ===============================================

def calculate_temporal_adjustment(team_name):
    """
    Adjust for recent form vs season-long performance.
    Returns adjustment factor for current strength (-2 to +2 range).
    """
    games = team_stats[team_name]['games']
    if len(games) < 4:
        return 0  # Not enough games for temporal analysis
    
    # Split season into early (all but last 4) and recent (last 4)
    early_games = games[:-4] if len(games) > 4 else []
    recent_games = games[-4:]
    
    if not early_games:
        return 0  # All games are "recent"
    
    # Calculate performance metrics for each period
    def calculate_period_performance(game_list):
        if not game_list:
            return 0.5, 0  # Neutral win rate, no margin
        
        wins = sum(1 for g in game_list if g['result'] == 'W')
        win_rate = wins / len(game_list)
        
        total_margin = sum(g['team_score'] - g['opp_score'] for g in game_list)
        avg_margin = total_margin / len(game_list)
        
        return win_rate, avg_margin
    
    early_win_rate, early_margin = calculate_period_performance(early_games)
    recent_win_rate, recent_margin = calculate_period_performance(recent_games)
    
    # Calculate improvement/decline
    win_rate_change = recent_win_rate - early_win_rate
    margin_change = recent_margin - early_margin
    
    # Convert to temporal adjustment (-2 to +2 range)
    adjustment = (win_rate_change * 2.0) + (margin_change / 14.0)
    
    return max(-2.0, min(2.0, adjustment))

# ===============================================
# MODULE 5: CONSISTENCY ANALYZER
# ===============================================

def calculate_consistency_factor(team_name):
    """
    Measure team consistency/reliability.
    Returns adjustment based on performance variance (-0.6 to +0.5 range).
    """
    games = team_stats[team_name]['games']
    if len(games) < 4:
        return 0  # Need multiple games for consistency analysis
    
    # Calculate game-by-game performance scores
    performance_scores = []
    for game in games:
        opponent_quality = get_current_opponent_quality(game['opponent'])
        margin = game['team_score'] - game['opp_score']
        
        # Expected margin based on opponent quality (rough approximation)
        expected_margin = (5.0 - opponent_quality) * 2  # Stronger opponents = negative expected margin
        
        # Performance score = how much better/worse than expected
        performance_score = margin - expected_margin
        performance_scores.append(performance_score)
    
    # Calculate variance
    if len(performance_scores) < 2:
        return 0
    
    mean_performance = sum(performance_scores) / len(performance_scores)
    variance = sum((score - mean_performance) ** 2 for score in performance_scores) / len(performance_scores)
    std_dev = math.sqrt(variance)
    
    # Convert to consistency factor
    # Lower variance = more consistent = small bonus
    # Higher variance = less reliable = small penalty
    if std_dev <= 10:
        consistency_bonus = 0.5  # Very consistent
    elif std_dev <= 15:
        consistency_bonus = 0.2  # Somewhat consistent
    elif std_dev <= 20:
        consistency_bonus = 0.0  # Average consistency
    elif std_dev <= 25:
        consistency_bonus = -0.3  # Inconsistent
    else:
        consistency_bonus = -0.6  # Very inconsistent
    
    return consistency_bonus

# ===============================================
# MODULE 6: FINAL RANKING COMPOSER
# ===============================================

def calculate_scientific_ranking(team_name):
    """
    Combine all modules into final scientific ranking score.
    Higher score = better ranking.
    """
    stats = team_stats[team_name]
    total_games = stats['wins'] + stats['losses']
    
    if total_games == 0:
        return {
            'total_score': 0.0,
            'components': {
                'victory_value': 0.0,
                'conference_multiplier': 1.0,
                'adjusted_victory_value': 0.0,
                'loss_penalty': 0.0,
                'temporal_adjustment': 0.0,
                'consistency_factor': 0.0,
                'games_bonus': 0.0
            },
            'basic_stats': {'wins': 0, 'losses': 0}
        }
    
    # Component 1: Victory Value (0-100+ range)
    victory_value, victory_details = calculate_total_victory_value(team_name)
    
    # NEW: Conference Multiplier for G5 teams
    team_conf = get_team_conference(team_name)
    if team_conf in G5_CONFERENCES or team_name in G5_INDEPENDENT_TEAMS:
        conference_multiplier = 0.85  # G5 teams get 85% credit
    else:
        conference_multiplier = 1.0   # P4 teams (and independents like Notre Dame) get full credit
    
    # Apply conference multiplier to victory value
    adjusted_victory_value = victory_value * conference_multiplier
    
    # Component 2: Loss Penalties (0-50+ range, subtracted)
    loss_penalty, loss_details = calculate_total_loss_penalty(team_name)
    
    # Component 3: Temporal Adjustment (-2 to +2 range)
    temporal_adj = calculate_temporal_adjustment(team_name)
    
    # Component 4: Consistency Factor (-0.6 to +0.5 range)
    consistency_factor = calculate_consistency_factor(team_name)
    
    # Component 5: Games Played Bonus (rewards full seasons)
    games_bonus = min(2.0, total_games * 0.15)  # Up to 2 points for 13+ games
    
    # Final Score Calculation - use ADJUSTED victory value
    total_score = (
        adjusted_victory_value -  # Now uses conference-adjusted victory value
        loss_penalty +           # Lower for bad losses  
        temporal_adj +           # Recent form adjustment
        consistency_factor +     # Reliability bonus/penalty
        games_bonus             # Slight bonus for playing full season
    )
    
    return {
        'total_score': round(total_score, 2),
        'components': {
            'victory_value': round(victory_value, 2),           # Original victory value
            'conference_multiplier': conference_multiplier,     # 1.0 for P4, 0.85 for G5
            'adjusted_victory_value': round(adjusted_victory_value, 2),  # After multiplier
            'loss_penalty': round(loss_penalty, 2),
            'temporal_adjustment': round(temporal_adj, 2),
            'consistency_factor': round(consistency_factor, 2),
            'games_bonus': round(games_bonus, 2)
        },
        'basic_stats': {
            'wins': stats['wins'],
            'losses': stats['losses'],
            'total_games': total_games
        }
    }



def calculate_comprehensive_stats(team_name):
    """
    Calculate comprehensive stats - UPDATED to remove P4/G5 legacy fields
    """
    scientific_result = calculate_scientific_ranking(team_name)
    
    # Map to old format for backward compatibility
    stats = team_stats[team_name]
    total_games = stats['wins'] + stats['losses']
    
    # Calculate some legacy fields that other parts of code might expect
    opponent_total_wins = 0
    opponent_total_losses = 0
    opponent_total_games = 0
    
    for game in stats['games']:
        opponent = game['opponent']
        if opponent in team_stats:
            opp_stats = team_stats[opponent]
            opponent_total_wins += opp_stats['wins']
            opponent_total_losses += opp_stats['losses']
            opponent_total_games += (opp_stats['wins'] + opp_stats['losses'])
    
    strength_of_schedule = opponent_total_wins / opponent_total_games if opponent_total_games > 0 else 0
    point_differential = stats['points_for'] - stats['points_against']
    opp_wl_differential = opponent_total_wins - opponent_total_losses
    
    return {
        # NEW: Scientific score as main ranking
        'adjusted_total': scientific_result['total_score'],
        
        # LEGACY: Keep all old fields for template compatibility (except P4/G5)
        'points_fielded': stats['points_for'],
        'points_allowed': stats['points_against'],
        'margin_of_victory': stats['margin_of_victory_total'],
        'point_differential': point_differential,
        'home_wins': stats['home_wins'],
        'road_wins': stats['road_wins'],
        # REMOVED: 'p4_wins': stats['p4_wins'], 'g5_wins': stats['g5_wins'],
        'opp_w': opponent_total_wins,
        'opp_l': opponent_total_losses,
        'strength_of_schedule': round(strength_of_schedule, 3),
        'opp_wl_differential': opp_wl_differential,
        'totals': scientific_result['components']['victory_value'],
        'total_wins': stats['wins'],
        'total_losses': stats['losses'],
        'strength_of_record': round(strength_of_schedule * (stats['wins'] / max(1, stats['wins'] + stats['losses'])), 3),
        
        # NEW: Scientific breakdown available for future use
        'scientific_breakdown': scientific_result
    }


def update_team_stats_simplified(team, opponent, team_score, opp_score, is_home, is_neutral_site=False, is_overtime=False):
    """Update team statistics after a game - SIMPLIFIED without game types"""
    
    # Special case: Don't update stats for FCS placeholder team
    if team == 'FCS' or team.upper() == 'FCS':
        return
    
    # Determine win/loss and margin of victory
    if team_score > opp_score:
        team_stats[team]['wins'] += 1
        # Add margin of victory (only for wins)
        team_stats[team]['margin_of_victory_total'] += (team_score - opp_score)
        
        # Track home/road wins (only if NOT neutral site)
        if not is_neutral_site:
            if is_home:
                team_stats[team]['home_wins'] += 1
            else:
                team_stats[team]['road_wins'] += 1
        
        # REMOVED: P4/G5 win tracking (no longer needed)
    else:
        team_stats[team]['losses'] += 1
        # REMOVED: P4/G5 loss tracking (no longer needed)
    
    # Update points
    team_stats[team]['points_for'] += team_score
    team_stats[team]['points_against'] += opp_score
    
    # Determine game location for display
    if is_neutral_site:
        location = 'Neutral'
    elif is_home:
        location = 'Home'
    else:
        location = 'Away'
    
    # Add game to history - ADDED overtime field
    team_stats[team]['games'].append({
        'opponent': opponent,
        'team_score': team_score,
        'opp_score': opp_score,
        'result': 'W' if team_score > opp_score else 'L',
        'home_away': location,
        'overtime': is_overtime  # NEW: Store overtime status for each game
    })

def analyze_common_opponents(team1_name, team2_name):
    """Analyze how both teams performed against common opponents"""
    team1_games = team_stats[team1_name]['games']
    team2_games = team_stats[team2_name]['games']
    
    # Find common opponents
    team1_opponents = {game['opponent'] for game in team1_games}
    team2_opponents = {game['opponent'] for game in team2_games}
    common_opponents = team1_opponents.intersection(team2_opponents)
    
    if not common_opponents:
        return {
            'has_common': False,
            'comparison': [],
            'advantage': 0,
            'summary': "No common opponents"
        }
    
    comparisons = []
    total_advantage = 0
    
    for opponent in common_opponents:
        # Find team1's game against this opponent
        team1_game = next((g for g in team1_games if g['opponent'] == opponent), None)
        team2_game = next((g for g in team2_games if g['opponent'] == opponent), None)
        
        if team1_game and team2_game:
            # Calculate point differential for each team
            team1_diff = team1_game['team_score'] - team1_game['opp_score']
            team2_diff = team2_game['team_score'] - team2_game['opp_score']
            
            advantage = team1_diff - team2_diff
            total_advantage += advantage
            
            comparisons.append({
                'opponent': opponent,
                'team1_result': f"{team1_game['result']} {team1_game['team_score']}-{team1_game['opp_score']}",
                'team2_result': f"{team2_game['result']} {team2_game['team_score']}-{team2_game['opp_score']}",
                'team1_diff': team1_diff,
                'team2_diff': team2_diff,
                'advantage': advantage
            })
    
    avg_advantage = total_advantage / len(comparisons) if comparisons else 0
    
    return {
        'has_common': True,
        'comparison': comparisons,
        'advantage': round(avg_advantage, 1),
        'summary': f"Common opponents favor {'Team 1' if avg_advantage > 0 else 'Team 2'} by {abs(avg_advantage):.1f} points per game"
    }

def calculate_recent_form(team_name, games_back=4):
    """Calculate recent form over last N games"""
    games = team_stats[team_name]['games']
    if len(games) < games_back:
        games_back = len(games)
    
    if games_back == 0:
        return {
            'record': '0-0',
            'avg_margin': 0,
            'trending': 'neutral',
            'last_games': []
        }
    
    recent_games = games[-games_back:]
    wins = sum(1 for g in recent_games if g['result'] == 'W')
    losses = len(recent_games) - wins
    
    # Calculate average margin (positive = winning by, negative = losing by)
    total_margin = sum((g['team_score'] - g['opp_score']) for g in recent_games)
    avg_margin = total_margin / len(recent_games)
    
    # Determine trend (are margins improving or declining?)
    if len(recent_games) >= 2:
        first_half = recent_games[:len(recent_games)//2]
        second_half = recent_games[len(recent_games)//2:]
        
        first_avg = sum((g['team_score'] - g['opp_score']) for g in first_half) / len(first_half)
        second_avg = sum((g['team_score'] - g['opp_score']) for g in second_half) / len(second_half)
        
        if second_avg > first_avg + 3:
            trending = 'up'
        elif second_avg < first_avg - 3:
            trending = 'down'
        else:
            trending = 'neutral'
    else:
        trending = 'neutral'
    
    return {
        'record': f"{wins}-{losses}",
        'avg_margin': round(avg_margin, 1),
        'trending': trending,
        'last_games': recent_games[-3:]  # Show last 3 games
    }

def analyze_style_matchup(team1_name, team2_name):
    """Analyze offensive vs defensive matchups"""
    team1_stats = calculate_comprehensive_stats(team1_name)
    team2_stats = calculate_comprehensive_stats(team2_name)
    
    # Calculate per-game averages
    team1_games = team1_stats['total_wins'] + team1_stats['total_losses']
    team2_games = team2_stats['total_wins'] + team2_stats['total_losses']
    
    if team1_games == 0 or team2_games == 0:
        return {
            'team1_offense': 0,
            'team1_defense': 0,
            'team2_offense': 0,
            'team2_defense': 0,
            'analysis': "Insufficient data for style analysis"
        }
    
    team1_ppg = team1_stats['points_fielded'] / team1_games
    team1_papg = team1_stats['points_allowed'] / team1_games
    team2_ppg = team2_stats['points_fielded'] / team2_games
    team2_papg = team2_stats['points_allowed'] / team2_games
    
    # Simple matchup analysis
    matchup_analysis = []
    
    if team1_ppg > team2_papg + 5:
        matchup_analysis.append(f"{team1_name}'s offense vs {team2_name}'s defense favors {team1_name}")
    elif team2_papg > team1_ppg + 5:
        matchup_analysis.append(f"{team1_name}'s offense vs {team2_name}'s defense favors {team2_name}")
    
    if team2_ppg > team1_papg + 5:
        matchup_analysis.append(f"{team2_name}'s offense vs {team1_name}'s defense favors {team2_name}")
    elif team1_papg > team2_ppg + 5:
        matchup_analysis.append(f"{team2_name}'s offense vs {team1_name}'s defense favors {team1_name}")
    
    if not matchup_analysis:
        matchup_analysis.append("Evenly matched on both sides of the ball")
    
    return {
        'team1_offense': round(team1_ppg, 1),
        'team1_defense': round(team1_papg, 1),
        'team2_offense': round(team2_ppg, 1),
        'team2_defense': round(team2_papg, 1),
        'analysis': "; ".join(matchup_analysis)
    }

def head_to_head_history(team1_name, team2_name):
    """Check if teams have played each other recently"""
    team1_games = team_stats[team1_name]['games']
    
    # Look for games against each other
    h2h_games = [g for g in team1_games if g['opponent'] == team2_name]
    
    if not h2h_games:
        return {
            'has_history': False,
            'summary': "Teams have not played each other"
        }
    
    # Get most recent game
    recent_game = h2h_games[-1]
    team1_wins = sum(1 for g in h2h_games if g['result'] == 'W')
    team1_losses = len(h2h_games) - team1_wins
    
    return {
        'has_history': True,
        'record': f"{team1_name} leads {team1_wins}-{team1_losses}",
        'last_game': recent_game,
        'summary': f"Last meeting: {team1_name} {recent_game['result']} {recent_game['team_score']}-{recent_game['opp_score']}"
    }

def predict_matchup_enhanced(team1_name, team2_name, location='neutral'):
    """
    ENHANCED comprehensive matchup prediction using scientific ranking system
    """
    # Get scientific ranking breakdowns
    team1_scientific = calculate_scientific_ranking(team1_name)
    team2_scientific = calculate_scientific_ranking(team2_name)
    
    team1_stats = calculate_comprehensive_stats(team1_name)
    team2_stats = calculate_comprehensive_stats(team2_name)
    
    # 1. CORE STRENGTH DIFFERENTIAL (Primary Factor - 60% weight)
    strength_diff = team1_scientific['total_score'] - team2_scientific['total_score']
    base_prediction = strength_diff * 2.2  # Refined scaling factor
    
    # 2. ENHANCED ADJUSTMENTS
    adjustments = {}
    total_adjustment = 0
    
    # A. Common Opponents Analysis (Enhanced)
    common_analysis = analyze_common_opponents_enhanced(team1_name, team2_name)
    if common_analysis['has_common'] and common_analysis['games_count'] >= 2:
        # Weight by number of common opponents and recency
        common_weight = min(0.4, common_analysis['games_count'] * 0.15)
        common_adj = common_analysis['advantage'] * common_weight
        adjustments['Common Opponents'] = round(common_adj, 1)
        total_adjustment += common_adj
    
    # B. Victory Quality Comparison
    victory_quality_diff = analyze_victory_quality_differential(team1_name, team2_name)
    if victory_quality_diff['significant']:
        adjustments['Victory Quality'] = victory_quality_diff['adjustment']
        total_adjustment += victory_quality_diff['adjustment']
    
    # C. Recent Form Analysis (Enhanced)
    team1_form = calculate_enhanced_recent_form(team1_name)
    team2_form = calculate_enhanced_recent_form(team2_name)
    
    form_differential = team1_form['momentum_score'] - team2_form['momentum_score']
    form_adj = form_differential * 0.8  # Increased weight for recent form
    if abs(form_adj) > 0.3:  # Only apply if significant
        adjustments['Recent Momentum'] = round(form_adj, 1)
        total_adjustment += form_adj
    
    # D. Conference Context (More Nuanced)
    conf_adj = calculate_conference_matchup_adjustment(team1_name, team2_name)
    if conf_adj != 0:
        adjustments['Conference Differential'] = conf_adj
        total_adjustment += conf_adj
    
    # E. Schedule Strength Comparison
    schedule_diff = analyze_schedule_strength_differential(team1_name, team2_name)
    if abs(schedule_diff) > 0.5:
        adjustments['Schedule Strength'] = round(schedule_diff, 1)
        total_adjustment += schedule_diff
    
    # F. Consistency Factor
    consistency_diff = (team1_scientific['components']['consistency_factor'] - 
                       team2_scientific['components']['consistency_factor'])
    if abs(consistency_diff) > 0.2:
        consistency_adj = consistency_diff * 2.0  # Amplify consistency impact
        adjustments['Consistency Edge'] = round(consistency_adj, 1)
        total_adjustment += consistency_adj
    
    # G. Home Field Advantage (Enhanced)
    hfa_adj = calculate_enhanced_home_field_advantage(team1_name, team2_name, location)
    if hfa_adj != 0:
        adjustments['Home Field Advantage'] = hfa_adj
        total_adjustment += hfa_adj
    
    # 3. FINAL PREDICTION CALCULATION
    final_margin = base_prediction + total_adjustment
    
    # 4. CONFIDENCE AND WIN PROBABILITY
    confidence_metrics = calculate_prediction_confidence(
        team1_name, team2_name, final_margin, adjustments
    )
    
    # Enhanced win probability calculation
    win_prob = calculate_enhanced_win_probability(final_margin, confidence_metrics)
    
    return {
        'base_margin': round(base_prediction, 1),
        'adjustments': adjustments,
        'final_margin': round(final_margin, 1),
        'win_probability': round(win_prob, 1),
        'winner': team1_name if final_margin > 0 else team2_name,
        'confidence': confidence_metrics['level'],
        'confidence_score': confidence_metrics['score'],
        'key_factors': identify_key_prediction_factors(adjustments, team1_scientific, team2_scientific),
        'detailed_breakdown': {
            'team1_scientific': team1_scientific,
            'team2_scientific': team2_scientific,
            'strength_differential': round(strength_diff, 2)
        }
    }

def analyze_common_opponents_enhanced(team1_name, team2_name):
    """Enhanced common opponent analysis with recency weighting"""
    team1_games = team_stats[team1_name]['games']
    team2_games = team_stats[team2_name]['games']
    
    # Find common opponents
    team1_opponents = {game['opponent'] for game in team1_games}
    team2_opponents = {game['opponent'] for game in team2_games}
    common_opponents = team1_opponents.intersection(team2_opponents)
    
    if not common_opponents:
        return {'has_common': False, 'advantage': 0, 'games_count': 0}
    
    comparisons = []
    total_advantage = 0
    weighted_advantage = 0
    total_weight = 0
    
    for opponent in common_opponents:
        # Find most recent games against this opponent
        team1_games_vs = [g for g in team1_games if g['opponent'] == opponent]
        team2_games_vs = [g for g in team2_games if g['opponent'] == opponent]
        
        if team1_games_vs and team2_games_vs:
            team1_game = team1_games_vs[-1]  # Most recent
            team2_game = team2_games_vs[-1]  # Most recent
            
            # Calculate opponent quality for weighting
            opponent_quality = get_current_opponent_quality(opponent)
            
            # Calculate performance differential
            team1_diff = team1_game['team_score'] - team1_game['opp_score']
            team2_diff = team2_game['team_score'] - team2_game['opp_score']
            advantage = team1_diff - team2_diff
            
            # Weight by opponent quality (better opponents matter more)
            weight = max(0.5, opponent_quality / 10.0)
            
            weighted_advantage += advantage * weight
            total_weight += weight
            total_advantage += advantage
            
            comparisons.append({
                'opponent': opponent,
                'team1_diff': team1_diff,
                'team2_diff': team2_diff,
                'advantage': advantage,
                'weight': weight,
                'opponent_quality': opponent_quality
            })
    
    avg_advantage = weighted_advantage / total_weight if total_weight > 0 else 0
    
    return {
        'has_common': True,
        'advantage': round(avg_advantage, 1),
        'games_count': len(comparisons),
        'comparisons': comparisons,
        'raw_advantage': round(total_advantage / len(comparisons), 1) if comparisons else 0
    }

def analyze_victory_quality_differential(team1_name, team2_name):
    """Compare the quality of victories between two teams"""
    team1_victory_value, team1_details = calculate_total_victory_value(team1_name)
    team2_victory_value, team2_details = calculate_total_victory_value(team2_name)
    
    # Get games count for normalization
    team1_wins = len(team1_details)
    team2_wins = len(team2_details)
    
    if team1_wins == 0 and team2_wins == 0:
        return {'significant': False, 'adjustment': 0}
    
    # Calculate per-win victory value
    team1_avg_victory = team1_victory_value / max(1, team1_wins)
    team2_avg_victory = team2_victory_value / max(1, team2_wins)
    
    victory_diff = team1_avg_victory - team2_avg_victory
    
    # Only significant if difference is meaningful
    if abs(victory_diff) < 0.8:
        return {'significant': False, 'adjustment': 0}
    
    # Scale the adjustment (cap at reasonable range)
    adjustment = max(-3.0, min(3.0, victory_diff * 1.5))
    
    return {
        'significant': True,
        'adjustment': round(adjustment, 1),
        'team1_avg_victory': round(team1_avg_victory, 2),
        'team2_avg_victory': round(team2_avg_victory, 2)
    }

def calculate_enhanced_recent_form(team_name, games_back=4):
    """Calculate enhanced recent form with momentum scoring"""
    games = team_stats[team_name]['games']
    if len(games) < 2:
        return {'momentum_score': 0, 'trend': 'insufficient_data'}
    
    recent_games = games[-games_back:] if len(games) >= games_back else games
    
    momentum_score = 0
    trend_points = []
    
    for i, game in enumerate(recent_games):
        # Recency weight (more recent games matter more)
        recency_weight = (i + 1) / len(recent_games)
        
        # Performance score for this game
        margin = game['team_score'] - game['opp_score']
        opponent_quality = get_current_opponent_quality(game['opponent'])
        
        # Expected margin based on opponent quality
        expected_margin = (5.0 - opponent_quality) * 1.8
        performance = margin - expected_margin
        
        # Weight by recency and add to momentum
        weighted_performance = performance * recency_weight
        momentum_score += weighted_performance
        trend_points.append(performance)
    
    # Determine trend
    if len(trend_points) >= 2:
        early_avg = sum(trend_points[:len(trend_points)//2]) / (len(trend_points)//2)
        late_avg = sum(trend_points[len(trend_points)//2:]) / (len(trend_points) - len(trend_points)//2)
        
        if late_avg > early_avg + 5:
            trend = 'improving'
        elif late_avg < early_avg - 5:
            trend = 'declining'
        else:
            trend = 'stable'
    else:
        trend = 'stable'
    
    return {
        'momentum_score': round(momentum_score / len(recent_games), 1),
        'trend': trend,
        'recent_performance': trend_points
    }

def calculate_conference_matchup_adjustment(team1_name, team2_name):
    """More nuanced conference matchup adjustments"""
    team1_conf = get_team_conference(team1_name)
    team2_conf = get_team_conference(team2_name)
    
    # P4 vs G5 adjustments based on actual performance differential
    if team1_conf in P4_CONFERENCES and team2_conf in G5_CONFERENCES:
        # P4 teams should have some advantage, but not as much if G5 team is strong
        team2_scientific = calculate_scientific_ranking(team2_name)
        base_adj = 2.5
        
        # Reduce advantage if G5 team has high victory value
        if team2_scientific['components']['adjusted_victory_value'] > 25:
            base_adj = 1.5  # Strong G5 team
        elif team2_scientific['components']['adjusted_victory_value'] > 35:
            base_adj = 0.8  # Elite G5 team
        
        return base_adj
        
    elif team2_conf in P4_CONFERENCES and team1_conf in G5_CONFERENCES:
        # Mirror the above logic
        team1_scientific = calculate_scientific_ranking(team1_name)
        base_adj = -2.5
        
        if team1_scientific['components']['adjusted_victory_value'] > 25:
            base_adj = -1.5
        elif team1_scientific['components']['adjusted_victory_value'] > 35:
            base_adj = -0.8
        
        return base_adj
    
    return 0  # Same level conferences

def analyze_schedule_strength_differential(team1_name, team2_name):
    """Analyze difference in schedule difficulty"""
    team1_games = team_stats[team1_name]['games']
    team2_games = team_stats[team2_name]['games']
    
    if not team1_games or not team2_games:
        return 0
    
    # Calculate average opponent quality
    team1_opp_quality = sum(get_current_opponent_quality(g['opponent']) for g in team1_games) / len(team1_games)
    team2_opp_quality = sum(get_current_opponent_quality(g['opponent']) for g in team2_games) / len(team2_games)
    
    quality_diff = team1_opp_quality - team2_opp_quality
    
    # Convert to point adjustment (stronger schedule = slight edge)
    adjustment = quality_diff * 0.8
    return max(-2.0, min(2.0, adjustment))

def calculate_enhanced_home_field_advantage(team1_name, team2_name, location):
    """Enhanced home field advantage based on team-specific performance"""
    if location == 'neutral':
        return 0
    
    base_hfa = 3.0  # Standard home field advantage
    
    if location == 'team1_home':
        # Check team1's home performance
        home_performance = analyze_home_performance(team1_name)
        hfa_modifier = home_performance['advantage_modifier']
        return round(base_hfa * hfa_modifier, 1)
    
    elif location == 'team2_home':
        # Check team2's home performance  
        home_performance = analyze_home_performance(team2_name)
        hfa_modifier = home_performance['advantage_modifier']
        return round(-base_hfa * hfa_modifier, 1)
    
    return 0

def analyze_home_performance(team_name):
    """Analyze how much a team benefits from playing at home"""
    games = team_stats[team_name]['games']
    
    home_games = [g for g in games if g['home_away'] == 'Home']
    away_games = [g for g in games if g['home_away'] == 'Away']
    
    if len(home_games) < 2 or len(away_games) < 2:
        return {'advantage_modifier': 1.0}  # Default
    
    # Calculate average margin at home vs away
    home_margins = [g['team_score'] - g['opp_score'] for g in home_games]
    away_margins = [g['team_score'] - g['opp_score'] for g in away_games]
    
    home_avg = sum(home_margins) / len(home_margins)
    away_avg = sum(away_margins) / len(away_margins)
    
    home_advantage = home_avg - away_avg
    
    # Convert to modifier (1.0 = normal, >1.0 = strong home field, <1.0 = weak home field)
    if home_advantage > 8:
        modifier = 1.3  # Strong home field
    elif home_advantage > 4:
        modifier = 1.1  # Slight home field advantage
    elif home_advantage < -4:
        modifier = 0.8  # Actually worse at home
    else:
        modifier = 1.0  # Normal
    
    return {'advantage_modifier': modifier}

def calculate_prediction_confidence(team1_name, team2_name, final_margin, adjustments):
    """Calculate confidence in the prediction"""
    confidence_factors = []
    
    # 1. Sample size (more games = more confidence)
    team1_games = len(team_stats[team1_name]['games'])
    team2_games = len(team_stats[team2_name]['games'])
    min_games = min(team1_games, team2_games)
    
    if min_games >= 8:
        confidence_factors.append(0.3)
    elif min_games >= 5:
        confidence_factors.append(0.2)
    else:
        confidence_factors.append(0.1)
    
    # 2. Margin size (bigger margins = more confidence)
    if abs(final_margin) > 14:
        confidence_factors.append(0.3)
    elif abs(final_margin) > 7:
        confidence_factors.append(0.2)
    else:
        confidence_factors.append(0.1)
    
    # 3. Common opponents (more shared opponents = more confidence)
    common_analysis = analyze_common_opponents_enhanced(team1_name, team2_name)
    if common_analysis['games_count'] >= 3:
        confidence_factors.append(0.2)
    elif common_analysis['games_count'] >= 1:
        confidence_factors.append(0.1)
    
    # 4. Consistency of adjustments (if all point same way = more confidence)
    positive_adj = sum(1 for adj in adjustments.values() if adj > 0.5)
    negative_adj = sum(1 for adj in adjustments.values() if adj < -0.5)
    
    if len(adjustments) > 0:
        consistency = max(positive_adj, negative_adj) / len(adjustments)
        confidence_factors.append(consistency * 0.2)
    
    total_confidence = sum(confidence_factors)
    
    if total_confidence >= 0.7:
        level = 'High'
    elif total_confidence >= 0.4:
        level = 'Medium'
    else:
        level = 'Low'
    
    return {
        'score': round(total_confidence, 2),
        'level': level,
        'factors': confidence_factors
    }

def calculate_enhanced_win_probability(margin, confidence_metrics):
    """Enhanced win probability calculation"""
    # Base probability from margin
    base_prob = 50 + (margin * 2.2)  # Slightly less aggressive than before
    
    # Adjust based on confidence
    confidence_adjustment = (confidence_metrics['score'] - 0.5) * 5
    
    final_prob = base_prob + confidence_adjustment
    
    # Cap between 5-95%
    return max(5, min(95, final_prob))

def identify_key_prediction_factors(adjustments, team1_scientific, team2_scientific):
    """Identify the most important factors in the prediction"""
    factors = []
    
    # Largest adjustments
    sorted_adj = sorted(adjustments.items(), key=lambda x: abs(x[1]), reverse=True)
    for factor, value in sorted_adj[:3]:  # Top 3 adjustments
        if abs(value) > 0.5:
            factors.append(f"{factor}: {value:+.1f}")
    
    # Scientific ranking components
    team1_components = team1_scientific['components']
    team2_components = team2_scientific['components']
    
    victory_diff = team1_components['adjusted_victory_value'] - team2_components['adjusted_victory_value']
    if abs(victory_diff) > 5:
        factors.append(f"Victory Quality Edge: {victory_diff:+.1f}")
    
    return factors[:4]  # Return top 4 factors
# Add this near the top with other global variables
scheduled_games = []

def parse_schedule_text(schedule_text, week, team_clarifications=None):
    """Parse pasted schedule text into structured game data with dates, times, and TV"""
    games = []
    unknown_teams = set()
    lines = [line.strip() for line in schedule_text.split('\n') if line.strip()]

    print(f"DEBUG PARSE: Processing {len(lines)} lines")
    
    current_date = None
    current_year = datetime.now().year
    
    def resolve_team_name(team_name):
        """Resolve team name using clarifications or existing mappings"""
        # NEW: Clean the team name first (remove rankings, etc.)
        team_name = clean_team_name(team_name)

        original_name = team_name
        team_name = clean_team_name(team_name)
        print(f"DEBUG RESOLVE: Original='{original_name}' Cleaned='{team_name}'")


        # First check if we have a clarification for this session
        if team_clarifications and team_name in team_clarifications:
            print(f"DEBUG RESOLVE: Found in clarifications: {team_name}")
            return team_clarifications[team_name]
        
        # Then check saved mappings
        if team_name in team_mappings:
            print(f"DEBUG RESOLVE: Found in saved mappings: {team_name}")
            return team_mappings[team_name]
        
        # Check if it's a known FBS team
        if team_name in TEAMS:
            print(f"DEBUG RESOLVE: Found '{team_name}' in TEAMS")
            return team_name
            
        # Check common variations
        for standard_name, variants in TEAM_VARIATIONS.items():
            if team_name in variants:
                print(f"DEBUG RESOLVE: Found '{team_name}' maps to '{standard_name}' via TEAM_VARIATIONS")
                return standard_name
        
        # If we get here, it's unknown
        print(f"DEBUG RESOLVE: '{team_name}' is UNKNOWN - adding to unknown_teams")
        unknown_teams.add(team_name)
        return team_name  # Return as-is for now
    
    def parse_date_line(line):
        """Try to parse a date from a line"""
        import re
        
        # Remove common words
        line_clean = re.sub(r'\b(matchup|time|tv|mobile|tickets)\b', '', line, flags=re.IGNORECASE).strip()
        
        # Pattern 1: "Saturday, August 23" or "Saturday, August 23, 2025"
        match = re.search(r'(\w+day),?\s+(\w+)\s+(\d{1,2})(?:,?\s+(\d{4}))?', line_clean, re.IGNORECASE)
        if match:
            day_name, month_name, day_num, year = match.groups()
            year = int(year) if year else current_year
            
            # Convert month name to number
            months = {
                'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
                'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12,
                'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'jun': 6, 'jul': 7, 'aug': 8, 
                'sep': 9, 'sept': 9, 'oct': 10, 'nov': 11, 'dec': 12
            }
            
            month_num = months.get(month_name.lower())
            if month_num:
                try:
                    return datetime(year, month_num, int(day_num)).strftime('%Y-%m-%d')
                except:
                    pass
        
        # Pattern 2: "8/23" or "8/23/25" or "8/23/2025"
        match = re.search(r'(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?', line_clean)
        if match:
            month, day, year = match.groups()
            if year:
                year = int(year)
                if year < 100:  # 2-digit year
                    year += 2000
            else:
                year = current_year
            
            try:
                return datetime(year, int(month), int(day)).strftime('%Y-%m-%d')
            except:
                pass
        
        return None
    
    def extract_time_and_tv(line):
        """Extract time and TV info from game line"""
        import re
        
        time_match = None
        tv_info = None
        
        # Extract time (12:00pm, 6:30pm, etc.)
        time_pattern = r'(\d{1,2}):?(\d{2})?\s*(am|pm|AM|PM)'
        time_search = re.search(time_pattern, line)


        if time_search:
            hour, minute, period = time_search.groups()
            minute = minute or '00'
            time_match = f"{hour}:{minute} {period.upper()}"
        
        # Extract TV networks
        tv_networks = ['ESPN', 'FOX', 'CBS', 'NBC', 'ABC', 'FS1', 'FS2', 'BTN', 'SECN', 'ACCN', 
                      'ESPN2', 'ESPNU', 'CBSSN', 'Paramount+', 'Peacock', 'ESPNEWS']
        
        for network in tv_networks:
            if network.lower() in line.lower():
                tv_info = network
                break
        
        return time_match, tv_info
    
    for i, line in enumerate(lines):
        try:
            # AGGRESSIVE SKIP LOGIC - Add this first
            line_lower = line.lower().strip()
            
            # Skip completely empty or very short lines
            if len(line_lower) < 3:
                continue
            
            # Skip obvious header/table content
            skip_phrases = [
                'matchup time', 'time (et)', 'tv/mobile', 'tickets', 'buy tickets',
                'matchup', 'tv/mobile tickets', 'time (et) tv', 'network', 'channel', 
                'broadcast', 'status', '(et)', 'mobile tickets'
            ]
            
            if any(phrase in line_lower for phrase in skip_phrases):
                print(f"SKIPPING: {line}")
                continue
            
            # Skip lines that are just punctuation or symbols
            if line_lower.replace(' ', '').replace('(', '').replace(')', '').replace('-', '').replace('=', '') == '':
                continue
            
            # Try to parse as date header first
            parsed_date = parse_date_line(line)
            if parsed_date:
                current_date = parsed_date
                continue
            
            # Skip lines that don't have game indicators AND aren't dates
            if not any(indicator in line_lower for indicator in ['vs', 'at', '@']):
                print(f"SKIPPING (no game indicators): {line}")
                continue
                
            game = None
            
            # NEW: Look ahead to next line for time/TV info
            next_line = ""
            if i + 1 < len(lines):
                next_line = lines[i + 1]
                # Check if next line looks like time/TV info
                import re
                if re.search(r'\d{1,2}:?\d{2}?\s*(am|pm|AM|PM)', next_line) or any(net in next_line.upper() for net in ['ESPN', 'FOX', 'CBS', 'NBC']):
                    print(f"DEBUG: Found time line: {next_line}")
                    # Combine current line with next line for parsing
                    combined_line = f"{line} {next_line}"
                    game_time, tv_network = extract_time_and_tv(combined_line)
                else:
                    game_time, tv_network = extract_time_and_tv(line)
            else:
                game_time, tv_network = extract_time_and_tv(line)
            
            print(f"DEBUG: Final extracted - time: {game_time}, tv: {tv_network}")
            
            # Clean the line for team parsing (remove time/TV info)
            import re
            line_clean = re.sub(r'\d{1,2}:?\d{2}?\s*(am|pm|AM|PM)', '', line)  # Remove time
            line_clean = re.sub(r'\b(ESPN|FOX|CBS|NBC|ABC|FS1|FS2|BTN|SECN|ACCN|ESPN2|ESPNU|CBSSN|Paramount\+|Peacock|ESPNEWS)\b', '', line_clean, flags=re.IGNORECASE)  # Remove TV
            line_clean = re.sub(r'\s+', ' ', line_clean).strip()  # Clean up spaces
            
            # Rest of your parsing logic stays the same...
            # Format 1: "Team A vs Team B (location)" - neutral site
            if ' vs ' in line_clean and '(' in line_clean:
                teams_part = line_clean.split('(')[0].strip()
                location = line_clean.split('(')[1].split(')')[0].strip()
                team1, team2 = [t.strip() for t in teams_part.split(' vs ')]
                
                team1_resolved = resolve_team_name(team1)
                team2_resolved = resolve_team_name(team2)
                
                game = {
                    'week': week,
                    'home_team': team1_resolved,
                    'away_team': team2_resolved,
                    'neutral': True,
                    'completed': False,
                    'location_note': location,
                    'original_home': team1,
                    'original_away': team2,
                    'game_date': current_date,
                    'game_time': game_time,
                    'tv_network': tv_network
                }
            
            # Format 2: "Team A at Team B" - Team B is home
            elif ' at ' in line_clean:
                away_team, home_team = [t.strip() for t in line_clean.split(' at ')]
                
                home_resolved = resolve_team_name(home_team)
                away_resolved = resolve_team_name(away_team)
                
                game = {
                    'week': week,
                    'home_team': home_resolved,
                    'away_team': away_resolved,
                    'neutral': False,
                    'completed': False,
                    'original_home': home_team,
                    'original_away': away_team,
                    'game_date': current_date,
                    'game_time': game_time,
                    'tv_network': tv_network
                }
            
            # Format 3: "Team A vs Team B" - Team A is home
            elif ' vs ' in line_clean:
                team1, team2 = [t.strip() for t in line_clean.split(' vs ')]
                
                team1_resolved = resolve_team_name(team1)
                team2_resolved = resolve_team_name(team2)
                
                game = {
                    'week': week,
                    'home_team': team1_resolved,
                    'away_team': team2_resolved,
                    'neutral': False,
                    'completed': False,
                    'original_home': team1,
                    'original_away': team2,
                    'game_date': current_date,
                    'game_time': game_time,
                    'tv_network': tv_network
                }
            
            if game:
                games.append(game)
                
        except Exception as e:
            print(f"Error parsing line '{line}': {e}")
            continue
    
    return games, list(unknown_teams)

def normalize_team_name(team_name):
    """Normalize team names for matching"""
    # Handle common variations
    variations = {
        'Western Kentucky': ['WKU', 'Western Kentucky'],
        'Miami': ['Miami', 'Miami (FL)', 'Miami Florida'],
        'FCS': ['FCS', 'Idaho State']  # Map specific FCS teams to generic FCS
    }
    
    for standard_name, variants in variations.items():
        if team_name in variants:
            return standard_name
    
    return team_name

def find_matching_scheduled_game(home_team, away_team, week):
    """Find a scheduled game that matches the completed game"""
    home_normalized = normalize_team_name(home_team)
    away_normalized = normalize_team_name(away_team)
    
    for i, scheduled in enumerate(scheduled_games):
        if scheduled['week'] != week or scheduled['completed']:
            continue
            
        sched_home = normalize_team_name(scheduled['home_team'])
        sched_away = normalize_team_name(scheduled['away_team'])
        
        # Check both orientations (home/away might be swapped)
        if ((sched_home == home_normalized and sched_away == away_normalized) or
            (sched_home == away_normalized and sched_away == home_normalized)):
            return i
    
    return None

@app.route('/debug_production')
def debug_production():
    """Debug what data exists in production"""
    import os
    
    debug_info = f"""
    <h1>Production Debug Info</h1>
    <p><strong>Current directory:</strong> {os.getcwd()}</p>
    <p><strong>DATA_DIR:</strong> {DATA_DIR}</p>
    <p><strong>DATA_DIR exists:</strong> {os.path.exists(DATA_DIR)}</p>
    
    <h3>Data Files:</h3>
    <p>scheduled_games.json exists: {os.path.exists(os.path.join(DATA_DIR, 'scheduled_games.json'))}</p>
    <p>scheduled_games.json size: {os.path.getsize(os.path.join(DATA_DIR, 'scheduled_games.json')) if os.path.exists(os.path.join(DATA_DIR, 'scheduled_games.json')) else 'N/A'} bytes</p>
    
    <h3>Loaded Data:</h3>
    <p>Scheduled games loaded: {len(scheduled_games)}</p>
    <p>First few scheduled games: {scheduled_games[:3] if scheduled_games else 'None'}</p>
    
    <h3>Directory Contents:</h3>
    """
    
    if os.path.exists(DATA_DIR):
        files = os.listdir(DATA_DIR)
        debug_info += f"<p>Files in DATA_DIR: {files}</p>"
    else:
        debug_info += "<p>DATA_DIR doesn't exist!</p>"
    
    # Check if files have content
    try:
        with open(os.path.join(DATA_DIR, 'scheduled_games.json'), 'r') as f:
            content = f.read()
            debug_info += f"<h3>scheduled_games.json content (first 500 chars):</h3><pre>{content[:500]}</pre>"
    except:
        debug_info += "<p>Could not read scheduled_games.json</p>"
    
    return debug_info
    


@app.route('/compare')
def team_compare():
    """Team comparison page"""
    return render_template('team_compare.html', conferences=CONFERENCES)

@app.route('/team_bowl_status/<team_name>')
def team_bowl_status_detail(team_name):
    """Show detailed bowl eligibility breakdown"""
    status = get_team_bowl_status(team_name)
    if not status:
        return "Team not found"
    
    return render_template_string("""
    <div class="card">
        <div class="card-header">{{ team_name }} Bowl Eligibility</div>
        <div class="card-body">
            <p><strong>Record:</strong> {{ status.total_wins }}-{{ status.losses }}</p>
            <p><strong>Real Wins:</strong> {{ status.real_wins }} (FCS wins don't count)</p>
            {% if status.fcs_wins > 0 %}
                <p><strong>FCS Wins:</strong> {{ status.fcs_wins }} (not counted for bowl eligibility)</p>
            {% endif %}
            
            {% if status.bowl_eligible %}
                <div class="alert alert-success">✅ Bowl Eligible</div>
            {% else %}
                <div class="alert alert-warning">
                    ❌ Not Bowl Eligible<br>
                    Needs {{ status.wins_needed }} more wins against FBS opponents
                </div>
            {% endif %}
        </div>
    </div>
    """, team_name=team_name, status=status)    



# Replace your compare_teams route with this simpler debug version first

@app.route('/compare_teams', methods=['POST'])
def compare_teams():
    """Debug version of team comparison"""
    try:
        team1 = request.form['team1']
        team2 = request.form['team2']
        location = request.form.get('location', 'neutral')
        
        print(f"DEBUG: Form data received - team1: {team1}, team2: {team2}, location: {location}")
        
        if team1 == team2:
            flash('Please select two different teams!', 'error')
            return redirect(url_for('team_compare'))
        
        # Check if teams exist
        if team1 not in team_stats:
            flash(f'{team1} not found in database!', 'error')
            return redirect(url_for('team_compare'))
        
        if team2 not in team_stats:
            flash(f'{team2} not found in database!', 'error') 
            return redirect(url_for('team_compare'))
        
        # Check if teams have played games
        team1_games = len(team_stats[team1]['games'])
        team2_games = len(team_stats[team2]['games'])
        
        print(f"DEBUG: {team1} has {team1_games} games, {team2} has {team2_games} games")
        
        if team1_games == 0:
            flash(f'{team1} has not played any games yet! Please add some games first.', 'error')
            return redirect(url_for('team_compare'))
            
        if team2_games == 0:
            flash(f'{team2} has not played any games yet! Please add some games first.', 'error')
            return redirect(url_for('team_compare'))
        
        # Get basic stats (using your existing functions)
        print("DEBUG: Getting comprehensive stats...")
        team1_stats = calculate_comprehensive_stats(team1)
        team2_stats = calculate_comprehensive_stats(team2)
        
        print("DEBUG: Getting scientific rankings...")
        team1_scientific = calculate_scientific_ranking(team1)
        team2_scientific = calculate_scientific_ranking(team2)
        
        print("DEBUG: Running prediction...")
        # Use your ORIGINAL prediction function for now
        prediction = predict_matchup_enhanced(team1, team2, location)
        
        print("DEBUG: Running additional analysis...")
        # Use your existing analysis functions
        common_opponents = analyze_common_opponents(team1, team2)
        team1_form = calculate_recent_form(team1)
        team2_form = calculate_recent_form(team2)
        style_matchup = analyze_style_matchup(team1, team2)
        h2h_history = head_to_head_history(team1, team2)
        
        print("DEBUG: Preparing template data...")
        comparison_data = {
            'team1': team1,
            'team2': team2,
            'team1_stats': team1_stats,
            'team2_stats': team2_stats,
            'team1_scientific': team1_scientific,
            'team2_scientific': team2_scientific,
            'prediction': prediction,
            'common_opponents': common_opponents,
            'team1_form': team1_form,
            'team2_form': team2_form,
            'style_matchup': style_matchup,
            'h2h_history': h2h_history,
            'location': location
        }
        
        print("DEBUG: Rendering template...")
        # Use your existing template for now
        return render_template('comparison_results.html', **comparison_data)
        
    except Exception as e:
        print(f"ERROR in compare_teams: {e}")
        import traceback
        traceback.print_exc()
        flash(f'Error comparing teams: {str(e)}', 'error')
        return redirect(url_for('team_compare'))

# Also add this simple team preview route
@app.route('/team_preview/<team_name>')
def team_preview(team_name):
    """Simple team preview for comparison page"""
    try:
        if team_name not in team_stats:
            return {'error': 'Team not found'}, 404
        
        stats = calculate_comprehensive_stats(team_name)
        basic_stats = team_stats[team_name]
        recent_form = calculate_recent_form(team_name)
        
        # Get current rank (simplified)
        current_rank = "NR"  # Default to Not Ranked
        
        preview_data = {
            'team': team_name,
            'rank': current_rank,
            'record': f"{basic_stats['wins']}-{basic_stats['losses']}",
            'conference': get_team_conference(team_name),
            'adjusted_total': round(stats['adjusted_total'], 1),
            'recent_form': recent_form['record'],
            'trending': recent_form['trending'],
            'logo_url': get_team_logo_url(team_name)
        }
        
        return preview_data
        
    except Exception as e:
        print(f"ERROR in team_preview: {e}")
        return {'error': str(e)}, 500

@app.route('/ranking_methodology')
def ranking_methodology():
    """Explain how the scientific ranking system works"""
    return render_template('ranking_methodology.html')

@app.route('/manage_rivalries')
@login_required
def manage_rivalries():
    """Admin page to view and manage rivalries"""
    return render_template_string("""
    <html>
    <head><title>Manage Rivalries</title></head>
    <body style="font-family: Arial; margin: 40px;">
        <h1>Rivalry Management</h1>
        
        <h2>Current Rivalries</h2>
        <div style="columns: 3; column-gap: 30px;">
        {% for team, rivals in rivalries.items() %}
            <div style="break-inside: avoid; margin-bottom: 15px;">
                <strong>{{ team }}:</strong><br>
                {% for rival in rivals %}
                    <span style="margin-left: 10px;">• {{ rival }}</span>
                    {% if is_rivalry_tier_1(team, rival) %}
                        <span style="color: red; font-weight: bold;">(Tier 1)</span>
                    {% endif %}
                    <br>
                {% endfor %}
            </div>
        {% endfor %}
        </div>
        
        <h2>Recent Rivalry Games</h2>
        <table style="border-collapse: collapse; width: 100%;">
            <tr style="background: #f0f0f0;">
                <th style="border: 1px solid #ddd; padding: 8px;">Team</th>
                <th style="border: 1px solid #ddd; padding: 8px;">vs</th>
                <th style="border: 1px solid #ddd; padding: 8px;">Result</th>
                <th style="border: 1px solid #ddd; padding: 8px;">Bonus</th>
            </tr>
            {% for game in recent_rivalry_games %}
            <tr>
                <td style="border: 1px solid #ddd; padding: 8px;">{{ game.team }}</td>
                <td style="border: 1px solid #ddd; padding: 8px;">{{ game.opponent }}</td>
                <td style="border: 1px solid #ddd; padding: 8px;">{{ game.result }} {{ game.score }}</td>
                <td style="border: 1px solid #ddd; padding: 8px;">+{{ game.bonus }}</td>
            </tr>
            {% endfor %}
        </table>
        
        <p><a href="/admin">Back to Admin</a></p>
    </body>
    </html>
    """, 
    rivalries=RIVALRIES, 
    recent_rivalry_games=get_recent_rivalry_games(),
    is_rivalry_tier_1=lambda t1, t2: get_rivalry_bonus(t1, t2) >= 1.0)

def get_recent_rivalry_games():
    """Get recent rivalry games for display"""
    rivalry_games = []
    
    for game in games_data[-20:]:  # Last 20 games
        home_team = game['home_team']
        away_team = game['away_team']
        
        if is_rivalry_game(home_team, away_team):
            # Home team perspective
            home_bonus = get_rivalry_bonus(home_team, away_team)
            if game['home_score'] > game['away_score']:
                rivalry_games.append({
                    'team': home_team,
                    'opponent': away_team,
                    'result': 'W',
                    'score': f"{game['home_score']}-{game['away_score']}",
                    'bonus': home_bonus
                })
            else:
                # Away team won
                away_bonus = get_rivalry_bonus(away_team, home_team)
                rivalry_games.append({
                    'team': away_team,
                    'opponent': home_team,
                    'result': 'W',
                    'score': f"{game['away_score']}-{game['home_score']}",
                    'bonus': away_bonus
                })
    
    return rivalry_games

def clean_team_name(team_name):
    """Clean team name by removing ranking numbers and extra formatting"""
    import re
    
    if not team_name:
        return team_name
    
    # Remove common ranking patterns
    patterns_to_remove = [
        r'^\d+\.\s*',           # "1. Alabama"
        r'^\d+\s+',             # "1 Alabama" 
        r'\s+\d+$',             # "Alabama 1"
        r'^\(\d+\)\s*',         # "(1) Alabama"
        r'\s*\(\d+\)$',         # "Alabama (1)"
        r'^#\d+\s+',            # "#1 Alabama"
        r'\s+#\d+$',            # "Alabama #1"
        r'^\d+\)\s*',           # "1) Alabama"
        r'^\d+-\s*',            # "1- Alabama"
    ]
    
    cleaned_name = team_name.strip()
    
    for pattern in patterns_to_remove:
        cleaned_name = re.sub(pattern, '', cleaned_name).strip()
    
    return cleaned_name

@app.route('/create_snapshot', methods=['POST'])
@login_required
def create_snapshot():
    try:
        week_name = request.form.get('week_name', f"Week_{len(historical_rankings) + 1}")
        save_weekly_snapshot(week_name)
        flash(f'Snapshot "{week_name}" created successfully!', 'success')
    except Exception as e:
        flash(f'Error creating snapshot: {e}', 'error')
    
    return redirect(url_for('admin'))

@app.route('/admin')
@login_required
def admin():
    # Create comprehensive stats table for all teams (full data)
    comprehensive_stats = []
    
    # Add all teams from all conferences
    for conf_name, teams in CONFERENCES.items():
        for team in teams:
            stats = calculate_comprehensive_stats(team)
            stats['team'] = team
            stats['conference'] = conf_name
            comprehensive_stats.append(stats)
    
    # Sort by Adjusted Total (highest first)
    comprehensive_stats.sort(key=lambda x: x['adjusted_total'], reverse=True)
    
    return render_template('admin.html', 
                         comprehensive_stats=comprehensive_stats, 
                         recent_games=games_data[-10:],
                         games_data=games_data,
                         historical_rankings=historical_rankings)


@app.route('/cfp_bracket')
def cfp_bracket():
    """Display current CFP bracket projection"""
    bracket = generate_cfp_bracket()
    return render_template('cfp_bracket.html', bracket=bracket)   


@app.route('/public')
@app.route('/')
def public_rankings():
    # Create comprehensive stats table for all teams (same as index)
    comprehensive_stats = []
    
    # Add all teams from all conferences
    for conf_name, teams in CONFERENCES.items():
        for team in teams:
            stats = calculate_comprehensive_stats(team)
            stats['team'] = team
            stats['conference'] = conf_name
            comprehensive_stats.append(stats)
    
    # Sort by Adjusted Total (highest first)
    comprehensive_stats.sort(key=lambda x: x['adjusted_total'], reverse=True)
    
    return render_template('public.html', comprehensive_stats=comprehensive_stats)   

# First, add this simple test route to check if the basic route works:
@app.route('/team_test/<team_name>')
def team_test(team_name):
    """Simple test to see if team detail routing works"""
    if team_name not in team_stats:
        return f"<h1>Team {team_name} not found in team_stats</h1>"
    
    basic_stats = team_stats[team_name]
    return f"""
    <h1>Team Test: {team_name}</h1>
    <p>Games: {len(basic_stats['games'])}</p>
    <p>Record: {basic_stats['wins']}-{basic_stats['losses']}</p>
    <p>Has games data: {len(basic_stats['games']) > 0}</p>
    <p><a href="/team/{team_name}">Try Full Detail Page</a></p>
    """


@app.route('/team/<team_name>')
def public_team_detail(team_name):
    """Public team detail page showing scientific ranking breakdown"""
    if team_name not in team_stats:
        flash('Team not found!', 'error')
        return redirect(url_for('public_rankings'))
    
    # Get scientific ranking breakdown
    scientific_result = calculate_scientific_ranking(team_name)
    basic_stats = team_stats[team_name]
    
   # Get opponent details for context
    opponent_details = []
    for game in basic_stats['games']:
        opponent_quality = get_current_opponent_quality(game['opponent'])
        is_rival = is_rivalry_game(team_name, game['opponent'])
        rivalry_bonus = get_rivalry_bonus(team_name, game['opponent']) if is_rival else 0
        
        opponent_details.append({
            'opponent': game['opponent'],
            'opponent_quality': round(opponent_quality, 1),
            'result': game['result'],
            'team_score': game['team_score'],
            'opp_score': game['opp_score'],
            'margin': game['team_score'] - game['opp_score'],
            'location': game['home_away'],
            'is_rivalry': is_rival,
            'rivalry_bonus': rivalry_bonus,
            'overtime': game.get('overtime', False)  # NEW: Include overtime status
        })
    
    # Calculate current ranking
    all_teams = []
    for conf_name, teams in CONFERENCES.items():
        for team in teams:
            if team_stats[team]['wins'] + team_stats[team]['losses'] > 0:
                stats = calculate_comprehensive_stats(team)
                all_teams.append({
                    'team': team,
                    'adjusted_total': stats['adjusted_total']
                })
    
    all_teams.sort(key=lambda x: x['adjusted_total'], reverse=True)
    current_rank = next((i+1 for i, team in enumerate(all_teams) if team['team'] == team_name), 'NR')
    
    template_data = {
        'team_name': team_name,
        'conference': get_team_conference(team_name),
        'current_rank': current_rank,
        'record': f"{basic_stats['wins']}-{basic_stats['losses']}",
        'scientific_result': scientific_result,
        'opponent_details': opponent_details,
        'total_teams_ranked': len(all_teams)
    }
    
    return render_template('public_team_detail.html', **template_data)


@app.route('/')
def index():
    # Create comprehensive stats table for all teams
    comprehensive_stats = []
    
    # Add all teams from all conferences
    for conf_name, teams in CONFERENCES.items():
        for team in teams:
            stats = calculate_comprehensive_stats(team)
            stats['team'] = team
            stats['conference'] = conf_name
            comprehensive_stats.append(stats)
    
    # Sort by Adjusted Total (highest first)
    comprehensive_stats.sort(key=lambda x: x['adjusted_total'], reverse=True)
    
    return render_template('index.html', comprehensive_stats=comprehensive_stats, recent_games=games_data[-10:])

@app.route('/import_schedule', methods=['POST'])
@login_required
def import_schedule():
    """Import schedule from pasted text - with team clarification"""
    print("DEBUG: import_schedule route was called!")  # Add this line first
    try:
        schedule_text = request.form.get('schedule_text', '').strip()
        week = request.form.get('week', '')
        print(f"DEBUG: schedule_text length: {len(schedule_text)}")  # Add this too
        print(f"DEBUG: week: {week}")  # And this
        
        if not schedule_text or not week:
            flash('Please provide both schedule text and week!', 'error')
            return redirect(url_for('weekly_results', week=week))
        
        result = parse_schedule_text(schedule_text, week)
        print(f"DEBUG: parse_schedule_text returned: {result}")
        print(f"DEBUG: type of result: {type(result)}")
        print(f"DEBUG: length of result: {len(result) if hasattr(result, '__len__') else 'No length'}")
        
        # Try to unpack and see what happens
        try:
            games, unknown_teams = result
            print(f"DEBUG: Successfully unpacked. Games: {len(games)}, Unknown teams: {unknown_teams}")
        except Exception as e:
            print(f"DEBUG: Unpacking failed: {e}")
            return redirect(url_for('weekly_results', week=week))
        
        if not games:
            flash('No games could be parsed from the text. Please check the format.', 'error')
            return redirect(url_for('weekly_results', week=week))
        
        # If we have unknown teams, go to clarification
        if unknown_teams:
            # Store the original text and week in session for clarification
            session['pending_schedule'] = {
                'schedule_text': schedule_text,
                'week': week,
                'unknown_teams': unknown_teams
            }
            return redirect(url_for('clarify_teams'))
        
        # No unknown teams - proceed with import
        return complete_schedule_import(games, week)
        
    except Exception as e:
        flash(f'Error importing schedule: {e}', 'error')
        return redirect(url_for('weekly_results', week=week))

def complete_schedule_import(games, week):
    """Complete the schedule import after clarifications"""
    try:
        global scheduled_games
        
        # Check if there are existing scheduled games for this week
        existing_games = [g for g in scheduled_games if g['week'] == week and not g.get('completed', False)]
        
        if existing_games:
            # User is importing additional games for a week that already has scheduled games
            # For now, we'll append (add) rather than replace
            flash(f'ℹ️ Adding {len(games)} more games to Week {week} (you already had {len(existing_games)} scheduled games)', 'info')
            
            # Just add the new games without removing existing ones
            scheduled_games.extend(games)
        else:
            # No existing games for this week, or only completed games
            # Remove any old scheduled games for this week (but keep completed ones)
            scheduled_games = [g for g in scheduled_games if g['week'] != week or g.get('completed', False)]
            
            # Add new scheduled games
            scheduled_games.extend(games)
        
        # Save to file
        save_scheduled_games()
        
        total_scheduled = len([g for g in scheduled_games if g['week'] == week and not g.get('completed', False)])
        flash(f'✅ Successfully imported {len(games)} games for Week {week}! (Total scheduled: {total_scheduled})', 'success')
        return redirect(url_for('weekly_results', week=week))
        
    except Exception as e:
        flash(f'Error completing import: {e}', 'error')
        return redirect(url_for('weekly_results', week=week))


@app.route('/clarify_teams')
@login_required
def clarify_teams():
    """Show team clarification page"""
    pending = session.get('pending_schedule')
    if not pending:
        flash('No pending schedule to clarify!', 'error')
        return redirect(url_for('weekly_results'))
    
    unknown_teams = pending['unknown_teams']
    team_suggestions = {}
    team_contexts = {}
    
    # Parse the schedule to get game contexts
    lines = [line.strip() for line in pending['schedule_text'].split('\n') if line.strip()]
    
    # Find which games each unknown team appears in
    for unknown_team in unknown_teams:
        team_contexts[unknown_team] = []
        for line in lines:
            if unknown_team.lower() in line.lower() and any(indicator in line.lower() for indicator in ['vs', 'at', '@']):
                team_contexts[unknown_team].append(line.strip())
    
    # Get suggestions for each unknown team
    for team in unknown_teams:
        team_suggestions[team] = get_team_suggestions(team)
    
    return render_template('clarify_teams.html', 
                         unknown_teams=unknown_teams,
                         team_suggestions=team_suggestions,
                         team_contexts=team_contexts,
                         week=pending['week'])

@app.route('/process_clarifications', methods=['POST'])
@login_required
def process_clarifications():
    """Process team clarifications and complete import"""
    try:
        pending = session.get('pending_schedule')
        if not pending:
            flash('No pending schedule to process!', 'error')
            return redirect(url_for('weekly_results'))
        
        # Get clarifications from form
        clarifications = {}
        for unknown_team in pending['unknown_teams']:
            clarification_type = request.form.get(f'type_{unknown_team}')
            
            if clarification_type == 'fcs':
                clarifications[unknown_team] = 'FCS'
            elif clarification_type == 'map':
                mapped_team = request.form.get(f'map_{unknown_team}')
                if mapped_team and mapped_team in TEAMS:
                    clarifications[unknown_team] = mapped_team
                else:
                    flash(f'Invalid mapping for {unknown_team}', 'error')
                    return redirect(url_for('clarify_teams'))
            elif clarification_type == 'custom':
                custom_name = request.form.get(f'custom_{unknown_team}', '').strip()
                if custom_name:
                    clarifications[unknown_team] = custom_name
                else:
                    flash(f'Please provide a custom name for {unknown_team}', 'error')
                    return redirect(url_for('clarify_teams'))
        
        # Save mappings for future use
        global team_mappings
        for original, mapped in clarifications.items():
            team_mappings[original] = mapped
        save_team_mappings()
        
        # Re-parse with clarifications
        games, _ = parse_schedule_text(pending['schedule_text'], pending['week'], clarifications)
        
        # Clear pending schedule from session
        session.pop('pending_schedule', None)
        
        # Complete the import
        return complete_schedule_import(games, pending['week'])
        
    except Exception as e:
        flash(f'Error processing clarifications: {e}', 'error')
        return redirect(url_for('clarify_teams'))

@app.route('/weekly_results')
@app.route('/weekly_results/<week>')
def weekly_results(week=None):
    # Get all unique weeks from games data
    weeks_with_games = sorted(set(game['week'] for game in games_data), key=lambda x: (
        # Sort by numeric value if it's a number, otherwise by string
        int(x) if x.isdigit() else (100 if x == 'Bowls' else 101 if x == 'CFP' else 999)
    ))
    
    # If no week specified, default to the most recent week with games
    if not week and weeks_with_games:
        week = weeks_with_games[-1]
    elif not week:
        week = '1'  # Default to week 1 if no games exist
    
    # Get scheduled games for the selected week that haven't been completed
    week_scheduled = [game for game in scheduled_games 
                     if game['week'] == week and not game.get('completed', False)]
    
    # Sort scheduled games by date and time
    def sort_key(game):
        game_date = game.get('game_date', '9999-12-31')
        game_time = game.get('game_time', '11:59 PM')
        
        try:
            if game_time:
                from datetime import datetime
                time_obj = datetime.strptime(game_time, '%I:%M %p')
                time_24h = time_obj.strftime('%H:%M')
            else:
                time_24h = '23:59'
        except:
            time_24h = '23:59'
        
        return f"{game_date} {time_24h}"
    
    week_scheduled.sort(key=sort_key)
    
    # Group scheduled games by date
    scheduled_by_date = {}
    for game in week_scheduled:
        game_date = game.get('game_date')
        if game_date:
            if game_date not in scheduled_by_date:
                scheduled_by_date[game_date] = []
            scheduled_by_date[game_date].append(game)
        else:
            # Games without dates go in a "TBD" group
            if 'No Date' not in scheduled_by_date:
                scheduled_by_date['No Date'] = []
            scheduled_by_date['No Date'].append(game)
    
    # Also group completed games by date
    week_games = [game for game in games_data if game['week'] == week]
    completed_by_date = {}
    
    for game in week_games:
        # Try to find corresponding scheduled game to get date
        game_date = None
        for scheduled in scheduled_games:
            if (scheduled['week'] == week and 
                ((scheduled['home_team'] == game['home_team'] and scheduled['away_team'] == game['away_team']) or
                 (scheduled['home_team'] == game['away_team'] and scheduled['away_team'] == game['home_team']))):
                game_date = scheduled.get('game_date')
                break
        
        if not game_date:
            game_date = 'No Date'
            
        if game_date not in completed_by_date:
            completed_by_date[game_date] = []
        completed_by_date[game_date].append(game)
    
    # Sort dates for display
    all_dates = set(list(scheduled_by_date.keys()) + list(completed_by_date.keys()))
    if 'No Date' in all_dates:
        all_dates.remove('No Date')
        sorted_dates = sorted([d for d in all_dates if d != 'No Date']) + ['No Date']
    else:
        sorted_dates = sorted(all_dates)
    
    return render_template('weekly_results.html', 
                         selected_week=week, 
                         weeks_with_games=weeks_with_games,
                         week_games=week_games,
                         scheduled_games=week_scheduled,
                         scheduled_by_date=scheduled_by_date,
                         completed_by_date=completed_by_date,
                         sorted_dates=sorted_dates,
                         all_weeks=WEEKS)       


@app.route('/add_game', methods=['GET', 'POST'])
@login_required
def add_game():
    if request.method == 'POST':
        try:
            # Get form data - ADDED overtime field
            week = request.form['week']
            home_team = request.form['home_team']
            away_team = request.form['away_team']
            home_score = int(request.form['home_score'])
            away_score = int(request.form['away_score'])
            is_neutral_site = 'neutral_site' in request.form
            is_overtime = 'overtime' in request.form  # NEW: Check for overtime
            
            # Validate that teams are different
            if home_team == away_team:
                flash('Teams must be different!', 'error')
                return redirect(url_for('add_game', selected_week=week))
            
            # FCS warning check
            if is_fcs_opponent(home_team) or is_fcs_opponent(away_team):
                flash('⚠️ FCS game detected - minimal ranking credit will be awarded for this victory', 'warning')
            
            # Add game to data - ADDED overtime field
            game = {
                'week': week,
                'home_team': home_team,
                'away_team': away_team,
                'home_score': home_score,
                'away_score': away_score,
                'is_neutral_site': is_neutral_site,
                'overtime': is_overtime,  # NEW: Store overtime status
                'date_added': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            games_data.append(game)
            
            # NEW: Check if this matches a scheduled game and mark it as completed
            match_index = find_matching_scheduled_game(home_team, away_team, week)
            if match_index is not None:
                scheduled_games[match_index]['completed'] = True
                save_scheduled_games()


            # Update team statistics - SIMPLIFIED (no game types needed)
            update_team_stats_simplified(home_team, away_team, home_score, away_score, True, is_neutral_site, is_overtime)
            update_team_stats_simplified(away_team, home_team, away_score, home_score, False, is_neutral_site, is_overtime)
            
            # Save data after adding game
            save_data()

            # Remember the selected week for next time
            session['last_selected_week'] = week
            
            location_text = " (Neutral Site)" if is_neutral_site else ""
            overtime_text = " (OT)" if is_overtime else ""
            scheduled_text = " ✓ Scheduled" if match_index is not None else ""
            flash(f'Game added: {home_team} {home_score} - {away_score} {away_team}{location_text}{overtime_text}', 'success')
            return redirect(url_for('add_game'))
            
        except ValueError:
            flash('Please enter valid scores (numbers only)', 'error')
            return redirect(url_for('add_game'))
    
    # GET request - render the form
    selected_week = request.args.get('selected_week') or session.get('last_selected_week', '')
    return render_template('add_game.html', 
                         conferences=CONFERENCES, 
                         weeks=WEEKS, 
                         recent_games=games_data[-10:], 
                         selected_week=selected_week)


def is_fcs_opponent(opponent_name):
    """Check if opponent is FCS"""
    return opponent_name == 'FCS' or opponent_name.upper() == 'FCS'


def save_team_mappings():
    """Save team mappings to JSON file"""
    try:
        mappings_file = os.path.join(DATA_DIR, 'team_mappings.json')
        with open(mappings_file, 'w') as f:
            json.dump(team_mappings, f, indent=2)
    except Exception as e:
        print(f"Error saving team mappings: {e}")

def load_team_mappings():
    """Load team mappings from JSON file"""
    global team_mappings
    try:
        mappings_file = os.path.join(DATA_DIR, 'team_mappings.json')
        with open(mappings_file, 'r') as f:
            team_mappings = json.load(f)
        print(f"Loaded {len(team_mappings)} team mappings")
    except FileNotFoundError:
        print("No team mappings file found, starting fresh")
        team_mappings = {}
    except Exception as e:
        print(f"Error loading team mappings: {e}")
        team_mappings = {}

def get_team_suggestions(unknown_team):
    """Get suggestions for unknown team names with variations check"""
    suggestions = []
    unknown_lower = unknown_team.lower().strip()
    
    # Remove common punctuation that might interfere
    unknown_clean = unknown_lower.replace('"', '').replace('(', '').replace(')', '').replace('.', '')
    
    # First, check if the unknown team is a variation of any official team
    variations = {
        # Your full variations dictionary goes here - copy from the previous artifact
        'Alabama': ['Alabama', 'Bama', 'Crimson Tide'],
        'Arkansas': ['Arkansas', 'Ark', 'Razorbacks'],
        'Auburn': ['Auburn', 'Tigers'],
        'Florida': ['Florida', 'UF', 'Gators'],
        'Georgia': ['Georgia', 'UGA', 'Bulldogs'],
        'Kentucky': ['Kentucky', 'UK', 'Wildcats'],
        'LSU': ['LSU', 'Louisiana State', 'Tigers'],
        'Mississippi State': ['Mississippi State', 'MSU', 'Miss State', 'Bulldogs'],
        'Missouri': ['Missouri', 'Mizzou', 'Tigers'],
        'Oklahoma': ['Oklahoma', 'OU', 'Sooners'],
        'Ole Miss': ['Ole Miss', 'Mississippi', 'Rebels'],
        'South Carolina': ['South Carolina', 'Gamecocks'],
        'Tennessee': ['Tennessee', 'Tenn', 'UT', 'Volunteers', 'Vols'],
        'Texas': ['Texas', 'UT', 'Longhorns'],
        'Texas A&M': ['Texas A&M', 'TAMU', 'A&M', 'Aggies', 'Texas AM'],
        'Vanderbilt': ['Vanderbilt', 'Vandy', 'Commodores'],
        'Illinois': ['Illinois', 'Illini', 'Fighting Illini'],
        'Indiana': ['Indiana', 'IU', 'Hoosiers'],
        'Iowa': ['Iowa', 'Hawkeyes'],
        'Maryland': ['Maryland', 'UMD', 'Terrapins', 'Terps'],
        'Michigan': ['Michigan', 'UM', 'Wolverines'],
        'Michigan State': ['Michigan State', 'MSU', 'Mich State', 'Spartans'],
        'Minnesota': ['Minnesota', 'Gophers', 'Golden Gophers'],
        'Nebraska': ['Nebraska', 'Huskers', 'Cornhuskers'],
        'Northwestern': ['Northwestern', 'NU', 'Wildcats'],
        'Ohio State': ['Ohio State', 'OSU', 'tOSU', 'Buckeyes'],
        'Oregon': ['Oregon', 'Ducks'],
        'Penn State': ['Penn State', 'PSU', 'Nittany Lions'],
        'Purdue': ['Purdue', 'Boilermakers'],
        'Rutgers': ['Rutgers', 'RU', 'Scarlet Knights'],
        'UCLA': ['UCLA', 'Bruins'],
        'USC': ['USC', 'Southern Cal', 'Southern California', 'Trojans'],
        'Washington': ['Washington', 'UW', 'Huskies'],
        'Wisconsin': ['Wisconsin', 'Badgers'],
        'Boston College': ['Boston College', 'BC', 'Eagles'],
        'California': ['California', 'Cal', 'Berkeley', 'Golden Bears'],
        'Clemson': ['Clemson', 'Tigers'],
        'Duke': ['Duke', 'Blue Devils'],
        'Florida State': ['Florida State', 'FSU', 'Seminoles'],
        'Georgia Tech': ['Georgia Tech', 'GT', 'Yellow Jackets'],
        'Louisville': ['Louisville', 'Cards', 'Cardinals'],
        'Miami': ['Miami', 'UM', 'Miami (FL)', 'Miami Florida', 'Miami FL', 'Hurricanes', 'The U'],
        'NC State': ['NC State', 'North Carolina State', 'NCSU', 'Wolfpack'],
        'North Carolina': ['North Carolina', 'UNC', 'Tar Heels', 'Carolina'],
        'Pittsburgh': ['Pittsburgh', 'Pitt', 'Panthers'],
        'SMU': ['SMU', 'Southern Methodist', 'Mustangs'],
        'Stanford': ['Stanford', 'Cardinal'],
        'Syracuse': ['Syracuse', 'Cuse', 'Orange'],
        'Virginia': ['Virginia', 'UVA', 'Cavaliers'],
        'Virginia Tech': ['Virginia Tech', 'VT', 'Hokies'],
        'Wake Forest': ['Wake Forest', 'Wake', 'Demon Deacons'],
        'Arizona': ['Arizona', 'Wildcats'],
        'Arizona State': ['Arizona State', 'ASU', 'Sun Devils'],
        'Baylor': ['Baylor', 'Bears'],
        'BYU': ['BYU', 'Brigham Young', 'Cougars'],
        'Cincinnati': ['Cincinnati', 'UC', 'Bearcats'],
        'Colorado': ['Colorado', 'CU', 'Buffaloes', 'Buffs'],
        'Houston': ['Houston', 'UH', 'Cougars'],
        'Iowa State': ['Iowa State', 'ISU', 'Cyclones'],
        'Kansas': ['Kansas', 'KU', 'Jayhawks'],
        'Kansas State': ['Kansas State', 'KSU', 'K-State', 'Wildcats'],
        'Oklahoma State': ['Oklahoma State', 'OSU', 'Cowboys'],
        'TCU': ['TCU', 'Texas Christian', 'Horned Frogs'],
        'Texas Tech': ['Texas Tech', 'TTU', 'Red Raiders'],
        'UCF': ['UCF', 'Central Florida', 'Knights'],
        'Utah': ['Utah', 'Utes'],
        'West Virginia': ['West Virginia', 'WVU', 'Mountaineers'],
        'Oregon State': ['Oregon State', 'OSU', 'Beavers'],
        'Washington State': ['Washington State', 'WSU', 'Cougars'],
        'South Florida': ['South Florida', 'USF', 'Bulls'],
        'UL Monroe': ['UL Monroe', 'ULM', 'Louisiana Monroe', 'Warhawks'],
        'Miami (OH)': ['Miami (OH)', 'Miami Ohio', 'Miami "Ohio"', 'Miami (Ohio)', 'RedHawks'],
        'Western Kentucky': ['Western Kentucky', 'WKU', 'Hilltoppers'],
        'Florida Intl': ['Florida Intl', 'FIU', 'Florida International', 'Panthers'],
        'UCF': ['UCF', 'Central Florida', 'Knights'],
        'TCU': ['TCU', 'Texas Christian', 'Horned Frogs'],
        'LSU': ['LSU', 'Louisiana State', 'Tigers'],
        'BYU': ['BYU', 'Brigham Young', 'Cougars'],
        'SMU': ['SMU', 'Southern Methodist', 'Mustangs'],
        'Texas A&M': ['Texas A&M', 'TAMU', 'A&M', 'Aggies', 'Texas AM'],
    }
    
    # Check variations dictionary - PRIORITY CHECK
    for official_name, variant_list in variations.items():
        for variant in variant_list:
            if unknown_clean == variant.lower():
                suggestions.insert(0, official_name)  # Put exact matches first
                break
            elif unknown_clean in variant.lower() or variant.lower() in unknown_clean:
                suggestions.append(official_name)
    
    # Then look for partial matches in known teams (original logic)
    for team in TEAMS:
        team_lower = team.lower()
        
        # Skip if we already found this team through variations
        if team in suggestions:
            continue
            
        # Contains match (either direction)
        if unknown_clean in team_lower or team_lower in unknown_clean:
            suggestions.append(team)
            continue
            
        # Word-by-word matching for multi-word teams
        unknown_words = unknown_clean.split()
        team_words = team_lower.split()
        
        # Check if any significant words match
        if len(unknown_words) > 0 and len(team_words) > 0:
            word_matches = 0
            for u_word in unknown_words:
                if len(u_word) > 2:  # Only check meaningful words
                    for t_word in team_words:
                        if u_word in t_word or t_word in u_word:
                            word_matches += 1
                            break
            
            # If we matched a good portion of words, suggest it
            if word_matches >= min(len(unknown_words), len(team_words)) * 0.7:
                suggestions.append(team)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_suggestions = []
    for suggestion in suggestions:
        if suggestion not in seen:
            seen.add(suggestion)
            unique_suggestions.append(suggestion)
    
    # Limit to top 5 suggestions
    return unique_suggestions[:5]

def normalize_team_name(team_name):
    """Normalize team names for matching"""
    # Handle common variations
    variations = {
            # SEC
            'Alabama': ['Alabama', 'Bama', 'Crimson Tide'],
            'Arkansas': ['Arkansas', 'Ark', 'Razorbacks'],
            'Auburn': ['Auburn', 'Tigers'],
            'Florida': ['Florida', 'UF', 'Gators'],
            'Georgia': ['Georgia', 'UGA', 'Bulldogs'],
            'Kentucky': ['Kentucky', 'UK', 'Wildcats'],
            'LSU': ['LSU', 'Louisiana State', 'Tigers'],
            'Mississippi State': ['Mississippi State', 'MSU', 'Miss State', 'Bulldogs'],
            'Missouri': ['Missouri', 'Mizzou', 'Tigers'],
            'Oklahoma': ['Oklahoma', 'OU', 'Sooners'],
            'Ole Miss': ['Ole Miss', 'Mississippi', 'Rebels'],
            'South Carolina': ['South Carolina', 'Gamecocks'],
            'Tennessee': ['Tennessee', 'Tenn', 'UT', 'Volunteers', 'Vols'],
            'Texas': ['Texas', 'UT', 'Longhorns'],
            'Texas A&M': ['Texas A&M', 'TAMU', 'A&M', 'Aggies', 'Texas AM'],
            'Vanderbilt': ['Vanderbilt', 'Vandy', 'Commodores'],

            # Big Ten
            'Illinois': ['Illinois', 'Illini', 'Fighting Illini'],
            'Indiana': ['Indiana', 'IU', 'Hoosiers'],
            'Iowa': ['Iowa', 'Hawkeyes'],
            'Maryland': ['Maryland', 'UMD', 'Terrapins', 'Terps'],
            'Michigan': ['Michigan', 'UM', 'Wolverines'],
            'Michigan State': ['Michigan State', 'MSU', 'Mich State', 'Spartans'],
            'Minnesota': ['Minnesota', 'Gophers', 'Golden Gophers'],
            'Nebraska': ['Nebraska', 'Huskers', 'Cornhuskers'],
            'Northwestern': ['Northwestern', 'NU', 'Wildcats'],
            'Ohio State': ['Ohio State', 'OSU', 'tOSU', 'Buckeyes'],
            'Oregon': ['Oregon', 'Ducks'],
            'Penn State': ['Penn State', 'PSU', 'Nittany Lions'],
            'Purdue': ['Purdue', 'Boilermakers'],
            'Rutgers': ['Rutgers', 'RU', 'Scarlet Knights'],
            'UCLA': ['UCLA', 'Bruins'],
            'USC': ['USC', 'Southern Cal', 'Southern California', 'Trojans'],
            'Washington': ['Washington', 'UW', 'Huskies'],
            'Wisconsin': ['Wisconsin', 'Badgers'],

            # ACC
            'Boston College': ['Boston College', 'BC', 'Eagles'],
            'California': ['California', 'Cal', 'Berkeley', 'Golden Bears'],
            'Clemson': ['Clemson', 'Tigers'],
            'Duke': ['Duke', 'Blue Devils'],
            'Florida State': ['Florida State', 'FSU', 'Seminoles'],
            'Georgia Tech': ['Georgia Tech', 'GT', 'Yellow Jackets'],
            'Louisville': ['Louisville', 'Cards', 'Cardinals'],
            'Miami': ['Miami', 'UM', 'Miami (FL)', 'Miami Florida', 'Miami FL', 'Hurricanes', 'The U'],
            'NC State': ['NC State', 'North Carolina State', 'NCSU', 'Wolfpack'],
            'North Carolina': ['North Carolina', 'UNC', 'Tar Heels', 'Carolina'],
            'Pittsburgh': ['Pittsburgh', 'Pitt', 'Panthers'],
            'SMU': ['SMU', 'Southern Methodist', 'Mustangs'],
            'Stanford': ['Stanford', 'Cardinal'],
            'Syracuse': ['Syracuse', 'Cuse', 'Orange'],
            'Virginia': ['Virginia', 'UVA', 'Cavaliers'],
            'Virginia Tech': ['Virginia Tech', 'VT', 'Hokies'],
            'Wake Forest': ['Wake Forest', 'Wake', 'Demon Deacons'],

            # Big 12
            'Arizona': ['Arizona', 'Wildcats'],
            'Arizona State': ['Arizona State', 'ASU', 'Sun Devils'],
            'Baylor': ['Baylor', 'Bears'],
            'BYU': ['BYU', 'Brigham Young', 'Cougars'],
            'Cincinnati': ['Cincinnati', 'UC', 'Bearcats'],
            'Colorado': ['Colorado', 'CU', 'Buffaloes', 'Buffs'],
            'Houston': ['Houston', 'UH', 'Cougars'],
            'Iowa State': ['Iowa State', 'ISU', 'Cyclones'],
            'Kansas': ['Kansas', 'KU', 'Jayhawks'],
            'Kansas State': ['Kansas State', 'KSU', 'K-State', 'Wildcats'],
            'Oklahoma State': ['Oklahoma State', 'OSU', 'Cowboys'],
            'TCU': ['TCU', 'Texas Christian', 'Horned Frogs'],
            'Texas Tech': ['Texas Tech', 'TTU', 'Red Raiders'],
            'UCF': ['UCF', 'Central Florida', 'Knights'],
            'Utah': ['Utah', 'Utes'],
            'West Virginia': ['West Virginia', 'WVU', 'Mountaineers'],

            # Pac-12 (remaining)
            'Oregon State': ['Oregon State', 'OSU', 'Beavers'],
            'Washington State': ['Washington State', 'WSU', 'Cougars'],

            # American Athletic Conference
            'Army': ['Army', 'Black Knights'],
            'Charlotte': ['Charlotte', '49ers'],
            'East Carolina': ['East Carolina', 'ECU', 'Pirates'],
            'Florida Atlantic': ['Florida Atlantic', 'FAU', 'Owls'],
            'Memphis': ['Memphis', 'Tigers'],
            'Navy': ['Navy', 'Midshipmen'],
            'North Texas': ['North Texas', 'UNT', 'Mean Green'],
            'Rice': ['Rice', 'Owls'],
            'South Florida': ['South Florida', 'USF', 'Bulls'],
            'Temple': ['Temple', 'Owls'],
            'Tulane': ['Tulane', 'Green Wave'],
            'Tulsa': ['Tulsa', 'Golden Hurricane'],
            'UAB': ['UAB', 'Alabama Birmingham', 'Blazers'],
            'UTSA': ['UTSA', 'Texas San Antonio', 'Roadrunners'],

            # Conference USA
            'Delaware': ['Delaware', 'Blue Hens'],
            'Florida Intl': ['Florida Intl', 'FIU', 'Florida International', 'Panthers'],
            'Jacksonville State': ['Jacksonville State', 'JSU', 'Gamecocks'],
            'Kennesaw State': ['Kennesaw State', 'Owls'],
            'LA Tech': ['LA Tech', 'Louisiana Tech', 'Bulldogs'],
            'Liberty': ['Liberty', 'Flames'],
            'Middle Tennessee': ['Middle Tennessee', 'MTSU', 'Blue Raiders'],
            'Missouri State': ['Missouri State', 'Bears'],
            'New Mexico St': ['New Mexico St', 'New Mexico State', 'NMSU', 'Aggies'],
            'Sam Houston': ['Sam Houston', 'Sam Houston State', 'SHSU', 'Bearkats'],
            'UTEP': ['UTEP', 'Texas El Paso', 'Miners'],
            'Western Kentucky': ['Western Kentucky', 'WKU', 'Hilltoppers'],

            # MAC
            'Akron': ['Akron', 'Zips'],
            'Ball State': ['Ball State', 'Cardinals'],
            'Bowling Green': ['Bowling Green', 'BGSU', 'Falcons'],
            'Buffalo': ['Buffalo', 'Bulls'],
            'Central Michigan': ['Central Michigan', 'CMU', 'Chippewas'],
            'Eastern Michigan': ['Eastern Michigan', 'EMU', 'Eagles'],
            'Kent State': ['Kent State', 'Golden Flashes'],
            'UMass': ['UMass', 'Massachusetts', 'Minutemen'],
            'Miami (OH)': ['Miami (OH)', 'Miami Ohio', 'Miami "Ohio"', 'Miami (Ohio)', 'RedHawks'],
            'Northern Illinois': ['Northern Illinois', 'NIU', 'Huskies'],
            'Ohio': ['Ohio', 'Bobcats'],
            'Toledo': ['Toledo', 'Rockets'],
            'Western Michigan': ['Western Michigan', 'WMU', 'Broncos'],

            # Mountain West
            'Air Force': ['Air Force', 'Falcons'],
            'Boise State': ['Boise State', 'Broncos'],
            'Colorado State': ['Colorado State', 'CSU', 'Rams'],
            'Fresno State': ['Fresno State', 'Bulldogs'],
            'Hawaii': ['Hawaii', 'Rainbow Warriors'],
            'Nevada': ['Nevada', 'Wolf Pack'],
            'New Mexico': ['New Mexico', 'UNM', 'Lobos'],
            'San Diego State': ['San Diego State', 'SDSU', 'Aztecs'],
            'San Jose State': ['San Jose State', 'SJSU', 'Spartans'],
            'UNLV': ['UNLV', 'Rebels'],
            'Utah State': ['Utah State', 'USU', 'Aggies'],
            'Wyoming': ['Wyoming', 'Cowboys'],

            # Sun Belt
            'Appalachian St': ['Appalachian St', 'Appalachian State', 'App State', 'Mountaineers'],
            'Arkansas State': ['Arkansas State', 'A-State', 'Red Wolves'],
            'Coastal Carolina': ['Coastal Carolina', 'Chanticleers'],
            'Georgia Southern': ['Georgia Southern', 'Eagles'],
            'Georgia State': ['Georgia State', 'Panthers'],
            'James Madison': ['James Madison', 'JMU', 'Dukes'],
            'UL Monroe': ['UL Monroe', 'ULM', 'Louisiana Monroe', 'Warhawks'],
            'Louisiana': ['Louisiana', 'UL', 'Ragin Cajuns', 'Louisiana Lafayette'],
            'Marshall': ['Marshall', 'Thundering Herd'],
            'Old Dominion': ['Old Dominion', 'ODU', 'Monarchs'],
            'South Alabama': ['South Alabama', 'USA', 'Jaguars'],
            'Southern Miss': ['Southern Miss', 'Southern Mississippi', 'USM', 'Golden Eagles'],
            'Texas State': ['Texas State', 'Bobcats'],
            'Troy': ['Troy', 'Trojans'],

            # Independents
            'Connecticut': ['Connecticut', 'UConn', 'Huskies'],
            'Notre Dame': ['Notre Dame', 'ND', 'Fighting Irish'],
        }
    
    for standard_name, variants in variations.items():
        if team_name in variants:
            return standard_name
    
    return team_name

def find_matching_scheduled_game(home_team, away_team, week):
    """Find a scheduled game that matches the completed game"""
    home_normalized = normalize_team_name(home_team)
    away_normalized = normalize_team_name(away_team)
    
    for i, scheduled in enumerate(scheduled_games):
        if scheduled['week'] != week or scheduled['completed']:
            continue
            
        sched_home = normalize_team_name(scheduled['home_team'])
        sched_away = normalize_team_name(scheduled['away_team'])
        
        # Check both orientations (home/away might be swapped)
        if ((sched_home == home_normalized and sched_away == away_normalized) or
            (sched_home == away_normalized and sched_away == home_normalized)):
            return i
    
    return None


@app.route('/analyze_fcs_games')
@login_required
def analyze_fcs_games():
    """Analyze all FCS games and their impact"""
    fcs_games = []
    
    for game in games_data:
        home_team = game['home_team']
        away_team = game['away_team']
        
        if is_fcs_opponent(home_team) or is_fcs_opponent(away_team):
            # Determine which team beat FCS
            if is_fcs_opponent(away_team):  # Home team beat FCS
                winner = home_team
                winner_score = game['home_score']
                loser_score = game['away_score']
            else:  # Away team beat FCS
                winner = away_team
                winner_score = game['away_score'] 
                loser_score = game['home_score']
            
            # Calculate victory value for this FCS win
            mock_game = {
                'result': 'W',
                'opponent': 'FCS',
                'team_score': winner_score,
                'opp_score': loser_score,
                'home_away': 'Home' if winner == home_team else 'Away'
            }
            victory_value = calculate_victory_value_with_rivalry(mock_game, winner)
            
            fcs_games.append({
                'week': game['week'],
                'winner': winner,
                'score': f"{winner_score}-{loser_score}",
                'margin': winner_score - loser_score,
                'victory_value': victory_value
            })
    
    return render_template_string("""
    <html>
    <head><title>FCS Games Analysis</title></head>
    <body style="font-family: Arial; margin: 40px;">
        <h1>FCS Games Analysis</h1>
        <p>Showing minimal credit given for beating FCS opponents:</p>
        
        <table style="border-collapse: collapse; width: 100%;">
            <tr style="background: #f0f0f0;">
                <th style="border: 1px solid #ddd; padding: 8px;">Week</th>
                <th style="border: 1px solid #ddd; padding: 8px;">Winner</th>
                <th style="border: 1px solid #ddd; padding: 8px;">Score</th>
                <th style="border: 1px solid #ddd; padding: 8px;">Margin</th>
                <th style="border: 1px solid #ddd; padding: 8px;">Victory Value</th>
            </tr>
            {% for game in fcs_games %}
            <tr>
                <td style="border: 1px solid #ddd; padding: 8px;">{{ game.week }}</td>
                <td style="border: 1px solid #ddd; padding: 8px;">{{ game.winner }}</td>
                <td style="border: 1px solid #ddd; padding: 8px;">{{ game.score }}</td>
                <td style="border: 1px solid #ddd; padding: 8px;">{{ game.margin }}</td>
                <td style="border: 1px solid #ddd; padding: 8px; color: red;">{{ game.victory_value }}</td>
            </tr>
            {% endfor %}
        </table>
        
        <div style="background: #fff3cd; padding: 15px; margin: 20px 0; border-radius: 5px;">
            <h3>FCS Game Penalties Applied:</h3>
            <ul>
                <li>Opponent Quality: 0.5/10 (extremely low)</li>
                <li>No location bonus (road wins vs FCS don't get extra credit)</li>
                <li>Minimal margin bonus (max 0.2 regardless of score)</li>
                <li>No conference bonus</li>
                <li>No rivalry bonus</li>
                <li>Hard cap at 1.0 total victory points</li>
            </ul>
        </div>
        
        <p><a href="/admin">Back to Admin</a></p>
    </body>
    </html>
    """, fcs_games=fcs_games)


# Replace your bowl_projections route with this clean version
# This removes all potential issues and uses simple error handling

# And add this test route:
@app.route('/team_simple/<team_name>')
def team_simple(team_name):
    """Super simple template test"""
    basic_stats = team_stats[team_name]
    opponent_details = []
    for game in basic_stats['games']:
        opponent_details.append({
            'opponent': game['opponent'],
            'result': game['result'],
        })
    
    return render_template('test_template.html', 
                         team_name=team_name, 
                         opponent_details=opponent_details)

@app.route('/bowl_projections')
def bowl_projections():
    """Bowl projections page showing all bowl games"""
    try:
        # Generate projections
        projections = generate_bowl_projections()
        
        # Organize bowls by tier for display
        bowls_by_tier = {
            'NY6': [],
            'Major': [],
            'Conference': [],
            'G5': [],
            'Championship': projections.get('conference_championships', [])
        }
        
        # Sort bowl projections by tier
        for bowl in projections.get('bowl_projections', []):
            tier = bowl.get('tier', 'Other')
            if tier in bowls_by_tier:
                bowls_by_tier[tier].append(bowl)
        
        # Prepare template data
        template_data = {
            'cfp_bracket': projections.get('cfp_bracket', {'all_teams': [], 'first_round_byes': []}),
            'bowls_by_tier': bowls_by_tier,
            'total_bowl_teams': projections.get('total_bowl_teams', 0)
        }
        
        return render_template('bowl_projections.html', **template_data)
        
    except Exception as e:
        # Simple error page
        return f"""
        <html>
        <head><title>Bowl Projections Error</title></head>
        <body style="font-family: Arial; margin: 40px;">
            <h1>Bowl Projections Error</h1>
            <p><strong>Error:</strong> {str(e)}</p>
            <p><a href="/">Back to Home</a> | <a href="/admin">Admin Panel</a></p>
        </body>
        </html>
        """


@app.route('/historical')
def historical_rankings():
    if len(historical_rankings) < 2:
        flash('Need at least 2 weekly snapshots to show movement', 'info')
        return redirect(url_for('public_rankings'))
    
    # Get the two most recent snapshots
    current_week = historical_rankings[-1]
    previous_week = historical_rankings[-2]
    
    # Calculate movement for each team
    movement_data = []
    
    # Create lookup for previous week rankings
    prev_rankings = {team['team']: team['rank'] for team in previous_week['rankings']}
    
    for team in current_week['rankings']:
        team_name = team['team']
        current_rank = team['rank']
        previous_rank = prev_rankings.get(team_name, None)
        
        if previous_rank:
            movement = previous_rank - current_rank  # Positive = moved up
            movement_data.append({
                'team': team_name,
                'conference': team['conference'],
                'current_rank': current_rank,
                'previous_rank': previous_rank,
                'movement': movement,
                'wins': team['wins'],
                'losses': team['losses'],
                'adjusted_total': team['adjusted_total']
            })
        else:
            # New team in rankings
            movement_data.append({
                'team': team_name,
                'conference': team['conference'],
                'current_rank': current_rank,
                'previous_rank': None,
                'movement': None,
                'wins': team['wins'],
                'losses': team['losses'],
                'adjusted_total': team['adjusted_total']
            })
    
    # Sort by current rank
    movement_data.sort(key=lambda x: x['current_rank'])
    
    return render_template('historical.html', 
                         movement_data=movement_data,
                         current_week=current_week,
                         previous_week=previous_week)

# Get scheduled games for the selected week that haven't been completed
    week_scheduled = [game for game in scheduled_games 
                     if game['week'] == week and not game.get('completed', False)]
    
    # Sort scheduled games by date and time
    def sort_key(game):
        game_date = game.get('game_date', '9999-12-31')
        game_time = game.get('game_time', '11:59 PM')
        
        try:
            if game_time:
                from datetime import datetime
                time_obj = datetime.strptime(game_time, '%I:%M %p')
                time_24h = time_obj.strftime('%H:%M')
            else:
                time_24h = '23:59'
        except:
            time_24h = '23:59'
        
        return f"{game_date} {time_24h}"
    
    week_scheduled.sort(key=sort_key)
    
    # Group scheduled games by date
    scheduled_by_date = {}
    for game in week_scheduled:
        game_date = game.get('game_date')
        if game_date:
            if game_date not in scheduled_by_date:
                scheduled_by_date[game_date] = []
            scheduled_by_date[game_date].append(game)
        else:
            # Games without dates go in a "TBD" group
            if 'No Date' not in scheduled_by_date:
                scheduled_by_date['No Date'] = []
            scheduled_by_date['No Date'].append(game)
    
    # Also group completed games by date
    week_games = [game for game in games_data if game['week'] == week]
    completed_by_date = {}
    
    for game in week_games:
        # Try to find corresponding scheduled game to get date
        game_date = None
        for scheduled in scheduled_games:
            if (scheduled['week'] == week and 
                ((scheduled['home_team'] == game['home_team'] and scheduled['away_team'] == game['away_team']) or
                 (scheduled['home_team'] == game['away_team'] and scheduled['away_team'] == game['home_team']))):
                game_date = scheduled.get('game_date')
                break
        
        if not game_date:
            game_date = 'No Date'
            
        if game_date not in completed_by_date:
            completed_by_date[game_date] = []
        completed_by_date[game_date].append(game)
    
    # Sort dates for display
    all_dates = set(list(scheduled_by_date.keys()) + list(completed_by_date.keys()))
    if 'No Date' in all_dates:
        all_dates.remove('No Date')
        sorted_dates = sorted([d for d in all_dates if d != 'No Date']) + ['No Date']
    else:
        sorted_dates = sorted(all_dates)
    
    return render_template('weekly_results.html', 
                         selected_week=week, 
                         weeks_with_games=weeks_with_games,
                         week_games=week_games,
                         scheduled_games=week_scheduled,
                         scheduled_by_date=scheduled_by_date,
                         completed_by_date=completed_by_date,
                         sorted_dates=sorted_dates,
                         all_weeks=WEEKS)

@app.route('/reset_data', methods=['POST'])
@login_required
def reset_data():
    """Reset all data - useful for testing or starting over"""
    global games_data, team_stats, historical_rankings
    games_data = []
    team_stats = defaultdict(lambda: {
        'wins': 0, 'losses': 0, 'points_for': 0, 'points_against': 0,
    'home_wins': 0, 'road_wins': 0, 'margin_of_victory_total': 0,
    'games': []
    })
    historical_rankings = []
    
    # Delete saved files
    try:
        games_file = os.path.join(DATA_DIR, 'games_data.json')
        stats_file = os.path.join(DATA_DIR, 'team_stats.json')
        historical_file = os.path.join(DATA_DIR, 'historical_rankings.json')
        
        if os.path.exists(games_file):
            os.remove(games_file)
        if os.path.exists(stats_file):
            os.remove(stats_file)
        if os.path.exists(historical_file):
            os.remove(historical_file)
        flash('All data has been reset!', 'success')
    except Exception as e:
        flash(f'Error resetting data: {e}', 'error')
    
    return redirect(url_for('admin'))

    # Historical rankings storage
historical_rankings = []

def save_weekly_snapshot(week_number):
    """Save current rankings as a weekly snapshot"""
    # Create comprehensive stats table
    comprehensive_stats = []
    
    for conf_name, teams in CONFERENCES.items():
        for team in teams:
            stats = calculate_comprehensive_stats(team)
            stats['team'] = team
            stats['conference'] = conf_name
            comprehensive_stats.append(stats)
    
    # Sort by Adjusted Total (highest first)
    comprehensive_stats.sort(key=lambda x: x['adjusted_total'], reverse=True)
    
    # Create snapshot with rankings
    snapshot = {
        'week': week_number,
        'date': datetime.now().strftime('%Y-%m-%d'),
        'rankings': []
    }
    
    for rank, team_data in enumerate(comprehensive_stats, 1):
        snapshot['rankings'].append({
            'rank': rank,
            'team': team_data['team'],
            'conference': team_data['conference'],
            'wins': team_data['total_wins'],
            'losses': team_data['total_losses'],
            'adjusted_total': team_data['adjusted_total']
        })
    
    # Add to historical data
    historical_rankings.append(snapshot)
    
    # Save to file
    save_historical_data()
    print(f"📸 Weekly snapshot saved for Week {week_number}")

def save_historical_data():
    """Save historical rankings to JSON file"""
    try:
        historical_file = os.path.join(DATA_DIR, 'historical_rankings.json')
        with open(historical_file, 'w') as f:
            json.dump(historical_rankings, f, indent=2)
    except Exception as e:
        print(f"Error saving historical data: {e}")

def load_historical_data():
    """Load historical rankings from JSON file"""
    global historical_rankings
    try:
        historical_file = os.path.join(DATA_DIR, 'historical_rankings.json')
        with open(historical_file, 'r') as f:
            historical_rankings = json.load(f)
        print(f"Loaded {len(historical_rankings)} historical snapshots")
    except FileNotFoundError:
        print("No historical data found, starting fresh")
        historical_rankings = []
    except Exception as e:
        print(f"Error loading historical data: {e}")
        historical_rankings = []


# Season Archive System
def archive_current_season(season_name):
    """Archive the current season's complete data"""
    try:
        # Create archives directory
        archives_dir = os.path.join(DATA_DIR, 'archives')
        os.makedirs(archives_dir, exist_ok=True)
        
        # Get current comprehensive stats for final rankings
        final_rankings = []
        for conf_name, teams in CONFERENCES.items():
            for team in teams:
                stats = calculate_comprehensive_stats(team)
                stats['team'] = team
                stats['conference'] = conf_name
                final_rankings.append(stats)
        
        # Sort by Adjusted Total (highest first) 
        final_rankings.sort(key=lambda x: x['adjusted_total'], reverse=True)
        
        # Add rank numbers
        for rank, team_data in enumerate(final_rankings, 1):
            team_data['final_rank'] = rank
        
        # Convert team_stats defaultdict to regular dict for JSON serialization
        team_stats_dict = {}
        for team, stats in team_stats.items():
            team_stats_dict[team] = dict(stats)
        
        # Create complete season archive
        season_archive = {
            'season_name': season_name,
            'archived_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_games': len(games_data),
            'total_teams_with_games': len([team for team, stats in team_stats.items() if stats['wins'] + stats['losses'] > 0]),
            'games_data': games_data,
            'team_stats': team_stats_dict,
            'historical_rankings': historical_rankings,
            'final_rankings': final_rankings[:25],  # Top 25 final rankings
            'season_summary': {
                'champion': final_rankings[0] if final_rankings else None,
                'total_weeks': len(historical_rankings),
                'conferences_represented': len(set(team['conference'] for team in final_rankings[:25] if final_rankings))
            }
        }
        
        # Save archive file
        archive_filename = f"{season_name.replace(' ', '_').lower()}_complete.json"
        archive_path = os.path.join(archives_dir, archive_filename)
        
        with open(archive_path, 'w') as f:
            json.dump(season_archive, f, indent=2)
        
        print(f"✅ Season '{season_name}' archived successfully to {archive_filename}")
        return True
        
    except Exception as e:
        print(f"❌ Error archiving season: {e}")
        return False

def load_archived_seasons():
    """Load list of all archived seasons"""
    try:
        archives_dir = os.path.join(DATA_DIR, 'archives')
        if not os.path.exists(archives_dir):
            return []
        
        archived_seasons = []
        for filename in os.listdir(archives_dir):
            if filename.endswith('_complete.json'):
                try:
                    archive_path = os.path.join(archives_dir, filename)
                    with open(archive_path, 'r') as f:
                        archive_data = json.load(f)
                    
                    # Extract summary info
                    season_info = {
                        'filename': filename,
                        'season_name': archive_data.get('season_name', 'Unknown Season'),
                        'archived_date': archive_data.get('archived_date', 'Unknown Date'),
                        'total_games': archive_data.get('total_games', 0),
                        'total_teams': archive_data.get('total_teams_with_games', 0),
                        'champion': archive_data.get('season_summary', {}).get('champion', {}).get('team', 'Unknown') if archive_data.get('season_summary', {}).get('champion') else 'No Champion',
                        'total_weeks': archive_data.get('season_summary', {}).get('total_weeks', 0)
                    }
                    archived_seasons.append(season_info)
                except Exception as e:
                    print(f"Error reading archive {filename}: {e}")
                    continue
        
        # Sort by archived date (newest first)
        archived_seasons.sort(key=lambda x: x['archived_date'], reverse=True)
        return archived_seasons
        
    except Exception as e:
        print(f"Error loading archived seasons: {e}")
        return []

def load_archived_season_details(filename):
    """Load complete details of a specific archived season"""
    try:
        archives_dir = os.path.join(DATA_DIR, 'archives')
        archive_path = os.path.join(archives_dir, filename)
        
        with open(archive_path, 'r') as f:
            return json.load(f)
            
    except Exception as e:
        print(f"Error loading archived season details: {e}")
        return None

def safe_reset_season():
    """Reset current season data (only call after archiving!)"""
    global games_data, team_stats, historical_rankings, scheduled_games
    
    games_data = []
    team_stats = defaultdict(lambda: {
        'wins': 0, 'losses': 0, 'points_for': 0, 'points_against': 0,
        'home_wins': 0, 'road_wins': 0, 'margin_of_victory_total': 0,
        'games': []
    })
    historical_rankings = []
    scheduled_games = []  # NEW: Reset scheduled games too
    
    # Delete current season files (archives are preserved)
    try:
        files_to_remove = ['games_data.json', 'team_stats.json', 'historical_rankings.json', 'scheduled_games.json', 'team_mappings.json']
        for filename in files_to_remove:
            file_path = os.path.join(DATA_DIR, filename)
            if os.path.exists(file_path):
                os.remove(file_path)
        print("🗑️ Current season data reset successfully")
        return True
    except Exception as e:
        print(f"Error resetting season data: {e}")
        return False




@app.route('/health')
def health_check():
    """Health check endpoint for load balancers"""
    return {'status': 'healthy'}, 200

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            session.permanent = True
            next_page = request.args.get('next')
            return redirect(next_page or url_for('public_rankings'))
        else:
            flash('Invalid credentials!', 'error')
    
    return render_template('login.html', next=request.args.get('next'))

@app.route('/logout')
def logout():
    session.pop('admin_logged_in', None)
    flash('Logged out successfully!', 'success')
    return redirect(url_for('public_rankings')) 

@app.route('/archive_season', methods=['POST'])
@login_required
def archive_season():
    """Archive the current season"""
    try:
        season_name = request.form.get('season_name', '').strip()
        if not season_name:
            flash('Please enter a season name!', 'error')
            return redirect(url_for('admin'))
        
        # Check if season has any data
        if len(games_data) == 0:
            flash('No games to archive! Add some games first.', 'error')
            return redirect(url_for('admin'))
        
        # Archive the season
        if archive_current_season(season_name):
            flash(f'✅ Season "{season_name}" archived successfully! You can now safely start a new season.', 'success')
        else:
            flash('❌ Error archiving season. Please try again.', 'error')
            
    except Exception as e:
        flash(f'Error archiving season: {e}', 'error')
    
    return redirect(url_for('admin'))

@app.route('/archived_seasons')
def archived_seasons():
    """View list of all archived seasons"""
    archived_seasons_list = load_archived_seasons()
    return render_template('archived_seasons.html', archived_seasons=archived_seasons_list)

@app.route('/archived_season/<filename>')
def view_archived_season(filename):
    """View details of a specific archived season"""
    # Security check - ensure filename is safe
    if not filename.endswith('_complete.json') or '/' in filename or '\\' in filename:
        flash('Invalid archive file!', 'error')
        return redirect(url_for('archived_seasons'))
    
    season_data = load_archived_season_details(filename)
    if not season_data:
        flash('Could not load archived season data!', 'error')
        return redirect(url_for('archived_seasons'))
    
    return render_template('archived_season_detail.html', season_data=season_data)

@app.route('/delete_archived_season', methods=['POST'])
@login_required
def delete_archived_season():
    """Delete a specific archived season"""
    try:
        filename = request.form.get('filename', '').strip()
        confirm_text = request.form.get('delete_confirm', '').strip()
        
        # Security checks
        if not filename.endswith('_complete.json') or '/' in filename or '\\' in filename:
            flash('Invalid archive file!', 'error')
            return redirect(url_for('archived_seasons'))
        
        if confirm_text != 'DELETE':
            flash('Delete confirmation failed. Please type DELETE exactly.', 'error')
            return redirect(url_for('archived_seasons'))
        
        # Check if file exists
        archives_dir = os.path.join(DATA_DIR, 'archives')
        archive_path = os.path.join(archives_dir, filename)
        
        if not os.path.exists(archive_path):
            flash('Archive file not found!', 'error')
            return redirect(url_for('archived_seasons'))
        
        # Load season name for confirmation message
        try:
            with open(archive_path, 'r') as f:
                archive_data = json.load(f)
            season_name = archive_data.get('season_name', 'Unknown Season')
        except:
            season_name = 'Unknown Season'
        
        # Delete the file
        os.remove(archive_path)
        flash(f'✅ Archived season "{season_name}" deleted successfully.', 'success')
        
    except Exception as e:
        flash(f'Error deleting archived season: {e}', 'error')
    
    return redirect(url_for('archived_seasons'))


@app.route('/safe_reset_data', methods=['POST'])
@login_required
def safe_reset_data():
    """Safely reset data with archive confirmation"""
    try:
        confirm_text = request.form.get('reset_confirm', '').strip()
        if confirm_text != 'RESET':
            flash('Reset confirmation failed. Please type RESET exactly.', 'error')
            return redirect(url_for('admin'))
        
        # Check if current season has been archived
        current_games_count = len(games_data)
        if current_games_count > 0:
            archived_seasons_list = load_archived_seasons()
            if not archived_seasons_list:
                flash('⚠️ You have games but no archived seasons! Please archive the current season first before resetting.', 'error')
                return redirect(url_for('admin'))
            
            # Check if latest archive is recent and has similar game count
            latest_archive = archived_seasons_list[0] if archived_seasons_list else None
            if latest_archive and abs(latest_archive['total_games'] - current_games_count) > 5:
                flash('⚠️ Current data differs significantly from latest archive. Please create a new archive first.', 'error')
                return redirect(url_for('admin'))
        
        # Perform the reset
        if safe_reset_season():
            flash('🗑️ Season data reset successfully! All previous seasons remain archived.', 'success')
        else:
            flash('❌ Error resetting season data.', 'error')
            
    except Exception as e:
        flash(f'Error resetting data: {e}', 'error')
    
    return redirect(url_for('admin'))   

@app.route('/import_csv', methods=['GET', 'POST'])
@login_required
def import_csv():
    """Import final rankings from CSV file"""
    if request.method == 'GET':
        return render_template('import_csv.html')
    
    try:
        season_name = request.form.get('season_name', '').strip()
        if not season_name:
            flash('Please enter a season name!', 'error')
            return redirect(url_for('import_csv'))
        
        # Check if file was uploaded
        if 'csv_file' not in request.files:
            flash('Please select a CSV file!', 'error')
            return redirect(url_for('import_csv'))
        
        file = request.files['csv_file']
        if file.filename == '':
            flash('Please select a CSV file!', 'error')
            return redirect(url_for('import_csv'))
        
        if not file.filename.endswith('.csv'):
            flash('Please upload a CSV file!', 'error')
            return redirect(url_for('import_csv'))
        
        # Read and parse CSV
        import csv
        import io
        
        # Read file content
        file_content = file.read().decode('utf-8')
        csv_data = list(csv.DictReader(io.StringIO(file_content)))
        
        if not csv_data:
            flash('CSV file is empty!', 'error')
            return redirect(url_for('import_csv'))
        
        # Validate required columns
        required_cols = ['Rank', 'Team', 'Conference', 'Wins', 'Losses', 'Adjusted_Total']
        missing_cols = [col for col in required_cols if col not in csv_data[0].keys()]
        if missing_cols:
            flash(f'Missing required columns: {", ".join(missing_cols)}', 'error')
            return redirect(url_for('import_csv'))
        
        # Process the data
        final_rankings = []
        for row in csv_data:
            try:
                team_data = {
                    'final_rank': int(row['Rank']),
                    'team': row['Team'].strip(),
                    'conference': row['Conference'].strip(),
                    'total_wins': int(row['Wins']),
                    'total_losses': int(row['Losses']),
                    'adjusted_total': float(row['Adjusted_Total']),
                    'p4_wins': int(row.get('P4_Wins', 0)) if row.get('P4_Wins', '').strip() else 0,
                    'g5_wins': int(row.get('G5_Wins', 0)) if row.get('G5_Wins', '').strip() else 0,
                    'strength_of_schedule': 0.500,  # Default value
                    'points_fielded': 0,  # Not available from CSV
                    'points_allowed': 0,  # Not available from CSV
                    'margin_of_victory': 0,  # Not available from CSV
                    'point_differential': 0,  # Not available from CSV
                    'home_wins': 0,  # Not available from CSV
                    'road_wins': 0,  # Not available from CSV
                    'opp_w': 0,  # Not available from CSV
                    'opp_l': 0,  # Not available from CSV
                    'opp_wl_differential': 0,  # Not available from CSV
                    'totals': float(row['Adjusted_Total'])  # Use adjusted total as totals
                }
                final_rankings.append(team_data)
            except (ValueError, KeyError) as e:
                flash(f'Error processing row {row.get("Rank", "?")}: {e}', 'error')
                return redirect(url_for('import_csv'))
        
        # Sort by rank to ensure proper order
        final_rankings.sort(key=lambda x: x['final_rank'])
        
        # Create the archive structure
        import_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        season_archive = {
            'season_name': season_name,
            'archived_date': import_date,
            'total_games': 0,  # Unknown from CSV import
            'total_teams_with_games': len(final_rankings),
            'games_data': [],  # No individual games from CSV
            'team_stats': {},  # No detailed stats from CSV
            'historical_rankings': [],  # No weekly data from CSV
            'final_rankings': final_rankings,
            'season_summary': {
                'champion': final_rankings[0] if final_rankings else None,
                'total_weeks': 0,  # Unknown from CSV
                'conferences_represented': len(set(team['conference'] for team in final_rankings)),
                'import_source': 'CSV Import',
                'import_date': import_date
            }
        }
        
        # Save the archive
        archives_dir = os.path.join(DATA_DIR, 'archives')
        os.makedirs(archives_dir, exist_ok=True)
        
        archive_filename = f"{season_name.replace(' ', '_').lower()}_complete.json"
        archive_path = os.path.join(archives_dir, archive_filename)
        
        with open(archive_path, 'w') as f:
            json.dump(season_archive, f, indent=2)
        
        flash(f'✅ Successfully imported {len(final_rankings)} teams for "{season_name}"!', 'success')
        return redirect(url_for('archived_seasons'))
        
    except Exception as e:
        flash(f'Error importing CSV: {e}', 'error')
        return redirect(url_for('import_csv'))


if __name__ == '__main__':
    
    
    # Load existing data
    load_data()
    
    print("College Football Ranking App")
    print("=" * 40)
    print("Templates created successfully!")
    print("Features:")
    print("- Add games with automatic P4/G5 classification")
    print("- Neutral site games (no home/road win credit)")
    print("- Weekly results page to review games by week")
    print("- Comprehensive statistics and ranking calculation")
    print("- Sortable table columns (click headers to sort)")
    print("- All FBS conferences included + FCS option")
    print("- Team detail pages with statistics")
    print("- Conference-organized dropdowns")
    print("- Data persistence (automatically saved)")
    print("- Reset data option in navigation")
    print("- Responsive Bootstrap UI")
    print(f"\nTotal teams: {len(TEAMS)} across {len(CONFERENCES)} conferences")
    print("Conferences included:")
    for conf_name, teams in CONFERENCES.items():
        classification = ""
        if conf_name in P4_CONFERENCES:
            classification = " (P4)"
        elif conf_name in G5_CONFERENCES:
            classification = " (G5)"
        elif conf_name == "Independent":
            classification = " (Notre Dame=P4, Connecticut=G5, FCS=None)"
        print(f"  - {conf_name}: {len(teams)} teams{classification}")
    print("\nP4 Conferences: ACC, Big Ten, Big XII, Pac 12, SEC, Notre Dame")
    print("G5 Conferences: American, Conference USA, MAC, Mountain West, Sun Belt, Connecticut")
    print("None Classification: FCS (for non-P4/G5 games)")
    print("Ready with your custom ranking formula!")
    print("\nHow game types work:")
    print("- Each team's game type reflects their OPPONENT's classification")
    print("- Example: Boston College (P4) vs Kent State (G5)")
    print("  → Boston College gets 'G5' game type (playing G5 opponent)")
    print("  → Kent State gets 'P4' game type (playing P4 opponent)")
    print("- Neutral site games: Neither team gets home/road win credit")
    print("  → Useful for bowl games, conference championships, etc.")
    print("\nData will be automatically saved to games_data.json and team_stats.json")
    print("Starting Flask development server...")
    
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5001)), debug=False)