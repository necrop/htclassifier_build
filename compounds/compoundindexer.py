"""
CompoundIndexer
"""

import os
import csv
import string
import pickle
from collections import defaultdict, Counter

from regexcompiler import ReplacementListCompiler
import lex.oed.thesaurus.thesaurusdb as tdb
from pickler.sensemanager import PickleLoader

WORDCLASSES = ('NN', 'JJ', 'RB', 'first')

LIGHT_STEMMER = ReplacementListCompiler((
    (r'(y|ies|ie)$', r'i'),
    (r'sses$', r'ss'),
    (r'([^s])s$', r'\1'),
))


class CompoundIndexer(object):

    """
    Processes for compilation of the compound indexes
    """
    index = {}

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            self.__dict__[k] = v
        if kwargs.get('resources_dir'):
            self.dir = os.path.join(self.resources_dir, 'compounds', 'clusters')
        else:
            self.dir = None

    def make_raw_index(self):
        store = {v: defaultdict(list) for v in WORDCLASSES}
        for letter in string.ascii_uppercase:
            print('\tIndexing compound elements in %s...' % letter)
            loader = PickleLoader(self.input_dir, letters=letter)
            for s in loader.iterate():
                if (s.wordclass in WORDCLASSES and
                        s.first_word() is not None and
                        s.last_word() is not None):
                    first = s.first_word()
                    last = s.last_word()
                    if first in ('non', 'anti', 'to'):
                        pass
                    else:
                        if len(last) >= 3:
                            last = LIGHT_STEMMER.edit(last.lower())
                            for leaf in s.thesaurus_nodes:
                                store[s.wordclass][last].append(leaf)
                        if len(first) >= 3:
                            first = LIGHT_STEMMER.edit(first.lower())
                            for leaf in s.thesaurus_nodes:
                                store['first'][first].append(leaf)

        for wordclass in WORDCLASSES:
            filepath = os.path.join(self.dir, wordclass + '_raw.csv')
            with open(filepath, 'w') as filehandle:
                csvwriter = csv.writer(filehandle)
                for lemma in sorted(store[wordclass].keys()):
                    vals = store[wordclass][lemma]
                    if wordclass == 'first' and len(vals) == 1:
                        pass
                    else:
                        row = [lemma,]
                        row.extend(vals)
                        csvwriter.writerow(row)

    def refine_index(self):
        for wordclass in WORDCLASSES:
            print('\tRefining compound index %s...' % wordclass)
            in_file = os.path.join(self.dir, wordclass + '_raw.csv')
            out_file = os.path.join(self.dir, wordclass)

            compound_words = []
            with open(in_file, 'r') as filehandle:
                csvreader = csv.reader(filehandle)
                for row in csvreader:
                    g = row.pop(0)
                    ids = [int(id) for id in row]
                    compound_words.append((g, ids))

            output = []
            for word, ids in compound_words:
                count, data = winnow(ids, wordclass)
                j = WordSet(word, wordclass, count, data)
                output.append(j)

            # Output file for pickled objects
            with open(out_file, 'wb') as filehandle:
                for o in output:
                    pickle.dump(o, filehandle)

    def load_data(self):
        CompoundIndexer.index = {}
        for wordclass in WORDCLASSES:
            file = os.path.join(self.dir, wordclass)
            results = []
            with open(file, 'rb') as filehandle:
                while 1:
                    try:
                        results.append(pickle.load(filehandle))
                    except EOFError:
                        break
            CompoundIndexer.index[wordclass] = {r.word: r for r in results}

    def find(self, word, wordclass):
        if not CompoundIndexer.index:
            self.load_data()
        word = LIGHT_STEMMER.edit(word.lower())
        if (wordclass in CompoundIndexer.index and
                word in CompoundIndexer.index[wordclass]):
            return CompoundIndexer.index[wordclass][word]
        else:
            return None


#=========================================================
# Hierarchical classes used for the pickled objects
#  (Each <WordSet> contains one or more <Level3Set>s, which
#  in turn contains one or more <WordclassLevelSet>s)
#=========================================================

class WordSet(object):

    def __init__(self, word, wordclass, count, data):
        self.word = word
        self.wordclass = wordclass
        self.count = count
        self.branches = [Level3Set(row) for row in data]

    def trace(self):
        print(repr(self.word), '\t%s\t(%d)' % (self.wordclass, self.count))
        for branch in self.branches:
            print('\t%s %d (%0.3g)' % (branch.breadcrumb(), branch.count,
                branch.probability(self.count)))
            for child in branch.child_nodes:
                print('\t\t', child.breadcrumb(), child.count)

    def find_branch_by_id(self, target_id):
        for b in self.branches:
            if int(b.id) == int(target_id):
                return b
        return None

    def combined_probabilities(self, other):
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
        # Recalculate probabilities so that they're a ratio to 1
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


def winnow(class_ids, wordclass):
    # Convert thesaurus IDs stored in the raw files to actual thesaurus classes
    thesclasses = [tdb.get_thesclass(id) for id in class_ids]
    if wordclass == 'NN':
        thesclasses = [t for t in thesclasses if t.wordclass == 'noun']
    elif wordclass == 'JJ':
        thesclasses = [t for t in thesclasses if t.wordclass == 'adjective']
    elif wordclass == 'RB':
        thesclasses = [t for t in thesclasses if t.wordclass == 'adverb']

    # Keep a note of the total number of instances of this word in compounds
    # (before we start winnowing out stuff)
    total = len(thesclasses)

    # Group into wordclass-level parent classes
    wordclass_groups = {}
    for t in thesclasses:
        p = t.wordclass_parent() or t
        if not p.id in wordclass_groups:
            wordclass_groups[p.id] = (p, [])
        wordclass_groups[p.id][1].append(t)
    # Reduce to a list of (parent_node, child_nodes) tuples
    wordclass_groups = list(wordclass_groups.values())
    # Sort so that the most common is first
    wordclass_groups.sort(key=lambda row: row[0].level)
    wordclass_groups.sort(key=lambda row: len(row[1]), reverse=True)

    # For each wordclass group, find the best child node to use
    #  (which may often be the wordclass node itself)
    wordclass_groups2 = []
    for parent_node, child_nodes in wordclass_groups:
        # If there's only one child node, or if any of the child nodes
        #  are at wordclass level, then we'll just use the wordclass level
        if (len(child_nodes) == 1 or
            any([t.id == parent_node.id for t in child_nodes])):
            best_child = parent_node
        # If all the children are on the same node, then we'll use that node
        elif len(set([t.id for t in child_nodes])) == 1:
            best_child = child_nodes[0]
        # ... Otherwise, poll to find the leading one out of the classes
        #  below wordclass level
        else:
            best_child = None
            for depth in (2, 1):
                # Find the level immediately below the parent wordclass level
                sub_parent_level = parent_node.level + depth
                # ... and count how many children are on each branch at this level
                counts = Counter([t.ancestor(level=sub_parent_level)
                    for t in child_nodes]).most_common()
                max_count = counts[0][1]
                if max_count >= len(child_nodes) * 0.8:
                    best_child = counts[0][0]
                elif depth == 1:
                    best = [c[0] for c in counts if c[1] == max_count]
                    # If there's a clear winner, we use that; otherwise, we
                    #  revert to using the parent node as a fallback
                    if len(best) == 1:
                        best_child = best[0]
                    else:
                        best_child = parent_node
                if best_child is not None:
                    break
        wordclass_groups2.append((parent_node, len(child_nodes), best_child))

    # Group into level-3 classes
    level3_groups = {}
    for g in wordclass_groups2:
        wordclass_parent = g[0]
        p = wordclass_parent.ancestor(level=3) or wordclass_parent
        if not p.id in level3_groups:
            level3_groups[p.id] = (p, [])
        level3_groups[p.id][1].append(g)
    # Reduce to a list of (parent_node, count, child_groups) tuples
    level3_groups = level3_groups.values()
    level3_groups = [(row[0], sum([g[1] for g in row[1]]), row[1],)
        for row in level3_groups]
    # Sort so that the most common is first
    level3_groups.sort(key=lambda row: row[1], reverse=True)

    # Drop the long tail of comparatively low-frequency branches
    level3_groups2 = []
    if level3_groups:
        max_count = level3_groups[0][1]
        level3_groups = [row for row in level3_groups
            if row[1] > max_count * 0.1]
        for parent, count, child_nodes in level3_groups:
            max_count = child_nodes[0][1]
            child_nodes = [g for g in child_nodes if g[1] > max_count * 0.1]
            level3_groups2.append((parent, count, child_nodes,))

    return total, level3_groups2
