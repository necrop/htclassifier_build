
from collections import namedtuple

import lex.oed.thesaurus.thesaurusdb as tdb

from .compoundderivative import compound_derivative

Target = namedtuple('Target', ['node', 'score', 'source', 'ratio'])


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
        return self.bayes_score() + self.target_score

    #def combined_score(self):
    #    if not self.bayes_score():
    #        return self.target_score
    #    else:
    #        return self.bayes_score()


def compute_best_guesses(sense, output):
    best_guesses = []

    # Try looking for cases where the Bayes evaluation coincides
    #  with the compounds index for the second element or with
    #  the ranked senses of the second element
    for bayes in output.bayes_filter(0.7):
        # Look for matches between the Bayes class and uses of the
        #  second element.
        # First try the compounds index for the second element...
        target_from_cindex = None
        for cindex in output.index_consensus:
            if cindex.thesclass().is_same_branch(bayes.thesclass()):
                for child in cindex.child_nodes[0:3]:
                    if child.thesclass().is_descendant_of(bayes.thesclass()):
                        target_from_cindex = Target(
                            node=child.exact_node(),
                            score=cindex.consensus_score,
                            source='Bayes + compound index',
                            ratio=child.ratio,
                        )
                        break
            if target_from_cindex is not None:
                break
        # ... and then try the ranked senses of the second element
        target_from_ranked_senses = None
        for j in output.ranked_senses:
            if (j.parent is not None and
                    j.parent.is_same_branch(bayes.thesclass()) and
                    j.classes[0].is_descendant_of(bayes.thesclass())):
                target_from_ranked_senses = Target(
                    node=_target_from_ranked_sense(j),
                    score=j.probability,
                    source='Bayes + ranked senses',
                    ratio=None,
                )
                break

        # If matches have been found from *both* the compounds index *and*
        #  the ranked senses, we need to decide which to use:
        target = None
        if (target_from_cindex is not None and
                target_from_ranked_senses is not None):
            # If the two matches point to roughly the same class, we prefer
            #  the compound-index version
            if (target_from_ranked_senses.node.wordclass_parent().id ==
                    target_from_cindex.node.wordclass_parent().id):
                target = target_from_cindex
            # If the compound-index version is too scattered (i.e. the
            #  target class has too low a ratio to the total set of classes),
            #  then we prefer the ranked-sense version
            elif (target_from_cindex.ratio < 0.2 and
                    target_from_ranked_senses.score > 0.1):
                target = target_from_ranked_senses
            # ... Otherwise, we default to using the compound-index version
            else:
                target = target_from_cindex
        else:
            target = target_from_cindex or target_from_ranked_senses or None

        # Turn the match into a BestGuess object, and add this to
        #  the best_guesses list
        if target:
            best_guesses.append(BestGuess(bayes, target.node,
                                          target.score, target.source))

    # If no best guess has been found, fall back to using senses of
    #  the second element
    if not best_guesses:
        for j in [j for j in output.ranked_senses if j.parent is not None]:
            target = _target_from_ranked_sense(j)
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

    best_guesses = _append_derivational_classification(best_guesses, sense)


    # Remove duplicates
    best_guesses_uniq = []
    seen = set()
    for g in best_guesses:
        if g.target.id not in seen:
            best_guesses_uniq.append(g)
            seen.add(g.target.id)

    return best_guesses_uniq


def _target_from_ranked_sense(sense):
    return (sense.classes[0].wordclass_parent_plus_one() or
            sense.classes[0].wordclass_parent() or
            sense.classes[0])


def _append_derivational_classification(best_guesses, sense):
    """
    If the compound is a derivative of another compound, prepend or append a
    classification based on the root form
    """
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
    return best_guesses
