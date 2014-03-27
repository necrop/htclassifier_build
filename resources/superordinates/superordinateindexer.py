"""
SuperordinateIndexer
"""

import os
import string
import csv
from collections import defaultdict, Counter

import lex.oed.thesaurus.thesaurusdb as tdb
from pickler.sensemanager import PickleLoader


# High-frequency superordinates - we'll not bother even attempting these
#  when refining the index
SKIPPABLE = {'person', 'makeVB', 'thing', 'beVB', 'causeVB', 'putVB',
             'state', 'takeVB', 'becomeVB', 'giveVB', 'bringVB', 'moveVB',
             'place', 'quality', 'substance', 'goVB', 'action', 'haveVB',
             'provideVB', 'condition', 'name', 'renderVB', 'comeVB',
             'setVB', 'part', 'cutVB', 'turnVB', 'coverVB', 'formVB',
             'word', 'actVB', }


class SuperordinateIndexer(object):

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            self.__dict__[k] = v

    def compile_index(self):
        self.data = defaultdict(lambda: defaultdict(list))
        letters = string.ascii_uppercase
        for letter in letters:
            print('\tIndexing superordinates in %s...' % letter)
            loader = PickleLoader(self.input_dir, letters=letter)
            for sense in loader.iterate():
                if (sense.wordclass in ('NN', 'VB') and
                        sense.superordinate is not None):
                    self._process_superordinate(sense.superordinate,
                                                sense.thesaurus_nodes)
                    if sense.superordinate != sense.superordinate_full:
                        self._process_superordinate(sense.superordinate_full,
                                                    sense.thesaurus_nodes)
        self._write_raw_index()

    def _process_superordinate(self, superordinate, nodes):
        superordinate = superordinate.replace('-', '').replace(' ', '')
        initial = find_initial(superordinate)
        if initial is not None:
            score = '%0.2f' % (1 / len(nodes),)
            for leaf in nodes:
                self.data[initial][superordinate].append((leaf, score))

    def _write_raw_index(self):
        for initial in sorted(self.data.keys()):
            out_file = os.path.join(self.output_dir, initial + '_raw.csv')
            with open(out_file, 'w') as filehandle:
                csvwriter = csv.writer(filehandle)
                for superordinate, vals in self.data[initial].items():
                    row = [superordinate, ]
                    for id, score in vals:
                        row.extend((id, score))
                    csvwriter.writerow(row)

    def refine_index(self):
        for letter in string.ascii_lowercase:
            print('\tRefining superordinate index %s...' % letter)
            in_file = os.path.join(self.output_dir, letter + '_raw.csv')
            out_file = os.path.join(self.output_dir, letter + '.csv')

            superordinates = []
            with open(in_file, 'r') as filehandle:
                csvreader = csv.reader(filehandle)
                for row in csvreader:
                    phrase = row[0]
                    if phrase in SKIPPABLE:
                        pass
                    else:
                        values = row[1:]
                        ids = [int(id) for id in values[::2]]
                        scores = [float(s) for s in values[1::2]]
                        total = sum(scores)
                        idmap = defaultdict(int)
                        for id, score in zip(ids, scores):
                            idmap[id] += score
                        superordinates.append((phrase,
                                               Counter(idmap).most_common()))

            superordinates2 = []
            for superordinate, values in superordinates:
                total = sum([v[1] for v in values])
                total = int(total + 0.1)
                winnowed = winnow(superordinate, values)
                # Should never need more than 4
                winnowed = winnowed[0:4]
                if winnowed:
                    row = [superordinate, total, ]
                    for t in winnowed:
                        row.extend([t[0].id, '%.2g' % t[1]])
                    superordinates2.append(row)
            superordinates2.sort(key=lambda s: s[0])

            with open(out_file, 'w') as filehandle:
                csvwriter = csv.writer(filehandle)
                for row in superordinates2:
                    row_encoded = [row.pop(0), ]
                    row_encoded.extend(row)
                    csvwriter.writerow(row_encoded)

    def list_most_frequent_superordinates(self):
        """
        List the 100 most frequent superordinates in the raw .csv files.
        Used for checking/QA purposes only.
        """
        superordinates = {}
        for letter in string.ascii_lowercase:
            in_file = os.path.join(self.output_dir, letter + '_raw.csv')
            with open(in_file, 'r') as filehandle:
                csvreader = csv.reader(filehandle)
                for row in csvreader:
                    phrase = row[0]
                    values = row[1:]
                    total = sum([float(s) for s in values[1::2]])
                    if total > 5:
                        superordinates[phrase] = total
        superordinates = Counter(superordinates).most_common()
        for s in superordinates[0:100]:
            print(repr(s[0]), s[1])


def winnow(superordinate, values):
    # Convert thesaurus IDs stored in the raw files to actual thesaurus classes
    thesclasses = [(tdb.get_thesclass(v[0]), v[1]) for v in values]
    if superordinate.endswith('VB'):
        thesclasses = [t for t in thesclasses if t[0].penn_wordclass() == 'VB']
    else:
        thesclasses = [t for t in thesclasses if t[0].penn_wordclass() == 'NN']

    # If there's only one sense, we can short-cut the winnowing process
    if len(thesclasses) <= 1:
        return [(t[0], 1) for t in thesclasses]

    # Use the hopper function to winnow out classes that contain less than
    #  25% of the total number of senses
    total = sum([t[1] for t in thesclasses])
    winnowed = _hopper(thesclasses, total, 0.25)
    winnowed.sort(key=lambda a: a[1], reverse=True)
    winnowed.sort(key=lambda a: a[2], reverse=True)

    # Strip out classes that are just parents of other classes
    parents = {t[0].parent.id: 0 for t in winnowed}
    # Keep a tally of how many of the parent's senses are covered
    #   by its children
    for t in winnowed:
        parents[t[0].parent.id] += t[1]
    # Remove a class if it's a parent of other classes and its total tally
    #  of senses is not much more than the sum of its children's (we use
    #  a margin of 1.3 to allow for some wastage through child classes that
    #  have been skipped)
    parent_stripped = [t for t in winnowed if not t[0].id in parents or
                       t[1] > parents[t[0].id] * 1.3]

    return [(t[0], t[1] / total) for t in parent_stripped]


def _hopper(thesclasses, total, ratio):
    winnowed = []
    for lev in (4, 5, 6, 7, 8, 9, 10):
        ancestors = defaultdict(int)
        for t in thesclasses:
            a = t[0].ancestor(level=lev)
            if a is not None:
                ancestors[a] += t[1]
        counts = Counter(ancestors).most_common()
        local_winnow = [(t[0], t[1], lev) for t in counts
                        if t[1] >= total * ratio]
        winnowed.extend(local_winnow)
        if not local_winnow:
            break
    return winnowed


def find_initial(superordinate):
    if ' ' in superordinate or len(superordinate) >= 4:
        initial = superordinate[0].lower()
        if initial in string.ascii_lowercase:
            return initial
    return None
