"""
Settings for HT Classifier build processes
"""

import os
from lex import lexconfig

PIPELINE = [
    ('populate_thesaurus_database', 0),
    ('store_classified', 0),
    ('store_unclassified', 1),
    ('bayes_classifier', 0),
    ('bayes_compounds', 0),
    ('index_binomials', 0),
    ('index_compounds', 0),
    ('index_main_senses', 0),
    ('index_superordinates', 0),
    ('reset_db', 1),
    ('classify1', 1),
    ('update_db', 1),
    ('classify2', 1),
    ('populate_json', 0),
    # Tests and diagnostics
    ('statistics', 0),
    ('test_sense_parser', 0),
    ('test_classifier', 0),
    ('random_sample', 0),
]

OED_ROOT = lexconfig.OED_DIR
PROJECT_ROOT = os.path.join(OED_ROOT, 'projects/htclassifier')
RESOURCES_DIR = os.path.join(PROJECT_ROOT, 'resources')
UNCLASSIFIED_DIR = os.path.join(PROJECT_ROOT, 'triage/unclassified')
CLASSIFIED_DIR = os.path.join(PROJECT_ROOT, 'triage/classified')
ITERATION1_DIR = os.path.join(PROJECT_ROOT, 'iteration1')
ITERATION2_DIR = os.path.join(PROJECT_ROOT, 'iteration2')
SAMPLES_DIR = os.path.join(PROJECT_ROOT, 'samples')
JSON_DIR = os.path.join(PROJECT_ROOT, 'db_json')
