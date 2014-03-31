import os
import pickle

from . import compoundindexerconfig

DIR = compoundindexerconfig.DIRECTORY
WORDCLASSES = compoundindexerconfig.WORDCLASSES
LIGHT_STEMMER = compoundindexerconfig.LIGHT_STEMMER

index = {}


def retrieve_from_compound_index(word, wordclass):
    if not index:
        _load_data()
    word = LIGHT_STEMMER.edit(word.lower())
    if wordclass in index and word in index[wordclass]:
        return index[wordclass][word]
    else:
        return None


def _load_data():
    for wordclass in WORDCLASSES:
        file = os.path.join(DIR, wordclass)
        results = []
        with open(file, 'rb') as filehandle:
            while 1:
                try:
                    results.append(pickle.load(filehandle))
                except EOFError:
                    break
        index[wordclass] = {r.word: r for r in results}
