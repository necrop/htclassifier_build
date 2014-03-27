import itertools

import lex.oed.thesaurus.thesaurusdb as tdb
from resources.mainsense.mainsense import MainSense
from utils.tracer import trace_class, trace_instance, trace_sense

main_sense_finder = MainSense()


def triangulate_synonyms(sense):
    """
    Looks for commonalities between synonyms
    """
    if not sense.synonyms or len(sense.synonyms) == 1:
        return None

    match = None
    synonyms = sense.synonyms

    candidate_branches = []
    # Two rounds: round 1 restricts by subject, round 2 does not
    for round in (1, 2):
        if round == 1 and not sense.subjects:
            continue
        elif round == 1:
            kwargs = {'wordclass': sense.wordclass, 'subjects': sense.subjects}
        elif round == 2:
            kwargs = {'wordclass': sense.wordclass}
            if sense.bayes.confidence() >= 6:
                kwargs['branches'] = sense.bayes.ids()
        for comb_size in [i for i in (3, 2) if len(synonyms) >= i]:
            for combination in itertools.combinations(synonyms, comb_size):
                common_ancestor, perm = tdb.common_ancestor(combination, **kwargs)
                if (common_ancestor is not None and
                        (common_ancestor.wordclass is not None or
                        common_ancestor.level > 3)):
                    candidate_branches.append((common_ancestor, perm))
            if candidate_branches:
                break
        if candidate_branches:
            break

    # If there's more than one possible match, promote any that match the
    #  sense's Bayes classification
    if len(candidate_branches) > 1 and sense.topical_classification is not None:
        tmp = [c for c in candidate_branches if
               c[0].is_descendant_of(sense.topical_classification)]
        if tmp:
            candidate_branches = tmp

    if candidate_branches:
        branch, synonym_senses = sorted(candidate_branches,
            key=lambda cb: cb[0].branch_size)[0]
        # If the matching class is too high, pick a class lower down to match
        #  one of the synonyms
        if branch.wordclass is None:
            synonym_senses = list(synonym_senses)
            synonym_senses.sort(key=lambda s: s.branch_size(), reverse=True)
            branch = synonym_senses[0].thesclass.wordclass_parent()
        match = branch
    return match


def match_single_synonym(sense):
    # Drop out any highly polysemous synonyms
    synonyms = []
    for syn in sense.synonyms:
        instances = tdb.search(lemma=syn,
                               wordclass=sense.wordclass,
                               current_only=True)
        if tdb.distinct_senses(instances) < 20:
            synonyms.append(syn)

    if not synonyms:
        return None, None

    match = None
    matching_synonym = None

    # If the sense can be restricted by subject area, try to find a match for
    #  *any* synonym (even if there's only one)
    if not match and synonyms and sense.subjects:
        candidates = []
        for syn in synonyms:
            candidates.extend(tdb.ranked_search(lemma=syn,
                                                wordclass=sense.wordclass,
                                                subjects=sense.subjects,
                                                current_only=True))
        if candidates and candidates[0].thesclass is not None:
            match = candidates[0].thesclass
            matching_synonym = candidates[0].lemma

    # If the sense is an interjection, try to find a match for
    #  *any* synonym (even if there's only one) - since interjection
    #  synonyms are more reliable and less ambiguous
    if not match and synonyms and sense.wordclass == 'UH':
        candidates = []
        for syn in synonyms:
            candidates.extend(tdb.ranked_search(lemma=syn,
                                                wordclass='UH',
                                                current_only=True))
        if candidates and candidates[0].thesclass is not None:
            match = candidates[0].thesclass
            matching_synonym = candidates[0].lemma

    # If any of the synonyms are single-sense (or nearly single-sense),
    #  then we assume that that is the correct sense
    if not match:
        candidates = []
        for syn in synonyms:
            syn_senses = tdb.ranked_search(lemma=syn,
                                           wordclass=sense.wordclass,
                                           current_only=True)
            if (syn_senses and
                    (tdb.distinct_senses(syn_senses) == 1 or
                    (tdb.distinct_senses(syn_senses) <= 3 and
                    len(synonyms) == 1))):
                candidates.append(syn_senses[0])
        for c in candidates:
            if c.thesclass is not None:
                match = c.thesclass
                matching_synonym = c.lemma
                break

    # If the sense can be restricted by Bayes classification(s), try to
    #   find a match for *any* synonym (even if there's only one)
    if not match and synonyms and sense.bayes.is_usable():
        candidates = []
        for syn in synonyms:
            candidates.extend(tdb.ranked_search(lemma=syn,
                                                wordclass=sense.wordclass,
                                                branches=sense.bayes.ids(),
                                                current_only=True))
        if candidates and candidates[0].thesclass is not None:
            match = candidates[0].thesclass
            matching_synonym = candidates[0].lemma

    return match, matching_synonym


def synonym_main_sense(sense):
    """If the sense is not subject-specific, we just pick the main sense
    of one of the synonyms.

    This is risky, so this function should only be used as a last-gasp
    effort.
    """
    if (len(sense.synonyms) == 1 and
            not sense.subjects and
            sense.bayes.confidence() <= 6):
        target_sense = main_sense_finder.main_sense(lemma=sense.synonyms[0],
            wordclass=sense.wordclass)
        if target_sense is not None and target_sense.thesclass is not None:
            match = target_sense.thesclass
            return match, sense.synonyms[0]
    return None, None

