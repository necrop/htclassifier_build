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
from .compoundderivative import compound_derivative
from .indexer.compoundindexretriever import retrieve_from_compound_index
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


class FormalCompoundAnalysis(object):

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            self.__dict__[k] = v

    def null_result(self):
        """
        Return a null CompoundAnalysisResult object
        """
        return CompoundAnalysisResult()

    def analyse(self, sense, entry_main_sense):
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
            return self.null_result()

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
        output.bayes_consensus = bayes_consensus(sense, bayes_modes)[0:10]

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

        # Establish the main sense of the first and last words
        word1_main_sense = entry_main_sense
        word2_main_sense = MAIN_SENSE_FINDER.main_sense(
            lemma=sense.last_element(), wordclass=sense.wordclass)

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


class CompoundAnalysisResult(object):

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            self.__dict__[key] = value

        self.best_guesses = []
        self.bayes_consensus = []
        self.index_consensus = []
        self.ranked_senses = []
        self.forced_result = None

    def __bool__(self):
        if self.best_guesses or self.bayes_consensus or self.forced_result:
            return True
        else:
            return False

    def best_guess(self):
        if self.best_guesses:
            return self.best_guesses[0]
        else:
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

    def trace(self, **kwargs):
        sanitize = kwargs.get('sanitize', False)

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
        lines.append('INDEX CONSENSUS:')
        for k in self.index_consensus:
            lines.append('\t%s (%0.2g)' % (k.breadcrumb(), k.consensus_score))
        lines.append('LAST WORD SENSES:')
        for k in self.ranked_senses:
            lines.append('\t%s (%0.2g)' % (k.breadcrumb(), k.probability))
        lines.append('----------------')
        lines.append('BEST GUESSES:')
        for g in self.best_guesses:
            lines.append('\t%s (%d)' % (g.target.breadcrumb_short(), g.target.id))
            lines.append('\t\t[%s] (%0.2g/%0.2g/%0.2g)' % (g.source,
                g.bayes_score(), g.target_score, g.combined_score()))
        if self.forced_result is not None:
            lines.append('FORCED:')
            lines.append('\t%s' % self.forced_result.breadcrumb_short())

        if sanitize:
            lines = [re.sub(r'[^a-zA-Z0-9.,:;()<> \[\]\t/#+-]', '?', l)
                for l in lines]

        return '\n'.join(lines)


class BestGuess(object):

    def __init__(self, bayes, target, target_score, source):
        self.bayes = bayes
        self.target = target
        self.target_score = target_score
        self.source = source

    def bayes_score(self):
        if self.bayes is None:
            return 0
        else:
            return self.bayes.consensus_score

    def combined_score(self):
        if not self.bayes_score():
            return self.target_score
        else:
            return self.bayes_score()


def bayes_consensus(sense, bayes_modes):
    consensus = {}
    for mode in bayes_modes:
        if sense.bayes.is_usable(mode=mode):
            for r in sense.bayes.filtered_results(mode=mode):
                identifier = r.id
                if identifier not in consensus:
                    # Add an attribute to track the consensus score
                    r.consensus_score = 0
                    consensus[identifier] = r
                score = r.posterior_probability
                # Tweak the score depending on the confidence level of
                #  the Bayes result - bearing in mind that the main
                #  Bayes result will tend to have higher confidence than
                #  than the compound Bayes result
                if sense.bayes.confidence(mode=mode) <= 3:
                    score *= 0.7
                elif sense.bayes.confidence(mode=mode) >= 8:
                    score *= 1.3
                consensus[identifier].consensus_score += score

    # Reduce to a list
    consensus = consensus.values()

    # Ditch a level-2 class if there's a level-3/-4 class with roughly
    #  the same score...
    level2 = [r for r in consensus if r.thesclass().level == 2]
    level34 = [r for r in consensus if r.thesclass().level == 3 or
        r.thesclass().level == 4]
    delete_set = set()
    for r2 in level2:
        for r34 in level34:
            if (r34.thesclass().is_descendant_of(r2.thesclass()) and
                    (r34.consensus_score > r2.consensus_score or
                    r34.consensus_score / r2.consensus_score > 0.8)):
                delete_set.add(r2.id)
    consensus = [r for r in consensus if r.id not in delete_set]

    # ...and ditch a level-3 class if there's a level-4 class with roughly
    #  the same score
    level3 = [r for r in consensus if r.thesclass().level == 3]
    level4 = [r for r in consensus if r.thesclass().level == 4]
    delete_set = set()
    for r3 in level3:
        for r4 in level4:
            if (r4.thesclass().parent.id == r3.id and
                    (r4.consensus_score > r3.consensus_score or
                    r4.consensus_score / r3.consensus_score > 0.8)):
                delete_set.add(r3.id)
    consensus = [r for r in consensus if r.id not in delete_set]

    # Convert scores to relative probabilities
    total = sum([r.consensus_score for r in consensus])
    for r in consensus:
        r.consensus_score = r.consensus_score / total
    # Sort so that the highest-scoring is first
    consensus.sort(key=lambda r: r.consensus_score, reverse=True)

    return consensus


def compute_best_guesses(sense, output):
    def target_from_ranked_sense(s):
        return (s.classes[0].wordclass_parent_plus_one() or
                s.classes[0].wordclass_parent() or
                s.classes[0])

    best_guesses = []

    # Try looking for cases where the Bayes evaluation coincides
    #  with the compounds index for the second element or with
    #  the ranked senses of the second element
    for bayes in output.bayes_filter(0.7):
        # Look for matches between the Bayes class and uses of the
        #  second element...
        # ...first try the compounds index for the second element...
        target_from_cindex = None
        for cindex in output.index_consensus:
            if cindex.thesclass().is_same_branch(bayes.thesclass()):
                for child in cindex.child_nodes[0:3]:
                    if child.thesclass().is_descendant_of(bayes.thesclass()):
                        target_from_cindex = {
                            'node': child.exact_node(),
                            'score': cindex.consensus_score,
                            'source': 'Bayes + compound index',
                            'ratio': child.ratio, }
                        break
            if target_from_cindex is not None:
                break
        # ... and then try the ranked senses of the second element
        target_from_ranked_senses = None
        for j in output.ranked_senses:
            if (j.parent is not None and
                    j.parent.is_same_branch(bayes.thesclass()) and
                    j.classes[0].is_descendant_of(bayes.thesclass())):
                target_from_ranked_senses = {
                    'node': target_from_ranked_sense(j),
                    'score': j.probability,
                    'source': 'Bayes + ranked senses', }
                break

        # If matches have been found from *both* the compounds index *and*
        #  the ranked senses, we need to decide which to use:
        t = None
        if (target_from_cindex is not None and
                target_from_ranked_senses is not None):
            # If the two matches point to roughly the same class, we prefer
            #  the compound-index version
            if (target_from_ranked_senses['node'].wordclass_parent().id ==
                    target_from_cindex['node'].wordclass_parent().id):
                t = target_from_cindex
            # If the compound-index version is too scattered (i.e. the
            #  target class has too low a ratio to the total set of classes),
            #  then we prefer the ranked-sense version
            elif (target_from_cindex['ratio'] < 0.2 and
                    target_from_ranked_senses['score'] > 0.1):
                t = target_from_ranked_senses
            # ... Otherwise, we default to using the compound-index version
            else:
                t = target_from_cindex
        else:
            t = target_from_cindex or target_from_ranked_senses or None

        # Turn the match into a BestGuess object, and add this to
        #  the best_guesses list
        if t is not None:
            best_guesses.append(BestGuess(bayes, t['node'], t['score'], t['source']))

    # If no best guess has been found, fall back to using senses of
    #  the second element
    if not best_guesses:
        for j in [j for j in output.ranked_senses if j.parent is not None]:
            target = target_from_ranked_sense(j)
            target_score = j.probability
            source = 'ranked senses'
            best_guesses.append(BestGuess(None, target, target_score, source))

    # ... and failing that, fall back to using the compound index
    #  for the second element
    if not best_guesses:
        for cindex in output.index_consensus:
            target = cindex.child_nodes[0].exact_node()
            target_score = cindex.consensus_score
            source = 'compound index'
            best_guesses.append(BestGuess(None, target, target_score, source))

    # Sort so that the highest-scoring is first
    best_guesses.sort(key=lambda g: g.combined_score(), reverse=True)

    # Make sure we haven't picked up any null classes along the way
    #  (this shouldn't happen, but we put a safeguard in just in case)
    best_guesses = [g for g in best_guesses if g.target is not None]

    # If the compound is a derivative of another compound, prepend a
    #  classification based on the root form
    base_compound_class, insert_position = compound_derivative(sense)
    if base_compound_class is not None:
        equiv = tdb.equivalent_class(base_compound_class, sense.wordclass)
        if (equiv is not None and
                equiv.wordclass is not None and
                not any([b.target.is_descendant_of(equiv) for b in best_guesses])):
            # Create a new derivative-based guess object
            #   Give it a dummy score, calculated to be higher or lower
            #   than the set of existing guesses
            if not best_guesses:
                score = 1
            elif insert_position == 'first':
                score = best_guesses[0].target_score * 1.1
            else:
                score = best_guesses[-1].target_score * 0.9
            new_guess = BestGuess(None, equiv, score, 'derivative')
            # ... and prepend/append it to the best_guesses list
            if insert_position == 'first':
                best_guesses.insert(0, new_guess)
            elif insert_position == 'last':
                best_guesses.append(new_guess)

    # Remove duplicates
    best_guesses_uniq = []
    seen = set()
    for g in best_guesses:
        if g.target.id not in seen:
            best_guesses_uniq.append(g)
            seen.add(g.target.id)

    return best_guesses_uniq


def rank_senses_for_last_element(sense):
    # By default we're agnostic about which entry it might come from
    #  (in the case of homographs)
    refentry, refid = (None, None)

    #   (If the last element is given as an etymon, this helps
    #   us to pin down the specific entry that it comes from)
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
