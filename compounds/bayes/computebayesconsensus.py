

def compute_bayes_consensus(sense, bayes_modes):
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
