#-------------------------------------------------------------------------------
# Name: CheckLevels

#-------------------------------------------------------------------------------

import os
import re
import string
from collections import defaultdict

import lex.oed.thesaurus.thesaurusdb as tdb
from lex.oed.projects.thesaurus.classifier.pickler.sensemanager import PickleLoader
from lex.oed.projects.thesaurus.classifier.config import ThesaurusConfig


config = ThesaurusConfig()
training_dir = config.get('paths', 'classified_dir')
parent_directories=[
    config.get('paths', 'iteration1_dir'),
    config.get('paths', 'iteration2_dir'),
]


def count_training():
    counts = {i: 0 for i in range(17)}
    pl = PickleLoader(training_dir)
    for sense in pl.iterate():
        for n in sense.thesaurus_nodes:
            thesclass = tdb.get_thesclass(n)
            counts[thesclass.level] += 1
    for i in range(17):
        print '%d\t%d' % (i, counts[i])


def count_classified():
    counts = {i: 0 for i in range(17)}
    for p in parent_directories:
        subdir = os.path.join(p, 'classified')
        pl = PickleLoader(subdir)
        for sense in pl.iterate():
            try:
                sense.class_id
            except AttributeError:
                pass
            else:
                thesclass = tdb.get_thesclass(sense.class_id)
                counts[thesclass.level] += 1
    for i in range(17):
        print '%d\t%d' % (i, counts[i])

if __name__ == '__main__':
    #count_training()
    count_classified()
