"""
make_raw_index
"""

import os
import csv
import string
from collections import defaultdict

from pickler.sensemanager import PickleLoader
from . import compoundindexerconfig

OUTPUT_DIR = compoundindexerconfig.DIRECTORY
WORDCLASSES = compoundindexerconfig.WORDCLASSES
LIGHT_STEMMER = compoundindexerconfig.LIGHT_STEMMER


def make_raw_index(input_dir):
    """
    Compile the raw compound index
    """
    store = {wordclass: defaultdict(list) for wordclass in WORDCLASSES}
    for letter in string.ascii_uppercase:
        print('\tIndexing compound elements in %s...' % letter)
        loader = PickleLoader(input_dir, letters=letter)
        for s in loader.iterate():
            if (s.wordclass in WORDCLASSES and
                    s.first_word() is not None and
                    s.last_word() is not None):
                first = s.first_word()
                last = s.last_word()
                if first in ('non', 'anti', 'to'):
                    pass
                else:
                    if len(last) >= 3:
                        last = LIGHT_STEMMER.edit(last.lower())
                        for leaf in s.thesaurus_nodes:
                            store[s.wordclass][last].append(leaf)
                    if len(first) >= 3:
                        first = LIGHT_STEMMER.edit(first.lower())
                        for leaf in s.thesaurus_nodes:
                            store['first'][first].append(leaf)

    for wordclass in compoundindexerconfig.WORDCLASSES:
        filepath = os.path.join(OUTPUT_DIR, wordclass + '_raw.csv')
        with open(filepath, 'w') as filehandle:
            csvwriter = csv.writer(filehandle)
            for lemma, vals in sorted(store[wordclass].items()):
                if wordclass == 'first' and len(vals) == 1:
                    pass
                else:
                    row = [lemma, ]
                    row.extend(vals)
                    csvwriter.writerow(row)
