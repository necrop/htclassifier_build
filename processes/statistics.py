#-------------------------------------------------------------------------------
# Name: Statistics

#-------------------------------------------------------------------------------

import os
import string
from collections import defaultdict

from pickler.sensemanager import PickleLoader
import lex.oed.thesaurus.thesaurusdb as tdb
from utils.tracer import trace_sense

triage = ('classified', 'unclassified', 'intractable')
letters = string.ascii_uppercase


class Statistics(object):
    cache = {}

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            self.__dict__[k] = v

    def compile_stats(self):
        self.sense_counts = {t: 0 for t in triage}
        self.wordclass = 0
        self.levels = defaultdict(int)
        self.reasons = defaultdict(int)
        for parent_dir in self.directories:
            for t in triage:
                if t == 'unclassified' and 'iteration1' in parent_dir:
                    pass
                else:
                    dir = os.path.join(parent_dir, t)
                    for letter in letters:
                        pl = PickleLoader(dir, letters=letter)
                        for sense in pl.iterate():
                            self.sense_counts[t] += 1
                            if t == 'classified':
                                self.inspect_classification(sense)

        for t in triage:
            print('%s\t%d' % (t, self.sense_counts[t]))
        for l in sorted(self.levels.keys()):
            print('level %d\t%d' % (l, self.levels[l]))
        print('classified with wordclass: %d' % self.wordclass)

        print('\nREASON CODES:')
        for r in sorted(self.reasons.keys()):
            print('\t%s\t%d' % (r, self.reasons[r]))

    def inspect_classification(self, sense):
        if sense.class_id not in Statistics.cache:
            thesclass = tdb.get_thesclass(sense.class_id)
            Statistics.cache[sense.class_id] = {'l': thesclass.level, 'w': False}
            if thesclass.wordclass is not None:
                Statistics.cache[sense.class_id]['w'] = True
        self.levels[Statistics.cache[sense.class_id]['l']] += 1
        if Statistics.cache[sense.class_id]['w']:
            self.wordclass += 1

        try:
            sense.reason_code
        except AttributeError:
            pass
        else:
            self.reasons[sense.reason_code] += 1

        #if sense.clone_num > 1:
        #    print(trace_sense(sense))
