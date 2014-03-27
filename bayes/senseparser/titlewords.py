import os
import re

from stringtools import porter_stem


class TitleWords(object):
    expansions = {'all': {}, 'first': {}, 'last': {}}

    def __init__(self, dir=None):
        if dir is not None and not TitleWords.expansions['all']:
            self._load_expansions(dir)

    def _load_expansions(self, dir):
        for mode in TitleWords.expansions.keys():
            in_file = os.path.join(dir, mode + '.txt')
            with open(in_file, 'r') as fh:
                for line in fh:
                    parts = line.strip().split('\t')
                    if len(parts) == 2:
                        abbreviation, expansion = parts
                        TitleWords.expansions[mode][parts[0] + '.'] = parts[1]

    def title_words(self, title):
        if title is None or not title:
            return set()

        title = re.sub('(\u2013|-|\'s )', ' ', title.lower())
        title = re.sub(r"[,:;()']", '', title)
        words = [w.strip() for w in title.split() if w.strip()]

        wordset = set()
        for i, w in enumerate(words):
            if w.endswith('.'):
                if i == 0 and w in TitleWords.expansions['first']:
                    w = TitleWords.expansions['first'][w]
                elif i == len(words)-1 and w in TitleWords.expansions['last']:
                    w = TitleWords.expansions['last'][w]
                elif w in TitleWords.expansions['all']:
                    w = TitleWords.expansions['all'][w]
                w = finish_expansion(w)
            if re.search(r'^[a-z]+$', w) and len(w) >= 4:
                wordset.add(porter_stem(w))

        #print '--------------------------------------------'
        #print repr(title)
        #print repr(wordset)
        return wordset

def finish_expansion(expansion):
    expansion = expansion.strip(' ?')
    for before, after in (
        ('log.', 'logy'),
        ('ol.', 'ology'),
        ('graph.', 'graphy'),
        ('metr.', 'metric'),
        ('religio.', 'religious'),
        ('shakesp.', 'shakespeare'),
        ('botan.', 'botanical'),
        ('chemi.', 'chemical'),
        ('scien.', 'scientific'),
        ('philosoph.', 'philosophy'),
        ('politic.', 'political'),
        ('medic.', 'medical'),
        ('natur.', 'natural'),
        ('potter.', 'pottery'),
        ('econom.', 'economic'),
        ('evolution.', 'evolution'),
        ('manufactur.', 'manufacturing'),
        ('mathematic.', 'mathematical'),
        ('mechani.', 'mechanical'),
        ('music.', 'musical'),
        ('scriptur.', 'scriptural'),
        ('catholic.', 'catholic'),
        ('agricultur.', 'agricultural'),
        ('anatom.', 'anatomy'),
    ):
        expansion = expansion.replace(before, after)
    return expansion
