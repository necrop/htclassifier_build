"""
topical_classification

Figures out a high-level topical classification, based either
on explicit subject labels or on Bayesian classification.
"""

# To be usable as an end result, a Bayes classification must be at
#  or below this level...
bayes_min_level = 4
# ... or below this size
bayes_max_size = 10000


def topical_classification(sense):
    """
    Figure out a high-level topical classification, based either
    on explicit subject labels or on Bayesian classification.
    """
    labelled_topics = sense.subject_classes()

    # Bayes-based classifications
    bayes_based_classes = set()
    for b in sense.bayes.branches():
        # Look for label-based classifications which might help to refine
        #  a more general Bayes-based classification
        descendants = [t for t in labelled_topics
                       if t == b or t.is_descendant_of(b)]
        for d in descendants:
            bayes_based_classes.add(d)
        if not descendants:
            bayes_based_classes.add(b)
    bayes_based_classes = list(bayes_based_classes)

    # Subject-label-based classifications
    if sense.bayes.confidence() <= 3:
        label_based_classes = list(labelled_topics)
    else:
        # Get subject-label-based categorizations which match the
        #   broad Bayes classifications
        # - Find broad (hgh-level) branches covered by the Bayes categories
        bayes_based_broad_categories = set(
            [t.id for t in sense.bayes.ancestors(level=2)])
        # - Then look for labels which fall within these branches
        if bayes_based_broad_categories:
            label_based_classes = [t for t in labelled_topics if
                                   t.ancestor(level=2).id in
                                   bayes_based_broad_categories]
        else:
            label_based_classes = list(labelled_topics)

    # Sort so that the most general (largest) is at the top
    bayes_based_classes.sort(key=lambda t: t.branch_size, reverse=True)
    label_based_classes.sort(key=lambda t: t.branch_size, reverse=True)

    # Pick the overall winner
    if (bayes_based_classes and sense.bayes.confidence() >= 3 and
        (sense.bayes.confidence() >= 7 or not label_based_classes)):
        winner = bayes_based_classes[0]
    elif label_based_classes:
        winner = label_based_classes[0]
    else:
        winner = None

    # If the winner is not specific enough, see if it can be replaced by a
    #  runner-up further down the same branch
    if (winner is not None and
            not winner.is_specific_enough(level=bayes_min_level, size=bayes_max_size)):
        desc1 = [t for t in label_based_classes if
                 t.is_descendant_of(winner) and
                 t.is_specific_enough(level=bayes_min_level, size=bayes_max_size)]
        desc2 = [t for t in bayes_based_classes if
                 t.is_descendant_of(winner) and
                 t.is_specific_enough(level=bayes_min_level, size=bayes_max_size)]
        if sense.bayes.confidence() >= 8:
            descendants = desc2 + desc1
        else:
            descendants = desc1 + desc2
        if descendants:
            winner = descendants[0]

    return winner, bayes_based_classes, label_based_classes
