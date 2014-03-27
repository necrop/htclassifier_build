"""
Superordinates
"""

import re

import lex.oed.thesaurus.thesaurusdb as tdb
from lex.oed.thesaurus.dbbackend.subjectmapper import SubjectMapper
from resources.mainsense.mainsense import MainSense
from utils.tracer import trace_sense, trace_instance, trace_class

# Generic superordinates - can't do anything with these.
GENERICS = {'person', 'thing', 'man', 'woman', 'action', 'act', 'quality',
            'condition', 'state', 'process', 'place', 'point'}

FOLLOWING_WORDS = {'NULL', 'or', 'as', 'who', 'which', 'where', 'that',
                   'given', 'made', 'held', 'worn', 'for', 'at', 'in',
                   'with', 'without'}
MAIN_SENSE_FINDER = MainSense()
SUBJECT_MAPPER = SubjectMapper()


class Superordinates(object):

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            self.__dict__[k] = v

    def is_generic(self, superordinate):
        if superordinate in GENERICS:
            return True
        else:
            return False

    def is_in_neutral_context(self, sense):
        if (sense.superordinate_tail is not None and
                isinstance(sense.superordinate_tail, str) and
                (sense.superordinate_tail in FOLLOWING_WORDS or
                re.search(r'^[a-z]+(ed|ing)$', sense.superordinate_tail))):
            return True
        else:
            return False

    def find_branch_from_superordinate(self, sense):
        """Classify by finding the main or only sense of the superordinate
        """
        if (sense.wordclass not in ('NN', 'JJ') or
                not sense.superordinate or
                len(sense.superordinate) < 3 or
                sense.superordinate in GENERICS):
            return None

        target_sense = None

        # If the superordinate is (more or less) single-sense, we assume that
        #  sense to be the correct one
        candidates = tdb.ranked_search(
            lemma=sense.superordinate,
            wordclass='NN',
            current_only=True)
        if candidates and tdb.distinct_senses(candidates) <= 2:
            target_sense = candidates[0]

        # Otherwise, narrow by Bayes classification
        if target_sense is None and sense.bayes.confidence() >= 8:
            target_sense = tdb.highest_ranked(
                lemma=sense.superordinate,
                wordclass='NN',
                branches=sense.bayes_based_classifications,
                current_only=True)

        # Otherwise, narrow by branches based on subject labels
        if target_sense is None and sense.label_based_classifications:
            target_sense = tdb.highest_ranked(
                lemma=sense.superordinate,
                wordclass='NN',
                branches=sense.label_based_classifications,
                current_only=True)

        # Otherwise, narrow by branches based on cross-references
        if target_sense is None and sense.xref_branches:
            target_sense = tdb.highest_ranked(
                lemma=sense.superordinate,
                wordclass='NN',
                branches=sense.xref_branches,
                current_only=True)

        # Last gasp: If the gloss consists more or less *only* of the
        #   superordinate (e.g. 'an abbey'), then it should be adequate to
        #   just use the main sense of the superordinate, even if it's
        #   multi-sense.
        # But don't risk this is there are cross-references or subject
        #   labels which might suggest a more specific use
        if (target_sense is None and not sense.subjects and
            not sense.xref_branches and sense.gloss is not None):
            g = re.sub(r'^(a|an|the) ', '', sense.gloss.lower())
            if g == sense.superordinate:
                target_sense = MAIN_SENSE_FINDER.main_sense(
                    lemma=sense.superordinate, wordclass='NN')

        # Otherwise, narrow by Bayes classification
        if target_sense is None and sense.bayes.is_usable():
            target_sense = tdb.highest_ranked(
                lemma=sense.superordinate,
                wordclass='NN',
                branches=sense.bayes_based_classifications,
                current_only=True)

        if target_sense is not None and target_sense.thesclass is not None:
            match = target_sense.thesclass
            if sense.wordclass == 'JJ':
                match = tdb.equivalent_class(match, 'JJ')
            return match
        else:
            return None

    def superordinate_lookup(self, sense, panic=False):
        """
        Classify by looking up how other senses with the same superordinate
        have been classified.
        """
        # Get all the branches relevant for this sense's long and/or short
        #  superordinate.
        branches = []
        superordinates = [sense.superordinate_full,]
        if sense.superordinate != sense.superordinate_full:
            superordinates.append(sense.superordinate)
        seen = set()
        for superordinate in [s for s in superordinates if s is not None]:
            superordinate = superordinate.replace('-', '').replace(' ', '')
            record = tdb.get_superordinate_record(superordinate)
            if record is not None:
                for b in record.branches:
                    if b.thesclass.id not in seen:
                        branches.append(b)
                        seen.add(b.thesclass.id)

        if branches:
            branches_filtered = []
            if panic:
                branches_filtered = [b for b in branches if b.probability > 0.4]
            else:
                xref_nodes = set(sense.xref_branches)
                branches_filtered = [b for b in branches if
                    set.intersection(b.thesclass.ancestor_ids(), xref_nodes)]

                if not branches_filtered and sense.bayes.confidence() >= 4:
                    bayes_ids = set(sense.bayes.ids())
                    branches_filtered = [b for b in branches if
                        set.intersection(b.thesclass.ancestor_ids(), bayes_ids)]

                if not branches_filtered and sense.bayes.confidence() >= 4:
                    # Try again with the Bayes classifications, but this
                    #  time just use their level-3 parents
                    bayes_ids = set([b.ancestor(level=3).id for b in
                                     sense.bayes.branches()
                                     if b.ancestor(level=3) is not None])
                    branches_filtered = [b for b in branches if
                                         set.intersection(
                                         b.thesclass.ancestor_ids(), bayes_ids)]

            if branches_filtered:
                # Find the best branch below wordclass level, or failing that,
                #   above wordclass level
                wc_branches = [b for b in branches_filtered if
                    b.thesclass.wordclass is not None] or branches_filtered
                wc_branches.sort(key=lambda b: b.probability, reverse=True)
                winning_branch = wc_branches[0].thesclass

                # If this is a compound, see if we can get more specific
                #   by finding an instance of the second element within the
                #   winning branch.
                # (Fairly unlikely, since most of these should already
                #   have been picked off by the compound classifiers.)
                if sense.last_element() is not None:
                    subclass = tdb.highest_ranked(lemma=sense.last_element(),
                                                  wordclass=sense.wordclass,
                                                  branches=[winning_branch.id,])
                    if (subclass is not None and
                        subclass.thesclass is not None):
                        winning_branch = subclass.thesclass

                return winning_branch

        return None

    def superordinate_adjective_state(self, sense):
        if sense.superordinate is not None:
            m = re.search(r'^state of being ([a-z-]+)-JJ$', sense.superordinate)
            if m is None:
                m = re.search(r'^being ([a-z-]+)-JJ state$', sense.superordinate)
            if m is not None:
                adjective = m.group(1)
                target_sense = MAIN_SENSE_FINDER.main_sense(lemma=adjective,
                                                            wordclass='JJ')
                if (target_sense is not None and
                    target_sense.thesclass is not None):
                    return tdb.equivalent_class(target_sense.thesclass, 'NN')
        return None
