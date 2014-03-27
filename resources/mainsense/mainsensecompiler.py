"""
MainSenseCompiler - Tools to help identify the main sense of a given entry
"""

import os
import csv
import string
from collections import defaultdict, Counter

import lex.oed.thesaurus.thesaurusdb as tdb
#from utils.tracer import trace_class, trace_instance
from pickler.sensemanager import PickleLoader

WORDCLASSES = ('NN', 'JJ')


class MainSenseCompiler(object):

    """
    Processes for compilation of the look-up tables
    """

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            self.__dict__[k] = v
        self.dir = os.path.join(self.resources_dir, 'main_senses')

    def make_raw_index(self):
        store = {'NN': defaultdict(list), 'JJ': defaultdict(list)}
        for letter in string.ascii_uppercase:
            print('\tCompiling main sense data in %s...' % letter)
            loader = PickleLoader(self.input_dir, letters=letter)
            for s in loader.iterate():
                if (s.wordclass in WORDCLASSES and
                        s.first_word() is not None and
                        s.last_word() is not None):
                    if (len(s.last_word()) < 3 or
                            (s.wordclass == 'JJ' and s.last_word().endswith('ed'))):
                        pass
                    else:
                        score = '%0.2f' % (1 / len(s.thesaurus_nodes),)
                        for leaf in s.thesaurus_nodes:
                            store[s.wordclass][s.last_word()].append((leaf, score))

        for wordclass in WORDCLASSES:
            filepath = os.path.join(self.dir, wordclass + '_raw.csv')
            with open(filepath, 'w') as filehandle:
                csvwriter = csv.writer(filehandle)
                for lemma in sorted(list(store[wordclass].keys())):
                    vals = store[wordclass][lemma]
                    row = [lemma,]
                    for id, score in vals:
                        row.extend((id, score))
                    csvwriter.writerow(row)

    def refine_index(self):
        for wordclass in WORDCLASSES:
            lemmas = []
            filepath = os.path.join(self.dir, wordclass + '_raw.csv')
            with open(filepath, 'r') as filehandle:
                csvreader = csv.reader(filehandle)
                for row in csvreader:
                    lemma = row[0]
                    values = row[1:]
                    ids = [int(id) for id in values[::2]]
                    scores = [float(s) for s in values[1::2]]
                    if sum(scores) >= 4:
                        idmap = defaultdict(int)
                        for id, score in zip(ids, scores):
                            idmap[id] += score
                        lemmas.append((lemma, Counter(idmap).most_common()))

            store = []
            for lemma, idcounter in lemmas:
                classes = [(tdb.get_thesclass(id), score)
                           for id, score in idcounter]
                total_score = sum([c[1] for c in classes])
                ancestors = defaultdict(int)
                for thesclass, score in classes:
                    a = thesclass.ancestor(level=3)
                    if a is not None:
                        ancestors[a] += score
                l3_ancestors = Counter(ancestors).most_common()

                if (l3_ancestors and
                        l3_ancestors[0][1] > total_score * 0.3 and
                        (len(l3_ancestors) == 1 or
                        l3_ancestors[0][1] > l3_ancestors[1][1] * 1.3)):
                    parent_branch = l3_ancestors[0][0]
                    ancestors = defaultdict(int)
                    for thesclass, score in classes:
                        a = thesclass.ancestor(level=4)
                        if a is not None and a.is_descendant_of(parent_branch):
                            ancestors[a] += score
                    l4_ancestors = Counter(ancestors).most_common()
                    if l4_ancestors and l4_ancestors[0][1] > total_score * 0.3:
                        target = l4_ancestors[0][0]
                    else:
                        target = parent_branch
                    store.append((lemma, target))

            outfile = os.path.join(self.dir, '%s_compounds.csv' % wordclass)
            with open(outfile, 'w') as filehandle:
                csvwriter = csv.writer(filehandle)
                for lemma, thesclass in store:
                    row = (lemma, thesclass.id, thesclass.breadcrumb())
                    csvwriter.writerow(row)

    def finalize(self):
        for wordclass in WORDCLASSES:
            lemmas = {}
            infile1 = os.path.join(self.dir, '%s_compounds.csv' % wordclass)
            infile2 = os.path.join(self.dir, '%s_manual.csv' % wordclass)
            with open(infile1, 'r') as filehandle:
                csvreader = csv.reader(filehandle)
                for row in csvreader:
                    lemmas[row[0]] = int(row[1])
            # Do the manual file second, so that it overrides the
            #  automatically-generated file
            with open(infile2, 'r') as filehandle:
                csvreader = csv.reader(filehandle)
                for row in csvreader:
                    lemmas[row[0]] = int(row[1])

            output = []
            for lemma, class_id in lemmas.items():
                # Retrieve the branch that the majority of compounds are on
                compound_branch = tdb.get_thesclass(class_id)

                # Get the highest-rated senses for the lemma
                ranked_senses = tdb.ranked_search(lemma=lemma, wordclass=wordclass)
                if ranked_senses:
                    max_rating = ranked_senses[0].rating()
                    ranked_senses = [s for s in ranked_senses if
                        max_rating > 0 and s.rating() > max_rating * 0.3]

                # Try filtering to just those senses that are on
                #   the same branch as the compounds
                ranked_filtered = [s for i, s in enumerate(ranked_senses) if
                    (i == 0 and s.thesclass is None) or
                    s.is_descendant_of(compound_branch)]
                # ... or else stick with original ranking
                if not ranked_filtered:
                    ranked_filtered = ranked_senses

                if ranked_filtered:
                    output.append(ranked_filtered[0])

            outfile = os.path.join(self.dir, '%s.csv' % wordclass)
            output.sort(key=lambda s: s.lemma)
            with open(outfile, 'w') as filehandle:
                csvwriter = csv.writer(filehandle)
                for s in output:
                    row = (s.lemma, s.refentry, s.refid,
                           s.entry_size, s.breadcrumb())
                    csvwriter.writerow(row)
