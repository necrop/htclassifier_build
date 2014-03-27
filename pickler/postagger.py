import os
import nltk


class PosTagger(object):
    default_tagger = None
    tagger = None

    def __init__(self, dir=None):
        if PosTagger.tagger is None and dir is not None:
            self._load_unigrams(dir)

    def tag(self, text):
        tokens = nltk.word_tokenize(text)
        return PosTagger.tagger.tag(tokens)

    def _load_unigrams(self, dir):
        unigrams = {}
        for filename in ('unigrams.txt', 'extras.txt'):
            filepath = os.path.join(dir, filename)
            with open(filepath) as fh:
                for line in fh:
                    line = line.strip()
                    lemma, pos = line.split('\t')
                    if pos == 'NP':
                        pos = 'NNP'
                    unigrams[lemma] = pos
        PosTagger.default_tagger = nltk.data.load(nltk.tag._POS_TAGGER)
        PosTagger.tagger =\
            nltk.tag.UnigramTagger(model=unigrams,
                                   backoff=PosTagger.default_tagger)
