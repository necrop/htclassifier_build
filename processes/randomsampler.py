#-------------------------------------------------------------------------------
# Name: RandomSampler

#-------------------------------------------------------------------------------

import os
import string
import csv
import random
from collections import defaultdict

from .pickler.sensemanager import PickleLoader
import lex.oed.thesaurus.thesaurusdb as tdb
from stringtools import lexical_sort

letters = string.ascii_uppercase

iterations = (
    ('general', 200, 'null'),
    ('NN', 100, 'wordclass'),
    ('VB', 100, 'wordclass'),
    ('JJ', 100, 'wordclass'),
    ('RB', 100, 'wordclass'),
    ('mainsense', 100, 'sensetype'),
    ('compound', 100, 'sensetype'),
    ('derivative', 100, 'sensetype'),
    ('defined', 100, 'deftype'),
    ('undefined', 100, 'deftype'),
)

columns = ('lemma', 'wordclass', 'definition', 'HT class ID', 'HT class',
    'below wordclass level?', 'evaluation', 'sense URL', 'HT class URL',
    'reason code')


class RandomSampler(object):

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            self.__dict__[k] = v

    def iterate(self):
        for name, size, function in iterations:
            print 'random-sampling for "%s"...' % name
            self.sample_to_csv(name, size, function)

    def sample_to_csv(self, name, size, function):
        self.collect_sample(name, size, function)
        out_file = os.path.join(self.out_dir, name + '.csv')
        with open(out_file, 'wb') as fh:
            csvwriter = csv.writer(fh)
            csvwriter.writerow(columns)
            for sense in self.sample:
                if sense.definition is not None:
                    definition = sense.definition[0:200]
                    if definition.startswith('='):
                        definition = '.' + definition
                else:
                    definition = '[undefined]'
                thesclass = tdb.get_thesclass(sense.class_id)
                if thesclass.wordclass is None:
                    wordclass_level = 'n'
                else:
                    wordclass_level = 'y'
                row = (
                    sense.lemma.encode('utf8'),
                    sense.wordclass,
                    definition.encode('utf8'),
                    thesclass.id,
                    thesclass.breadcrumb().encode('utf8'),
                    wordclass_level,
                    '',
                    sense.oed_url(),
                    thesclass.oed_url(),
                    sense.reason_code,
                )
                csvwriter.writerow(row)

    def collect_sample(self, name, size, function):
        total = 0
        for parent_dir in self.directories:
            dir = os.path.join(parent_dir, 'classified')
            for letter in letters:
                pl = PickleLoader(dir, letters=letter)
                for sense in pl.iterate():
                    if is_valid(sense, name, function):
                        total += 1

        sense_index = set()
        while len(sense_index) < size:
            i = random.randint(0, total)
            if not i in sense_index:
                sense_index.add(i)

        self.sample = []
        count = 0
        for parent_dir in self.directories:
            dir = os.path.join(parent_dir, 'classified')
            for letter in letters:
                pl = PickleLoader(dir, letters=letter)
                for sense in pl.iterate():
                    if is_valid(sense, name, function):
                        if count in sense_index:
                            self.sample.append(sense)
                        count += 1

        self.sample.sort(key=lambda s: lexical_sort(s.lemma))



def is_valid(sense, name, function):
    """Add condition here for filtering senses
    """
    if sense.clone_num > 0:
        return False
    if function == 'null':
        return True
    if function == 'wordclass' and name == sense.wordclass:
        return True
    if function == 'sensetype':
        if name == 'mainsense' and sense.subentry_type == 'main sense':
            return True
        if sense.subentry_type == name:
            return True
    if function == 'deftype' and name == 'undefined' and sense.is_undefined():
        return True
    if function == 'deftype' and name == 'defined' and not sense.is_undefined():
        return True
    return False

