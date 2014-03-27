"""
Binomials - Manages indexing and lookup of binomial terms (animals and plants)
"""

import os
import csv
from collections import defaultdict, Counter

import lex.oed.thesaurus.thesaurusdb as tdb
from pickler.sensemanager import PickleLoader
#from utils.tracer import trace_class

living_world_id = 8835
living_world_node = tdb.get_thesclass(living_world_id)
life_branches = (22501, 29205, 17709)  # plant, animal, microorganism


class Binomials(object):
    index = {'binomials': {}, 'genera': {}, }

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            self.__dict__[k] = v
        try:
            self.resources_dir
        except AttributeError:
            pass
        else:
            dir = os.path.join(self.resources_dir, 'taxonomy')
            self.raw_files = {
                'binomials': os.path.join(dir, 'binomials_raw.csv'),
                'genera': os.path.join(dir, 'genera_raw.csv'),
            }
            self.clean_files = {
                'binomials': os.path.join(dir, 'binomials.csv'),
                'genera': os.path.join(dir, 'genera.csv'),
            }

    def load_data(self):
        if not Binomials.index['binomials']:
            for t in ('genera', 'binomials'):
                with open(self.clean_files[t], 'r') as filehandle:
                    csvreader = csv.reader(filehandle)
                    for row in csvreader:
                        key = row[0].lower()
                        value = int(row[1])
                        Binomials.index[t][key] = value

    def find_class(self, term):
        term = term.lower()
        try:
            return Binomials.index['binomials'][term]
        except KeyError:
            genus = term.split(' ')[0]  # works even if term is already genus
            try:
                return Binomials.index['genera'][genus]
            except KeyError:
                return None

    #=======================================================
    # Processes for initial compilation of the indexes
    #=======================================================

    def make_raw_index(self):
        store = {v: defaultdict(list) for v in ('genera', 'binomials')}
        loader = PickleLoader(self.input_dir)
        for s in loader.iterate():
            if (s.wordclass == 'NN' and
                    (s.binomials or s.genera)):
                for leaf in s.thesaurus_nodes:
                    thesclass = tdb.get_thesclass(leaf)
                    if any([thesclass.is_descendant_of(id) for id in
                            life_branches]):
                        for g in s.genera:
                            store['genera'][g].append(leaf)
                        for b in s.binomials:
                            store['binomials'][b].append(leaf)
                            genus = b.split(' ')[0]
                            if genus not in s.genera:
                                store['genera'][b.split(' ')[0]].append(leaf)

        for k in ('genera', 'binomials'):
            with open(self.raw_files[k], 'w') as filehandle:
                csvwriter = csv.writer(filehandle)
                for t, vals in store[k].items():
                   row = [t,]
                   row.extend(vals)
                   csvwriter.writerow(row)

    def refine_genera_index(self):
        genera = []
        with open(self.raw_files['genera'], 'r') as filehandle:
            csvreader = csv.reader(filehandle)
            for row in csvreader:
                g = row.pop(0)
                ids = [int(id) for id in row]
                genera.append((g, ids))
        genera2 = []
        for genus, vals in genera:
            parent = drilldown(vals)
            if parent is not living_world_node:
                genera2.append((genus, parent))

        with open(self.clean_files['genera'], 'w') as filehandle:
            csvwriter = csv.writer(filehandle)
            for t, v in genera2:
                row = [t, v.id, v.breadcrumb()]
                csvwriter.writerow(row)

    def refine_binomial_index(self):
        # Load the genus terms and their branch
        genera = {}
        with open(self.clean_files['genera'], 'r') as filehandle:
            csvreader = csv.reader(filehandle)
            for row in csvreader:
                genera[row[0]] = int(row[1])

        # load the raw binomials data
        binomials = []
        with open(self.raw_files['binomials'], 'r') as filehandle:
            csvreader = csv.reader(filehandle)
            for row in csvreader:
                b = row.pop(0)
                ids = [int(id) for id in row]
                binomials.append((b, ids))

        # Trim down to just those thesaurus classes that are inside the genus
        # term's branch
        binomials2 = []
        for b in binomials:
            binomial = b[0]
            genus = binomial.split(' ')[0]
            thesclasses = [tdb.get_thesclass(v) for v in b[1]]
            if genus in genera:
                thesclasses = [t for t in thesclasses if
                    t.is_descendant_of(genera[genus])]
            # Of the remainder, pick the largest branch
            if thesclasses:
                histogram = Counter(thesclasses).most_common()
                most_common = [t[0] for t in histogram if t[1] == histogram[0][1]]
                most_common.sort(key=lambda t: t.branch_size, reverse=True)
                binomials2.append((binomial, most_common[0]))

        with open(self.clean_files['binomials'], 'w') as filehandle:
            csvwriter = csv.writer(filehandle)
            for t, v in binomials2:
                row = [t, v.id, v.breadcrumb()]
                csvwriter.writerow(row)


def drilldown(vals):
    thesclasses = [tdb.get_thesclass(v) for v in vals]
    thesclasses = [t for t in thesclasses if t.wordclass == 'NN' or
                   t.wordclass == 'noun']
    branch = living_world_node
    for lev in (4, 5, 6, 7, 8, 9):
        level_ancestors = [t.ancestor(level=lev) for t in thesclasses]
        level_ancestors = [a for a in level_ancestors if a is not None and
                           a.is_descendant_of(branch)]
        if level_ancestors:
            histogram = Counter(level_ancestors).most_common()
            most_common = [t[0] for t in histogram if t[1] == histogram[0][1]]
            #print str(lev), str(len(most_common))
            if len(most_common) > 1:
                break
            branch = most_common[0]
            if branch.wordclass is not None:
                break
        else:
            break
    return branch
