
import lex.oed.thesaurus.thesaurusdb as tdb
from resources.mainsense.mainsense import MainSense

main_sense_finder = MainSense()


def ranked_sense_summary(**kwargs):
    """
    Return a summary of the ranked_search() results, reduced to a
    given thesaurus level (defaults to level=3)

    Returns a ranked list of result objects, each with the following
    attributes:
     * parent: level-3 parent class;
     * classes: ranked list of thesaurus classes which map to the parent;
     * summed_rating: sum of c.rating() values for each c in classes;
     * probability: probability of this row (based on summed rating).

    Keyword arguments:
     * level (int): the parent thesaurus level which will be returned
     * omit_null (True/False): if True, any senses which don't have
            a classification will be ignored
     ... plus all the usual optional keyword arguments passed on to
     tdb.search() (lemma, wordclass, refentry, refid, etc.).
    """
    level = kwargs.get('level', 3)
    lemma = kwargs.get('lemma')
    wordclass = kwargs.get('wordclass')
    omit_null = kwargs.get('omit_null', False)

    if lemma is not None:
        main_sense = main_sense_finder.main_sense(lemma=lemma,
                                                  wordclass=wordclass,
                                                  listed_only=True)
        if main_sense is not None:
            kwargs['promote'] = main_sense.refid

    candidates = tdb.ranked_search(**kwargs)
    if omit_null:
        candidates = [c for c in candidates if c.thesclass is not None]

    # Give each thesclass a probability value (as a ratio of the sum
    #  of all senses' ratings)
    total = sum([c.rating() for c in candidates])
    if total <= 0:
        total = 1

    summary = {}
    for c in candidates:
        if c.thesclass is None or c.thesclass.ancestor(level=level) is None:
            ancestor = None
            identifier = 0
        else:
            ancestor = c.thesclass.ancestor(level=level)
            identifier = ancestor.id
        if not identifier in summary:
            summary[identifier] = ResultRow(ancestor)
        summary[identifier].append(c)

    # Convert to a list
    summary = list(summary.values())
    # Add a probability score (0 < p < 1) to each row
    [row.set_probability(total) for row in summary]
    # Sort by probability
    summary.sort(key=lambda r: r.probability, reverse=True)

    return summary


class ResultRow(object):

    def __init__(self, parent):
        self.parent = parent
        self.classes = []
        self.summed_rating = 0
        self.probability = 0
        self.seen = set() # used to stop the same sense being added twice

    def append(self, sense):
        signature = (sense.refentry, sense.refid,)
        if signature in self.seen:
            pass
        elif self.classes and sense.thesclass is None:
            pass
        else:
            self.classes.append(sense.thesclass)
            self.summed_rating += sense.rating()
            self.seen.add(signature)

    def set_probability(self, total):
        self.probability = self.summed_rating / total

    def breadcrumb(self):
        if self.parent is not None:
            return self.parent.breadcrumb()
        else:
            return '[None]'
