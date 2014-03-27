
import lex.oed.thesaurus.thesaurusdb as tdb
from utils.tracer import trace_sense


def apply_bayes_filter(sense, candidate_classifications, mode='filter'):
    """
    Filter candidate classifications so that only those which match
    Bayes classifications get through.
    """
    # Don't attempt if:
    #  - the candidate_classifications list is empty;
    #  - it's a derivative sense (Bayes can often be off for these);
    #  - it's a split definition (ditto).
    if (not candidate_classifications or
        sense.subentry_type == 'derivative' or
        sense.is_affix_subentry() or
        sense.is_split_definition()):
        return candidate_classifications

    # Include branches based on compound analysis
    if sense.compound_analysis:
        compound_branches = [c.thesclass() for c in
                             sense.compound_analysis.bayes_consensus]
    else:
        compound_branches = []

    if mode == 'filter':
        # Wide sieve
        candidate_classifications = _apply_wide_sieve(sense,
            candidate_classifications, compound_branches)

    if mode == 'promote':
        # Stricter constraints
        candidate_classifications = _apply_promotion(sense,
            candidate_classifications, compound_branches)

    return candidate_classifications


def _apply_wide_sieve(sense, candidate_classifications, compound_branches):
    """
    Apply a wide sieve - only filter out classifications which don't
    match *any* of the Bayes classifications.
    """
    # Bail out if Bayes confidence is not high enough
    if sense.bayes.confidence() < 5:
       return candidate_classifications

    # We're going to be generous at this stage; so we get
    #  a set of branches that includes *all* the branches
    #  stored as output from the Bayes classifier. Hence we set
    #  the total probability > 1 (to err on the safe side).
    filter = sense.bayes.branches(total_probability=1.2) +\
        compound_branches + sense.subject_classes()
    filter = tdb.remove_redundant_classes(filter)

    favoured = [c for c in candidate_classifications
                if any([c.is_descendant_of(b) for b in filter])]
    return favoured

def _apply_promotion(sense, candidate_classifications, compound_branches):
    """
    Reorganize the list of candidate_classifications so that those that
    pass the constraints are at the top, and those that fail the constraints
    are at the bottom.

    Order is preserved otherwise.
    """
    # Bail out if Bayes confidence is not high enough
    if sense.bayes.confidence() < 8:
       return candidate_classifications
    # Bail out if classification is based on an '='-type cross-reference
    if candidate_classifications[0].reason_code == 'eqxr':
        return candidate_classifications

    # Build the set of branches to use as a filter
    filter = sense.bayes.branches(total_probability=.99) +\
        sense.subject_classes()

    filter = tdb.remove_redundant_classes(filter)

    favoured = []
    deprecated = []
    for c in candidate_classifications:
        if any([c.is_descendant_of(b) for b in filter]):
            favoured.append(c)
        else:
            deprecated.append(c)
    #if favoured and deprecated:
    #    z = [c.id for c in favoured + deprecated]
    #    k = [c.id for c in candidate_classifications]
    #    if z != k:
    #        print(trace_sense(sense))
    #        for c in filter:
    #            print('CONSTRAINT:' + c.breadcrumb())
    #        print '\n'
    #        for c in candidate_classifications:
    #            print(c.breadcrumb())
    #        print '\n'
    #        for c in favoured + deprecated:
    #            print('>>> ' + c.breadcrumb())
    return favoured + deprecated
