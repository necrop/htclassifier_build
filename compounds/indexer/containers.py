
"""
Containers:
-- WordSet
-- Level3Set
-- WordclassLevelSet

Hierarchical classes used for the pickled objects
 (Each <WordSet> contains one or more <Level3Set>s, which
 in turn contains one or more <WordclassLevelSet>s)
"""

import lex.oed.thesaurus.thesaurusdb as tdb


class WordSet(object):

    def __init__(self, word, wordclass, count, data):
        self.word = word
        self.wordclass = wordclass
        self.count = count
        self.branches = [Level3Set(row) for row in data]

    def trace(self):
        print(self.word, '\t%s\t(%d)' % (self.wordclass, self.count))
        for branch in self.branches:
            print('\t%s %d (%0.3g)' % (branch.breadcrumb(),
                                       branch.count,
                                       branch.probability(self.count)))
            for child in branch.child_nodes:
                print('\t\t', child.breadcrumb(), child.count)

    def find_branch_by_id(self, target_id):
        for b in self.branches:
            if int(b.id) == int(target_id):
                return b
        return None

    def combined_probabilities(self, other):
        """
        For each branch in self, calculate the combined probability of the
        branch by adding together the probabilities of self and other
        (the first and second words in the compound)
        """
        if other is None:
            for b in self.branches:
                b.consensus_score = b.probability(self.count)
            probabilities = self.branches[:]
        else:
            # Probability value that will be used when a given branch does
            # not occur in other at all - calculated to be lower than the
            # lowest value in other
            other_default_probability = 0.5 / other.count

            for b in self.branches:
                b_other = other.find_branch_by_id(b.id)
                if b_other is not None:
                    other_probability = b_other.probability(other.count)
                else:
                    other_probability = other_default_probability
                combined_prob = b.probability(self.count) + other_probability
                b.consensus_score = combined_prob
            probabilities = self.branches[:]

        # Sort so that the highest probability is first
        probabilities.sort(key=lambda row: row.consensus_score, reverse=True)
        # Recalculate probabilities as ratios (x/1)
        total = sum([row.consensus_score for row in probabilities])
        for row in probabilities:
            row.consensus_score = row.consensus_score / total

        return probabilities


class Level3Set(object):

    def __init__(self, n):
        l3_node, count, child_nodes = n
        self.id = l3_node.id
        self.count = count
        self.child_nodes = [WordclassLevelSet(n, self.count)
                            for n in child_nodes]

    def node(self):
        try:
            return self._node
        except AttributeError:
            self._node = tdb.get_thesclass(self.id)
            return self._node

    def thesclass(self):
        return self.node()

    def breadcrumb(self):
        return self.node().breadcrumb()

    def probability(self, total):
        """
        Calculate the probability of this branch (as a ratio of its
        count to the total counts of all branches)
        """
        return self.count / total

    def first_child_node(self):
        return self.child_nodes[0]


class WordclassLevelSet(object):

    def __init__(self, n, total_count):
        wordclass_node, count, best_node = n
        self.id = wordclass_node.id
        self.count = count
        self.exact_id = best_node.id
        self.ratio = count / total_count

    def node(self):
        try:
            return self._node
        except AttributeError:
            self._node = tdb.get_thesclass(self.id)
            return self._node

    def thesclass(self):
        return self.node()

    def breadcrumb(self):
        return self.node().breadcrumb()

    def probability(self, total):
        return self.count / total

    def exact_node(self):
        try:
            return self._exact_node
        except AttributeError:
            self._exact_node = tdb.get_thesclass(self.exact_id)
            return self._exact_node
