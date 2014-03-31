import os
import re
from collections import defaultdict, namedtuple

from resources.subjectlabelparser import SubjectLabelParser
from .keywordsfilter import KeywordsFilter
from .titlewords import TitleWords
from .lemmaparsers import lemma_components, compound_components

# Tokens won't be taken from citations or quotation text in quotations
#  with dates before these:
CIT_MIN_DATE = 1550
QT_MIN_DATE = 1700
TITLEWORDS_MIN_DATE = 1750

SenseData = namedtuple('SenseData', ['lemma', 'refentry', 'refid',
    'branches', 'definition_keywords', 'quotation_keywords', 'citations',
    'title_words', 'lemma_words', 'subjects', 'usage_labels', 'has_binomials',
    'date', 'wordclass'])


class SenseParser(object):

    def __init__(self, dir, subject_map_file):
        self.parent_dir = dir  # /bayes/ directory
        self.label_parser = SubjectLabelParser(file=subject_map_file)
        self.kwf = KeywordsFilter(dir=dir)
        self.title_parser = TitleWords(
            dir=os.path.join(dir, 'citation_expansions'))

    def parse_sense(self, sense, etyma, entry_id):
        branches = branch_nodes(sense.thesaurus_categories())
        lemma_words = compound_components(sense, etyma)
        citations = self.kwf.filter_citations(get_citations(sense))
        subjects = get_subject_labels(sense, self.label_parser)
        usages = get_usage_labels(sense)

        def_tokens = sense.definition_manager().tokens() + lemma_components(sense, etyma)
        if sense.parent_definition_manager() is not None:
            def_tokens = def_tokens + sense.parent_definition_manager().tokens()
        dkeywords = self.kwf.filter_keywords(def_tokens, lemma=sense.lemma)

        q_tokens = get_quotation_keywords(sense)
        qkeywords = self.kwf.filter_keywords(q_tokens, lemma=sense.lemma)

        title_words = get_title_words(sense, self.title_parser)
        title_words = self.kwf.filter_titlewords(title_words, lemma=sense.lemma)

        if (sense.definition_manager().genera() or
                sense.definition_manager().families() or
                sense.definition_manager().binomials() or
                sense.quotations_binomials()):
            has_binomials = True
        else:
            has_binomials = False

        if not sense.date().start or sense.date().start < 600:
            # guess if undated (no quotations)
            if sense.is_marked_obsolete():
                date = 1600
            else:
                date = 1800
        elif sense.date().start and sense.date().start > 1900:
            date = 1900
        elif sense.date().start and sense.date().start > 1200:
            date = int(sense.date().start / 100) * 100
        else:
            date = 1100
        # There's only ever one first date, but we make
        #  it a set to match the other feature types
        date = set([str(date),])

        # Ditto with wordclass
        if (sense.primary_wordclass() is None or
                sense.primary_wordclass().penn is None):
            wordclass = []
        else:
            wordclass= set([sense.primary_wordclass().penn,])

        return SenseData(sense.lemma, int(entry_id), int(sense.node_id()),
                         branches, dkeywords, qkeywords, citations,
                         title_words, lemma_words, subjects, usages,
                         has_binomials, date, wordclass,)


def branch_nodes(thesaurus_paths):
    idset = set()
    for path in thesaurus_paths:
        for p in path.split('/'):
            idset.add(int(p))
    return idset


def get_subject_labels(sense, label_parser):
    """
    Find any labels within the sense or in headers, and map these
    to their corresponding subject ontology nodes.

    Note that we have to do this from scratch, rather than use the
    ones already provided in the sense's ch_subject characteristic,
    because the latter is not independent of the sense's existing
    thesaurus classification (if any) - so it would not make for
    good training data!

    Instead we use the SubjectLabelParser (aliased as self.label_parser)
    to convert raw labels into subject ontology nodes.
    """
    subjects = set()
    for label in sense.labels():
        for node in label_parser.map_label_to_nodes(label):
            subjects.add(node)
    return subjects


def get_quotation_keywords(sense):
    # Get the four most recent post-1700 quotations
    quotes = ([q for q in sense.quotations() if q.year() >= QT_MIN_DATE] or
              [q for q in sense.quotations() if q.year() >= CIT_MIN_DATE])
    quotes.reverse()
    quotes = quotes[0:4]

    # Collect quotation_words from each quotation
    quotation_words = []
    for q in quotes:
        quotation_words.extend(q.ranked_collocates(sense.lemma))

    # Uniq any duplicates
    coll_uniq = defaultdict(list)
    for token, distance in quotation_words:
        coll_uniq[token].append(distance)
    collrank = [(t, min(distances), len(distances)) for t, distances in
                coll_uniq.items()]

    quotation_words = set()
    for token, distance, count in collrank:
        if distance <= 10 or count >= 2:
            quotation_words.add(token)

    return quotation_words


def get_citations(sense):
    # Get all post-1600 quotations
    quotes = [q for q in sense.quotations() if q.year() >= CIT_MIN_DATE and
              not q.is_newspaper()]
    citations = set()
    for q in quotes:
        cit = q.author() or q.title() or None
        if cit is not None:
            cit = re.sub(r'[0-9()]', '', cit).replace('\u2013', '')
            cit = re.sub('  +', ' ', cit)
            citations.add(cit.strip())
    return citations


def get_title_words(sense, title_word_parser):
    # Words from the title in citations
    title_words = set()
    titles = [q.title() for q in sense.quotations() if
              q.year() >= TITLEWORDS_MIN_DATE and not q.is_newspaper()]
    for t in titles:
        for w in title_word_parser.title_words(t):
            title_words.add(w)
    return title_words


def get_usage_labels(sense):
    return set([usage_label for usage_label in
                sense.characteristic_heads('usage') if not usage_label in
                ('rare', 'historical', 'archaic', 'irregular', 'disused')])
