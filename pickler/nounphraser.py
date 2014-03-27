
import re
from collections import namedtuple

import nltk

from lex.inflections.singularizer import Singularizer
import lex.oed.thesaurus.thesaurusdb as tdb
from .definitiontogloss import gloss_normalizer
from .postagger import PosTagger
from utils.tracer import trace_sense

POS_TAGGER = PosTagger()
SINGLER = Singularizer()

PERSON_WHO_PATTERN = re.compile(r' who ([a-z]{3,}s)( |,|$)')
PERSON_DOING_PATTERN = re.compile(r' (person|man|woman|someone) ([a-z]{3,})ing( |,|$)')
PERSON_IS_PATTERN = re.compile(r' (person|man|woman|someone) who is ([a-z]+)( |,|$)')
PERSON_DID_PATTERN = re.compile(r' (person|man|woman|someone) ([a-z]{3,}ed)( |,|$)')

# Noun-phrase chunker
GRAMMAR = r"""
    NP: {<DT|PP\$>?<JJ.*>*<NN.*>+<POS><JJ.*>*<NN.*>+}
        {<DT|PP\$>?<CD>*<JJ.*>*<NN.*>+}
        {<DT|PP\$>?<NN>?<JJ>?<NN.*>+}
"""
CHUNK_PARSER = nltk.RegexpParser(GRAMMAR)
TokenPair = namedtuple('TokenPair', ['token', 'pos'])
NPpair = namedtuple('NPpair', ['full', 'short'])

JJ_INDICATORS = ('of or', 'involving', 'pertaining' 'relating', 'consisting',
                 'designating', 'characterized by', 'of, ', 'that is a ',
                 'that is an ', 'resembling a ', 'resembling an ',
                 'denoting a ', 'denoting an ')

# In a noun definition, the first NP won't be regarded as the superordinate
#  if it's preceded by one of these
NN_STOPWORDS = {'by', 'to', 'for', 'with', 'of', 'at', 'in', 'from'}

PLACES = re.compile(r'^(north|south|east|west|central)(ern|) (america|africa|europe)$')
PLACENAME_BIGRAMS = ('united states', 'great britain', 'united kingdom',
                     'new zealand', 'latin america', 'middle east',
                     'far east')


class NounPhraser(object):

    def __init__(self, sense):
        self.sense = sense
        self.wordclass = sense.wordclass

    def gloss(self):
        try:
            return self._gloss_cleaned
        except AttributeError:
            self._gloss_cleaned = gloss_normalizer(self.sense.gloss,
                                                   self.wordclass)
            return self._gloss_cleaned

    def tagged_tokens(self):
        try:
            return self._tagged_tokens
        except AttributeError:
            if not self.gloss().strip():
                self._tagged_tokens = []
            else:
                # Tokenize and pos-tag the tokens
                tagged = POS_TAGGER.tag(self.gloss())
                # Lower-case all the tokens
                self._tagged_tokens = [(t[0].lower(), t[1])
                                       for t in tagged]
            return self._tagged_tokens

    def chunks(self):
        try:
            return self._chunks
        except AttributeError:
            self._chunks = parse_noun_phrases(self.tagged_tokens())
            return self._chunks

    def noun_phrases(self):
        return [c.token for c in self.chunks() if c.pos == 'NP']

    def adjectives(self):
        return [t[0] for t in self.tagged_tokens() if t[1] == 'JJ']

    def superordinate(self):
        if self.sense.wordclass == 'VB':
            return self._find_verb_superordinate()
        else:
            return self._find_noun_superordinate()

    def _find_noun_superordinate(self):
        if (self.gloss().startswith('one who') or
                self.gloss().startswith('someone')):
            super_short = 'person'
            super_full = 'person'
            following_word = None
        elif (self.gloss().startswith('=') or
                not self.noun_phrases() or
                self.sense.wordclass not in ('NN', 'JJ')):
            super_short = None
            super_full = None
            following_word = None
        elif (self.sense.wordclass == 'JJ' and
                not any([self.gloss().startswith(ind) for ind in JJ_INDICATORS])):
            super_short = None
            super_full = None
            following_word = None
        else:
            superordinate = (None, None)
            following_word = None
            for i, c in enumerate(self.chunks()):
                if c.pos == 'NP':
                    # Disregard if it looks like it's in a subordinate clause
                    #   or similar
                    if (self.sense.wordclass == 'NN' and
                            i > 0 and
                            self.chunks()[i-1].token in NN_STOPWORDS):
                        pass
                    # Otherwise, grab the first NP as the superordinate
                    else:
                        superordinate = c.token
                        # Record the following word
                        try:
                            self.chunks()[i+1]
                        except IndexError:
                            following_word = 'NULL'
                        else:
                            if self.chunks()[i+1].pos != 'NP':
                                following_word = self.chunks()[i+1].token
                    break
            super_full = superordinate[0]
            super_short = superordinate[1]

        # 'person' becomes 'person who drinks', etc.
        super_short = extend_person(super_short, self.gloss())

        # Reverse 'of' phrases, so 'chief of town' becomes 'town chief'
        if super_short is not None:
            m = re.search(r'(.+) of (.+)$', super_short)
            if m is not None:
                super_short = m.group(2) + ' ' + m.group(1)

        return super_full, super_short, following_word

    def _find_verb_superordinate(self):
        if self.gloss():
            #print repr(self.sense.lemma)
            #print repr(self.sense.gloss)
            #print repr(self.gloss())
            #print '----------------------------------------------'
            superordinate = re.sub(r'^to ', '', self.gloss())
            super_full = superordinate.strip(' ,.:;') + 'VB'
            super_short = superordinate.split(' ')[0].strip(' ,.:;') + 'VB'
            return super_full, super_short, None
        else:
            return None, None, None


def parse_noun_phrases(tagged):
    # Remove extraneous adverbs
    tagged = [t for t in tagged if not (t[0].endswith('ly') and t[1] == 'RB')]
    tagged = [t for t in tagged if not t[0] == 'other']

    # Remove second term in 'x or y' clauses
    tagged = remove_alternatives(tagged)

    if not tagged:
        return []

    # Chunk into noun phrases
    chunks_raw = CHUNK_PARSER.parse(tagged)
    # Strip down the noun phrase to known lemmas (singularized)
    chunks = []
    for n in chunks_raw:
        if isinstance(n, nltk.tree.Tree) and n.label() == 'NP':
            chunks.append(TokenPair(np_cleaner(n), 'NP'))
        else:
            chunks.append(TokenPair(n[0], n[1]))

    # Join together 'of'-linked noun phrases
    chunks2 = []
    ratchet = 0
    for i, chunk in enumerate(chunks):
        if i < ratchet:
            pass
        else:
            if chunk.pos == 'NP':
                try:
                    chunks[i+2]
                except IndexError:
                    next = chunk
                else:
                    if (chunks[i+1].token in ('of', 'for') and
                            chunks[i+2].pos in ('NP', 'VBG')):
                        glue = ' ' + chunks[i+1].token + ' '
                        if chunks[i+2].pos == 'NP':
                            lemma_full = chunk.token.full + glue + chunks[i+2].token.full
                            lemma_short = chunk.token.short + glue + chunks[i+2].token.short
                        elif chunks[i+2].pos == 'VBG':
                            vbg_token = chunks[i+2].token
                            if vbg_token == 'becoming':
                                vbg_token = 'being'
                            lemma_full = chunk.token.full + glue + vbg_token
                            lemma_short = chunk.token.short + glue + vbg_token
                        jump = 3

                        # Turn 'action of using' into 'action of using axe', etc.
                        if chunks[i+2].pos == 'VBG':
                            try:
                                chunks[i+3]
                            except IndexError:
                                pass
                            else:
                                if chunks[i+3].pos == 'NP':
                                    lemma_full += ' ' + chunks[i+3].token.short
                                    lemma_short += ' ' + chunks[i+3].token.short
                                    jump += 1
                                elif chunks[i+2].token in ('being', 'becoming') and chunks[i+3].pos in ('JJ', 'VBD', 'VBN'):
                                    lemma_full += ' ' + chunks[i+3].token + '-JJ'
                                    lemma_short += ' ' + chunks[i+3].token + '-JJ'
                                    jump += 1
                        next = TokenPair(NPpair(full=lemma_full, short=lemma_short), 'NP')
                        ratchet = i + jump  # skip the next two tokens
                    else:
                        next = chunk
            else:
                next = chunk
            chunks2.append(next)
    return chunks2


def np_cleaner(ntuple):
    start = 0
    for i, t in enumerate(ntuple):
        token, pos = t
        if pos in ('POS', 'DT'):
            start = i + 1
    ntuple = ntuple[start:]
    if ntuple[-1][1] == 'NNS':
        ntuple[-1] = (SINGLER.singularize(ntuple[-1][0]), 'NN')

    # Create a shortened version of the ntuple which trims the ngram
    #   down to just the core ngram constituting a known OED lemma
    #   (usually just a 1-gram or 2-gram)
    ntuple_short = ntuple[:]
    while len(ntuple_short) > 1:
        ngram = ' '.join([t[0] for t in ntuple_short])
        if tdb.search_current(lemma=ngram, wordclass='NN'):
            break
        if PLACES.search(ngram) or ngram in PLACENAME_BIGRAMS:
            break
        ntuple_short.pop(0)

    full = ' '.join([t[0] for t in ntuple]).replace(" 's", "'s")
    short = ' '.join([t[0] for t in ntuple_short]).replace(" 's", "'s")
    return NPpair(full=full, short=short)


def remove_alternatives(tagged):
    """
    Remove the 'or' + alternative in 'x or y' clauses, where x and y
    have the same part of speech.

    In most cases we remove the 'or' and the second alternative; e.g.
    'an ethical or behavioural standard' becomes 'an ethical standard'.

    But where the second alternative is followed by an 'of' clause, we remove
    the *first* alternative; e.g. 'a feeling or state of mind' becomes
    'a state of mind'- since we can't be sure that the 'of' clause
    would always make sense when fused to the first alternative.
    """
    removal_index = []
    for i, t in enumerate(tagged):
        try:
            tagged[i+2]
        except IndexError:
            pass
        else:
            if tagged[i+1][0] == 'or' and t[1] == tagged[i+2][1]:
                if (t[1] == 'NN' and
                        i < len(tagged) - 4 and
                        tagged[i+3][0] == 'of' and
                        tagged[i+4][1] == 'NN'):
                    removal_index.extend([i, i+1])
                else:
                    pass
                    #removal_index.extend([i+1, i+2])
    if removal_index:
        tagged2 = []
        for i, t in enumerate(tagged):
            if i not in removal_index:
                tagged2.append(t)
        return tagged2
    else:
        return tagged


def extend_person(superordinate, gloss):
    if superordinate is not None and superordinate in ('person', 'man', 'woman'):
        m = PERSON_WHO_PATTERN.search(gloss)
        if m is not None:
            superordinate = 'person who %s' % m.group(1)
        else:
            m = PERSON_DOING_PATTERN.search(gloss)
            if m is not None:
                superordinate = 'person who %ss' % m.group(2)
            else:
                m = PERSON_DID_PATTERN.search(gloss)
                if m is not None:
                    superordinate = '%s person' % m.group(2)
                else:
                    m = PERSON_IS_PATTERN.search(gloss)
                    if m is not None:
                        superordinate = '%s person' % m.group(2)
    return superordinate
