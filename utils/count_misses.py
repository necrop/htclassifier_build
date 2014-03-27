
import os
import csv
import math
from collections import defaultdict, namedtuple

from lex.entryiterator import EntryIterator

oed_dir = "C:/j/work/dictionaries/oed/oedpub/oed_publication_text/"

def count():
    counts = defaultdict(lambda: defaultdict(int))

    ei = EntryIterator(path=oed_dir,
                       dictType="oed",
                       fixLigatures=True,
                       verbosity="low")
    for entry in ei.iterate():
        entry.share_quotations()
        senses = {"all": entry.senses, "missed": [s for s in
            entry.senses if not s.thesaurus_categories()]}
        for j in ("all", "missed"):
            for s in senses[j]:
                counts[j]["all"] += 1
                if s.is_subentry() and s.definition():
                    counts[j]["defined_subentry"] += 1
                elif s.is_subentry():
                    counts[j]["undefined_subentry"] += 1
                else:
                    counts[j]["main_sense"] += 1
                counts[j]["quotations"] += s.num_quotations
                if s.primary_wordclass.penn in ('NN', 'VB', 'JJ', 'RB'):
                    counts[j][s.primary_wordclass.penn] += 1
                else:
                    counts[j]['other_wordclass'] += 1
                if entry.is_revised:
                    counts[j]["revised"] += 1
                else:
                    counts[j]["unrevised"] += 1

    for j in ("all", "missed"):
        print j
        for k, v in counts[j].items():
            print "\t%s\t%d" % (k, v)


if __name__ == "__main__":
    count()
