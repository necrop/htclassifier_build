"""
FormalCompoundAnalysis

Analyses a compound formally, in order to guess possible
classifications based on the lemma alone, without reference to
the definition (if any)

Used especially for undefined compounds
"""

import re

import lex.oed.thesaurus.thesaurusdb as tdb

from resources.mainsense.mainsense import MainSense
from ..indexer.compoundindexretriever import retrieve_from_compound_index
from ..bayes.computebayesconsensus import compute_bayes_consensus
from .computebestguesses import compute_best_guesses
from classifyengine.rankedsensesummary import ranked_sense_summary

WORDCLASSES = ('NN', 'JJ', 'RB', 'first')
MAIN_SENSE_FINDER = MainSense()

# Living world, abstract properties, relative properties - dangerous
#  classes since very vague and miscellaneous
DANGER_BRANCHES = {8835, 82596, 111290}

PARASYN_ENDINGS = {word: tdb.get_thesclass(class_id)
                   for word, class_id in (('shaped', 98385),
                                          ('colour', 81487),
                                          ('coloured', 81487))}

SIMILATIVE = {'like', 'wise', 'based', 'containing', 'form', 'formed', 'free'}

# Don't attempt compounds where either word is one of these:
STOPWORDS = {'of', 'a', 'an', 'in', 'to', 'the', 'by', 'for', 'less'}


def formal_compound_analysis(sense, entry_main_sense):
    """
    Figure out a likely thesaurus class based on the form of a
    two-part compound lemma.

    This is the main way of classifying undefined compounds, and
    can be used to support other methods for defined compounds.

    Returns a CompoundAnalysisResult object
    """
    # Bug out if this is not a workable compound
    if (sense.last_element() is None or
            sense.last_element() in STOPWORDS or
            sense.first_element() in STOPWORDS or
            sense.wordclass not in WORDCLASSES):
        return formal_compound_null_result()

    # Initialize the CompoundAnalysisResult object which will be returned
    output = CompoundAnalysisResult(lemma=sense.lemma,
                                    refentry=sense.entry_id,
                                    refid=sense.node_id)
    output.is_undefined = sense.is_undefined()

    #=====================================
    # Build the core tables for the result object
    #=====================================

    # Insert consensus of different Bayes evaluations
    if sense.is_possibly_parasynthetic():
        bayes_modes = ('main', 'bias_high',)
    else:
        bayes_modes = ('main', 'bias_low',)
    output.bayes_consensus = compute_bayes_consensus(sense, bayes_modes)[0:10]

    # Insert ranked senses for the second word
    output.ranked_senses = rank_senses_for_last_element(sense)[0:10]

    # Likely thesaurus branches for the first and last elements,
    #  derived from the index of compound elements
    word1_index = retrieve_from_compound_index(sense.first_element(),
                                               'first')
    word2_index = retrieve_from_compound_index(sense.last_element(),
                                               sense.wordclass)

    if (word1_index is not None and
            word1_index.count >= 5 and
            word2_index is not None and
            word2_index.count >= 5):
        p = word2_index.combined_probabilities(word1_index)
    elif word2_index is not None and word2_index.count >= 5:
        p = word2_index.combined_probabilities(None)
    else:
        p = []
    output.index_consensus = p[0:10]
    if word2_index is not None:
        output.index_count = word2_index.count

    # Establish the main sense of the first and last words
    word1_main_sense = entry_main_sense
    word2_main_sense = MAIN_SENSE_FINDER.main_sense(
        lemma=sense.last_element(),
        wordclass=sense.wordclass
    )

    #=====================================
    # Handlers for special cases
    #=====================================

    # Special handling of 'doctor-like', 'cat-wise', etc. - we just return
    #   the wordclass branch equivalent to the first element
    if ((sense.last_element() in SIMILATIVE and
            sense.wordclass in ('JJ', 'RB')) or
            (sense.last_element() in ('piece', 'part') and
            sense.wordclass == 'NN')):
        if (word1_main_sense is not None and
                word1_main_sense.thesclass is not None):
            t = tdb.equivalent_class(word1_main_sense.thesclass,
                                     sense.wordclass)
            if t is not None:
                output.forced_result = t.wordclass_parent() or t
            output.forced_result = t
        return output

    # Special handling of 'pro-...' and 'anti-...'- we just return
    #   the wordclass branch equivalent to the first element
    if (sense.first_element() in ('pro', 'anti', 'un') and
            sense.wordclass in ('JJ', 'NN')):
        if (word2_main_sense is not None and
                word2_main_sense.thesclass is not None):
            t = tdb.equivalent_class(word2_main_sense.thesclass,
                                     sense.wordclass)
            if t is not None:
                output.forced_result = t.wordclass_parent() or t
        return output

    # Special handling of '...-shaped', '...-coloured', etc.
    if sense.last_element() in PARASYN_ENDINGS:
        output.forced_result = PARASYN_ENDINGS[sense.last_element()]
        return output

    # Special handling of cases where the Second element is single-sense
    #   (but don't risk this with upper-case forms or possible plurals)
    if (sense.wordclass == 'NN' and
            len(output.ranked_senses) == 1 and
            len(output.ranked_senses[0].classes) == 1 and
            output.ranked_senses[0].classes[0] is not None and
            sense.last_element().islower() and
            not re.search(r'[^s]s$', sense.last_element())):
        output.forced_result = output.ranked_senses[0].classes[0]
        return output

    #=====================================
    # Handler for regular cases (compute best guesses)
    #=====================================
    output.best_guesses = compute_best_guesses(sense, output)

    return output


def formal_compound_null_result():
    """
    Return a null CompoundAnalysisResult object
    """
    return CompoundAnalysisResult()


class CompoundAnalysisResult(object):

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            self.__dict__[key] = value

        self.best_guesses = []
        self.bayes_consensus = []
        self.index_consensus = []
        self.index_count = 0
        self.ranked_senses = []
        self.forced_result = None

    def __bool__(self):
        if self.best_guesses or self.bayes_consensus or self.forced_result:
            return True
        else:
            return False

    def best_guess(self):
        try:
            return self.best_guesses[0]
        except IndexError:
            return None

    def best_guess_thesclass(self):
        if self.best_guess() is not None:
            return self.best_guess().target
        else:
            return None

    def best_guess_class(self):
        return self.best_guess_thesclass()

    def bayes_filter(self, ratio):
        return self._ranking_filter(ratio, self.bayes_consensus)

    def index_filter(self, ratio):
        return self._ranking_filter(ratio, self.index_consensus)

    def _ranking_filter(self, ratio, ranked_list):
        if not ranked_list:
            return []
        else:
            max_value = ranked_list[0].consensus_score
            return [r for r in ranked_list
                    if r.consensus_score >= max_value * ratio]

    def trace(self):
        try:
            self.is_undefined
        except AttributeError:
            def_status = '?'
        else:
            if self.is_undefined:
                def_status = 'undefined'
            else:
                def_status = 'defined'

        lines = []
        lines.append('%s\t\t[%s]\t%d#eid%d' % (self.lemma, def_status,
            self.refentry, self.refid))
        lines.append('----------------')
        lines.append('BAYES CONSENSUS:')
        for b in self.bayes_filter(0.7):
            lines.append('\t%s (%0.2g)' % (b.breadcrumb(), b.consensus_score))
        lines.append('INDEX CONSENSUS (/%d):' % self.index_count)
        for k in self.index_consensus:
            lines.append('\t%s (%0.2g)' % (k.breadcrumb(), k.consensus_score))
        lines.append('LAST WORD SENSES:')
        for k in self.ranked_senses:
            lines.append('\t%s (%0.2g)' % (k.breadcrumb(), k.probability))
        lines.append('----------------')
        lines.append('BEST GUESSES:')
        for g in self.best_guesses:
            lines.append('\t%s (%d)' % (g.target.breadcrumb_short(), g.target.id))
            lines.append('\t\t[%s] (%0.2g/%0.2g --> %0.2g)' % (g.source,
                g.bayes_score(), g.target_score, g.combined_score()))
        if self.forced_result is not None:
            lines.append('FORCED:')
            lines.append('\t%s' % self.forced_result.breadcrumb_short())
        return '\n'.join(lines)


def rank_senses_for_last_element(sense):
    """
    Determine the most likely sense(s) of the last element
    """
    # By default we're agnostic about which entry it might come from
    #  (in the case of homographs)
    refentry, refid = (None, None)

    # If the last element is given as an etymon, this helps
    #   us to pin down the specific entry that it comes from
    for etymon in [etymon for etymon in sense.etyma
                   if etymon[0] == sense.last_element()]:
        refentry = etymon[1]

    # If the second element is also given as a cross-reference,
    #  this should point us to the right sense
    for xr in [xr for xr in sense.cross_references if
               xr.lemma == sense.last_element()]:
        refentry = xr.refentry
        refid = xr.refid

    return ranked_sense_summary(lemma=sense.last_element(),
                                wordclass=sense.wordclass,
                                refentry=refentry,
                                refid=refid,
                                current_only=True,
                                include_homographs=True,
                                level=3)
