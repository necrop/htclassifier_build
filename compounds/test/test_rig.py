from __future__ import division
from collections import defaultdict
import string
import numpy

from lex.oed.projects.thesaurus.classifier.config import ThesaurusConfig
from lex.oed.projects.thesaurus.classifier.compounds.bayescompounds import BayesCompounds

config = ThesaurusConfig()

bayes = BayesCompounds(
    resources_dir=config.get('paths', 'resources_dir'),
)


def spool():
    for letter in string.ascii_lowercase:
        bayes.load_results(letter)
        for s in bayes.results.values():
            #if s.confidence() in (4, 5):
            show_sense(s)

def feature_distance_histogram():
    spread = defaultdict(int)
    ave = []
    for letter in string.ascii_lowercase:
        bayes.load_results(letter)
        for s in bayes.results.values():
            ave.append(s.max_feature_distance())
            j = int(s.max_feature_distance())
            if j > 25:
                j = 25
            spread[j] += 1
    total = sum(spread.values())
    for i in range (0, 26):
        print i, spread[i], int((spread[i] / total) * 100)
    print 'mean average: %f' % numpy.mean(ave)

def confidence_spread():
    spread = defaultdict(int)
    for letter in string.ascii_lowercase:
        bayes.load_results(letter)
        for s in bayes.results.values():
            spread[s.confidence()] += 1
    total = sum(spread.values())
    for i in range (1, 6):
        print i, spread[i], int((spread[i] / total) * 100)

def show_sense(s):
    results = s.filtered_results(max_delta=0.3)
    print '\n-------------------------------------\n'
    print '%d#eid%d' % (s.refentry, s.refid)
    print repr(s.lemma)
    print repr(s.details())
    print 'feature distance: ', s.max_feature_distance()

    k = s.average_delta_bottom()
    for i, r in enumerate(results):
        diff = r.delta(s.base_score()) / k
        print '\t%s\t%0.3g\t%0.3g' % (r.breadcrumb(), r.posterior, s.feature_distance(0, i) or 0)



if __name__ == '__main__':
    spool()
    #feature_distance_histogram()
    #confidence_spread()

