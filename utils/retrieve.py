#-------------------------------------------------------------------------------
# Name: Retrieve

#-------------------------------------------------------------------------------

import os
import re
import string
from collections import defaultdict

from lex.oed.projects.thesaurus.classifier.pickler.sensemanager import PickleLoader
from lex.oed.projects.thesaurus.classifier.tracer import trace_class, trace_instance, trace_sense
from lex.oed.projects.thesaurus.classifier.config import ThesaurusConfig


config = ThesaurusConfig()
parent_directories=[
    config.get('paths', 'iteration1_dir'),
    config.get('paths', 'iteration2_dir'),
]
letters = string.ascii_uppercase


while 1:
    print """
===========================================================


Enter lemma (optionally followed by '-c' or '-u' to specify
    classified or unclassified):
"""
    lemma = raw_input('>>>')
    lemma = lemma.strip()
    if lemma.endswith(' -c'):
        dirs = ['classified',]
    elif lemma.endswith(' -u'):
        dirs = ['unclassified',]
    else:
        dirs = ['classified', 'unclassified',]

    lemma = re.sub(r' +-.$', '', lemma)
    initial = lemma[0].upper()

    if initial in letters:
        seen = set()
        for p in parent_directories:
            for d in dirs:
                subdir = os.path.join(p, d)
                pl = PickleLoader(subdir, letters=initial)
                for sense in pl.iterate():
                    if sense.lemma == lemma and sense.node_id not in seen:
                        print '----------------------------------------'
                        print trace_sense(sense)
                        seen.add(sense.node_id)

