from __future__ import division, print_function
from collections import defaultdict
import string
import numpy

from lex.oed.projects.thesaurus.classifier.config import ThesaurusConfig
from lex.oed.projects.thesaurus.classifier.bayes.bayesclassifier import BayesClassifier
from lex.oed.projects.thesaurus.classifier.compounds.bayescompounds import BayesCompounds

config = ThesaurusConfig()

#bayes = BayesClassifier(
#    resources_dir=config.get('paths', 'resources_dir'),
#)
bayes = BayesCompounds(
    resources_dir=config.get('paths', 'resources_dir'),
)


def spool():
    for letter in string.ascii_lowercase:
        bayes.load_results(letter)
        for s in bayes.results.values():
            s.recover_probabilities()
            #ad = s.average_delta(total_probability=.95)
            #if s.confidence() >= 7 and s.num_features() < 10:
            show_probabilities(s)

def find_word(word):
    initial = word.lower()[0]
    bayes.load_results(initial, 'bias_high')
    for s in bayes.results.values():
        if s.lemma == word:
            s.recover_probabilities()
            show_probabilities(s)

def average_delta_histogram():
    spread = defaultdict(int)
    ave = []
    for letter in string.ascii_lowercase:
        bayes.load_results(letter, 'bias_high')
        for s in bayes.results.values():
            s.recover_probabilities()
            ad = s.average_delta(total_probability=.95)
            ave.append(ad)
            if ad < 5:
                j = int(ad)
            else:
                j = int(ad/5) * 5
            if j > 50:
                j = 50
            spread[j] += 1
    total = sum(spread.values())
    for i in sorted(spread.keys()):
        print(i, spread[i], int((spread[i] / total) * 100))
    print('mean average: %f' % numpy.mean(ave))

def confidence_spread():
    spread = defaultdict(int)
    for letter in string.ascii_lowercase:
        bayes.load_results(letter, 'bias_high')
        for s in bayes.results.values():
            s.recover_probabilities()
            spread[s.confidence()] += 1
    total = sum(spread.values())
    for i in sorted(spread.keys()):
        print(i, spread[i], int((spread[i] / total) * 100))

def show_probabilities(s):
    print_basics(s)
    for r in s.filtered_results(total_probability=.95):
        print('\t%s\t%0.3g\t%0.3g\t%0.3g' % (r.breadcrumb(), r.prior_probability, r.posterior_probability, r.delta()))
    print('>>> %0.3g' % s.average_delta(total_probability=.95))



def print_basics(s):
    print('\n' + '-' * 30 + '\n')
    print('%d#eid%d' % (s.refentry, s.refid))
    print(repr(s.lemma))
    print(repr(s.details()))
    print('Features: %d     Confidence: %d' % (s.num_features(), s.confidence()))

if __name__ == '__main__':
    #average_delta_histogram()
    #spool()
    #confidence_spread()
    find_word('archaeobotanist')


