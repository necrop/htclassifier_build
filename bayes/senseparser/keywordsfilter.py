import os

from stringtools import porter_stem


class KeywordsFilter(object):
    stopwords = set()
    stopcitations = set()
    stoptitlewords = set()
    stoplabels = set()

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            self.__dict__[k] = v

    def filter_keywords(self, keywords, lemma=None):
        if lemma is not None:
            lemma = porter_stem(lemma)[0:8]
        # Filter out stopwords
        keywords = self._filter_stopwords(keywords)
        keywords2 = set()
        for k in keywords:
            k = k.replace('-', '')
            # cut down to just the first 8 characters
            k = k[0:8]
            if lemma is None or lemma != k:
                keywords2.add(k)
        # Filter again, to be on the safe side
        return self._filter_stopwords(keywords2)

    def filter_citations(self, citations):
        if not KeywordsFilter.stopcitations:
            self._load_stopcitations()
        return [t for t in citations if
                t not in KeywordsFilter.stopcitations]

    def filter_titlewords(self, keywords, lemma=None):
        if lemma is not None:
            lemma = porter_stem(lemma)[0:8]
        # Filter out stopwords
        keywords = self._filter_stoptitlewords(keywords)
        keywords2 = set()
        for k in keywords:
            k = k.replace('-', '')
            # cut down to just the first 8 characters
            k = k[0:8]
            if lemma is None or lemma != k:
                keywords2.add(k)
        # Filter again, to be on the safe side
        return self._filter_stoptitlewords(keywords2)

    def _filter_stopwords(self, keywords):
        if not KeywordsFilter.stopwords:
            self._load_stopwords()
        return [t for t in keywords if
                t not in KeywordsFilter.stopwords and len(t) > 2]

    def _filter_stoptitlewords(self, keywords):
        if not KeywordsFilter.stoptitlewords:
            self._load_stoptitlewords()
        keywords = self._filter_stopwords(keywords)
        return [t for t in keywords if
                t not in KeywordsFilter.stoptitlewords]

    def _load_stopwords(self):
        f = os.path.join(self.dir, 'stopwords.txt')
        with open(f, 'r') as fh:
            lines = fh.readlines()
            for l in lines:
                l = l.lower().strip().strip(' .')
                if l:
                    KeywordsFilter.stopwords.add(porter_stem(l))

    def _load_stopcitations(self):
        f = os.path.join(self.dir, 'stopcitations.txt')
        with open(f, 'r') as fh:
            lines = fh.readlines()
            for l in lines:
                l = l.strip()
                if l:
                    KeywordsFilter.stopcitations.add(l)

    def _load_stoptitlewords(self):
        f = os.path.join(self.dir, 'stoptitlewords.txt')
        with open(f, 'r') as fh:
            lines = fh.readlines()
            for l in lines:
                l = l.lower().strip().strip(' .')
                if l:
                    KeywordsFilter.stoptitlewords.add(porter_stem(l))
