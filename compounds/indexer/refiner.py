
import os
import pickle
import csv
from collections import Counter

import lex.oed.thesaurus.thesaurusdb as tdb

from . import compoundindexerconfig
from .containers import WordSet

DIRECTORY = compoundindexerconfig.DIRECTORY
WORDCLASSES = compoundindexerconfig.WORDCLASSES


def refine_index():
    for wordclass in WORDCLASSES:
        print('\tRefining compound index %s...' % wordclass)
        in_file = os.path.join(DIRECTORY, wordclass + '_raw.csv')
        out_file = os.path.join(DIRECTORY, wordclass)

        compound_words = []
        with open(in_file, 'r') as filehandle:
            csvreader = csv.reader(filehandle)
            for row in csvreader:
                word = row.pop(0)
                ids = [int(id) for id in row]
                compound_words.append((word, ids))

        output = []
        for word, ids in compound_words:
            count, data = winnow(ids, wordclass)
            j = WordSet(word, wordclass, count, data)
            output.append(j)

        # Output file for pickled objects
        with open(out_file, 'wb') as filehandle:
            for o in output:
                pickle.dump(o, filehandle)


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
                # ... and count how many children are on each branch
                # at this level
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
