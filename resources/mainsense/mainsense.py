"""
MainSense -- Utility to return the main sense of a given entry or lemma.
"""

import os
import csv

import lex.oed.thesaurus.thesaurusdb as tdb

wordclasses = ('NN', 'JJ')


class MainSense(object):
    cache = {wc: {} for wc in wordclasses}
    data = {wc: {} for wc in wordclasses}
    loaded = False

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            self.__dict__[k] = v
        try:
            self.resources_dir
        except AttributeError:
            pass
        else:
            self.dir = os.path.join(self.resources_dir, 'main_senses')
            self.load_data()

    def main_sense(self, **kwargs):
        lemma = kwargs.get('lemma')
        wordclass = kwargs.get('wordclass', None)
        entry_id = kwargs.get('refentry', None)
        listed_only = kwargs.get('listed_only', False)

        # Work out what the wordclass should be, if it's not been passed
        #  explicitly
        naive_main_sense = None
        if wordclass is None:
            naive_main_sense = tdb.highest_ranked(lemma=lemma,
                                                  refentry=entry_id)
            if naive_main_sense is not None:
                wordclass = naive_main_sense.wordclass
            else:
                wordclass = 'NN'

        # Find the main sense from the look-up tables
        instance = None
        try:
            instance = MainSense.cache[wordclass][lemma]
        except KeyError:
            try:
                refentry, refid = MainSense.data[wordclass][lemma]
            except KeyError:
                pass
            else:
                instance = tdb.highest_ranked(lemma=lemma,
                                              wordclass=wordclass,
                                              refentry=refentry,
                                              refid=refid)
                # Store this instance in the cache
                MainSense.cache[wordclass][lemma] = instance

        # Nix the instance if it's got the wrong refentry value
        if (instance is not None and
                entry_id is not None and
                instance.refentry != entry_id):
            instance = None

        # Fall back to ThesaurusDB's main_sense algorithm,
        #  unless the listed_only argument has been passed
        if not listed_only:
            if instance is None and naive_main_sense is not None:
                # Don't bother recalculating if already calculated above
                instance = naive_main_sense
            elif instance is None:
                instance = tdb.highest_ranked(lemma=lemma,
                                              wordclass=wordclass,
                                              refentry=entry_id)

        return instance

    def load_data(self):
        if not MainSense.loaded:
            for wordclass in wordclasses:
                # We load the 'force' file second, so that it overwrites
                #  the corresponding entry from the main file
                filepath1 = os.path.join(self.dir, wordclass + '.csv')
                filepath2 = os.path.join(self.dir, wordclass + '_force.csv')
                for filepath in (filepath1, filepath2):
                    if not os.path.isfile(filepath):
                        continue
                    with open(filepath, 'r') as filehandle:
                        csvreader = csv.reader(filehandle)
                        for row in csvreader:
                            lemma = row[0]
                            refentry = int(row[1])
                            refid = int(row[2])
                            MainSense.data[wordclass][lemma] = (refentry, refid)
                            MainSense.data[wordclass][refentry] = (refentry, refid)
            MainSense.loaded = True
